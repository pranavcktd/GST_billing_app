"""GSTR-3B (with portal JSON), and composition returns CMP-08 / GSTR-4 — one engine for screen and file.

Classification of documents in the period (cancelled documents are ignored):
  Outward (sale +, credit note −)
    export / SEZ (EXPWP, EXPWOP, SEZWP, SEZWOP) ........ 3.1(b) zero-rated
    lines at 0% ........................................ 3.1(c) nil / exempt
    everything else .................................... 3.1(a) taxable
    inter-state to unregistered / composition buyers ... 3.2
  Inward (purchase / expense +, debit note −)
    reverse charge (incl. import of services) .......... 3.1(d) liability
    ITC: import of goods IMPG, import of services IMPS, other reverse charge ISRC, all other OTH ... 4(A)
    blocked credit u/s 17(5) ........................... 4(D)(1)
    nil / exempt / composition / unregistered inward ... 5
"""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..gst.constants import BusinessGstType, PartyGstType, VoucherType
from ..gst.states import state_label
from ..models import Business, Party, Voucher
from ..reports.accounting import itc_claimable

ZERO = Decimal("0")
HEADS = ("igst", "cgst", "sgst", "cess")
COMPOSITION_RATE = {"TRADER": Decimal("1"), "MANUFACTURER": Decimal("1"), "RESTAURANT": Decimal("5"), "SERVICE": Decimal("6")}
ZERO_RATED = {"EXPWP", "EXPWOP", "SEZWP", "SEZWOP"}


def _t() -> dict:
    return {"taxable": ZERO, **{h: ZERO for h in HEADS}}


def _add(b: dict, src, sign: int = 1) -> None:
    b["taxable"] += sign * src.taxable
    for h in HEADS:
        b[h] += sign * getattr(src, h)


def _docs(db: Session, biz_id: str, types, date_from: dt.date, date_to: dt.date):
    return db.scalars(select(Voucher).options(selectinload(Voucher.lines), selectinload(Voucher.expense_category)).where(
        Voucher.business_id == biz_id, Voucher.type.in_(types), Voucher.cancelled.is_(False),
        Voucher.date >= date_from, Voucher.date <= date_to).order_by(Voucher.date)).all()


def gstr3b(db: Session, biz: Business, date_from: dt.date, date_to: dt.date) -> dict:
    parties = {p.id: p for p in db.scalars(select(Party).where(Party.business_id == biz.id))}
    osup_det, osup_zero, isup_rev = _t(), _t(), _t()
    nil_exempt = ZERO
    unreg: dict[str, dict] = defaultdict(lambda: dict(taxable=ZERO, igst=ZERO))
    comp: dict[str, dict] = defaultdict(lambda: dict(taxable=ZERO, igst=ZERO))
    itc = {k: _t() for k in ("IMPG", "IMPS", "ISRC", "OTH")}
    itc_blocked = _t()
    inward_exempt = {"inter": ZERO, "intra": ZERO}

    for v in _docs(db, biz.id, [VoucherType.SALE, VoucherType.SALE_RETURN], date_from, date_to):
        if not v.tax_applicable:
            continue
        sign = 1 if v.type == VoucherType.SALE else -1
        party = parties.get(v.party_id)
        for l in v.lines:
            if v.export_type in ZERO_RATED:
                _add(osup_zero, l, sign)
            elif l.gst_rate == 0:
                nil_exempt += sign * l.taxable
            else:
                _add(osup_det, l, sign)
                if v.inter_state and not v.party_gstin:
                    b = unreg[v.place_of_supply]
                    b["taxable"] += sign * l.taxable
                    b["igst"] += sign * l.igst
                elif v.inter_state and party is not None and party.gst_type == PartyGstType.COMPOSITION:
                    b = comp[v.place_of_supply]
                    b["taxable"] += sign * l.taxable
                    b["igst"] += sign * l.igst

    for v in _docs(db, biz.id, [VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN, VoucherType.EXPENSE], date_from, date_to):
        sign = -1 if v.type == VoucherType.PURCHASE_RETURN else 1
        side = "inter" if v.inter_state else "intra"
        if not v.tax_applicable:
            inward_exempt[side] += sign * v.taxable
            continue
        for l in v.lines:
            if l.gst_rate == 0:
                inward_exempt[side] += sign * l.taxable
        if v.reverse_charge:
            _add(isup_rev, v, sign)
        if itc_claimable(v, biz):
            key = ("IMPS" if v.reverse_charge else "IMPG") if v.export_type == "IMPORT" else ("ISRC" if v.reverse_charge else "OTH")
            _add(itc[key], v, sign)
        elif v.type == VoucherType.EXPENSE and v.expense_category is not None and v.expense_category.itc_blocked:
            _add(itc_blocked, v, sign)

    itc_net = _t()
    for b in itc.values():
        for h in HEADS:
            itc_net[h] += b[h]
    liability = {h: osup_det[h] + osup_zero[h] + isup_rev[h] for h in HEADS}
    net = {h: liability[h] - itc_net[h] for h in HEADS}
    return dict(
        applicable=biz.gst_type == BusinessGstType.REGULAR,
        outward_taxable=osup_det, zero_rated=osup_zero, nil_exempt=nil_exempt, inward_rcm=isup_rev,
        inter_state_unregistered=[dict(pos=state_label(p), pos_code=p, **x) for p, x in sorted(unreg.items())],
        inter_state_composition=[dict(pos=state_label(p), pos_code=p, **x) for p, x in sorted(comp.items())],
        itc_import_goods=itc["IMPG"], itc_import_services=itc["IMPS"], itc_rcm=itc["ISRC"], itc_other=itc["OTH"],
        itc_total=itc_net, itc_blocked=itc_blocked, inward_exempt=inward_exempt,
        liability=liability, net_payable=net,
    )


def _f(x) -> float:
    return float(Decimal(x or 0).quantize(Decimal("0.01")))


def _amt(b: dict, heads=("iamt", "camt", "samt", "csamt")) -> dict:
    m = {"iamt": "igst", "camt": "cgst", "samt": "sgst", "csamt": "cess"}
    return {k: _f(b[m[k]]) for k in heads}


def gstr3b_json(db: Session, biz: Business, date_from: dt.date, date_to: dt.date) -> dict:
    """GSTR-3B in the JSON format of the GST portal / offline utility."""
    d = gstr3b(db, biz, date_from, date_to)
    zero4 = {"iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0}
    return {
        "gstin": biz.gstin, "ret_period": date_to.strftime("%m%Y"),
        "sup_details": {
            "osup_det": {"txval": _f(d["outward_taxable"]["taxable"]), **_amt(d["outward_taxable"])},
            "osup_zero": {"txval": _f(d["zero_rated"]["taxable"]), **_amt(d["zero_rated"], ("iamt", "csamt"))},
            "osup_nil_exmp": {"txval": _f(d["nil_exempt"])},
            "isup_rev": {"txval": _f(d["inward_rcm"]["taxable"]), **_amt(d["inward_rcm"])},
            "osup_nongst": {"txval": 0.0},
        },
        "inter_sup": {
            "unreg_details": [{"pos": r["pos_code"], "txval": _f(r["taxable"]), "iamt": _f(r["igst"])} for r in d["inter_state_unregistered"]],
            "comp_details": [{"pos": r["pos_code"], "txval": _f(r["taxable"]), "iamt": _f(r["igst"])} for r in d["inter_state_composition"]],
            "uin_details": [],
        },
        "itc_elg": {
            "itc_avl": [
                {"ty": "IMPG", **_amt(d["itc_import_goods"]), "camt": 0.0, "samt": 0.0},
                {"ty": "IMPS", **_amt(d["itc_import_services"]), "camt": 0.0, "samt": 0.0},
                {"ty": "ISRC", **_amt(d["itc_rcm"])},
                {"ty": "ISD", **zero4},
                {"ty": "OTH", **_amt(d["itc_other"])},
            ],
            "itc_rev": [{"ty": "RUL", **zero4}, {"ty": "OTH", **zero4}],
            "itc_net": _amt(d["itc_total"]),
            "itc_inelg": [{"ty": "RUL", **_amt(d["itc_blocked"])}, {"ty": "OTH", **zero4}],
        },
        "inward_sup": {"isup_details": [
            {"ty": "GST", "inter": _f(d["inward_exempt"]["inter"]), "intra": _f(d["inward_exempt"]["intra"])},
            {"ty": "NONGST", "inter": 0.0, "intra": 0.0},
        ]},
        "intr_ltfee": {"intr_details": zero4, "ltfee_details": {}},
    }


# ================================================================ composition scheme
def cmp08(db: Session, biz: Business, date_from: dt.date, date_to: dt.date) -> dict:
    """Quarterly statement CMP-08: tax on turnover at the composition rate + reverse-charge tax."""
    rate = COMPOSITION_RATE.get(biz.composition_type or "TRADER", Decimal("1"))
    turnover = ZERO
    for v in _docs(db, biz.id, [VoucherType.SALE, VoucherType.SALE_RETURN], date_from, date_to):
        turnover += (1 if v.type == VoucherType.SALE else -1) * v.taxable
    rcm = _t()
    for v in _docs(db, biz.id, [VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN, VoucherType.EXPENSE], date_from, date_to):
        if v.reverse_charge and v.tax_applicable:
            _add(rcm, v, -1 if v.type == VoucherType.PURCHASE_RETURN else 1)
    half = (turnover * rate / 200).quantize(Decimal("0.01"))
    outward = dict(taxable=turnover, igst=ZERO, cgst=half, sgst=half, cess=ZERO)
    total = {h: outward[h] + rcm[h] for h in HEADS}
    return dict(applicable=biz.gst_type == BusinessGstType.COMPOSITION, category=biz.composition_type, rate=rate,
                outward=outward, inward_rcm=rcm, total=total)


def gstr4(db: Session, biz: Business, date_from: dt.date, date_to: dt.date) -> dict:
    """Annual return GSTR-4 tables for a composition taxpayer (use the financial year as period)."""
    b2b: dict[str, dict] = defaultdict(lambda: dict(name="", invoices=0, **_t()))
    b2b_rcm: dict[str, dict] = defaultdict(lambda: dict(name="", invoices=0, **_t()))
    unreg = _t()
    imp_services = _t()
    for v in _docs(db, biz.id, [VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN, VoucherType.EXPENSE], date_from, date_to):
        sign = -1 if v.type == VoucherType.PURCHASE_RETURN else 1
        if v.export_type == "IMPORT" and v.reverse_charge:
            _add(imp_services, v, sign)
        elif v.party_gstin:
            target = b2b_rcm if v.reverse_charge else b2b
            row = target[v.party_gstin]
            row["name"] = v.party_name
            row["invoices"] += 1
            _add(row, v, sign)
        else:
            _add(unreg, v, sign)
    quarters = []
    start = date_from
    while start <= date_to:
        end = min((dt.date(start.year + (start.month + 2) // 12, (start.month + 2) % 12 + 1, 1) - dt.timedelta(days=1)), date_to)
        q = cmp08(db, biz, start, end)
        quarters.append(dict(period=f"{start:%b %Y} – {end:%b %Y}", turnover=q["outward"]["taxable"],
                             tax=q["total"]["cgst"] + q["total"]["sgst"], rcm_tax=sum((q["inward_rcm"][h] for h in HEADS), ZERO)))
        start = end + dt.timedelta(days=1)
    return dict(applicable=biz.gst_type == BusinessGstType.COMPOSITION,
                inward_b2b=[dict(gstin=k, **v) for k, v in sorted(b2b.items())],
                inward_b2b_rcm=[dict(gstin=k, **v) for k, v in sorted(b2b_rcm.items())],
                inward_unregistered=unreg, import_of_services=imp_services, quarters=quarters)
