"""GST returns and business reports, computed from stored documents."""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from ..gst.constants import ItemType, PaymentType, VoucherType
from ..gst.states import state_label
from ..models import Account, Business, ExpenseCategory, Item, Party, Payment, StockMovement, Voucher
from . import config_store
from .ledger import item_stock, party_balances
from .vouchers import to_out

ZERO = Decimal("0")
TAX_FIELDS = ("taxable", "igst", "cgst", "sgst", "cess")


def _zero() -> dict:
    return {f: ZERO for f in TAX_FIELDS}


def _add(bucket: dict, src, sign: int = 1) -> None:
    for f in TAX_FIELDS:
        bucket[f] += sign * (src[f] if isinstance(src, dict) else getattr(src, f))


def _vouchers(db: Session, bid: str, types, date_from: dt.date, date_to: dt.date, include_cancelled=False):
    q = (
        select(Voucher)
        .options(selectinload(Voucher.lines), selectinload(Voucher.allocations))
        .where(Voucher.business_id == bid, Voucher.type.in_(types), Voucher.date >= date_from, Voucher.date <= date_to)
        .order_by(Voucher.date, Voucher.number)
    )
    if not include_cancelled:
        q = q.where(Voucher.cancelled.is_(False))
    return db.scalars(q).all()


def _rate_rows(v: Voucher, include_zero: bool = False) -> dict[Decimal, dict]:
    rows: dict[Decimal, dict] = defaultdict(_zero)
    for l in v.lines:
        if l.gst_rate > 0 or include_zero:
            _add(rows[l.gst_rate], l)
    return rows


def _rows_list(rows: dict[Decimal, dict]) -> list[dict]:
    return [{"rate": r, **vals} for r, vals in sorted(rows.items())]


# ---------------------------------------------------------------- GSTR-1
def gstr1(db: Session, biz: Business, date_from: dt.date, date_to: dt.date) -> dict:
    all_docs = _vouchers(db, biz.id, [VoucherType.SALE, VoucherType.SALE_RETURN], date_from, date_to, True)
    active = [v for v in all_docs if not v.cancelled and v.tax_applicable]

    b2b, b2cl, cdnr, exp, cdnur = [], [], [], [], []
    b2cs: dict[tuple, dict] = defaultdict(_zero)
    nil = {k: ZERO for k in ("inter_registered", "intra_registered", "inter_unregistered", "intra_unregistered")}
    hsn: dict[tuple, dict] = {}

    for v in active:
        is_sale = v.type == VoucherType.SALE
        sign = 1 if is_sale else -1
        registered = bool(v.party_gstin)
        rows = _rate_rows(v)
        doc = dict(id=v.id, number=v.number, date=v.date, party_name=v.party_name, gstin=v.party_gstin,
                   pos=state_label(v.place_of_supply), reverse_charge=v.reverse_charge,
                   value=v.grand_total, rates=_rows_list(rows))

        for l in v.lines:
            if l.gst_rate == 0:
                key = ("inter_" if v.inter_state else "intra_") + ("registered" if registered else "unregistered")
                nil[key] += sign * l.taxable
            hkey = ("B2B" if registered else "B2C", l.hsn_sac or "", l.unit or "OTH", l.gst_rate)
            h = hsn.setdefault(hkey, dict(qty=ZERO, value=ZERO, **_zero()))
            h["qty"] += sign * l.qty
            h["value"] += sign * l.total
            _add(h, l, sign)

        doc["type"] = {"SEZWP": "SEWP", "SEZWOP": "SEWOP"}.get(v.export_type or "", "R") if registered else (v.export_type or "")
        if v.export_type and v.export_type.startswith("EXP"):
            doc.update(shipping_bill=v.shipping_bill_no, shipping_date=v.shipping_bill_date, port=v.port_code,
                       rates=_rows_list(_rate_rows(v, include_zero=True)))
            (exp if is_sale else cdnur).append(doc)
        elif is_sale:
            if registered:
                b2b.append(doc)
            elif v.inter_state and v.grand_total > config_store.get("b2cl_limit", v.date):
                b2cl.append(doc)
            else:
                for rate, vals in rows.items():
                    _add(b2cs[(v.place_of_supply, rate)], vals)
        elif registered:
            original = db.get(Voucher, v.original_voucher_id) if v.original_voucher_id else None
            doc["original_number"] = original.number if original else None
            doc["original_date"] = original.date if original else None
            cdnr.append(doc)
        else:
            # Credit notes to unregistered buyers (non-B2CL) are netted off in B2CS.
            for rate, vals in rows.items():
                _add(b2cs[(v.place_of_supply, rate)], vals, -1)

    docs = []
    for vtype, label in ((VoucherType.SALE, "Invoices for outward supply"), (VoucherType.SALE_RETURN, "Credit Note")):
        ds = [v for v in all_docs if v.type == vtype]
        if ds:
            docs.append(dict(nature=label, from_number=ds[0].number, to_number=ds[-1].number, total=len(ds),
                             cancelled=sum(1 for v in ds if v.cancelled),
                             net_issued=sum(1 for v in ds if not v.cancelled)))

    def total_of(docs_or_rows):
        t = _zero()
        for d in docs_or_rows:
            for r in d["rates"]:
                _add(t, r)
        return t

    b2cs_rows = [dict(pos=state_label(pos), rate=rate, **vals) for (pos, rate), vals in sorted(b2cs.items())]
    b2cs_total = _zero()
    for r in b2cs_rows:
        _add(b2cs_total, r)
    cdnr_total = total_of(cdnr)

    return dict(
        applicable=biz.gst_type.value == "REGULAR",
        period={"from": date_from, "to": date_to},
        b2b=b2b, b2b_total=total_of(b2b),
        b2cl=b2cl, b2cl_total=total_of(b2cl),
        b2cs=b2cs_rows, b2cs_total=b2cs_total,
        cdnr=cdnr, cdnr_total=cdnr_total,
        exp=exp, exp_total=total_of(exp), cdnur=cdnur, cdnur_total=total_of(cdnur),
        nil=nil,
        hsn=[dict(section=k[0], hsn=k[1], uqc=k[2], rate=k[3], **v) for k, v in sorted(hsn.items())],
        docs=docs,
    )


# ---------------------------------------------------------------- GSTR-3B
def gstr3b(db: Session, biz: Business, date_from: dt.date, date_to: dt.date) -> dict:
    from .gst_returns import gstr3b as compute

    return compute(db, biz, date_from, date_to)


# ---------------------------------------------------------------- registers
def register(db: Session, biz: Business, types, date_from: dt.date, date_to: dt.date) -> dict:
    rows = []
    tot = dict(taxable=ZERO, cgst=ZERO, sgst=ZERO, igst=ZERO, cess=ZERO, grand_total=ZERO, paid=ZERO, balance=ZERO)
    for v in _vouchers(db, biz.id, types, date_from, date_to, include_cancelled=True):
        o = to_out(v)
        row = dict(id=v.id, type=v.type, date=v.date, number=v.number, party_name=v.party_name,
                   gstin=v.party_gstin, pos=state_label(v.place_of_supply),
                   supplier_invoice_no=v.supplier_invoice_no,
                   taxable=v.taxable, cgst=v.cgst, sgst=v.sgst, igst=v.igst, cess=v.cess,
                   grand_total=v.grand_total, paid=o.paid, balance=o.balance, status=o.status)
        rows.append(row)
        if not v.cancelled:
            sign = -1 if v.type in (VoucherType.SALE_RETURN, VoucherType.PURCHASE_RETURN) else 1
            for k in tot:
                tot[k] += sign * row[k]
    return dict(rows=rows, total=tot)


# ---------------------------------------------------------------- stock
def stock_summary(db: Session, biz: Business, date_from: dt.date, date_to: dt.date) -> dict:
    items = db.scalars(
        select(Item).where(Item.business_id == biz.id, Item.type == ItemType.GOODS).order_by(Item.name)
    ).all()
    opening = item_stock(db, biz.id, as_of=date_from - dt.timedelta(days=1))
    movement = db.execute(
        select(
            StockMovement.item_id,
            func.sum(case((StockMovement.qty > 0, StockMovement.qty), else_=0)),
            func.sum(StockMovement.qty),
        )
        .where(StockMovement.business_id == biz.id, StockMovement.date >= date_from, StockMovement.date <= date_to)
        .group_by(StockMovement.item_id)
    ).all()
    moves = {iid: (inward or ZERO, net or ZERO) for iid, inward, net in movement}
    rows, total_value = [], ZERO
    for it in items:
        op = opening.get(it.id, ZERO)
        inward, net = moves.get(it.id, (ZERO, ZERO))
        outward = inward - net
        closing = op + net
        value = (closing * it.purchase_price).quantize(Decimal("0.01")) if closing > 0 else ZERO
        total_value += value
        rows.append(dict(id=it.id, name=it.name, code=it.code, hsn_sac=it.hsn_sac, unit=it.unit,
                         opening=op, inward=inward, outward=outward, closing=closing,
                         purchase_price=it.purchase_price, value=value,
                         low=it.low_stock_level is not None and closing <= it.low_stock_level))
    return dict(rows=rows, total_value=total_value)


# ---------------------------------------------------------------- outstanding
def outstanding(db: Session, biz: Business) -> dict:
    balances = party_balances(db, biz.id)
    parties = {p.id: p for p in db.scalars(select(Party).where(Party.business_id == biz.id))}
    receivable, payable = [], []
    for pid, bal in balances.items():
        p = parties.get(pid)
        if not p or bal == 0:
            continue
        row = dict(id=pid, name=p.name, phone=p.phone, gstin=p.gstin, amount=abs(bal))
        (receivable if bal > 0 else payable).append(row)
    receivable.sort(key=lambda r: -r["amount"])
    payable.sort(key=lambda r: -r["amount"])
    return dict(
        receivable=receivable, payable=payable,
        total_receivable=sum((r["amount"] for r in receivable), ZERO),
        total_payable=sum((r["amount"] for r in payable), ZERO),
    )


# ---------------------------------------------------------------- dashboard
def dashboard(db: Session, biz: Business, today: dt.date) -> dict:
    month_start = today.replace(day=1)

    def net_total(types_signs, start, end):
        q = (
            select(Voucher.type, func.coalesce(func.sum(Voucher.grand_total), 0))
            .where(Voucher.business_id == biz.id, Voucher.cancelled.is_(False),
                   Voucher.type.in_(list(types_signs)), Voucher.date >= start, Voucher.date <= end)
            .group_by(Voucher.type)
        )
        return sum((types_signs[VoucherType(t)] * Decimal(s) for t, s in db.execute(q)), ZERO)

    sales_signs = {VoucherType.SALE: 1, VoucherType.SALE_RETURN: -1}
    purchase_signs = {VoucherType.PURCHASE: 1, VoucherType.PURCHASE_RETURN: -1}

    trend = []
    y, m = today.year, today.month
    for _ in range(6):
        start = dt.date(y, m, 1)
        end = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))
        trend.append(dict(month=start.strftime("%b %Y"), sales=net_total(sales_signs, start, end),
                          purchases=net_total(purchase_signs, start, end),
                          expenses=net_total({VoucherType.EXPENSE: 1}, start, end)))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    trend.reverse()

    received = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.business_id == biz.id, Payment.type == PaymentType.IN, Payment.date >= month_start)
    )
    out = outstanding(db, biz)

    items = db.scalars(select(Item).where(Item.business_id == biz.id, Item.type == ItemType.GOODS,
                                          Item.low_stock_level.is_not(None))).all()
    stock = item_stock(db, biz.id, [i.id for i in items])
    low = [dict(id=i.id, name=i.name, stock=stock.get(i.id, ZERO), unit=i.unit, level=i.low_stock_level)
           for i in items if stock.get(i.id, ZERO) <= i.low_stock_level]

    recent = db.scalars(
        select(Voucher).options(selectinload(Voucher.allocations))
        .where(Voucher.business_id == biz.id).order_by(Voucher.created_at.desc()).limit(8)
    ).all()

    # inventory summary
    from ..reports.accounting import avg_costs, stock_qty
    from .accounts import account_balances, cash_account

    goods = db.scalars(select(Item).where(Item.business_id == biz.id, Item.type == ItemType.GOODS,
                                          Item.is_active.is_(True))).all()
    qty_now = stock_qty(db, biz.id, today)
    costs = avg_costs(db, biz.id, today)
    inventory = dict(
        items=len(goods),
        value=sum(((max(qty_now.get(i.id, ZERO), ZERO) * costs.get(i.id, ZERO)).quantize(Decimal("0.01"))
                   for i in goods), ZERO),
        sale_value=sum(((max(qty_now.get(i.id, ZERO), ZERO) * i.sale_price).quantize(Decimal("0.01"))
                        for i in goods), ZERO),
        low=sum(1 for i in goods if i.low_stock_level is not None and 0 < qty_now.get(i.id, ZERO) <= i.low_stock_level),
        out=sum(1 for i in goods if qty_now.get(i.id, ZERO) <= 0),
    )

    # cash & bank
    cash_account(db, biz.id)
    balances = account_balances(db, biz.id)
    accounts = [dict(id=a.id, name=a.name, type=a.type.value, balance=balances.get(a.id, ZERO))
                for a in db.scalars(select(Account).where(Account.business_id == biz.id, Account.is_active.is_(True))
                                    .order_by(Account.is_default_cash.desc(), Account.name))]
    open_cheques = db.scalars(select(Payment).where(Payment.business_id == biz.id,
                                                    Payment.cheque_status == "OPEN")).all()
    cash_bank = dict(
        total=sum((a["balance"] for a in accounts), ZERO), accounts=accounts,
        cheques_in=sum((p.amount for p in open_cheques if p.type == PaymentType.IN), ZERO),
        cheques_out=sum((p.amount for p in open_cheques if p.type == PaymentType.OUT), ZERO),
    )

    # expenses this month
    exp_rows = db.execute(
        select(ExpenseCategory.name, func.coalesce(func.sum(Voucher.grand_total), 0))
        .join(ExpenseCategory, ExpenseCategory.id == Voucher.expense_category_id)
        .where(Voucher.business_id == biz.id, Voucher.type == VoucherType.EXPENSE, Voucher.cancelled.is_(False),
               Voucher.date >= month_start, Voucher.date <= today)
        .group_by(ExpenseCategory.name)).all()
    exp_sorted = sorted(((n, Decimal(t)) for n, t in exp_rows), key=lambda x: -x[1])
    expenses = dict(
        month=sum((t for _, t in exp_sorted), ZERO),
        top=[dict(category=n, amount=t) for n, t in exp_sorted[:5]],
    )

    return dict(
        inventory=inventory,
        cash_bank=cash_bank,
        expenses=expenses,
        sales_today=net_total(sales_signs, today, today),
        sales_month=net_total(sales_signs, month_start, today),
        purchases_month=net_total(purchase_signs, month_start, today),
        received_month=Decimal(received or 0),
        receivable=out["total_receivable"],
        payable=out["total_payable"],
        trend=trend,
        low_stock=low[:10],
        recent=[to_out(v).model_dump(mode="json") for v in recent],
    )
