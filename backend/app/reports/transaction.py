import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select

from ..gst.constants import ItemType, PaymentType, VoucherType, document_title
from ..gst.states import state_label
from ..models import Item, Payment
from ..services.accounts import account_balances, movements
from ..services.vouchers import to_out
from .accounting import EPOCH, avg_costs, balance_sheet, profit_and_loss
from .base import (
    ZERO,
    RCtx,
    col,
    link_doc,
    money,
    pct,
    result,
    section,
    stat,
    totals,
    vouchers,
)

LABEL = {t: document_title(t, True) for t in VoucherType}
LABEL[VoucherType.SALE] = "Sale"


def _register(r: RCtx, types, title):
    rows = []
    for v in vouchers(r, types, r.date_from, r.date_to, include_cancelled=True, party_id=r.party_id):
        o = to_out(v)
        neg = v.type in (VoucherType.SALE_RETURN, VoucherType.PURCHASE_RETURN)
        s = -1 if neg else 1
        rows.append(dict(
            _link=link_doc(v.id), date=v.date, type=LABEL[v.type], number=v.number, party=v.party_name,
            gstin=v.party_gstin or "", pos=state_label(v.place_of_supply), ref=v.supplier_invoice_no or "",
            taxable=s * v.taxable, cgst=s * v.cgst, sgst=s * v.sgst, igst=s * v.igst, cess=s * v.cess,
            total=s * v.grand_total, paid=o.paid, balance=o.balance, status=o.status,
            **({"_style": "sub"} if v.cancelled else {}),
        ))
    keys = ["taxable", "cgst", "sgst", "igst", "cess", "total", "paid", "balance"]
    cols = [col("date", "Date", "date"), col("type", "Type"), col("number", "Number"), col("party", "Party"),
            col("gstin", "GSTIN")]
    if VoucherType.PURCHASE in types:
        cols.append(col("ref", "Supplier bill"))
    cols += money(("taxable", "Taxable"), ("cgst", "CGST"), ("sgst", "SGST"), ("igst", "IGST"), ("cess", "Cess"),
                  ("total", "Total"), ("paid", "Paid"), ("balance", "Balance")) + [col("status", "Status")]
    t = totals(rows, keys)
    return result(title, [section(cols, rows, total=t, note="Returns are shown as negative; cancelled documents are greyed and excluded from totals.")],
                  summary=[stat("Net total", t["total"]), stat("Taxable", t["taxable"]), stat("Outstanding", t["balance"])])


def sale_register(r: RCtx):
    return _register(r, [VoucherType.SALE, VoucherType.SALE_RETURN], "Sale report")


def purchase_register(r: RCtx):
    return _register(r, [VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN], "Purchase report")


def day_book(r: RCtx):
    rows = []
    for v in vouchers(r, list(VoucherType), r.date_from, r.date_to):
        rows.append(dict(_link=link_doc(v.id), date=v.date, type=LABEL[v.type], number=v.number,
                         party=v.party_name, amount=v.grand_total, money_in=ZERO, money_out=ZERO, sort=v.created_at))
    for m in movements(r.db, r.bid, r.date_from, r.date_to):
        if m["kind"].startswith("Transfer"):
            continue
        rows.append(dict(date=m["date"], type=m["kind"], number=m["number"], party=m["party"] or "",
                         amount=abs(m["amount"]), money_in=max(m["amount"], ZERO), money_out=max(-m["amount"], ZERO),
                         sort=m["created"]))
    rows.sort(key=lambda x: (x["date"], x["sort"]))
    for x in rows:
        x.pop("sort")
    cols = [col("date", "Date", "date"), col("type", "Type"), col("number", "Number"), col("party", "Party"),
            *money(("amount", "Amount"), ("money_in", "Money in"), ("money_out", "Money out"))]
    t = totals(rows, ["money_in", "money_out"])
    return result("Day book", [section(cols, rows, total=t)],
                  summary=[stat("Money in", t["money_in"]), stat("Money out", t["money_out"]),
                           stat("Net", t["money_in"] - t["money_out"])])


def _line_cost(line, costs, items) -> Decimal:
    it = items.get(line.item_id)
    if not it:
        return ZERO
    if it.type == ItemType.SERVICE:
        return (line.qty * (it.purchase_price or ZERO)).quantize(Decimal("0.01"))
    return (line.qty * costs.get(it.id, ZERO)).quantize(Decimal("0.01"))


def bill_wise_profit(r: RCtx):
    costs = avg_costs(r.db, r.bid, r.date_to)
    items = {i.id: i for i in r.db.scalars(select(Item).where(Item.business_id == r.bid))}
    rows = []
    for v in vouchers(r, [VoucherType.SALE, VoucherType.SALE_RETURN], r.date_from, r.date_to, party_id=r.party_id):
        s = -1 if v.type == VoucherType.SALE_RETURN else 1
        cost = sum((_line_cost(l, costs, items) for l in v.lines), ZERO)
        profit = v.taxable - cost
        rows.append(dict(_link=link_doc(v.id), date=v.date, number=v.number, type=LABEL[v.type], party=v.party_name,
                         sale=s * v.taxable, cost=s * cost, profit=s * profit, margin=pct(profit, v.taxable)))
    t = totals(rows, ["sale", "cost", "profit"])
    t["margin"] = pct(t["profit"], t["sale"])
    cols = [col("date", "Date", "date"), col("number", "Bill no."), col("type", "Type"), col("party", "Party"),
            *money(("sale", "Sale value (excl. tax)"), ("cost", "Cost of goods"), ("profit", "Profit")),
            col("margin", "Margin", "pct")]
    return result("Bill wise profit", [section(cols, rows, total=t, note="Cost uses weighted-average purchase cost; services use their purchase price.")],
                  summary=[stat("Sales", t["sale"]), stat("Profit", t["profit"]), stat("Margin", t["margin"], "pct")])


def _stmt_row(label, amount=None, style=None, indent=False):
    row = {"label": ("    " if indent else "") + label, "amount": amount}
    if style:
        row["_style"] = style
    return row


def profit_loss(r: RCtx):
    p = profit_and_loss(r.db, r.biz, r.date_from, r.date_to)
    rows = [
        _stmt_row("Income", style="head"),
        _stmt_row("Sales", p["sales"], indent=True),
        _stmt_row("Less: Sale returns (credit notes)", -p["sale_returns"], indent=True),
        _stmt_row("Net sales", p["net_sales"], "bold"),
        _stmt_row("Cost of goods sold", style="head"),
        _stmt_row("Opening stock", p["opening_stock"], indent=True),
        _stmt_row("Purchases", p["purchases"], indent=True),
        _stmt_row("Less: Purchase returns (debit notes)", -p["purchase_returns"], indent=True),
        *[_stmt_row(f"Direct expense: {k}", v, indent=True) for k, v in sorted(p["direct"].items())],
        _stmt_row("Less: Closing stock", -p["closing_stock"], indent=True),
        _stmt_row("Cost of goods sold", p["cogs"], "bold"),
        _stmt_row("Gross profit", p["gross_profit"], "bold"),
        _stmt_row("Indirect expenses", style="head"),
        *[_stmt_row(k, v, indent=True) for k, v in sorted(p["indirect"].items())],
        _stmt_row("Loan interest & charges", p["interest"], indent=True),
        _stmt_row("Total indirect expenses", p["indirect_total"] + p["interest"], "bold"),
        _stmt_row("Other income: round off (net)", p["round_off"]),
        _stmt_row("Net profit" if p["net_profit"] >= 0 else "Net loss", p["net_profit"], "bold"),
    ]
    cols = [col("label", "Particulars"), col("amount", "Amount", "money")]
    return result("Profit & loss", [section(cols, rows, note="Stock is valued at weighted-average cost. Amounts exclude GST where input credit is available.")],
                  summary=[stat("Net sales", p["net_sales"]), stat("Gross profit", p["gross_profit"]),
                           stat("Net profit", p["net_profit"])])


def _aging(r: RCtx, types, title):
    buckets = ["not_due", "d30", "d60", "d90", "d90p"]
    labels = ["Not due", "1–30 days", "31–60 days", "61–90 days", "90+ days"]
    by_party: dict = defaultdict(lambda: {b: ZERO for b in buckets})
    names, bills = {}, []
    for v in vouchers(r, types, date_to=r.as_of):
        if not v.party_id:
            continue
        due = v.grand_total - sum((a.amount for a in v.allocations), ZERO)
        if due <= 0:
            continue
        ref = v.due_date or v.date
        days = (r.as_of - ref).days
        b = "not_due" if days <= 0 else "d30" if days <= 30 else "d60" if days <= 60 else "d90" if days <= 90 else "d90p"
        by_party[v.party_id][b] += due
        names[v.party_id] = v.party_name
        bills.append(dict(_link=link_doc(v.id), date=v.date, number=v.number, party=v.party_name, due_date=v.due_date,
                          days=max(days, 0), amount=v.grand_total, due=due))
    rows = [dict(_link=f"/parties/{pid}", party=names[pid], **vals, total=sum(vals.values(), ZERO))
            for pid, vals in sorted(by_party.items(), key=lambda x: names[x[0]])]
    keys = buckets + ["total"]
    cols = [col("party", "Party"), *money(*zip(buckets, labels)), col("total", "Total", "money")]
    bill_cols = [col("date", "Bill date", "date"), col("number", "Bill no."), col("party", "Party"),
                 col("due_date", "Due date", "date"), col("days", "Days overdue", "int"),
                 *money(("amount", "Bill amount"), ("due", "Outstanding"))]
    bills.sort(key=lambda b: -b["days"])
    t = totals(rows, keys)
    return result(title, [section(cols, rows, "By party", total=t),
                          section(bill_cols, bills, "Open bills", total=totals(bills, ["amount", "due"]))],
                  subtitle=f"As of {r.as_of:%d/%m/%Y}; age counted from due date (or bill date)",
                  summary=[stat("Outstanding", t["total"]), stat("Overdue 90+ days", t["d90p"])])


def sale_aging(r: RCtx):
    return _aging(r, [VoucherType.SALE], "Sale aging (receivables)")


def purchase_aging(r: RCtx):
    return _aging(r, [VoucherType.PURCHASE, VoucherType.EXPENSE], "Purchase aging (payables)")


def cash_flow(r: RCtx):
    opening = sum(account_balances(r.db, r.bid, r.date_from - dt.timedelta(days=1)).values(), ZERO)
    flows: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for m in movements(r.db, r.bid, r.date_from, r.date_to):
        for name, amt in m["flows"]:
            flows[name] += amt
    groups = {
        "Operating activities": ["Receipts from customers", "Payments to suppliers", "Expenses paid",
                                 "GST deposited", "TDS deposited", "TCS deposited", "Interest paid"],
        "Financing activities": ["Capital introduced", "Drawings", "Loans received", "Loan principal repaid"],
    }
    rows = [_stmt_row("Opening cash & bank balance", opening, "bold")]
    net = ZERO
    for g, names in groups.items():
        rows.append(_stmt_row(g, style="head"))
        sub = ZERO
        for n in names:
            if flows.get(n):
                rows.append(_stmt_row(n, flows[n], indent=True))
                sub += flows[n]
        rows.append(_stmt_row(f"Net cash from {g.lower()}", sub, "bold"))
        net += sub
    rows.append(_stmt_row("Net change in cash & bank", net, "bold"))
    rows.append(_stmt_row("Closing cash & bank balance", opening + net, "bold"))
    return result("Cash flow", [section([col("label", "Particulars"), col("amount", "Amount", "money")], rows,
                                        note="Transfers between your own accounts are excluded. Cheques count when cleared.")],
                  summary=[stat("Opening", opening), stat("Net change", net), stat("Closing", opening + net)])


def balance_sheet_report(r: RCtx):
    bs = balance_sheet(r.db, r.biz, r.as_of)
    c = bs["capital"]
    liab = [_stmt_row("Capital", style="head"),
            _stmt_row("Opening capital", c["opening"], indent=True),
            _stmt_row("Add: Capital introduced", c["introduced"], indent=True),
            _stmt_row("Less: Drawings", -c["drawings"], indent=True),
            _stmt_row("Add: Net profit (cumulative)", c["profit"], indent=True),
            _stmt_row("Capital account", c["closing"], "bold"),
            _stmt_row("Liabilities", style="head"),
            *[_stmt_row(n, v, indent=True) for n, v in bs["liabilities"]],
            _stmt_row("Total liabilities & capital", bs["total_liabilities"], "bold")]
    assets = [_stmt_row("Assets", style="head"),
              *[_stmt_row(n, v, indent=True) for n, v in bs["assets"]],
              _stmt_row("Total assets", bs["total_assets"], "bold")]
    if bs["difference"]:
        assets.append(_stmt_row("Difference (please report)", bs["difference"], "bold"))
    cols = [col("label", "Particulars"), col("amount", "Amount", "money")]
    return result("Balance sheet", [section(cols, liab, "Capital & liabilities"), section(cols, assets, "Assets")],
                  subtitle=f"As of {r.as_of:%d/%m/%Y}",
                  summary=[stat("Total assets", bs["total_assets"]), stat("Capital", c["closing"]),
                           stat("Net profit to date", c["profit"])])


def capital_account(r: RCtx):
    from ..models import CapitalEntry
    start = balance_sheet(r.db, r.biz, r.date_from - dt.timedelta(days=1))["capital"]["closing"] if r.date_from > EPOCH else ZERO
    entries = r.db.scalars(select(CapitalEntry).where(CapitalEntry.business_id == r.bid,
                                                      CapitalEntry.date >= r.date_from,
                                                      CapitalEntry.date <= r.date_to).order_by(CapitalEntry.date)).all()
    profit = profit_and_loss(r.db, r.biz, r.date_from, r.date_to)["net_profit"]
    end = balance_sheet(r.db, r.biz, r.date_to)["capital"]["closing"]
    rows = [_stmt_row("Opening capital", start, "bold")]
    for e in entries:
        rows.append({"label": f"    {e.date:%d/%m/%Y} {'Capital introduced' if e.type.value == 'INTRODUCED' else 'Drawings'}"
                              + (f" — {e.note}" if e.note else ""),
                     "amount": e.amount if e.type.value == "INTRODUCED" else -e.amount})
    moved = sum((x["amount"] for x in rows[1:]), ZERO)
    rows += [_stmt_row("Net profit for the period", profit),
             _stmt_row("Opening balances entered during the period", end - start - profit - moved),
             _stmt_row("Closing capital", end, "bold")]
    rows = [x for x in rows if x["amount"] or x.get("_style")]
    return result("Capital account", [section([col("label", "Particulars"), col("amount", "Amount", "money")], rows)],
                  summary=[stat("Opening", start), stat("Net profit", profit), stat("Closing", end)])


def payment_register(r: RCtx):
    rows = []
    for p in r.db.scalars(select(Payment).where(Payment.business_id == r.bid, Payment.date >= r.date_from,
                                                Payment.date <= r.date_to).order_by(Payment.date)):
        if r.party_id and p.party_id != r.party_id:
            continue
        rows.append(dict(date=p.date, number=p.number, type="Payment In" if p.type == PaymentType.IN else "Payment Out",
                         party=p.party.name if p.party else "", mode=p.mode.value.title(), account=p.account.name,
                         amount_in=p.amount if p.type == PaymentType.IN else ZERO,
                         amount_out=p.amount if p.type == PaymentType.OUT else ZERO, tds=p.tds_amount,
                         cheque=p.cheque_status or ""))
    cols = [col("date", "Date", "date"), col("number", "Number"), col("type", "Type"), col("party", "Party"),
            col("mode", "Mode"), col("account", "Account"),
            *money(("amount_in", "Received"), ("amount_out", "Paid"), ("tds", "TDS")), col("cheque", "Cheque")]
    t = totals(rows, ["amount_in", "amount_out", "tds"])
    return result("Payment report", [section(cols, rows, total=t)],
                  summary=[stat("Received", t["amount_in"]), stat("Paid", t["amount_out"])])

