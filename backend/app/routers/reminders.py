"""Payment reminders: settings, who is due, send now (e-mail), WhatsApp text, history."""

import datetime as dt
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import BCtx
from ..models import Party, ReminderLog, Voucher
from ..services import reminders as R
from ..services.ledger import party_balances
from ..services.platform_audit import log
from .auth import frontend_url

router = APIRouter(prefix="/reminders", tags=["reminders"])


class SettingsIn(BaseModel):
    enabled: bool = False
    before_days: list[int] = Field(default_factory=lambda: [3], max_length=5)
    on_due: bool = True
    after_days: list[int] = Field(default_factory=lambda: [3, 7, 15, 30], max_length=10)
    default_credit_days: int = Field(0, ge=0, le=365)
    cc_me: bool = True
    attach_pdf: bool = True


@router.get("/settings")
def get_reminder_settings(ctx: BCtx):
    ctx.need("sales", "view")
    return R.settings(ctx.business)


@router.put("/settings")
def put_reminder_settings(data: SettingsIn, ctx: BCtx):
    ctx.need("settings", "edit")
    clean = data.model_dump()
    clean["before_days"] = sorted({d for d in clean["before_days"] if 0 < d <= 60})
    clean["after_days"] = sorted({d for d in clean["after_days"] if 0 < d <= 365})
    ctx.business.reminder_settings = clean
    ctx.db.commit()
    return R.settings(ctx.business)


@router.get("/due")
def due(ctx: BCtx):
    """Every customer with unpaid invoices: totals, days overdue, contact details, last reminder."""
    ctx.need("sales", "view")
    s = R.settings(ctx.business)
    today = dt.date.today()
    by_party: dict[str, list] = {}
    for v in R.open_invoices(ctx.db, ctx.business):
        by_party.setdefault(v.party_id, []).append(v)
    if not by_party:
        return []
    balances = party_balances(ctx.db, ctx.bid, list(by_party))
    parties = {p.id: p for p in ctx.db.scalars(select(Party).where(Party.id.in_(list(by_party))))}
    last: dict[str, dt.datetime] = {}
    for r in ctx.db.scalars(select(ReminderLog).where(ReminderLog.business_id == ctx.bid, ReminderLog.status == "SENT")
                            .order_by(ReminderLog.created_at)):
        last[r.party_id] = r.created_at
    out = []
    for pid, vs in by_party.items():
        p = parties.get(pid)
        if p is None:
            continue
        rows = [dict(id=v.id, number=v.number, date=v.date, due=R._due(v, s), balance=float(R._balance(v)),
                     overdue=max((today - R._due(v, s)).days, 0)) for v in vs]
        out.append(dict(party_id=pid, name=p.name, email=p.email, phone=p.phone, whatsapp=R.wa_phone(p.phone),
                        invoices=rows, total=sum(r["balance"] for r in rows), net_balance=float(balances.get(pid, 0)),
                        max_overdue=max(r["overdue"] for r in rows), last_reminded=last.get(pid)))
    return sorted(out, key=lambda x: (-x["max_overdue"], -x["total"]))


class SendIn(BaseModel):
    party_ids: list[str] = Field(min_length=1, max_length=200)
    voucher_ids: list[str] | None = None  # limit to these invoices (default: every unpaid invoice of the party)
    note: str | None = Field(None, max_length=1000)


@router.post("/send")
def send(data: SendIn, ctx: BCtx, request: Request):
    ctx.need("sales", "view")
    base = frontend_url(request)
    results = []
    for pid in data.party_ids:
        party = ctx.db.get(Party, pid)
        if party is None or party.business_id != ctx.bid:
            raise HTTPException(404, "Party not found")
        vs = R.open_invoices(ctx.db, ctx.business, [pid])
        if data.voucher_ids:
            vs = [v for v in vs if v.id in set(data.voucher_ids)]
        if not vs:
            results.append(dict(party_id=pid, name=party.name, sent=False, error="No unpaid invoices"))
            continue
        ok, err = R.send_party(ctx.db, ctx.business, party, [(v, "MANUAL") for v in vs], base, automatic=False,
                               actor=ctx.user, note=data.note)
        results.append(dict(party_id=pid, name=party.name, sent=ok, error=err, to=party.email))
    sent = sum(1 for r in results if r["sent"])
    log(ctx.db, ctx.user, "ACTION", "reminder", f"Payment reminders sent: {sent} of {len(results)}", business_id=ctx.bid,
        request=request)
    ctx.db.commit()
    return {"sent": sent, "results": results}


@router.get("/whatsapp/{party_id}")
def whatsapp(party_id: str, ctx: BCtx, request: Request, voucher_id: str | None = None):
    """Message text and a wa.me link; the user sends it from their own WhatsApp."""
    ctx.need("sales", "view")
    party = ctx.db.get(Party, party_id)
    if party is None or party.business_id != ctx.bid:
        raise HTTPException(404, "Party not found")
    vs = R.open_invoices(ctx.db, ctx.business, [party_id])
    if voucher_id:
        vs = [v for v in vs if v.id == voucher_id]
    if not vs:
        raise HTTPException(400, "No unpaid invoices for this party")
    text = R.whatsapp_text(ctx.business, party, R._rows(vs, R.settings(ctx.business), dt.date.today()), frontend_url(request))
    for v in vs:
        ctx.db.add(ReminderLog(business_id=ctx.bid, party_id=party.id, voucher_id=v.id, stage="MANUAL", channel="WHATSAPP",
                               sent_to=party.phone, status="SENT", automatic=False, amount=R._balance(v), by_name=ctx.user.name))
    ctx.db.commit()
    phone = R.wa_phone(party.phone)
    return {"text": text, "phone": phone, "url": f"https://wa.me/{phone or ''}?text={quote(text)}"}


@router.get("/log")
def history(ctx: BCtx, limit: int = 100):
    ctx.need("sales", "view")
    rows = ctx.db.execute(select(ReminderLog, Party.name, Voucher.number).outerjoin(Party, Party.id == ReminderLog.party_id)
                          .outerjoin(Voucher, Voucher.id == ReminderLog.voucher_id).where(ReminderLog.business_id == ctx.bid)
                          .order_by(ReminderLog.created_at.desc()).limit(min(limit, 500))).all()
    return [dict(id=r.id, party=name, number=number, stage=r.stage, channel=r.channel, to=r.sent_to, status=r.status,
                 error=r.error, automatic=r.automatic, amount=float(r.amount or 0), by=r.by_name, at=r.created_at)
            for r, name, number in rows]
