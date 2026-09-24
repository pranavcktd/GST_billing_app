"""Cash & bank: every rupee that moves through an account, from all sources.

Sources: payments in/out (incl. those made while billing), transfers, capital,
loans and tax payments. Statements, balances and the cash-flow report are built
from this one list so they can never disagree.
"""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..gst.constants import AccountType, CapitalType, LoanTxnType, PaymentType, VoucherType
from ..models import (
    Account,
    AccountTransfer,
    CapitalEntry,
    Loan,
    LoanTxn,
    Payment,
    PaymentAllocation,
    TaxPayment,
)

ZERO = Decimal("0")


def cash_account(db: Session, business_id: str) -> Account:
    acc = db.scalar(select(Account).where(Account.business_id == business_id, Account.is_default_cash.is_(True)))
    if acc is None:
        acc = Account(business_id=business_id, type=AccountType.CASH, name="Cash in Hand", is_default_cash=True)
        db.add(acc)
        db.flush()
    return acc


def resolve_account(db: Session, business_id: str, account_id: str | None) -> Account:
    if not account_id:
        return cash_account(db, business_id)
    acc = db.get(Account, account_id)
    if not acc or acc.business_id != business_id:
        raise HTTPException(404, "Cash/bank account not found")
    return acc


def movements(
    db: Session,
    business_id: str,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    account_id: str | None = None,
) -> list[dict]:
    """Signed money movements (+ in, - out). Each row carries `flows` for the cash-flow report."""
    rows: list[dict] = []

    def add(date, acc, amount, kind, number, party, ref_type, ref_id, created, flows, note=None):
        rows.append(dict(date=date, account_id=acc, amount=amount, kind=kind, number=number, party=party,
                         ref_type=ref_type, ref_id=ref_id, created=created, flows=flows, note=note))

    payments = db.scalars(
        select(Payment)
        .options(selectinload(Payment.party), selectinload(Payment.allocations).selectinload(PaymentAllocation.voucher))
        .where(Payment.business_id == business_id)
    ).all()
    for p in payments:
        if not p.amount or p.cheque_status in ("OPEN", "BOUNCED"):
            continue  # cheques move money only once cleared
        date = p.cleared_on if p.cheque_status == "CLEARED" and p.cleared_on else p.date
        if p.type == PaymentType.IN:
            flow = "Receipts from customers"
            add(date, p.account_id, p.amount, "Payment In", p.number, p.party.name if p.party else None,
                "payment", p.id, p.created_at, [(flow, p.amount)], p.reference)
        else:
            is_expense = any(a.voucher.type == VoucherType.EXPENSE for a in p.allocations)
            flow = "Expenses paid" if is_expense else "Payments to suppliers"
            add(date, p.account_id, -p.amount, "Expense" if is_expense else "Payment Out", p.number,
                p.party.name if p.party else None, "payment", p.id, p.created_at, [(flow, -p.amount)], p.reference)

    for t in db.scalars(select(AccountTransfer).where(AccountTransfer.business_id == business_id)):
        add(t.date, t.from_account_id, -t.amount, "Transfer out", "", None, "transfer", t.id, t.created_at, [], t.note)
        add(t.date, t.to_account_id, t.amount, "Transfer in", "", None, "transfer", t.id, t.created_at, [], t.note)

    for c in db.scalars(select(CapitalEntry).where(CapitalEntry.business_id == business_id)):
        if c.type == CapitalType.INTRODUCED:
            add(c.date, c.account_id, c.amount, "Capital introduced", "", None, "capital", c.id, c.created_at,
                [("Capital introduced", c.amount)], c.note)
        else:
            add(c.date, c.account_id, -c.amount, "Drawings", "", None, "capital", c.id, c.created_at,
                [("Drawings", -c.amount)], c.note)

    loans = {l.id: l.name for l in db.scalars(select(Loan).where(Loan.business_id == business_id))}
    for x in db.scalars(select(LoanTxn).where(LoanTxn.business_id == business_id)):
        name = loans.get(x.loan_id, "Loan")
        if x.type == LoanTxnType.DISBURSEMENT:
            add(x.date, x.account_id, x.principal, "Loan received", name, None, "loan", x.loan_id, x.created_at,
                [("Loans received", x.principal)], x.note)
        elif x.type == LoanTxnType.EMI:
            add(x.date, x.account_id, -(x.principal + x.interest), "Loan EMI", name, None, "loan", x.loan_id,
                x.created_at, [("Loan principal repaid", -x.principal), ("Interest paid", -x.interest)], x.note)
        else:
            add(x.date, x.account_id, -x.interest, "Loan charges", name, None, "loan", x.loan_id, x.created_at,
                [("Interest paid", -x.interest)], x.note)

    for tp in db.scalars(select(TaxPayment).where(TaxPayment.business_id == business_id)):
        add(tp.date, tp.account_id, -tp.amount, f"{tp.type.value} paid", tp.reference or "", None, "tax", tp.id,
            tp.created_at, [(f"{tp.type.value} deposited", -tp.amount)], tp.note)

    if account_id:
        rows = [r for r in rows if r["account_id"] == account_id]
    if date_from:
        rows = [r for r in rows if r["date"] >= date_from]
    if date_to:
        rows = [r for r in rows if r["date"] <= date_to]
    rows.sort(key=lambda r: (r["date"], r["created"]))
    return rows


def account_balances(db: Session, business_id: str, as_of: dt.date | None = None) -> dict[str, Decimal]:
    bal: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for a in db.scalars(select(Account).where(Account.business_id == business_id)):
        bal[a.id] += a.opening_balance or ZERO
    for m in movements(db, business_id, date_to=as_of):
        bal[m["account_id"]] += m["amount"]
    return dict(bal)


def statement(db: Session, account: Account, date_from: dt.date | None, date_to: dt.date | None) -> dict:
    opening = account.opening_balance or ZERO
    entries, running = [], None
    for m in movements(db, account.business_id, date_to=date_to, account_id=account.id):
        if date_from and m["date"] < date_from:
            opening += m["amount"]
            continue
        running = (running if running is not None else opening) + m["amount"]
        entries.append({**{k: m[k] for k in ("date", "kind", "number", "party", "ref_type", "ref_id", "note")},
                        "deposit": m["amount"] if m["amount"] > 0 else ZERO,
                        "withdrawal": -m["amount"] if m["amount"] < 0 else ZERO,
                        "balance": running})
    return dict(opening=opening, closing=running if running is not None else opening, entries=entries)
