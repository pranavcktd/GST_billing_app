"""Payment in / out with allocation against open bills."""

from decimal import Decimal

from sqlalchemy import func, select

from ..deps import Ctx
from ..gst.constants import PaymentMode, PaymentType, VoucherType
from ..models import Party, Payment, PaymentAllocation, Voucher
from ..schemas import PaymentIn, PaymentOut
from .accounts import resolve_account
from .numbering import allocate_number
from .vouchers import bad, payment_number_exists

ZERO = Decimal("0")

# Which documents a payment of each direction settles.
SETTLES = {
    PaymentType.IN: [VoucherType.SALE, VoucherType.PURCHASE_RETURN],
    PaymentType.OUT: [VoucherType.PURCHASE, VoucherType.SALE_RETURN, VoucherType.EXPENSE],
}


def _allocated(ctx: Ctx, voucher_id: str) -> Decimal:
    return ctx.db.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(PaymentAllocation.voucher_id == voucher_id)
    ) or ZERO


def open_vouchers(ctx: Ctx, party_id: str, ptype: PaymentType) -> list[tuple[Voucher, Decimal]]:
    """Unsettled bills of the party, oldest first, with their outstanding amount."""
    vouchers = ctx.db.scalars(
        select(Voucher)
        .where(
            Voucher.business_id == ctx.bid,
            Voucher.party_id == party_id,
            Voucher.cancelled.is_(False),
            Voucher.type.in_(SETTLES[ptype]),
        )
        .order_by(Voucher.date, Voucher.created_at)
    ).all()
    out = []
    for v in vouchers:
        due = v.grand_total - sum((a.amount for a in v.allocations), ZERO)
        if due > 0:
            out.append((v, due))
    return out


def create_payment(ctx: Ctx, data: PaymentIn) -> Payment:
    db, biz = ctx.db, ctx.business
    party = db.get(Party, data.party_id)
    if not party or party.business_id != ctx.bid:
        raise bad("Party not found", 404)

    if data.amount + data.tds_amount <= 0:
        raise bad("Enter the amount")
    account = resolve_account(db, ctx.bid, data.account_id)
    prefix = biz.receipt_prefix if data.type == PaymentType.IN else biz.payment_prefix
    payment = Payment(
        business_id=ctx.bid, type=data.type, date=data.date, party_id=party.id, amount=data.amount,
        tds_amount=data.tds_amount, account_id=account.id,
        cheque_status="OPEN" if data.mode == PaymentMode.CHEQUE else None,
        cheque_date=(data.cheque_date or data.date) if data.mode == PaymentMode.CHEQUE else None,
        mode=data.mode, reference=data.reference, notes=data.notes,
        number=allocate_number(db, ctx.bid, f"PAYMENT_{data.type.value}", prefix, data.date,
                               lambda n: payment_number_exists(ctx, data.type, n)),
    )
    db.add(payment)

    _allocate(ctx, payment, party, data)
    db.flush()
    return payment


def _allocate(ctx: Ctx, payment: Payment, party: Party, data: PaymentIn, first: list[str] | None = None) -> None:
    """Settle bills with the payment: the chosen bill, then `first` (the bills it settled before an edit), then oldest open bills."""
    db = ctx.db
    remaining = data.amount + data.tds_amount
    targets: list[tuple[Voucher, Decimal]] = []
    if data.voucher_id:
        v = db.get(Voucher, data.voucher_id)
        if not v or v.business_id != ctx.bid or v.party_id != party.id or v.type not in SETTLES[data.type]:
            raise bad("The selected bill does not belong to this party")
        if v.cancelled:
            raise bad("The selected bill is cancelled")
        due = v.grand_total - _allocated(ctx, v.id)
        if due > 0:
            targets.append((v, due))
    for vid in first or []:
        v = db.get(Voucher, vid)
        if (v and vid != data.voucher_id and v.business_id == ctx.bid and v.party_id == party.id
                and not v.cancelled and v.type in SETTLES[data.type]):
            due = v.grand_total - _allocated(ctx, v.id)
            if due > 0:
                targets.append((v, due))
    if data.auto_allocate:
        seen = {v.id for v, _ in targets}
        targets += [(v, due) for v, due in open_vouchers(ctx, party.id, data.type) if v.id not in seen]

    for v, due in targets:
        if remaining <= 0:
            break
        amt = min(due, remaining)
        payment.allocations.append(PaymentAllocation(voucher_id=v.id, amount=amt))
        remaining -= amt


def update_payment(ctx: Ctx, payment: Payment, data: PaymentIn) -> Payment:
    """Correct a payment's party, date, amount, account, mode or reference; its bills are settled again."""
    db = ctx.db
    if data.type != payment.type:
        raise bad("A payment in cannot be changed to a payment out — delete it and record a new one")
    party = db.get(Party, data.party_id)
    if not party or party.business_id != ctx.bid:
        raise bad("Party not found", 404)
    if data.amount + data.tds_amount <= 0:
        raise bad("Enter the amount")
    before = [a.voucher_id for a in payment.allocations] if party.id == payment.party_id else []
    payment.allocations.clear()
    db.flush()
    db.expire_all()  # bills' allocation lists are reloaded without this payment
    payment.party_id, payment.date, payment.amount, payment.tds_amount = party.id, data.date, data.amount, data.tds_amount
    payment.account_id = resolve_account(db, ctx.bid, data.account_id).id
    payment.reference, payment.notes = data.reference, data.notes
    if data.mode != payment.mode:
        payment.cheque_status = "OPEN" if data.mode == PaymentMode.CHEQUE else None
        payment.cleared_on = None
    payment.mode = data.mode
    payment.cheque_date = (data.cheque_date or data.date) if data.mode == PaymentMode.CHEQUE else None
    if payment.cheque_status != "BOUNCED":
        _allocate(ctx, payment, party, data, first=before)
    db.flush()
    return payment


def payment_out(p: Payment) -> PaymentOut:
    out = PaymentOut.model_validate(p)
    out.party_name = p.party.name if p.party else None
    out.account_name = p.account.name if p.account else None
    out.allocated = sum((a.amount for a in p.allocations), ZERO)
    return out
