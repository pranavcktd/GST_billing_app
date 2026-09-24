from collections import defaultdict

from ..gst.constants import VoucherType
from ..gst.states import state_label
from ..models import Voucher
from .accounting import itc_claimable, tax_of
from .base import ZERO, RCtx, col, link_doc, money, result, section, stat, totals, vouchers

TAX = ("taxable", "igst", "cgst", "sgst", "cess")
TAX_COLS = money(("taxable", "Taxable"), ("igst", "IGST"), ("cgst", "CGST"), ("sgst", "SGST"), ("cess", "Cess"))
INWARD = [VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN, VoucherType.EXPENSE]
OUTWARD = [VoucherType.SALE, VoucherType.SALE_RETURN]


def _sign(v: Voucher) -> int:
    return -1 if v.type in (VoucherType.SALE_RETURN, VoucherType.PURCHASE_RETURN) else 1


def _rate_rows(v: Voucher):
    rows = defaultdict(lambda: {k: ZERO for k in TAX})
    for l in v.lines:
        for k in TAX:
            rows[l.gst_rate][k] += getattr(l, k)
    return rows


def gstr2(r: RCtx):
    """Inward supplies with GST, to reconcile against GSTR-2B."""
    b2b, cdn, other = [], [], []
    for v in vouchers(r, INWARD, r.date_from, r.date_to):
        if not v.tax_applicable:
            continue
        for rate, vals in sorted(_rate_rows(v).items()):
            if not any(vals.values()):
                continue
            row = dict(_link=link_doc(v.id), gstin=v.party_gstin or "", party=v.party_name,
                       number=v.supplier_invoice_no or v.number, date=v.supplier_invoice_date or v.date,
                       pos=state_label(v.place_of_supply), rcm="Y" if v.reverse_charge else "N",
                       itc="Yes" if itc_claimable(v, r.biz) else "No", value=v.grand_total, rate=rate, **vals)
            (cdn if v.type == VoucherType.PURCHASE_RETURN else b2b if v.party_gstin else other).append(row)
    cols = [col("gstin", "Supplier GSTIN"), col("party", "Supplier"), col("number", "Bill no."),
            col("date", "Bill date", "date"), col("pos", "POS"), col("rcm", "RCM"), col("itc", "ITC eligible"),
            col("value", "Bill value", "money"), col("rate", "Rate", "pct"), *TAX_COLS]
    return result("GSTR-2 (purchases)", [
        section(cols, b2b, "B2B — purchases from registered suppliers", totals(b2b, TAX)),
        section(cols, cdn, "Debit notes issued to suppliers", totals(cdn, TAX)),
        section(cols, other, "Purchases from unregistered suppliers (incl. RCM)", totals(other, TAX)),
    ], summary=[stat("ITC (B2B)", sum((x["igst"] + x["cgst"] + x["sgst"] + x["cess"] for x in b2b), ZERO))])


def gst_transactions(r: RCtx):
    rows = []
    for v in vouchers(r, OUTWARD + INWARD, r.date_from, r.date_to):
        s = _sign(v)
        rows.append(dict(_link=link_doc(v.id), date=v.date, type=v.type.value.replace("_", " ").title(),
                         number=v.number, party=v.party_name, gstin=v.party_gstin or "",
                         pos=state_label(v.place_of_supply), **{k: s * getattr(v, k) for k in TAX},
                         total=s * v.grand_total))
    cols = [col("date", "Date", "date"), col("type", "Type"), col("number", "Number"), col("party", "Party"),
            col("gstin", "GSTIN"), col("pos", "POS"), *TAX_COLS, col("total", "Total", "money")]
    return result("GST transaction report", [section(cols, rows, total=totals(rows, TAX + ("total",)),
                  note="Sales and purchases together; returns are negative.")])


def gstr9(r: RCtx):
    """Annual return summary (use a financial-year period)."""
    out = {k: ZERO for k in TAX}
    cn = {k: ZERO for k in TAX}
    nil = ZERO
    itc = {k: ZERO for k in TAX}
    rcm = {k: ZERO for k in TAX}
    hsn_out: dict = defaultdict(lambda: dict(qty=ZERO, **{k: ZERO for k in TAX}))
    hsn_in: dict = defaultdict(lambda: dict(qty=ZERO, **{k: ZERO for k in TAX}))
    for v in vouchers(r, OUTWARD + INWARD, r.date_from, r.date_to):
        if not v.tax_applicable:
            continue
        s = _sign(v)
        for l in v.lines:
            target = hsn_out if v.type in OUTWARD else hsn_in
            h = target[(l.hsn_sac or "", l.unit or "OTH", l.gst_rate)]
            h["qty"] += s * l.qty
            for k in TAX:
                h[k] += s * getattr(l, k)
            if v.type in OUTWARD and l.gst_rate == 0:
                nil += s * l.taxable
        if v.type == VoucherType.SALE:
            for k in TAX:
                out[k] += getattr(v, k)
        elif v.type == VoucherType.SALE_RETURN:
            for k in TAX:
                cn[k] += getattr(v, k)
        else:
            if v.reverse_charge:
                for k in TAX:
                    rcm[k] += s * getattr(v, k)
            if itc_claimable(v, r.biz):
                for k in TAX:
                    itc[k] += s * getattr(v, k)
    rows = [
        dict(label="4A-4L  Supplies on which tax is payable (gross)", **out, _style="bold"),
        dict(label="4G     Inward supplies on reverse charge", **rcm),
        dict(label="4I     Credit notes issued (−)", **{k: -v for k, v in cn.items()}),
        dict(label="5      Nil rated / exempt supplies", taxable=nil, igst=None, cgst=None, sgst=None, cess=None),
        dict(label="6      Input tax credit availed", **itc, _style="bold"),
        dict(label="9      Tax payable (4 net − 6)", taxable=None,
             **{k: out[k] - cn[k] + rcm[k] - itc[k] for k in ("igst", "cgst", "sgst", "cess")}, _style="bold"),
    ]
    hcols = [col("hsn", "HSN"), col("uqc", "UQC"), col("qty", "Qty", "qty"), col("rate", "Rate", "pct"), *TAX_COLS]
    to_rows = lambda d: [dict(hsn=k[0], uqc=k[1], rate=k[2], **v) for k, v in sorted(d.items())]  # noqa: E731
    return result("GSTR-9 (annual summary)", [
        section([col("label", "Table"), *TAX_COLS], rows),
        section(hcols, to_rows(hsn_out), "17 — HSN summary of outward supplies"),
        section(hcols, to_rows(hsn_in), "18 — HSN summary of inward supplies"),
    ], subtitle="Choose the financial year as the period. Verify against filed GSTR-1/3B before filing.")


def _hsn(r: RCtx, services_only: bool, title: str, inward: bool = False):
    agg: dict = defaultdict(lambda: dict(qty=ZERO, value=ZERO, **{k: ZERO for k in TAX}))
    desc = {}
    for v in vouchers(r, INWARD if inward else OUTWARD, r.date_from, r.date_to):
        s = _sign(v)
        for l in v.lines:
            code = l.hsn_sac or ""
            if services_only and not code.startswith("99"):
                continue
            a = agg[(code, l.unit or "OTH", l.gst_rate)]
            desc.setdefault(code, l.name)
            a["qty"] += s * l.qty
            a["value"] += s * l.total
            for k in TAX:
                a[k] += s * getattr(l, k)
    rows = [dict(hsn=k[0] or "(missing)", desc=desc.get(k[0], ""), uqc=k[1], rate=k[2], **v)
            for k, v in sorted(agg.items())]
    cols = [col("hsn", "HSN/SAC"), col("desc", "Description"), col("uqc", "UQC"), col("qty", "Qty", "qty"),
            col("rate", "Rate", "pct"), col("value", "Total value", "money"), *TAX_COLS]
    return result(title, [section(cols, rows, total=totals(rows, ("value",) + TAX))])


def hsn_sales(r: RCtx):
    return _hsn(r, False, "Sale summary by HSN")


def hsn_purchases(r: RCtx):
    return _hsn(r, False, "Purchase summary by HSN", inward=True)


def sac_report(r: RCtx):
    return _hsn(r, True, "SAC report (services)")


def gst_summary(r: RCtx):
    """Month-wise output tax, input credit and net liability."""
    months: dict = defaultdict(lambda: dict(output=ZERO, rcm=ZERO, itc=ZERO))
    for v in vouchers(r, OUTWARD + INWARD, r.date_from, r.date_to):
        if not v.tax_applicable:
            continue
        m = months[v.date.strftime("%Y-%m")]
        s = _sign(v)
        if v.type in OUTWARD:
            m["output"] += s * tax_of(v)
        else:
            if v.reverse_charge:
                m["rcm"] += s * tax_of(v)
            if itc_claimable(v, r.biz):
                m["itc"] += s * tax_of(v)
    rows = [dict(month=k, **v, net=v["output"] + v["rcm"] - v["itc"]) for k, v in sorted(months.items())]
    cols = [col("month", "Month"), *money(("output", "Output tax"), ("rcm", "Reverse charge"),
                                          ("itc", "Input tax credit"), ("net", "Net payable"))]
    t = totals(rows, ["output", "rcm", "itc", "net"])
    return result("GST report", [section(cols, rows, total=t)],
                  summary=[stat("Output tax", t["output"]), stat("ITC", t["itc"]), stat("Net payable", t["net"])])


def gst_rate_report(r: RCtx):
    agg: dict = defaultdict(lambda: dict(s_taxable=ZERO, s_tax=ZERO, p_taxable=ZERO, p_tax=ZERO))
    for v in vouchers(r, OUTWARD + INWARD, r.date_from, r.date_to):
        if not v.tax_applicable:
            continue
        s = _sign(v)
        side = "s" if v.type in OUTWARD else "p"
        for l in v.lines:
            a = agg[l.gst_rate]
            a[f"{side}_taxable"] += s * l.taxable
            a[f"{side}_tax"] += s * (l.cgst + l.sgst + l.igst + l.cess)
    rows = [dict(rate=k, **v) for k, v in sorted(agg.items())]
    cols = [col("rate", "GST rate", "pct"), *money(("s_taxable", "Sales taxable"), ("s_tax", "Output tax"),
                                                    ("p_taxable", "Purchases taxable"), ("p_tax", "Input tax"))]
    return result("GST rate report", [section(cols, rows, total=totals(rows, ["s_taxable", "s_tax", "p_taxable", "p_tax"]))])
