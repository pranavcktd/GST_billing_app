from collections import defaultdict


from fastapi import HTTPException
from sqlalchemy import select

from ..gst.constants import VoucherType
from ..gst.states import state_label
from ..models import Item, Party
from ..services.ledger import party_balances, party_ledger
from .accounting import avg_costs
from .base import ZERO, RCtx, col, link_doc, money, pct, result, section, stat, totals, vouchers
from .transaction import _line_cost

SALE_TYPES = [VoucherType.SALE, VoucherType.SALE_RETURN]
PURCHASE_TYPES = [VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN]


def _party(r: RCtx) -> Party:
    p = r.db.get(Party, r.party_id) if r.party_id else None
    if not p or p.business_id != r.bid:
        raise HTTPException(400, "Select a party")
    return p


def _signed(v) -> int:
    return -1 if v.type in (VoucherType.SALE_RETURN, VoucherType.PURCHASE_RETURN) else 1


def party_statement(r: RCtx):
    p = _party(r)
    led = party_ledger(r.db, p, r.date_from, r.date_to)
    rows = [dict(date=r.date_from, kind="Opening balance", number="", debit=None, credit=None,
                 balance=led["opening"], _style="sub")]
    for e in led["entries"]:
        rows.append(dict(_link=link_doc(e["ref_id"]) if e["ref_type"] == "voucher" else None, date=e["date"],
                         kind=e["kind"], number=e["number"], debit=e["debit"], credit=e["credit"], balance=e["balance"]))
    t = totals(rows[1:], ["debit", "credit"])
    t["balance"] = led["closing"]
    cols = [col("date", "Date", "date"), col("kind", "Type"), col("number", "Number"),
            *money(("debit", "Debit (+)"), ("credit", "Credit (−)"), ("balance", "Balance"))]
    return result(f"Party statement — {p.name}", [section(cols, rows, total=t,
                  note="Positive balance = receivable from party, negative = payable to party.")],
                  subtitle=" · ".join(x for x in (p.gstin, p.phone, state_label(p.state_code)) if x),
                  summary=[stat("Opening", led["opening"]), stat("Debits", t["debit"]), stat("Credits", t["credit"]),
                           stat("Closing", led["closing"])])


def party_ledger_summary(r: RCtx):
    rows = []
    for p in r.db.scalars(select(Party).where(Party.business_id == r.bid).order_by(Party.name)):
        led = party_ledger(r.db, p, r.date_from, r.date_to)
        debit = sum((e["debit"] for e in led["entries"]), ZERO)
        credit = sum((e["credit"] for e in led["entries"]), ZERO)
        if not (led["opening"] or debit or credit):
            continue
        rows.append(dict(_link=f"/parties/{p.id}", party=p.name, opening=led["opening"], debit=debit, credit=credit,
                         closing=led["closing"]))
    cols = [col("party", "Party"), *money(("opening", "Opening"), ("debit", "Debit"), ("credit", "Credit"),
                                          ("closing", "Closing"))]
    return result("Party ledger (all parties)", [section(cols, rows, total=totals(rows, ["opening", "debit", "credit", "closing"]))])


def all_parties(r: RCtx):
    bal = party_balances(r.db, r.bid)
    rows = []
    for p in r.db.scalars(select(Party).where(Party.business_id == r.bid).order_by(Party.name)):
        b = bal.get(p.id, ZERO)
        rows.append(dict(_link=f"/parties/{p.id}", name=p.name, type=p.type.value.title(), gstin=p.gstin or "",
                         phone=p.phone or "", email=p.email or "", state=state_label(p.state_code),
                         receivable=b if b > 0 else ZERO, payable=-b if b < 0 else ZERO,
                         credit_limit=p.credit_limit, status="Active" if p.is_active else "Inactive"))
    cols = [col("name", "Name"), col("type", "Type"), col("gstin", "GSTIN"), col("phone", "Phone"),
            col("email", "Email"), col("state", "State"),
            *money(("receivable", "Receivable"), ("payable", "Payable"), ("credit_limit", "Credit limit")),
            col("status", "Status")]
    t = totals(rows, ["receivable", "payable"])
    return result("All parties", [section(cols, rows, total=t)],
                  summary=[stat("Parties", len(rows), "int"), stat("To collect", t["receivable"]), stat("To pay", t["payable"])])


def party_pnl(r: RCtx):
    costs = avg_costs(r.db, r.bid, r.date_to)
    items = {i.id: i for i in r.db.scalars(select(Item).where(Item.business_id == r.bid))}
    agg: dict = defaultdict(lambda: dict(sale=ZERO, cost=ZERO))
    names = {}
    for v in vouchers(r, SALE_TYPES, r.date_from, r.date_to):
        key = v.party_id or "_cash"
        names[key] = v.party_name if v.party_id else "Cash / walk-in"
        s = _signed(v)
        agg[key]["sale"] += s * v.taxable
        agg[key]["cost"] += s * sum((_line_cost(l, costs, items) for l in v.lines), ZERO)
    rows = [dict(_link=f"/parties/{k}" if k != "_cash" else None, party=names[k], sale=a["sale"], cost=a["cost"],
                 profit=a["sale"] - a["cost"], margin=pct(a["sale"] - a["cost"], a["sale"]))
            for k, a in sorted(agg.items(), key=lambda x: -(x[1]["sale"] - x[1]["cost"]))]
    t = totals(rows, ["sale", "cost", "profit"])
    t["margin"] = pct(t["profit"], t["sale"])
    cols = [col("party", "Party"), *money(("sale", "Sales (excl. tax)"), ("cost", "Cost"), ("profit", "Profit")),
            col("margin", "Margin", "pct")]
    return result("Party wise profit & loss", [section(cols, rows, total=t)],
                  summary=[stat("Sales", t["sale"]), stat("Profit", t["profit"])])


def party_by_item(r: RCtx):
    p = _party(r)
    agg: dict = defaultdict(lambda: dict(sale_qty=ZERO, sale_amt=ZERO, pur_qty=ZERO, pur_amt=ZERO))
    for v in vouchers(r, SALE_TYPES + PURCHASE_TYPES, r.date_from, r.date_to, party_id=p.id):
        s = _signed(v)
        is_sale = v.type in SALE_TYPES
        for l in v.lines:
            a = agg[(l.name, l.unit or "")]
            a["sale_qty" if is_sale else "pur_qty"] += s * l.qty
            a["sale_amt" if is_sale else "pur_amt"] += s * l.taxable
    rows = [dict(item=k[0], unit=k[1], **v) for k, v in sorted(agg.items())]
    cols = [col("item", "Item"), col("unit", "Unit"), col("sale_qty", "Sale qty", "qty"),
            col("sale_amt", "Sale amount", "money"), col("pur_qty", "Purchase qty", "qty"),
            col("pur_amt", "Purchase amount", "money")]
    return result(f"Party report by item — {p.name}", [section(cols, rows, total=totals(rows, ["sale_amt", "pur_amt"]))])


def sale_purchase_by_party(r: RCtx):
    agg: dict = defaultdict(lambda: dict(sale=ZERO, purchase=ZERO))
    names = {}
    for v in vouchers(r, SALE_TYPES + PURCHASE_TYPES, r.date_from, r.date_to):
        key = v.party_id or ("_cash_sale" if v.type in SALE_TYPES else "_cash_purchase")
        names[key] = v.party_name if v.party_id else "Cash / walk-in"
        agg[key]["sale" if v.type in SALE_TYPES else "purchase"] += _signed(v) * v.grand_total
    rows = [dict(_link=f"/parties/{k}" if not k.startswith("_") else None, party=names[k], **a)
            for k, a in sorted(agg.items(), key=lambda x: names[x[0]])]
    cols = [col("party", "Party"), *money(("sale", "Sales (incl. tax)"), ("purchase", "Purchases (incl. tax)"))]
    t = totals(rows, ["sale", "purchase"])
    return result("Sale / purchase by party", [section(cols, rows, total=t)],
                  summary=[stat("Sales", t["sale"]), stat("Purchases", t["purchase"])])



