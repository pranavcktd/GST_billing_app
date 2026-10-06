"""Recurring invoices: create from an invoice, schedule, pause / resume, run now, history."""

import datetime as dt
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import BCtx
from ..gst.constants import VoucherType
from ..models import Party, RecurringInvoice, Voucher
from ..services import recurring as RC
from .auth import frontend_url

router = APIRouter(prefix="/recurring", tags=["recurring"])
Freq = Literal["WEEKLY", "MONTHLY", "QUARTERLY", "HALF_YEARLY", "YEARLY"]


def _get(ctx: BCtx, rid: str) -> RecurringInvoice:
    r = ctx.db.get(RecurringInvoice, rid)
    if r is None or r.business_id != ctx.bid:
        raise HTTPException(404, "Recurring invoice not found")
    return r


def _out(ctx: BCtx, r: RecurringInvoice, party_names: dict | None = None) -> dict:
    party = (party_names or {}).get(r.party_id) if party_names is not None else (ctx.db.get(Party, r.party_id).name if r.party_id else None)
    total = sum(float(l.get("qty") or 0) * float(l.get("rate") or 0) for l in r.template.get("lines") or [])
    return dict(id=r.id, name=r.name, party_id=r.party_id, party=party, frequency=r.frequency, interval=r.interval,
                start_date=r.start_date, end_date=r.end_date, next_date=r.next_date, due_days=r.due_days, auto_email=r.auto_email,
                status=r.status, generated_count=r.generated_count, last_generated_at=r.last_generated_at, last_error=r.last_error,
                lines=len(r.template.get("lines") or []), approx_value=round(total, 2), upcoming=RC.upcoming(r))


@router.get("")
def list_recurring(ctx: BCtx):
    ctx.need("sales", "view")
    rows = ctx.db.scalars(select(RecurringInvoice).where(RecurringInvoice.business_id == ctx.bid)
                          .order_by(RecurringInvoice.status, RecurringInvoice.next_date)).all()
    names = dict(ctx.db.execute(select(Party.id, Party.name).where(Party.id.in_([r.party_id for r in rows if r.party_id]))).all()) if rows else {}
    return [_out(ctx, r, names) for r in rows]


class CreateIn(BaseModel):
    voucher_id: str
    name: str | None = Field(None, max_length=200)
    frequency: Freq = "MONTHLY"
    interval: int = Field(1, ge=1, le=12)
    start_date: dt.date
    end_date: dt.date | None = None
    due_days: int = Field(0, ge=0, le=365)
    auto_email: bool = False


@router.post("", status_code=201)
def create(data: CreateIn, ctx: BCtx):
    ctx.need("sales", "create")
    v = ctx.db.get(Voucher, data.voucher_id)
    if v is None or v.business_id != ctx.bid:
        raise HTTPException(404, "Invoice not found")
    if v.type != VoucherType.SALE or not v.party_id:
        raise HTTPException(400, "Recurring invoices are made from a sale invoice with a customer")
    if data.end_date and data.end_date < data.start_date:
        raise HTTPException(422, "End date is before the start date")
    r = RecurringInvoice(business_id=ctx.bid, party_id=v.party_id, name=data.name or f"{v.party_name} — {data.frequency.lower().replace('_', '-')}",
                         template=RC.template_from(v), frequency=data.frequency, interval=data.interval, start_date=data.start_date,
                         end_date=data.end_date, next_date=data.start_date, due_days=data.due_days, auto_email=data.auto_email,
                         created_by=ctx.user.name)
    ctx.db.add(r)
    ctx.db.commit()
    return _out(ctx, r)


class UpdateIn(BaseModel):
    name: str | None = Field(None, max_length=200)
    frequency: Freq | None = None
    interval: int | None = Field(None, ge=1, le=12)
    next_date: dt.date | None = None
    end_date: dt.date | None = None
    clear_end_date: bool = False
    due_days: int | None = Field(None, ge=0, le=365)
    auto_email: bool | None = None
    status: Literal["ACTIVE", "PAUSED"] | None = None
    template_from_voucher_id: str | None = None  # replace items / rates with those of another invoice


@router.put("/{rid}")
def update(rid: str, data: UpdateIn, ctx: BCtx):
    ctx.need("sales", "edit")
    r = _get(ctx, rid)
    for k in ("name", "frequency", "interval", "next_date", "end_date", "due_days", "auto_email"):
        v = getattr(data, k)
        if v is not None:
            setattr(r, k, v)
    if data.clear_end_date:
        r.end_date = None
    if data.status:
        if data.status == "ACTIVE" and r.status == "ENDED" and not data.next_date:
            raise HTTPException(400, "This schedule has ended — set a next date to restart it")
        r.status = data.status
    if data.template_from_voucher_id:
        v = ctx.db.get(Voucher, data.template_from_voucher_id)
        if v is None or v.business_id != ctx.bid or v.type != VoucherType.SALE:
            raise HTTPException(404, "Invoice not found")
        r.template, r.party_id = RC.template_from(v), v.party_id
    if r.status == "ENDED" and data.next_date:
        r.status = "ACTIVE"
    ctx.db.commit()
    return _out(ctx, r)


@router.delete("/{rid}", status_code=204)
def delete(rid: str, ctx: BCtx):
    ctx.need("sales", "delete")
    ctx.db.delete(_get(ctx, rid))
    ctx.db.commit()


@router.post("/{rid}/run")
def run_now(rid: str, ctx: BCtx, request: Request):
    """Create the invoices that are due today or earlier (normally done automatically each hour)."""
    ctx.need("sales", "create")
    r = _get(ctx, rid)
    made = RC.generate_due(ctx.db, r, dt.date.today(), frontend_url(request))
    r = ctx.db.get(RecurringInvoice, rid)
    if not made and r.last_error:
        raise HTTPException(400, r.last_error)
    return {"created": [dict(id=v.id, number=v.number, date=v.date) for v in made], "recurring": _out(ctx, r)}


@router.get("/{rid}/invoices")
def invoices(rid: str, ctx: BCtx):
    ctx.need("sales", "view")
    _get(ctx, rid)
    rows = ctx.db.scalars(select(Voucher).where(Voucher.recurring_id == rid).order_by(Voucher.date.desc()).limit(100)).all()
    return [dict(id=v.id, number=v.number, date=v.date, total=float(v.grand_total), cancelled=v.cancelled) for v in rows]

