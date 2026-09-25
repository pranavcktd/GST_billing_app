"""Godowns (stock locations) and stock transfers between them."""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Godown, Item, StockMovement

ZERO = Decimal("0")


def default_godown(db: Session, business_id: str) -> Godown:
    g = db.scalar(select(Godown).where(Godown.business_id == business_id, Godown.is_default.is_(True)))
    if g is None:
        g = Godown(business_id=business_id, name="Main Godown", is_default=True)
        db.add(g)
        db.flush()
    return g


def resolve_godown(db: Session, business_id: str, godown_id: str | None) -> Godown:
    if not godown_id:
        return default_godown(db, business_id)
    g = db.get(Godown, godown_id)
    if not g or g.business_id != business_id:
        raise HTTPException(404, "Godown not found")
    return g


def stock_by_godown(db: Session, business_id: str, as_of: dt.date | None = None,
                    item_id: str | None = None) -> dict[tuple[str, str], Decimal]:
    """{(item_id, godown_id): qty}. Movements without a godown belong to the default godown."""
    default_id = default_godown(db, business_id).id
    q = (select(StockMovement.item_id, StockMovement.godown_id, func.sum(StockMovement.qty))
         .where(StockMovement.business_id == business_id)
         .group_by(StockMovement.item_id, StockMovement.godown_id))
    if as_of:
        q = q.where(StockMovement.date <= as_of)
    if item_id:
        q = q.where(StockMovement.item_id == item_id)
    out: dict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
    for iid, gid, qty in db.execute(q):
        out[(iid, gid or default_id)] += qty or ZERO
    return dict(out)


def godown_stock_values(db: Session, business_id: str) -> dict[str, Decimal]:
    prices = {i.id: i.purchase_price or ZERO for i in db.scalars(select(Item).where(Item.business_id == business_id))}
    vals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for (iid, gid), q in stock_by_godown(db, business_id).items():
        if q > 0:
            vals[gid] += (q * prices.get(iid, ZERO)).quantize(Decimal("0.01"))
    return dict(vals)
