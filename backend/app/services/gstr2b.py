"""GSTR-2B reconciliation: supplier-reported invoices (portal JSON) vs purchase bills in the books.

Result buckets:
* Matched          — same supplier GSTIN + invoice no., taxable & tax within ₹1
* Amount mismatch  — found in both, values differ
* Missing in books — supplier reported it; you have not recorded the purchase
* Not in 2B        — you recorded it (and may be claiming ITC) but the supplier has not reported it
"""

import datetime as dt
import json
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..gst.constants import VoucherType
from ..models import Business, Voucher

ZERO = Decimal("0")
TOL = Decimal("1")


def _key(gstin: str, number: str) -> tuple[str, str]:
    n = re.sub(r"[^A-Z0-9]", "", (number or "").upper()).lstrip("0")
    return (gstin or "").upper(), n


def _dec(x) -> Decimal:
    return Decimal(str(x or 0))


def _doc_totals(d: dict) -> dict:
    """2B documents carry totals; older files only have items — sum them."""
    items = d.get("items") or d.get("itms") or []
    def pick(k, alt):
        if k in d:
            return _dec(d[k])
        return sum((_dec((i.get("itm_det") or i).get(k, (i.get("itm_det") or i).get(alt))) for i in items), ZERO)
    return {"taxable": pick("txval", "txval"), "igst": pick("igst", "iamt"), "cgst": pick("cgst", "camt"),
            "sgst": pick("sgst", "samt"), "cess": pick("cess", "csamt"), "value": _dec(d.get("val"))}


def parse(content: bytes) -> tuple[list[dict], str | None]:
    try:
        raw = json.loads(content)
    except ValueError as e:
        raise HTTPException(400, "Upload the GSTR-2B JSON file downloaded from the GST portal") from e
    data = raw.get("data", raw)
    docdata = data.get("docdata", data)
    rows = []
    for sup in docdata.get("b2b", []):
        for inv in sup.get("inv", []):
            rows.append({"gstin": sup.get("ctin"), "supplier": sup.get("trdnm", ""), "number": inv.get("inum"),
                         "date": inv.get("dt"), "kind": "Invoice", "itc": inv.get("itcavl", "Y"), **_doc_totals(inv)})
    for sup in docdata.get("cdnr", []):
        for nt in sup.get("nt", []):
            sign = -1 if nt.get("typ", "C") == "C" else 1
            t = _doc_totals(nt)
            rows.append({"gstin": sup.get("ctin"), "supplier": sup.get("trdnm", ""), "number": nt.get("ntnum"),
                         "date": nt.get("dt"), "kind": "Credit note" if sign < 0 else "Debit note",
                         "itc": nt.get("itcavl", "Y"), **{k: sign * v for k, v in t.items()}})
    if not rows and not ("b2b" in docdata or "cdnr" in docdata):
        raise HTTPException(400, "No B2B invoices found — is this a GSTR-2B JSON file?")
    return rows, data.get("rtnprd")


def reconcile(db: Session, biz: Business, content: bytes, date_from: dt.date, date_to: dt.date) -> dict:
    portal, period = parse(content)
    books = db.scalars(select(Voucher).where(
        Voucher.business_id == biz.id, Voucher.type.in_([VoucherType.PURCHASE, VoucherType.EXPENSE]),
        Voucher.cancelled.is_(False), Voucher.party_gstin.is_not(None),
        Voucher.date >= date_from, Voucher.date <= date_to)).all()
    book_map = {_key(v.party_gstin, v.supplier_invoice_no or v.number): v for v in books}
    seen = set()
    matched, mismatch, missing = [], [], []
    for p in portal:
        k = _key(p["gstin"], p["number"])
        v = book_map.get(k)
        row = dict(gstin=p["gstin"], supplier=p["supplier"], number=p["number"], date=p["date"], kind=p["kind"],
                   portal_taxable=p["taxable"], portal_tax=p["igst"] + p["cgst"] + p["sgst"] + p["cess"])
        if v is None:
            missing.append({**row, "itc": "Yes" if p["itc"] == "Y" else "No"})
            continue
        seen.add(k)
        book_tax = v.igst + v.cgst + v.sgst + v.cess
        row.update(_link=f"/doc/{v.id}", book_number=v.number, book_taxable=v.taxable, book_tax=book_tax,
                   diff_tax=row["portal_tax"] - book_tax)
        ok = abs(row["portal_taxable"] - v.taxable) <= TOL and abs(row["diff_tax"]) <= TOL
        (matched if ok else mismatch).append(row)
    not_in_2b = [dict(_link=f"/doc/{v.id}", gstin=v.party_gstin, supplier=v.party_name,
                      number=v.supplier_invoice_no or v.number, date=v.date.strftime("%d-%m-%Y"),
                      book_taxable=v.taxable, book_tax=v.igst + v.cgst + v.sgst + v.cess)
                 for k, v in book_map.items() if k not in seen]

    def col(key, label, type="text"):
        return {"key": key, "label": label, "type": type}

    base = [col("gstin", "Supplier GSTIN"), col("supplier", "Supplier"), col("number", "Invoice no."), col("date", "Date")]
    both = base + [col("book_number", "Our entry"), col("portal_taxable", "2B taxable", "money"),
                   col("book_taxable", "Books taxable", "money"), col("portal_tax", "2B tax", "money"),
                   col("book_tax", "Books tax", "money"), col("diff_tax", "Tax difference", "money")]
    tax = lambda rows, k: sum((r[k] for r in rows), ZERO)  # noqa: E731
    return {
        "title": "GSTR-2B reconciliation", "subtitle": f"Return period {period or '—'} vs purchases {date_from:%d/%m/%Y}–{date_to:%d/%m/%Y}",
        "summary": [
            {"label": "Matched", "value": len(matched), "type": "int"},
            {"label": "Amount mismatch", "value": len(mismatch), "type": "int"},
            {"label": "Missing in books", "value": len(missing), "type": "int"},
            {"label": "Not in 2B (ITC at risk)", "value": float(tax(not_in_2b, "book_tax")), "type": "money"},
            {"label": "ITC available in 2B", "value": float(tax([p for p in missing + matched + mismatch if p.get('itc', 'Yes') != 'No'], "portal_tax")), "type": "money"},
        ],
        "sections": [
            {"title": "Amount mismatch — check the bill with the supplier", "columns": both, "rows": mismatch, "total": None, "note": None},
            {"title": "Missing in books — record these purchases", "columns": base + [col("kind", "Type"), col("portal_taxable", "Taxable", "money"), col("portal_tax", "Tax", "money"), col("itc", "ITC available")], "rows": missing, "total": None, "note": None},
            {"title": "Not in GSTR-2B — supplier has not reported; do not claim ITC yet", "columns": base + [col("book_taxable", "Taxable", "money"), col("book_tax", "Tax", "money")], "rows": not_in_2b, "total": None, "note": None},
            {"title": "Matched", "columns": both, "rows": matched, "total": None, "note": "Invoice numbers are compared ignoring spaces, symbols and leading zeros; amounts within ₹1."},
        ],
    }
