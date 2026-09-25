import datetime as dt

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import BCtx
from ..gst.constants import PaymentType
from ..models import Party, Payment, PaymentAllocation
from ..schemas import PaymentIn, PaymentOut
from ..services.payments import create_payment, open_vouchers, payment_out
from ..services.vouchers import to_out

router = APIRouter(prefix="/payments", tags=["payments"])


def _mod(t: PaymentType) -> str:
    return "payments_in" if t == PaymentType.IN else "payments_out"


@router.get("", response_model=list[PaymentOut])
def list_payments(
    ctx: BCtx,
    type: PaymentType | None = None,
    party_id: str | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: int = 200,
    offset: int = 0,
):
    q = (
        select(Payment)
        .options(selectinload(Payment.allocations).selectinload(PaymentAllocation.voucher), selectinload(Payment.party))
        .where(Payment.business_id == ctx.bid)
        .order_by(Payment.date.desc(), Payment.created_at.desc())
    )
    allowed = [t for t in PaymentType if ctx.can(_mod(t), "view")]
    if type:
        ctx.need(_mod(type), "view")
        q = q.where(Payment.type == type)
    else:
        q = q.where(Payment.type.in_(allowed))
    if party_id:
        q = q.where(Payment.party_id == party_id)
    if date_from:
        q = q.where(Payment.date >= date_from)
    if date_to:
        q = q.where(Payment.date <= date_to)
    return [payment_out(p) for p in ctx.db.scalars(q.limit(min(limit, 1000)).offset(offset))]


@router.get("/open-bills")
def open_bills(ctx: BCtx, party_id: str, type: PaymentType):
    ctx.need(_mod(type), "view")
    party = ctx.db.get(Party, party_id)
    if not party or party.business_id != ctx.bid:
        raise HTTPException(404, "Party not found")
    return [{**to_out(v).model_dump(mode="json"), "due": float(due)} for v, due in open_vouchers(ctx, party_id, type)]


@router.post("", response_model=PaymentOut, status_code=201)
def create(data: PaymentIn, ctx: BCtx):
    ctx.need("payments_in" if data.type == PaymentType.IN else "payments_out", "create")
    p = create_payment(ctx, data)
    ctx.db.commit()
    ctx.db.refresh(p)
    return payment_out(p)


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: str, ctx: BCtx):
    p = ctx.db.get(Payment, payment_id)
    if not p or p.business_id != ctx.bid:
        raise HTTPException(404, "Payment not found")
    ctx.need(_mod(p.type), "view")
    return payment_out(p)


@router.delete("/{payment_id}", status_code=204)
def delete_payment(payment_id: str, ctx: BCtx):
    p = ctx.db.get(Payment, payment_id)
    if not p or p.business_id != ctx.bid:
        raise HTTPException(404, "Payment not found")
    ctx.need(_mod(p.type), "delete")
    ctx.need_past_edit(p.date)
    ctx.db.delete(p)
    ctx.db.commit()
