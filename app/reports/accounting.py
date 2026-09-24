"""Profit & loss and balance sheet derived from the transactions.

The app records single-entry documents, but each one implies a balanced
double entry. The balance sheet is built so every document's two sides land
on it:

  sale             Dr debtors / cash   Cr sales, output GST, TCS payable, round off
  purchase/expense Dr purchases or expense, input GST (if claimable), TCS receivable
                   Cr creditors / cash
  payment          Dr/Cr cash & bank, TDS receivable/payable   vs   party
  capital / loans / transfers / tax challans move cash against capital, loans, tax dues
  stock            valued at weighted-average cost, same figure in P&L and balance sheet

Opening balances (accounts, parties, opening stock, loans) form the opening capital.
If the two sides differ, a "Difference" line appears and flags a gap in the logic.
"""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..gst.constants import (
    BusinessGstType,
    CapitalType,
    ExpenseKind,
    ItemType,
    LoanTxnType,
    PaymentType,
    StockMoveType,
    TaxPaymentType,
    VoucherType,
)
from ..models import (
    Account,
    Business,
    CapitalEntry,
    ExpenseCategory,
    Item,
    Loan,
    LoanTxn,
    Party,
    Payment,
    StockMovement,
    TaxPayment,
    Voucher,
)
from ..services.accounts import account_balances
from ..services.ledger import party_balances

ZERO = Decimal("0")
PAISE = Decimal("0.01")
EPOCH = dt.date(1900, 1, 1)


# ---------------------------------------------------------------- stock valuation
def avg_costs(db: Session, bid: str, as_of: dt.date) -> dict[str, Decimal]:
    """Weighted-average cost per item from opening stock and purchases up to `as_of`."""
    qty: dict[str, Decimal] = defaultdict(lambda: ZERO)
    val: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for m in db.scalars(select(StockMovement).where(
            StockMovement.business_id == bid, StockMovement.date <= as_of,
            StockMovement.type.in_([StockMoveType.OPENING, StockMoveType.PURCHASE]), StockMovement.qty > 0)):
        qty[m.item_id] += m.qty
        val[m.item_id] += m.qty * (m.rate or ZERO)
    costs = {i: (val[i] / qty[i]) for i in qty if qty[i]}
    for it in db.scalars(select(Item).where(Item.business_id == bid)):
        costs.setdefault(it.id, it.purchase_price or ZERO)
    return costs


def stock_qty(db: Session, bid: str, as_of: dt.date) -> dict[str, Decimal]:
    q: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for m in db.scalars(select(StockMovement).where(StockMovement.business_id == bid, StockMovement.date <= as_of)):
        q[m.item_id] += m.qty
    return q


def stock_value(db: Session, bid: str, as_of: dt.date) -> Decimal:
    if as_of < EPOCH:
        return ZERO
    costs = avg_costs(db, bid, as_of)
    qty = stock_qty(db, bid, as_of)
    goods = {i.id for i in db.scalars(select(Item).where(Item.business_id == bid, Item.type == ItemType.GOODS))}
    return sum(((max(q, ZERO) * costs.get(i, ZERO)).quantize(PAISE) for i, q in qty.items() if i in goods), ZERO)


def opening_stock_movements_value(db: Session, bid: str, date_from: dt.date, date_to: dt.date) -> Decimal:
    return sum(((m.qty * (m.rate or ZERO)).quantize(PAISE) for m in db.scalars(select(StockMovement).where(
        StockMovement.business_id == bid, StockMovement.type == StockMoveType.OPENING,
        StockMovement.date >= date_from, StockMovement.date <= date_to))), ZERO)


# ---------------------------------------------------------------- GST treatment of inward documents
def itc_claimable(v: Voucher, biz: Business) -> bool:
    return (biz.gst_type == BusinessGstType.REGULAR and v.tax_applicable
            and bool(v.party_gstin or v.reverse_charge))


def tax_of(v) -> Decimal:
    return v.cgst + v.sgst + v.igst + v.cess


def inward_cost(v: Voucher, biz: Business) -> Decimal:
    """What a purchase/expense costs the business (GST is a cost only when no credit is available)."""
    return v.taxable + (ZERO if itc_claimable(v, biz) else tax_of(v))


def _docs(db, bid, types, date_from, date_to):
    return db.scalars(select(Voucher).where(
        Voucher.business_id == bid, Voucher.type.in_(types), Voucher.cancelled.is_(False),
        Voucher.date >= date_from, Voucher.date <= date_to)).all()


# ---------------------------------------------------------------- P&L
def profit_and_loss(db: Session, biz: Business, date_from: dt.date, date_to: dt.date) -> dict:
    bid = biz.id
    docs = _docs(db, bid, [VoucherType.SALE, VoucherType.SALE_RETURN, VoucherType.PURCHASE,
                           VoucherType.PURCHASE_RETURN, VoucherType.EXPENSE], date_from, date_to)
    cats = {c.id: c for c in db.scalars(select(ExpenseCategory).where(ExpenseCategory.business_id == bid))}

    sales = sale_returns = purchases = purchase_returns = round_off = ZERO
    direct: dict[str, Decimal] = defaultdict(lambda: ZERO)
    indirect: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for v in docs:
        if v.type == VoucherType.SALE:
            sales += v.taxable
            round_off += v.round_off
        elif v.type == VoucherType.SALE_RETURN:
            sale_returns += v.taxable
            round_off -= v.round_off
        elif v.type == VoucherType.PURCHASE:
            purchases += inward_cost(v, biz)
            round_off -= v.round_off
        elif v.type == VoucherType.PURCHASE_RETURN:
            purchase_returns += inward_cost(v, biz)
            round_off += v.round_off
        else:
            cat = cats.get(v.expense_category_id)
            bucket = direct if cat and cat.kind == ExpenseKind.DIRECT else indirect
            bucket[cat.name if cat else "Uncategorised"] += inward_cost(v, biz)
            round_off -= v.round_off

    interest = sum((t.interest for t in db.scalars(select(LoanTxn).where(
        LoanTxn.business_id == bid, LoanTxn.date >= date_from, LoanTxn.date <= date_to))), ZERO)

    opening_stock = stock_value(db, bid, date_from - dt.timedelta(days=1)) + \
        opening_stock_movements_value(db, bid, date_from, date_to)
    closing_stock = stock_value(db, bid, date_to)

    net_sales = sales - sale_returns
    net_purchases = purchases - purchase_returns
    direct_total = sum(direct.values(), ZERO)
    cogs = opening_stock + net_purchases + direct_total - closing_stock
    gross = net_sales - cogs
    indirect_total = sum(indirect.values(), ZERO)
    net = gross - indirect_total - interest + round_off
    return dict(
        sales=sales, sale_returns=sale_returns, net_sales=net_sales,
        opening_stock=opening_stock, purchases=purchases, purchase_returns=purchase_returns,
        net_purchases=net_purchases, direct=dict(direct), direct_total=direct_total,
        closing_stock=closing_stock, cogs=cogs, gross_profit=gross,
        indirect=dict(indirect), indirect_total=indirect_total, interest=interest,
        round_off=round_off, net_profit=net,
    )


# ---------------------------------------------------------------- balance sheet
def gst_position(db: Session, biz: Business, as_of: dt.date) -> dict:
    output = rcm = itc = ZERO
    for v in _docs(db, biz.id, list(VoucherType), EPOCH, as_of):
        if not v.tax_applicable:
            continue
        t = tax_of(v)
        if v.type == VoucherType.SALE:
            output += t
        elif v.type == VoucherType.SALE_RETURN:
            output -= t
        elif v.type in (VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN, VoucherType.EXPENSE):
            sign = -1 if v.type == VoucherType.PURCHASE_RETURN else 1
            if v.reverse_charge:
                rcm += sign * t
            if itc_claimable(v, biz):
                itc += sign * t
    return dict(output=output, rcm=rcm, itc=itc)


def balance_sheet(db: Session, biz: Business, as_of: dt.date) -> dict:
    bid = biz.id
    accounts = db.scalars(select(Account).where(Account.business_id == bid)).all()
    acc_bal = account_balances(db, bid, as_of)
    parties = db.scalars(select(Party).where(Party.business_id == bid)).all()
    p_bal = party_balances(db, bid, as_of=as_of)
    debtors = sum((b for b in p_bal.values() if b > 0), ZERO)
    creditors = -sum((b for b in p_bal.values() if b < 0), ZERO)

    pays = db.scalars(select(Payment).where(Payment.business_id == bid, Payment.date <= as_of)).all()
    live = [p for p in pays if p.cheque_status != "BOUNCED"]
    in_transit = [p for p in live if p.cheque_status == "OPEN" or (
        p.cheque_status == "CLEARED" and p.cleared_on and p.cleared_on > as_of)]
    cheques_in_hand = sum((p.amount for p in in_transit if p.type == PaymentType.IN), ZERO)
    cheques_issued = sum((p.amount for p in in_transit if p.type == PaymentType.OUT), ZERO)
    tds_receivable = sum((p.tds_amount for p in live if p.type == PaymentType.IN), ZERO)
    tds_deducted = sum((p.tds_amount for p in live if p.type == PaymentType.OUT), ZERO)

    tcs_collected = tcs_paid_to_suppliers = ZERO
    for v in _docs(db, bid, [VoucherType.SALE, VoucherType.SALE_RETURN, VoucherType.PURCHASE,
                             VoucherType.PURCHASE_RETURN, VoucherType.EXPENSE], EPOCH, as_of):
        sign = -1 if v.type in (VoucherType.SALE_RETURN, VoucherType.PURCHASE_RETURN) else 1
        if v.type in (VoucherType.SALE, VoucherType.SALE_RETURN):
            tcs_collected += sign * v.tcs_amount
        else:
            tcs_paid_to_suppliers += sign * v.tcs_amount

    tax_paid = defaultdict(lambda: ZERO)
    for tp in db.scalars(select(TaxPayment).where(TaxPayment.business_id == bid, TaxPayment.date <= as_of)):
        tax_paid[tp.type] += tp.amount

    gst = gst_position(db, biz, as_of)
    gst_net = gst["output"] + gst["rcm"] - gst["itc"] - tax_paid[TaxPaymentType.GST]
    tds_payable = tds_deducted - tax_paid[TaxPaymentType.TDS]
    tcs_payable = tcs_collected - tax_paid[TaxPaymentType.TCS]

    loans = db.scalars(select(Loan).where(Loan.business_id == bid)).all()
    loan_rows = []
    for l in loans:
        bal = l.opening_balance or ZERO
        for t in l.txns:
            if t.date <= as_of:
                bal += t.principal if t.type == LoanTxnType.DISBURSEMENT else (
                    -t.principal if t.type == LoanTxnType.EMI else ZERO)
        if bal:
            loan_rows.append((l.name, bal))

    cap = db.scalars(select(CapitalEntry).where(CapitalEntry.business_id == bid, CapitalEntry.date <= as_of)).all()
    introduced = sum((c.amount for c in cap if c.type == CapitalType.INTRODUCED), ZERO)
    drawings = sum((c.amount for c in cap if c.type == CapitalType.DRAWINGS), ZERO)
    opening_capital = (
        sum((a.opening_balance or ZERO for a in accounts), ZERO)
        + sum((p.opening_balance or ZERO for p in parties), ZERO)
        + opening_stock_movements_value(db, bid, EPOCH, as_of)
        - sum((l.opening_balance or ZERO for l in loans), ZERO)
    )
    profit = profit_and_loss(db, biz, EPOCH, as_of)["net_profit"]
    capital = opening_capital + introduced - drawings + profit

    assets = [(a.name, acc_bal.get(a.id, ZERO)) for a in accounts if acc_bal.get(a.id, ZERO) or a.is_active]
    assets += [("Cheques in hand (not cleared)", cheques_in_hand), ("Sundry debtors", debtors),
               ("Closing stock", stock_value(db, bid, as_of)), ("TDS receivable", tds_receivable),
               ("TCS receivable", tcs_paid_to_suppliers)]
    if gst_net < 0:
        assets.append(("GST input credit", -gst_net))
    liabilities = [(f"Loan: {n}", b) for n, b in loan_rows]
    liabilities += [("Sundry creditors", creditors), ("Cheques issued (not cleared)", cheques_issued),
                    ("TDS payable", tds_payable), ("TCS payable", tcs_payable)]
    if gst_net > 0:
        liabilities.append(("GST payable", gst_net))

    total_assets = sum((v for _, v in assets), ZERO)
    total_liab = sum((v for _, v in liabilities), ZERO) + capital
    return dict(
        assets=[(n, v) for n, v in assets if v],
        liabilities=[(n, v) for n, v in liabilities if v],
        capital=dict(opening=opening_capital, introduced=introduced, drawings=drawings, profit=profit, closing=capital),
        total_assets=total_assets, total_liabilities=total_liab, difference=total_assets - total_liab,
    )
