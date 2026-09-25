import datetime as dt

from fastapi import APIRouter, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from ..deps import BCtx
from ..gst.constants import VOUCHER_META, VoucherType
from ..models import Voucher
from ..schemas import VoucherDetailOut, VoucherIn, VoucherOut
from ..services.numbering import preview_number
from ..permissions import voucher_module
from ..services.vouchers import cancel_voucher, save_voucher, to_detail, to_out

router = APIRouter(prefix="/vouchers", tags=["vouchers"])


def _get(ctx: BCtx, voucher_id: str, action: str = "view") -> Voucher:
    v = ctx.db.get(Voucher, voucher_id)
    if not v or v.business_id != ctx.bid:
        raise HTTPException(404, "Document not found")
    ctx.need(voucher_module(v.type), action)
    return v


def _viewable_types(ctx: BCtx) -> list[VoucherType]:
    return [t for t in VoucherType if ctx.can(voucher_module(t), "view")]


@router.get("", response_model=list[VoucherOut])
def list_vouchers(
    ctx: BCtx,
    type: VoucherType | None = None,
    party_id: str | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    search: str | None = None,
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    q = (
        select(Voucher)
        .options(selectinload(Voucher.allocations))
        .where(Voucher.business_id == ctx.bid)
        .order_by(Voucher.date.desc(), Voucher.created_at.desc())
    )
    if type:
        ctx.need(voucher_module(type), "view")
        q = q.where(Voucher.type == type)
    else:
        q = q.where(Voucher.type.in_(_viewable_types(ctx)))
    if party_id:
        q = q.where(Voucher.party_id == party_id)
    if date_from:
        q = q.where(Voucher.date >= date_from)
    if date_to:
        q = q.where(Voucher.date <= date_to)
    if search:
        like = f"%{search}%"
        q = q.where(or_(Voucher.number.ilike(like), Voucher.party_name.ilike(like)))
    rows = [to_out(v) for v in ctx.db.scalars(q.limit(min(limit, 1000)).offset(offset))]
    if status:
        rows = [r for r in rows if r.status == status]
    return rows


@router.get("/next-number")
def next_number(ctx: BCtx, type: VoucherType, date: dt.date | None = None):
    prefix = getattr(ctx.business, VOUCHER_META[type]["prefix"])
    return {"number": preview_number(ctx.db, ctx.bid, type.value, prefix, date or dt.date.today())}


@router.post("", response_model=VoucherDetailOut, status_code=201)
def create_voucher(data: VoucherIn, ctx: BCtx):
    ctx.need(voucher_module(data.type), "create")
    v = save_voucher(ctx, data)
    ctx.db.commit()
    ctx.db.refresh(v)
    return to_detail(ctx, v)


@router.get("/{voucher_id}", response_model=VoucherDetailOut)
def get_voucher(voucher_id: str, ctx: BCtx):
    return to_detail(ctx, _get(ctx, voucher_id))


@router.put("/{voucher_id}", response_model=VoucherDetailOut)
def update_voucher(voucher_id: str, data: VoucherIn, ctx: BCtx):
    current = _get(ctx, voucher_id, "edit")
    ctx.need_past_edit(min(current.date, data.date))
    v = save_voucher(ctx, data, current)
    ctx.db.commit()
    ctx.db.refresh(v)
    return to_detail(ctx, v)


@router.post("/{voucher_id}/cancel", response_model=VoucherDetailOut)
def cancel(voucher_id: str, ctx: BCtx):
    v = _get(ctx, voucher_id, "delete")
    ctx.need_past_edit(v.date)
    if v.cancelled:
        raise HTTPException(400, "Already cancelled")
    cancel_voucher(ctx, v)
    ctx.db.commit()
    ctx.db.refresh(v)
    return to_detail(ctx, v)
