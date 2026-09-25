"""GSTR-1 JSON in the format accepted by the GST portal / offline tool (upload via "Prepare offline").

Sections: b2b, b2cl, b2cs, cdnr, cdnur (B2CL credit notes), nil, hsn (B2B/B2C split), doc_issue.
Always review the file in the GST offline tool before uploading.
"""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..gst.constants import B2CL_LIMIT, VoucherType
from ..models import Business, Voucher

ZERO = Decimal("0")


def _f(x) -> float:
    return float(Decimal(x or 0).quantize(Decimal("0.01")))


def _date(d: dt.date) -> str:
    return d.strftime("%d-%m-%Y")


def _items(v: Voucher, only_rated=True) -> list[dict]:
    rows: dict[Decimal, dict] = defaultdict(lambda: dict(txval=ZERO, iamt=ZERO, camt=ZERO, samt=ZERO, csamt=ZERO))
    for l in v.lines:
        if only_rated and l.gst_rate == 0:
            continue
        r = rows[l.gst_rate]
        r["txval"] += l.taxable
        r["iamt"] += l.igst
        r["camt"] += l.cgst
        r["samt"] += l.sgst
        r["csamt"] += l.cess
    out = []
    for rate, r in sorted(rows.items()):
        det = {"txval": _f(r["txval"]), "rt": float(rate), "csamt": _f(r["csamt"])}
        if v.inter_state:
            det["iamt"] = _f(r["iamt"])
        else:
            det["camt"], det["samt"] = _f(r["camt"]), _f(r["samt"])
        out.append({"num": int(rate * 100) + 1, "itm_det": det})
    return out


def build(db: Session, biz: Business, date_from: dt.date, date_to: dt.date) -> dict:
    docs = db.scalars(select(Voucher).options(selectinload(Voucher.lines)).where(
        Voucher.business_id == biz.id, Voucher.type.in_([VoucherType.SALE, VoucherType.SALE_RETURN]),
        Voucher.date >= date_from, Voucher.date <= date_to).order_by(Voucher.date, Voucher.number)).all()
    active = [v for v in docs if not v.cancelled and v.tax_applicable]

    b2b: dict[str, list] = defaultdict(list)
    b2cl: dict[str, list] = defaultdict(list)
    cdnr: dict[str, list] = defaultdict(list)
    cdnur: list = []
    b2cs: dict[tuple, dict] = defaultdict(lambda: dict(txval=ZERO, iamt=ZERO, camt=ZERO, samt=ZERO, csamt=ZERO))
    nil = {k: ZERO for k in ("INTRB2B", "INTRAB2B", "INTRB2C", "INTRAB2C")}
    hsn = {"B2B": defaultdict(lambda: dict(qty=ZERO, txval=ZERO, iamt=ZERO, camt=ZERO, samt=ZERO, csamt=ZERO, desc="")),
           "B2C": defaultdict(lambda: dict(qty=ZERO, txval=ZERO, iamt=ZERO, camt=ZERO, samt=ZERO, csamt=ZERO, desc=""))}
    originals = {v.id: v for v in docs}

    for v in active:
        sale = v.type == VoucherType.SALE
        sign = 1 if sale else -1
        reg = bool(v.party_gstin)
        for l in v.lines:
            if l.gst_rate == 0:
                nil[("INTR" if v.inter_state else "INTRA") + ("B2B" if reg else "B2C")] += sign * l.taxable
            h = hsn["B2B" if reg else "B2C"][(l.hsn_sac or "", (l.unit or "OTH")[:3], l.gst_rate)]
            h["qty"] += sign * l.qty
            h["txval"] += sign * l.taxable
            h["iamt"] += sign * l.igst
            h["camt"] += sign * l.cgst
            h["samt"] += sign * l.sgst
            h["csamt"] += sign * l.cess
            h["desc"] = h["desc"] or l.name[:30]
        items = _items(v)
        if not items:
            continue
        if sale:
            inv = {"inum": v.number, "idt": _date(v.date), "val": _f(v.grand_total), "pos": v.place_of_supply,
                   "itms": items}
            if reg:
                b2b[v.party_gstin].append({**inv, "rchrg": "Y" if v.reverse_charge else "N", "inv_typ": "R"})
            elif v.inter_state and v.grand_total > B2CL_LIMIT:
                b2cl[v.place_of_supply].append({k: inv[k] for k in ("inum", "idt", "val", "itms")})
            else:
                for it in items:
                    d = it["itm_det"]
                    b = b2cs[("INTER" if v.inter_state else "INTRA", v.place_of_supply, d["rt"])]
                    for k in ("txval", "iamt", "camt", "samt", "csamt"):
                        b[k] += Decimal(str(d.get(k, 0)))
        else:
            note = {"ntty": "C", "nt_num": v.number, "nt_dt": _date(v.date), "val": _f(v.grand_total),
                    "pos": v.place_of_supply, "itms": items}
            if reg:
                cdnr[v.party_gstin].append({**note, "rchrg": "N", "inv_typ": "R"})
            else:
                orig = originals.get(v.original_voucher_id)
                if orig and orig.inter_state and orig.grand_total > B2CL_LIMIT:
                    cdnur.append({**note, "typ": "B2CL"})
                else:
                    for it in items:  # other credit notes to consumers reduce B2CS
                        d = it["itm_det"]
                        b = b2cs[("INTER" if v.inter_state else "INTRA", v.place_of_supply, d["rt"])]
                        for k in ("txval", "iamt", "camt", "samt", "csamt"):
                            b[k] -= Decimal(str(d.get(k, 0)))

    def hsn_rows(section):
        out = []
        for n, ((code, uqc, rate), h) in enumerate(sorted(section.items()), 1):
            out.append({"num": n, "hsn_sc": code, "desc": h["desc"], "uqc": uqc, "qty": float(h["qty"]),
                        "rt": float(rate), "txval": _f(h["txval"]), "iamt": _f(h["iamt"]), "camt": _f(h["camt"]),
                        "samt": _f(h["samt"]), "csamt": _f(h["csamt"])})
        return out

    doc_det = []
    for n, (vtype, label) in enumerate(((VoucherType.SALE, "Invoices for outward supply"),
                                        (VoucherType.SALE_RETURN, "Credit Note")), 1):
        ds = [v for v in docs if v.type == vtype]
        if ds:
            doc_det.append({"doc_num": 1 if vtype == VoucherType.SALE else 5, "doc_typ": label, "docs": [{
                "num": 1, "from": ds[0].number, "to": ds[-1].number, "totnum": len(ds),
                "cancel": sum(1 for v in ds if v.cancelled), "net_issue": sum(1 for v in ds if not v.cancelled)}]})

    out = {
        "gstin": biz.gstin, "fp": date_to.strftime("%m%Y"), "version": "GST3.2", "hash": "hash",
        "b2b": [{"ctin": k, "inv": v} for k, v in sorted(b2b.items())],
        "b2cl": [{"pos": k, "inv": v} for k, v in sorted(b2cl.items())],
        "b2cs": [{"sply_ty": k[0], "pos": k[1], "typ": "OE", "rt": k[2],
                  "txval": _f(b["txval"]), "csamt": _f(b["csamt"]),
                  **({"iamt": _f(b["iamt"])} if k[0] == "INTER" else {"camt": _f(b["camt"]), "samt": _f(b["samt"])})}
                 for k, b in sorted(b2cs.items()) if b["txval"]],
        "cdnr": [{"ctin": k, "nt": v} for k, v in sorted(cdnr.items())],
        "cdnur": cdnur,
        "nil": {"inv": [{"sply_ty": k, "expt_amt": 0, "nil_amt": _f(v), "ngsup_amt": 0} for k, v in nil.items() if v]},
        "hsn": {"hsn_b2b": hsn_rows(hsn["B2B"]), "hsn_b2c": hsn_rows(hsn["B2C"])},
        "doc_issue": {"doc_det": doc_det},
    }
    return {k: v for k, v in out.items() if v not in ([], {"inv": []}, {"doc_det": []})}
