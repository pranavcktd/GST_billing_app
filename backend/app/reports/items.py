from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from ..gst.constants import ItemType, StockMoveType, VoucherType
from ..models import Item, StockMovement
from .accounting import avg_costs, stock_qty
from .base import ZERO, RCtx, col, link_doc, money, pct, result, section, stat, totals, vouchers
from .transaction import _line_cost

PAISE = Decimal("0.01")
SALE_TYPES = [VoucherType.SALE, VoucherType.SALE_RETURN]
PURCHASE_TYPES = [VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN]


def _items(r: RCtx, goods_only=True):
    q = select(Item).where(Item.business_id == r.bid).order_by(Item.name)
    if goods_only:
        q = q.where(Item.type == ItemType.GOODS)
    return r.db.scalars(q).all()


def _item(r: RCtx) -> Item:
    it = r.db.get(Item, r.item_id) if r.item_id else None
    if not it or it.business_id != r.bid:
        raise HTTPException(400, "Select an item")
    return it


def _sign(v) -> int:
    return -1 if v.type in (VoucherType.SALE_RETURN, VoucherType.PURCHASE_RETURN) else 1


def _moves(r: RCtx):
    """Per item: opening (before period) and period movement by type."""
    agg: dict = defaultdict(lambda: defaultdict(lambda: ZERO))
    for m in r.db.scalars(select(StockMovement).where(StockMovement.business_id == r.bid,
                                                      StockMovement.date <= r.date_to)):
        a = agg[m.item_id]
        if m.date < r.date_from:
            a["opening"] += m.qty
        else:
            a[m.type.value] += m.qty
    return agg


def stock_summary(r: RCtx):
    costs = avg_costs(r.db, r.bid, r.date_to)
    agg = _moves(r)
    rows = []
    for it in _items(r):
        a = agg[it.id]
        inward = sum((v for k, v in a.items() if k != "opening" and v > 0), ZERO)
        outward = -sum((v for k, v in a.items() if k != "opening" and v < 0), ZERO)
        closing = a["opening"] + inward - outward
        cost = costs.get(it.id, ZERO)
        rows.append(dict(_link=f"/items/{it.id}", item=it.name, code=it.code or "", category=it.category or "",
                         unit=it.unit, opening=a["opening"], inward=inward, outward=outward, closing=closing,
                         cost=cost.quantize(PAISE), value=(max(closing, ZERO) * cost).quantize(PAISE),
                         sale_value=(max(closing, ZERO) * it.sale_price).quantize(PAISE)))
    cols = [col("item", "Item"), col("code", "Code"), col("category", "Category"), col("unit", "Unit"),
            col("opening", "Opening", "qty"), col("inward", "In", "qty"), col("outward", "Out", "qty"),
            col("closing", "Closing", "qty"), col("cost", "Avg cost", "money"),
            *money(("value", "Stock value"), ("sale_value", "Value at sale price"))]
    t = totals(rows, ["value", "sale_value"])
    return result("Stock summary", [section(cols, rows, total=t)],
                  summary=[stat("Items", len(rows), "int"), stat("Stock value (cost)", t["value"]),
                           stat("Value at sale price", t["sale_value"])])


def stock_details(r: RCtx):
    agg = _moves(r)
    keys = ["opening", "OPENING", "PURCHASE", "SALE_RETURN", "SALE", "PURCHASE_RETURN", "ADJUSTMENT"]
    rows = []
    for it in _items(r):
        a = agg[it.id]
        row = dict(_link=f"/items/{it.id}", item=it.name, unit=it.unit, **{k: a[k] for k in keys})
        row["SALE"] = -row["SALE"]
        row["PURCHASE_RETURN"] = -row["PURCHASE_RETURN"]
        row["closing"] = sum((a[k] for k in keys), ZERO)
        rows.append(row)
    cols = [col("item", "Item"), col("unit", "Unit"), col("opening", "Opening", "qty"),
            col("OPENING", "Opening stock added", "qty"), col("PURCHASE", "Purchased", "qty"),
            col("SALE_RETURN", "Sale returns", "qty"), col("SALE", "Sold", "qty"),
            col("PURCHASE_RETURN", "Purchase returns", "qty"), col("ADJUSTMENT", "Adjustments (±)", "qty"),
            col("closing", "Closing", "qty")]
    return result("Stock details", [section(cols, rows)])


def low_stock(r: RCtx):
    qty = stock_qty(r.db, r.bid, r.as_of)
    rows = []
    for it in _items(r):
        q = qty.get(it.id, ZERO)
        if it.low_stock_level is not None and q <= it.low_stock_level:
            rows.append(dict(_link=f"/items/{it.id}", item=it.name, unit=it.unit, stock=q, level=it.low_stock_level,
                             short=it.low_stock_level - q,
                             status="Out of stock" if q <= 0 else "Low"))
    cols = [col("item", "Item"), col("unit", "Unit"), col("stock", "In stock", "qty"),
            col("level", "Minimum level", "qty"), col("short", "Short by", "qty"), col("status", "Status")]
    return result("Low stock summary", [section(cols, rows)], summary=[stat("Items low", len(rows), "int")])


def item_details(r: RCtx):
    it = _item(r)
    days: dict = defaultdict(lambda: dict(sale=ZERO, purchase=ZERO, returns_in=ZERO, returns_out=ZERO, adjust=ZERO))
    opening = ZERO
    for m in r.db.scalars(select(StockMovement).where(StockMovement.item_id == it.id,
                                                      StockMovement.date <= r.date_to).order_by(StockMovement.date)):
        if m.date < r.date_from:
            opening += m.qty
            continue
        d = days[m.date]
        key = {StockMoveType.SALE: "sale", StockMoveType.PURCHASE: "purchase", StockMoveType.OPENING: "purchase",
               StockMoveType.SALE_RETURN: "returns_in", StockMoveType.PURCHASE_RETURN: "returns_out"}.get(m.type, "adjust")
        d[key] += abs(m.qty) if key != "adjust" else m.qty
    rows, running = [], opening
    for day, d in sorted(days.items()):
        running += d["purchase"] + d["returns_in"] - d["sale"] - d["returns_out"] + d["adjust"]
        rows.append(dict(date=day, **d, closing=running))
    cols = [col("date", "Date", "date"), col("purchase", "Purchased", "qty"), col("sale", "Sold", "qty"),
            col("returns_in", "Sale returns", "qty"), col("returns_out", "Purchase returns", "qty"),
            col("adjust", "Adjustment", "qty"), col("closing", "Closing", "qty")]
    return result(f"Item details — {it.name}", [section(cols, rows)],
                  summary=[stat("Opening", opening, "qty"), stat("Closing", running, "qty")])


def item_by_party(r: RCtx):
    it = _item(r)
    agg: dict = defaultdict(lambda: dict(sale_qty=ZERO, sale_amt=ZERO, pur_qty=ZERO, pur_amt=ZERO))
    names = {}
    for v in vouchers(r, SALE_TYPES + PURCHASE_TYPES, r.date_from, r.date_to):
        for l in v.lines:
            if l.item_id != it.id:
                continue
            key = v.party_id or "_cash"
            names[key] = v.party_name if v.party_id else "Cash / walk-in"
            sale = v.type in SALE_TYPES
            agg[key]["sale_qty" if sale else "pur_qty"] += _sign(v) * l.qty
            agg[key]["sale_amt" if sale else "pur_amt"] += _sign(v) * l.taxable
    rows = [dict(_link=f"/parties/{k}" if k != "_cash" else None, party=names[k], **a) for k, a in agg.items()]
    cols = [col("party", "Party"), col("sale_qty", "Sale qty", "qty"), col("sale_amt", "Sale amount", "money"),
            col("pur_qty", "Purchase qty", "qty"), col("pur_amt", "Purchase amount", "money")]
    return result(f"Item report by party — {it.name}", [section(cols, rows, total=totals(rows, ["sale_amt", "pur_amt"]))])


def item_pnl(r: RCtx):
    costs = avg_costs(r.db, r.bid, r.date_to)
    items = {i.id: i for i in _items(r, goods_only=False)}
    agg: dict = defaultdict(lambda: dict(qty=ZERO, sale=ZERO, cost=ZERO))
    for v in vouchers(r, SALE_TYPES, r.date_from, r.date_to):
        s = _sign(v)
        for l in v.lines:
            a = agg[l.item_id or f"_{l.name}"]
            a["qty"] += s * l.qty
            a["sale"] += s * l.taxable
            a["cost"] += s * _line_cost(l, costs, items)
            a.setdefault("name", l.name)
    rows = [dict(_link=f"/items/{k}" if not k.startswith("_") else None,
                 item=items[k].name if k in items else a["name"], qty=a["qty"], sale=a["sale"], cost=a["cost"],
                 profit=a["sale"] - a["cost"], margin=pct(a["sale"] - a["cost"], a["sale"]))
            for k, a in agg.items()]
    rows.sort(key=lambda x: -x["profit"])
    t = totals(rows, ["sale", "cost", "profit"])
    t["margin"] = pct(t["profit"], t["sale"])
    cols = [col("item", "Item"), col("qty", "Qty sold", "qty"),
            *money(("sale", "Sales (excl. tax)"), ("cost", "Cost"), ("profit", "Profit")), col("margin", "Margin", "pct")]
    return result("Item wise profit & loss", [section(cols, rows, total=t)],
                  summary=[stat("Sales", t["sale"]), stat("Profit", t["profit"]), stat("Margin", t["margin"], "pct")])


def sale_purchase_by_category(r: RCtx):
    items = {i.id: i for i in _items(r, goods_only=False)}
    agg: dict = defaultdict(lambda: dict(sale_qty=ZERO, sale_amt=ZERO, pur_qty=ZERO, pur_amt=ZERO))
    for v in vouchers(r, SALE_TYPES + PURCHASE_TYPES, r.date_from, r.date_to):
        sale = v.type in SALE_TYPES
        for l in v.lines:
            cat = (items[l.item_id].category if l.item_id in items else None) or "Uncategorised"
            agg[cat]["sale_qty" if sale else "pur_qty"] += _sign(v) * l.qty
            agg[cat]["sale_amt" if sale else "pur_amt"] += _sign(v) * l.taxable
    rows = [dict(category=k, **v) for k, v in sorted(agg.items())]
    cols = [col("category", "Category"), col("sale_qty", "Sale qty", "qty"), col("sale_amt", "Sale amount", "money"),
            col("pur_qty", "Purchase qty", "qty"), col("pur_amt", "Purchase amount", "money")]
    return result("Sale / purchase by item category", [section(cols, rows, total=totals(rows, ["sale_amt", "pur_amt"]))])


def stock_by_category(r: RCtx):
    costs = avg_costs(r.db, r.bid, r.as_of)
    qty = stock_qty(r.db, r.bid, r.as_of)
    agg: dict = defaultdict(lambda: dict(items=0, qty=ZERO, value=ZERO))
    for it in _items(r):
        q = qty.get(it.id, ZERO)
        a = agg[it.category or "Uncategorised"]
        a["items"] += 1
        a["qty"] += q
        a["value"] += (max(q, ZERO) * costs.get(it.id, ZERO)).quantize(PAISE)
    rows = [dict(category=k, **v) for k, v in sorted(agg.items())]
    cols = [col("category", "Category"), col("items", "Items", "int"), col("qty", "Quantity", "qty"),
            col("value", "Stock value", "money")]
    return result("Stock summary by item category", [section(cols, rows, total=totals(rows, ["value"]))])


def batch_report(r: RCtx):
    agg: dict = defaultdict(lambda: dict(inward=ZERO, outward=ZERO, expiry=None, mfg=None))
    items = {i.id: i for i in _items(r)}
    for v in vouchers(r, SALE_TYPES + PURCHASE_TYPES, date_to=r.as_of):
        for l in v.lines:
            if not l.batch_no or l.item_id not in items:
                continue
            a = agg[(l.item_id, l.batch_no)]
            inward = v.type in (VoucherType.PURCHASE, VoucherType.SALE_RETURN)
            a["inward" if inward else "outward"] += l.qty
            a["expiry"] = a["expiry"] or l.expiry_date
            a["mfg"] = a["mfg"] or l.mfg_date
    rows = []
    for (iid, batch), a in sorted(agg.items(), key=lambda x: (items[x[0][0]].name, x[0][1])):
        bal = a["inward"] - a["outward"]
        expired = a["expiry"] is not None and a["expiry"] < r.as_of
        rows.append(dict(_link=f"/items/{iid}", item=items[iid].name, batch=batch, mfg=a["mfg"], expiry=a["expiry"],
                         inward=a["inward"], outward=a["outward"], balance=bal,
                         status="Expired" if expired and bal > 0 else ""))
    cols = [col("item", "Item"), col("batch", "Batch"), col("mfg", "Mfg date", "date"),
            col("expiry", "Expiry", "date"), col("inward", "In", "qty"), col("outward", "Out", "qty"),
            col("balance", "Balance", "qty"), col("status", "Status")]
    return result("Item batch report", [section(cols, rows, note="Batches come from the batch no. entered on bills.")])


def serial_report(r: RCtx):
    serials: dict = {}
    for v in vouchers(r, SALE_TYPES + PURCHASE_TYPES, date_to=r.as_of):
        for l in v.lines:
            for sn in [x.strip() for x in (l.serial_nos or "").split(",") if x.strip()]:
                s = serials.setdefault((l.name, sn), dict(item=l.name, serial=sn, purchased=None, pur_doc="",
                                                          sold=None, sale_doc="", party=""))
                if v.type in (VoucherType.PURCHASE, VoucherType.SALE_RETURN):
                    s["purchased"], s["pur_doc"] = v.date, v.number
                    if v.type == VoucherType.SALE_RETURN:
                        s["sold"], s["sale_doc"], s["party"] = None, "", ""
                else:
                    s["sold"], s["sale_doc"], s["party"] = v.date, v.number, v.party_name
    rows = [dict(**s, status="Sold" if s["sold"] else "In stock") for s in serials.values()]
    rows.sort(key=lambda x: (x["item"], x["serial"]))
    cols = [col("item", "Item"), col("serial", "Serial no."), col("purchased", "In on", "date"),
            col("pur_doc", "In doc"), col("sold", "Sold on", "date"), col("sale_doc", "Sale doc"),
            col("party", "Customer"), col("status", "Status")]
    return result("Item serial report", [section(cols, rows)],
                  summary=[stat("In stock", sum(1 for x in rows if x["status"] == "In stock"), "int"),
                           stat("Sold", sum(1 for x in rows if x["status"] == "Sold"), "int")])


def item_discount(r: RCtx):
    agg: dict = defaultdict(lambda: dict(qty=ZERO, gross=ZERO, discount=ZERO))
    for v in vouchers(r, [VoucherType.SALE], r.date_from, r.date_to):
        for l in v.lines:
            a = agg[l.name]
            a["qty"] += l.qty
            a["gross"] += l.amount
            a["discount"] += l.discount
    rows = [dict(item=k, **v, net=v["gross"] - v["discount"], pct=pct(v["discount"], v["gross"]))
            for k, v in sorted(agg.items()) if v["discount"]]
    cols = [col("item", "Item"), col("qty", "Qty", "qty"), *money(("gross", "Gross amount"), ("discount", "Discount"),
                                                                  ("net", "Net amount")), col("pct", "Avg discount", "pct")]
    return result("Item wise discount", [section(cols, rows, total=totals(rows, ["gross", "discount", "net"]))])



