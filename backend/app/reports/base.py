"""Shared building blocks for the report catalogue.

Every report returns the same shape so one frontend page can render all of them:

    {title, subtitle, summary: [{label, value, type}],
     sections: [{title, columns: [{key, label, type}], rows: [...], total: {...}, note}]}

Column types: text, money, qty, date, pct, int. A row may carry `_style`
("bold" | "head" | "sub") and `_link` (frontend path).
"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Business, Voucher

ZERO = Decimal("0")


@dataclass
class RCtx:
    db: Session
    biz: Business
    date_from: dt.date
    date_to: dt.date
    as_of: dt.date
    party_id: str | None = None
    item_id: str | None = None
    account_id: str | None = None
    loan_id: str | None = None
    category_id: str | None = None

    @property
    def bid(self) -> str:
        return self.biz.id


def col(key: str, label: str, type: str = "text") -> dict:
    return {"key": key, "label": label, "type": type}


def money(*pairs: tuple[str, str]) -> list[dict]:
    return [col(k, l, "money") for k, l in pairs]


def section(columns, rows, title=None, total=None, note=None) -> dict:
    return {"title": title, "columns": columns, "rows": rows, "total": total, "note": note}


def result(title: str, sections: list[dict], subtitle: str | None = None, summary: list[dict] | None = None) -> dict:
    return {"title": title, "subtitle": subtitle, "summary": summary or [], "sections": sections}


def stat(label: str, value, type: str = "money") -> dict:
    return {"label": label, "value": value, "type": type}


def totals(rows: list[dict], keys) -> dict:
    t = {k: ZERO for k in keys}
    for r in rows:
        if r.get("_style") in ("head", "sub"):
            continue
        for k in keys:
            t[k] += r.get(k) or ZERO
    return t


def vouchers(r: RCtx, types, date_from=None, date_to=None, include_cancelled=False, party_id=None):
    q = (select(Voucher)
         .options(selectinload(Voucher.lines), selectinload(Voucher.allocations))
         .where(Voucher.business_id == r.bid, Voucher.type.in_(list(types)))
         .order_by(Voucher.date, Voucher.number))
    if date_from:
        q = q.where(Voucher.date >= date_from)
    if date_to:
        q = q.where(Voucher.date <= date_to)
    if not include_cancelled:
        q = q.where(Voucher.cancelled.is_(False))
    if party_id:
        q = q.where(Voucher.party_id == party_id)
    return r.db.scalars(q).all()


def group_sum(items, key_fn, fields) -> dict:
    out: dict = defaultdict(lambda: {f: ZERO for f in fields})
    for it in items:
        k = key_fn(it)
        for f, v in fields.items():
            out[k][f] += v(it)
    return out


def link_doc(v_id: str) -> str:
    return f"/doc/{v_id}"


def pct(part: Decimal, whole: Decimal) -> Decimal:
    return (part * 100 / whole).quantize(Decimal("0.01")) if whole else ZERO
