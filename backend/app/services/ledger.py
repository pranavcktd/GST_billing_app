"""Party balances, party ledger and item stock — all derived from transactions."""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..gst.constants import PAYMENT_LEDGER, VOUCHER_META, PaymentType, VoucherType
from ..models import Party, Payment, StockMovement, Voucher

ZERO = Decimal("0")
NOT_BOUNCED = or_(Payment.cheque_status.is_(None), Payment.cheque_status != "BOUNCED")
LEDGER_VOUCHER_TYPES = [t for t, m in VOUCHER_META.items() if m["ledger"]]


def party_balances(
    db: Session, business_id: str, party_ids: list[str] | None = None, as_of: dt.date | None = None
) -> dict[str, Decimal]:
    """Positive = receivable (party owes us), negative = payable."""
    bal: dict[str, Decimal] = defaultdict(lambda: ZERO)

    pq = select(Party.id, Party.opening_balance).where(Party.business_id == business_id)
    vq = (
        select(Voucher.party_id, Voucher.type, func.sum(Voucher.grand_total))
        .where(
            Voucher.business_id == business_id,
            Voucher.cancelled.is_(False),
            Voucher.type.in_(LEDGER_VOUCHER_TYPES),
            Voucher.party_id.is_not(None),
        )
        .group_by(Voucher.party_id, Voucher.type)
    )
    payq = (
        select(Payment.party_id, Payment.type, func.sum(Payment.amount + Payment.tds_amount))
        .where(Payment.business_id == business_id, Payment.party_id.is_not(None), NOT_BOUNCED)
        .group_by(Payment.party_id, Payment.type)
    )
    if as_of is not None:
        vq = vq.where(Voucher.date <= as_of)
        payq = payq.where(Payment.date <= as_of)
    if party_ids is not None:
        pq = pq.where(Party.id.in_(party_ids))
        vq = vq.where(Voucher.party_id.in_(party_ids))
        payq = payq.where(Payment.party_id.in_(party_ids))

    for pid, opening in db.execute(pq):
        bal[pid] += opening or ZERO
    for pid, vtype, total in db.execute(vq):
        bal[pid] += VOUCHER_META[VoucherType(vtype)]["ledger"] * (total or ZERO)
    for pid, ptype, total in db.execute(payq):
        bal[pid] += PAYMENT_LEDGER[PaymentType(ptype)] * (total or ZERO)
    return dict(bal)


_LEDGER_LABEL = {
    VoucherType.SALE: "Sale",
    VoucherType.SALE_RETURN: "Credit Note",
    VoucherType.PURCHASE: "Purchase",
    VoucherType.PURCHASE_RETURN: "Debit Note",
    VoucherType.EXPENSE: "Expense",
}


def party_ledger(db: Session, party: Party, date_from: dt.date | None, date_to: dt.date | None) -> dict:
    rows = []
    for v in db.scalars(
        select(Voucher).where(
            Voucher.party_id == party.id,
            Voucher.cancelled.is_(False),
            Voucher.type.in_(LEDGER_VOUCHER_TYPES),
        )
    ):
        sign = VOUCHER_META[v.type]["ledger"]
        rows.append(dict(date=v.date, kind=_LEDGER_LABEL[v.type], number=v.number, ref_id=v.id,
                         ref_type="voucher", amount=sign * v.grand_total, created=v.created_at))
    for p in db.scalars(select(Payment).where(Payment.party_id == party.id, NOT_BOUNCED)):
        sign = PAYMENT_LEDGER[p.type]
        rows.append(dict(date=p.date, kind="Payment In" if p.type == PaymentType.IN else "Payment Out",
                         number=p.number, ref_id=p.id, ref_type="payment", amount=sign * p.settled,
                         created=p.created_at))
    rows.sort(key=lambda r: (r["date"], r["created"]))

    opening = party.opening_balance or ZERO
    entries = []
    running = opening
    for r in rows:
        if date_from and r["date"] < date_from:
            opening += r["amount"]
            running = opening
            continue
        if date_to and r["date"] > date_to:
            continue
        running += r["amount"]
        entries.append(dict(
            date=r["date"], kind=r["kind"], number=r["number"], ref_id=r["ref_id"], ref_type=r["ref_type"],
            debit=r["amount"] if r["amount"] > 0 else ZERO,
            credit=-r["amount"] if r["amount"] < 0 else ZERO,
            balance=running,
        ))
    return dict(opening=opening, closing=running, entries=entries)


def item_stock(
    db: Session, business_id: str, item_ids: list[str] | None = None, as_of: dt.date | None = None
) -> dict[str, Decimal]:
    q = (
        select(StockMovement.item_id, func.sum(StockMovement.qty))
        .where(StockMovement.business_id == business_id)
        .group_by(StockMovement.item_id)
    )
    if item_ids is not None:
        q = q.where(StockMovement.item_id.in_(item_ids))
    if as_of:
        q = q.where(StockMovement.date <= as_of)
    return {iid: qty or ZERO for iid, qty in db.execute(q)}
