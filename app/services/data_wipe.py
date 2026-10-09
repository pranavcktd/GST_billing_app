"""Clear a business's data (for example after testing, before going live), group by group.

A backup is always taken first (kind WIPE — never pruned) and e-mailed when e-mail is set up. The company profile,
settings, logins, godowns and backup history are never cleared. Masters can only go together with everything that
uses them (`requires`), so nothing is left pointing at a deleted party, item or account.
"""

import datetime as dt

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..gst.constants import StockMoveType, VoucherType
from ..models import (
    Account,
    AccountTransfer,
    Bom,
    Business,
    CapitalEntry,
    ComplianceFiling,
    Counter,
    Document,
    Employee,
    ExpenseItem,
    GstReturnStatus,
    HsnCode,
    Item,
    Loan,
    LoanTxn,
    Party,
    Payment,
    PaymentAllocation,
    PayrollRun,
    PriceList,
    Production,
    RecurringInvoice,
    StockMovement,
    StockTransfer,
    TaxPayment,
    Voucher,
)
from . import backup as bk

V = VoucherType
GROUPS = [
    dict(key="sales", label="Sales", help="Invoices, credit notes, quotations, sale orders, delivery challans, recurring bills",
         types=[V.SALE, V.SALE_RETURN, V.ESTIMATE, V.SALE_ORDER, V.DELIVERY_CHALLAN], requires=[]),
    dict(key="purchases", label="Purchases", help="Purchase bills, debit notes, purchase orders",
         types=[V.PURCHASE, V.PURCHASE_RETURN, V.PURCHASE_ORDER], requires=[]),
    dict(key="expenses", label="Expenses", help="Expense entries (including salary entries)", types=[V.EXPENSE], requires=[]),
    dict(key="payments", label="All payments & receipts", help="Every payment in and out, including advances and cheques",
         types=[], requires=[]),
    dict(key="stock", label="Stock entries", help="Stock adjustments, godown transfers, production", types=[], requires=[]),
    dict(key="banking", label="Bank & cash entries", help="Account transfers, capital, tax payments, loans", types=[], requires=[]),
    dict(key="staff", label="Staff & payroll", help="Employees, attendance, payroll, salary advances", types=[], requires=[]),
    dict(key="documents", label="Document vault", help="Uploaded documents and links", types=[], requires=[]),
    dict(key="compliance", label="Compliance records", help="Filings marked done and GST return status", types=[], requires=[]),
    dict(key="parties", label="Parties (customers & suppliers)", help="Needs every bill and payment cleared too",
         types=[], requires=["sales", "purchases", "expenses", "payments"], master=True),
    dict(key="items", label="Items, price lists & HSN list", help="Needs sales, purchases and stock entries cleared too",
         types=[], requires=["sales", "purchases", "stock"], master=True),
    dict(key="expense_items", label="Expense items", help="Your saved expense heads", types=[], requires=[], master=True),
    dict(key="accounts", label="Bank accounts", help="Bank accounts (cash in hand stays, opening balance set to 0). "
         "Needs payments and bank entries cleared too", types=[], requires=["payments", "banking"], master=True),
]
BY_KEY = {g["key"]: g for g in GROUPS}


def options() -> list[dict]:
    return [{k: g.get(k, False) if k == "master" else g[k] for k in ("key", "label", "help", "requires", "master")} for g in GROUPS]


def closure(keys: list[str]) -> list[str]:
    """Selected groups plus everything they require, in the listed order."""
    bad = [k for k in keys if k not in BY_KEY]
    if bad:
        raise HTTPException(422, f"Unknown data group: {', '.join(bad)}")
    out = set()
    todo = list(keys)
    while todo:
        k = todo.pop()
        if k not in out:
            out.add(k)
            todo += BY_KEY[k]["requires"]
    return [g["key"] for g in GROUPS if g["key"] in out]


def counts(db: Session, bid: str) -> dict[str, int]:
    """How many records each group holds now (shown next to the tick boxes)."""
    def n(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(model.business_id == bid, *where)) or 0
    out = {g["key"]: n(Voucher, Voucher.type.in_(g["types"])) for g in GROUPS if g["types"]}
    out["payments"] = n(Payment)
    out["stock"] = n(StockMovement, StockMovement.type.in_([StockMoveType.ADJUSTMENT, StockMoveType.TRANSFER,
                                                            StockMoveType.PRODUCTION, StockMoveType.CONSUMPTION]))
    out["banking"] = n(AccountTransfer) + n(CapitalEntry) + n(TaxPayment) + n(Loan)
    out["staff"] = n(Employee)
    out["documents"] = n(Document)
    out["compliance"] = n(ComplianceFiling) + n(GstReturnStatus)
    out["parties"] = n(Party)
    out["items"] = n(Item)
    out["expense_items"] = n(ExpenseItem)
    out["accounts"] = n(Account, Account.is_default_cash.is_(False))
    return out


def wipe(db: Session, biz: Business, keys: list[str], confirm_name: str, actor, by_admin: bool = False) -> dict:
    if (confirm_name or "").strip().lower() != biz.name.strip().lower():
        raise HTTPException(400, "Type the business name exactly to confirm")
    groups = closure(keys)
    if not groups:
        raise HTTPException(422, "Choose what to clear")
    bid = biz.id
    before = counts(db, bid)

    # ---- safety backup first, saved on its own (kept even if clearing fails)
    b = bk.create_backup(db, biz, actor.id, "WIPE")
    db.commit()
    backup_id, created = b.id, b.created_at
    to = biz.backup_email or (db.get(type(actor), biz.owner_id).email if biz.owner_id else None)
    emailed, email_error = None, None
    if to:
        try:
            bk.email_backup(db, biz, to, b.data, created)
            b.emailed_to = emailed = to
            db.commit()
        except Exception as e:  # noqa: BLE001 — e-mail is a convenience; the saved backup is what counts
            db.rollback()
            email_error = getattr(e, "detail", None) or str(e)

    sel = set(groups)
    vtypes = [t for g in groups for t in BY_KEY[g]["types"]]
    gone_v = select(Voucher.id).where(Voucher.business_id == bid, Voucher.type.in_(vtypes))

    # ---- payments: all, or those that only settled cleared bills (+ unlinked ones of a cleared side)
    if "payments" in sel:
        db.execute(delete(Payment).where(Payment.business_id == bid))
    elif vtypes:
        kept_link = select(PaymentAllocation.payment_id).where(PaymentAllocation.voucher_id.not_in(gone_v))
        linked = select(PaymentAllocation.payment_id)
        only_gone = Payment.id.in_(select(PaymentAllocation.payment_id).where(PaymentAllocation.voucher_id.in_(gone_v)))
        loose_sides = [t for t, g in (("IN", "sales"), ("OUT", "purchases")) if g in sel]
        db.execute(delete(Payment).where(Payment.business_id == bid, Payment.id.not_in(kept_link), only_gone))
        if loose_sides:
            db.execute(delete(Payment).where(Payment.business_id == bid, Payment.id.not_in(linked),
                                             Payment.type.in_(loose_sides)))
    # ---- documents (lines, stock movements, payment links and reminders go with them)
    if vtypes:
        db.execute(update(Voucher).where(Voucher.business_id == bid, Voucher.original_voucher_id.in_(gone_v))
                   .values(original_voucher_id=None))
        db.execute(delete(Voucher).where(Voucher.id.in_(gone_v)))
    if "sales" in sel:
        db.execute(delete(RecurringInvoice).where(RecurringInvoice.business_id == bid))
    if "stock" in sel:
        db.execute(delete(StockMovement).where(StockMovement.business_id == bid, StockMovement.type.in_(
            [StockMoveType.ADJUSTMENT, StockMoveType.TRANSFER, StockMoveType.PRODUCTION, StockMoveType.CONSUMPTION])))
        db.execute(delete(StockTransfer).where(StockTransfer.business_id == bid))
        db.execute(delete(Production).where(Production.business_id == bid))
    if "banking" in sel:
        for m in (AccountTransfer, CapitalEntry, TaxPayment, LoanTxn, Loan):
            db.execute(delete(m).where(m.business_id == bid))
    if "staff" in sel:
        db.execute(delete(PayrollRun).where(PayrollRun.business_id == bid))
        db.execute(delete(Employee).where(Employee.business_id == bid))
    if "documents" in sel:
        db.execute(delete(Document).where(Document.business_id == bid))
    if "compliance" in sel:
        db.execute(delete(ComplianceFiling).where(ComplianceFiling.business_id == bid))
        db.execute(delete(GstReturnStatus).where(GstReturnStatus.business_id == bid))
    # ---- masters
    if "parties" in sel:
        db.execute(delete(Party).where(Party.business_id == bid))
    if "items" in sel:
        for m in (Bom, PriceList, Item, HsnCode):
            db.execute(delete(m).where(m.business_id == bid))
    if "expense_items" in sel:
        db.execute(delete(ExpenseItem).where(ExpenseItem.business_id == bid))
    if "accounts" in sel:
        db.execute(delete(Account).where(Account.business_id == bid, Account.is_default_cash.is_(False)))
        db.execute(update(Account).where(Account.business_id == bid).values(opening_balance=0))
    # ---- numbering restarts for cleared series
    keys_reset = [t.value for t in vtypes] + (["PAYMENT_IN", "PAYMENT_OUT"] if "payments" in sel else []) + (
        ["STOCK_TRANSFER", "PRODUCTION"] if "stock" in sel else [])
    if keys_reset:
        db.execute(delete(Counter).where(Counter.business_id == bid, Counter.key.in_(keys_reset)))

    from .platform_audit import log

    after = counts(db, bid)
    labels = ", ".join(BY_KEY[g]["label"] for g in groups)
    log(db, actor, "DELETE", "data-wipe", f"Cleared data{' (by platform admin)' if by_admin else ''}: {labels}. "
        f"Backup taken first ({bk.filename(biz.name, created)})", business_id=bid)
    db.commit()
    return {"cleared": groups, "removed": {k: before[k] - after.get(k, 0) for k in before if before[k] - after.get(k, 0)},
            "backup_id": backup_id, "backup_file": bk.filename(biz.name, created), "emailed_to": emailed,
            "email_error": email_error, "at": dt.datetime.now(dt.UTC)}
