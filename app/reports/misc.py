"""Business status, taxes (TDS/TCS), expenses, orders and loan reports."""

from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..gst.constants import PaymentType, VoucherType
from ..models import Account, ExpenseCategory, ExpenseItem, Loan, Party, Payment, TaxPayment
from ..services.accounts import cash_account, statement
from .base import ZERO, RCtx, col, link_doc, money, pct, result, section, stat, totals, vouchers


# ---------------------------------------------------------------- business status
def bank_statement(r: RCtx):
    acc = r.db.get(Account, r.account_id) if r.account_id else cash_account(r.db, r.bid)
    if not acc or acc.business_id != r.bid:
        raise HTTPException(400, "Select an account")
    st = statement(r.db, acc, r.date_from, r.date_to)
    rows = [dict(date=r.date_from, kind="Opening balance", number="", party="", deposit=None, withdrawal=None,
                 balance=st["opening"], _style="sub")]
    for e in st["entries"]:
        rows.append(dict(date=e["date"], kind=e["kind"], number=e["number"], party=e["party"] or e["note"] or "",
                         deposit=e["deposit"], withdrawal=e["withdrawal"], balance=e["balance"]))
    t = totals(rows[1:], ["deposit", "withdrawal"])
    t["balance"] = st["closing"]
    cols = [col("date", "Date", "date"), col("kind", "Type"), col("number", "Ref"), col("party", "Party / note"),
            *money(("deposit", "Money in"), ("withdrawal", "Money out"), ("balance", "Balance"))]
    return result(f"Account statement — {acc.name}", [section(cols, rows, total=t)],
                  summary=[stat("Opening", st["opening"]), stat("In", t["deposit"]), stat("Out", t["withdrawal"]),
                           stat("Closing", st["closing"])])


def discount_report(r: RCtx):
    rows = []
    for v in vouchers(r, [VoucherType.SALE, VoucherType.PURCHASE], r.date_from, r.date_to):
        if not v.discount:
            continue
        rows.append(dict(_link=link_doc(v.id), date=v.date, number=v.number,
                         type="Given (sale)" if v.type == VoucherType.SALE else "Received (purchase)",
                         party=v.party_name, gross=v.sub_total, discount=v.discount,
                         pct=pct(v.discount, v.sub_total)))
    given = sum((x["discount"] for x in rows if x["type"].startswith("Given")), ZERO)
    received = sum((x["discount"] for x in rows if x["type"].startswith("Received")), ZERO)
    cols = [col("date", "Date", "date"), col("number", "Bill no."), col("type", "Type"), col("party", "Party"),
            *money(("gross", "Gross amount"), ("discount", "Discount")), col("pct", "Discount %", "pct")]
    return result("Discount report", [section(cols, rows)],
                  summary=[stat("Discount given", given), stat("Discount received", received)])


# ---------------------------------------------------------------- TDS / TCS
def _pan(p: Party | None) -> str:
    return (p.pan or (p.gstin[2:12] if p.gstin else "")) if p else ""


def form_27eq(r: RCtx):
    """TCS collected on sales — data for the quarterly TCS return (Form 27EQ)."""
    rows = []
    parties = {p.id: p for p in r.db.scalars(select(Party).where(Party.business_id == r.bid))}
    for v in vouchers(r, [VoucherType.SALE, VoucherType.SALE_RETURN], r.date_from, r.date_to):
        if not v.tcs_amount:
            continue
        s = -1 if v.type == VoucherType.SALE_RETURN else 1
        p = parties.get(v.party_id)
        rows.append(dict(_link=link_doc(v.id), date=v.date, number=v.number, party=v.party_name, pan=_pan(p),
                         value=s * (v.grand_total - v.tcs_amount - v.round_off), rate=v.tcs_rate,
                         tcs=s * v.tcs_amount))
    cols = [col("date", "Date", "date"), col("number", "Invoice"), col("party", "Collectee"), col("pan", "PAN"),
            col("value", "Amount received/debited", "money"), col("rate", "TCS rate", "pct"),
            col("tcs", "TCS collected", "money")]
    t = totals(rows, ["value", "tcs"])
    return result("Form No. 27EQ (TCS collected)", [section(cols, rows, total=t)],
                  subtitle="Choose the quarter as the period.", summary=[stat("TCS collected", t["tcs"])])


def tcs_receivable(r: RCtx):
    rows = []
    for v in vouchers(r, [VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN, VoucherType.EXPENSE],
                      r.date_from, r.date_to):
        if not v.tcs_amount:
            continue
        s = -1 if v.type == VoucherType.PURCHASE_RETURN else 1
        rows.append(dict(_link=link_doc(v.id), date=v.date, number=v.supplier_invoice_no or v.number,
                         party=v.party_name, gstin=v.party_gstin or "", rate=v.tcs_rate, tcs=s * v.tcs_amount))
    cols = [col("date", "Date", "date"), col("number", "Bill no."), col("party", "Supplier"), col("gstin", "GSTIN"),
            col("rate", "TCS rate", "pct"), col("tcs", "TCS paid", "money")]
    t = totals(rows, ["tcs"])
    return result("TCS receivable", [section(cols, rows, total=t, note="TCS charged by suppliers — claimable against your income tax.")],
                  summary=[stat("TCS receivable", t["tcs"])])


def _tds(r: RCtx, ptype: PaymentType, title: str, note: str):
    rows = []
    for p in r.db.scalars(select(Payment).options(selectinload(Payment.party)).where(
            Payment.business_id == r.bid, Payment.type == ptype, Payment.tds_amount > 0,
            Payment.date >= r.date_from, Payment.date <= r.date_to).order_by(Payment.date)):
        if p.cheque_status == "BOUNCED":
            continue
        rows.append(dict(date=p.date, number=p.number, party=p.party.name if p.party else "", pan=_pan(p.party),
                         gross=p.amount + p.tds_amount, tds=p.tds_amount, net=p.amount))
    cols = [col("date", "Date", "date"), col("number", "Payment"), col("party", "Party"), col("pan", "PAN"),
            *money(("gross", "Gross amount"), ("tds", "TDS"), ("net", "Net paid/received"))]
    t = totals(rows, ["gross", "tds", "net"])
    return result(title, [section(cols, rows, total=t, note=note)], summary=[stat("TDS", t["tds"])])


def tds_payable(r: RCtx):
    return _tds(r, PaymentType.OUT, "TDS payable", "TDS you deducted while paying suppliers — deposit it and file Form 26Q.")


def tds_receivable(r: RCtx):
    return _tds(r, PaymentType.IN, "TDS receivable", "TDS your customers deducted — verify in Form 26AS and claim in your ITR.")


def tax_payments(r: RCtx):
    rows = [dict(date=t.date, type=t.type.value, period=t.period or "", reference=t.reference or "", amount=t.amount)
            for t in r.db.scalars(select(TaxPayment).where(TaxPayment.business_id == r.bid,
                                                           TaxPayment.date >= r.date_from,
                                                           TaxPayment.date <= r.date_to).order_by(TaxPayment.date))]
    cols = [col("date", "Date", "date"), col("type", "Tax"), col("period", "Period"), col("reference", "Challan / CIN"),
            col("amount", "Amount", "money")]
    return result("Tax payments (challans)", [section(cols, rows, total=totals(rows, ["amount"]))])


# ---------------------------------------------------------------- expenses
def _expenses(r: RCtx):
    docs = vouchers(r, [VoucherType.EXPENSE], r.date_from, r.date_to, party_id=r.party_id)
    if r.category_id:
        docs = [v for v in docs if v.expense_category_id == r.category_id]
    return docs


def expense_transactions(r: RCtx):
    cats = {c.id: c for c in r.db.scalars(select(ExpenseCategory).where(ExpenseCategory.business_id == r.bid))}
    rows = []
    for v in _expenses(r):
        o_paid = sum((a.amount for a in v.allocations), ZERO)
        rows.append(dict(_link=link_doc(v.id), date=v.date, number=v.number,
                         category=cats[v.expense_category_id].name if v.expense_category_id in cats else "",
                         party=v.party_name, taxable=v.taxable, tax=v.cgst + v.sgst + v.igst + v.cess,
                         total=v.grand_total, paid=o_paid, balance=v.grand_total - o_paid))
    cols = [col("date", "Date", "date"), col("number", "Number"), col("category", "Category"), col("party", "Paid to"),
            *money(("taxable", "Amount"), ("tax", "GST"), ("total", "Total"), ("paid", "Paid"), ("balance", "Balance"))]
    t = totals(rows, ["taxable", "tax", "total", "paid", "balance"])
    return result("Expense transaction report", [section(cols, rows, total=t)],
                  summary=[stat("Total expenses", t["total"]), stat("GST on expenses", t["tax"])])


def expense_category_report(r: RCtx):
    cats = {c.id: c for c in r.db.scalars(select(ExpenseCategory).where(ExpenseCategory.business_id == r.bid))}
    agg: dict = defaultdict(lambda: dict(count=0, taxable=ZERO, tax=ZERO, total=ZERO))
    for v in _expenses(r):
        a = agg[v.expense_category_id]
        a["count"] += 1
        a["taxable"] += v.taxable
        a["tax"] += v.cgst + v.sgst + v.igst + v.cess
        a["total"] += v.grand_total
    grand = sum((a["total"] for a in agg.values()), ZERO)
    rows = [dict(category=cats[k].name if k in cats else "Uncategorised",
                 kind=cats[k].kind.value.title() if k in cats else "", **a, share=pct(a["total"], grand))
            for k, a in sorted(agg.items(), key=lambda x: -x[1]["total"])]
    cols = [col("category", "Category"), col("kind", "Direct / indirect"), col("count", "Entries", "int"),
            *money(("taxable", "Amount"), ("tax", "GST"), ("total", "Total")), col("share", "Share", "pct")]
    return result("Expense category report", [section(cols, rows, total=totals(rows, ["taxable", "tax", "total"]))])


def expense_item_report(r: RCtx):
    names = {i.id: i.name for i in r.db.scalars(select(ExpenseItem).where(ExpenseItem.business_id == r.bid))}
    agg: dict = defaultdict(lambda: dict(qty=ZERO, amount=ZERO, tax=ZERO, total=ZERO))
    for v in _expenses(r):
        for l in v.lines:
            a = agg[names.get(l.expense_item_id, l.name)]
            a["qty"] += l.qty
            a["amount"] += l.taxable
            a["tax"] += l.cgst + l.sgst + l.igst + l.cess
            a["total"] += l.total
    rows = [dict(item=k, **v) for k, v in sorted(agg.items(), key=lambda x: -x[1]["total"])]
    cols = [col("item", "Expense item"), col("qty", "Qty", "qty"),
            *money(("amount", "Amount"), ("tax", "GST"), ("total", "Total"))]
    return result("Expense item report", [section(cols, rows, total=totals(rows, ["amount", "tax", "total"]))])


# ---------------------------------------------------------------- orders / challans / estimates
def _orders(r: RCtx, vtype: VoucherType, title: str):
    rows = []
    for v in vouchers(r, [vtype], r.date_from, r.date_to, include_cancelled=True, party_id=r.party_id):
        status = "Cancelled" if v.cancelled else "Converted" if v.converted_to_id else "Open"
        if not v.cancelled and not v.converted_to_id and v.due_date and v.due_date < r.as_of:
            status = "Overdue"
        rows.append(dict(_link=link_doc(v.id), date=v.date, number=v.number, party=v.party_name,
                         due=v.due_date, items=len(v.lines), total=v.grand_total, status=status,
                         **({"_style": "sub"} if v.cancelled else {})))
    open_rows = [x for x in rows if x["status"] in ("Open", "Overdue")]
    cols = [col("date", "Date", "date"), col("number", "Number"), col("party", "Party"),
            col("due", "Due / delivery date", "date"), col("items", "Lines", "int"), col("total", "Amount", "money"),
            col("status", "Status")]
    return result(title, [section(cols, rows)],
                  summary=[stat("Total", len(rows), "int"), stat("Open", len(open_rows), "int"),
                           stat("Open value", sum((x["total"] for x in open_rows), ZERO))])


def sale_orders(r: RCtx):
    return _orders(r, VoucherType.SALE_ORDER, "Sale order report")


def purchase_orders(r: RCtx):
    return _orders(r, VoucherType.PURCHASE_ORDER, "Purchase order report")


def delivery_challans(r: RCtx):
    return _orders(r, VoucherType.DELIVERY_CHALLAN, "Delivery challan report")


def estimates(r: RCtx):
    return _orders(r, VoucherType.ESTIMATE, "Estimate / quotation report")


def pending_order_items(r: RCtx):
    agg: dict = defaultdict(lambda: dict(so_qty=ZERO, so_amt=ZERO, po_qty=ZERO, po_amt=ZERO))
    for v in vouchers(r, [VoucherType.SALE_ORDER, VoucherType.PURCHASE_ORDER], date_to=r.as_of):
        if v.converted_to_id:
            continue
        key = "so" if v.type == VoucherType.SALE_ORDER else "po"
        for l in v.lines:
            agg[(l.name, l.unit or "")][f"{key}_qty"] += l.qty
            agg[(l.name, l.unit or "")][f"{key}_amt"] += l.taxable
    rows = [dict(item=k[0], unit=k[1], **v) for k, v in sorted(agg.items())]
    cols = [col("item", "Item"), col("unit", "Unit"), col("so_qty", "To deliver (sale orders)", "qty"),
            col("so_amt", "Value", "money"), col("po_qty", "To receive (purchase orders)", "qty"),
            col("po_amt", "Value", "money")]
    return result("Pending order items", [section(cols, rows)])


# ---------------------------------------------------------------- loans
def loan_statement(r: RCtx):
    from ..routers.loans import statement as loan_stmt

    loan = r.db.get(Loan, r.loan_id) if r.loan_id else None
    if not loan or loan.business_id != r.bid:
        raise HTTPException(400, "Select a loan")
    st = loan_stmt(loan, r.date_from, r.date_to)
    rows = [dict(date=r.date_from, type="Opening balance", received=None, principal=None, interest=None,
                 paid=None, balance=st["opening"], _style="sub")]
    rows += [dict(date=e["date"], type=e["type"].title(), received=e["received"], principal=e["principal"]
                  if e["type"] == "EMI" else None, interest=e["interest"], paid=e["paid"], balance=e["balance"])
             for e in st["entries"]]
    cols = [col("date", "Date", "date"), col("type", "Type"),
            *money(("received", "Loan received"), ("principal", "Principal repaid"), ("interest", "Interest / charges"),
                   ("paid", "Total paid"), ("balance", "Outstanding"))]
    t = totals(rows[1:], ["received", "principal", "interest", "paid"])
    t["balance"] = st["closing"]
    return result(f"Loan statement — {loan.name}", [section(cols, rows, total=t)],
                  summary=[stat("Outstanding", st["closing"]), stat("Interest paid", t["interest"])])


def loan_summary(r: RCtx):
    from ..routers.loans import outstanding

    rows = []
    for l in r.db.scalars(select(Loan).options(selectinload(Loan.txns)).where(Loan.business_id == r.bid)):
        interest = sum((t.interest for t in l.txns if r.date_from <= t.date <= r.date_to), ZERO)
        rows.append(dict(name=l.name, lender=l.lender or "", rate=l.interest_rate, outstanding=outstanding(l, r.as_of),
                         interest=interest))
    cols = [col("name", "Loan"), col("lender", "Lender"), col("rate", "Interest rate", "pct"),
            *money(("outstanding", "Outstanding"), ("interest", "Interest paid in period"))]
    return result("Loan accounts", [section(cols, rows, total=totals(rows, ["outstanding", "interest"]))])
