"""Price lists (customer-specific selling rates) and the 'last rate charged' lookup for invoices."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from ..deps import BCtx
from ..gst.constants import VoucherType
from ..models import Item, Party, PriceList, PriceListItem, Voucher, VoucherLine

router = APIRouter(tags=["price lists"])
CENT = Decimal("0.01")


def _get(ctx: BCtx, pid: str) -> PriceList:
    pl = ctx.db.get(PriceList, pid)
    if pl is None or pl.business_id != ctx.bid:
        raise HTTPException(404, "Price list not found")
    return pl


def _out(ctx: BCtx, pl: PriceList, counts: dict | None = None) -> dict:
    items = (counts or {}).get(pl.id) if counts is not None else ctx.db.scalar(
        select(func.count()).select_from(PriceListItem).where(PriceListItem.price_list_id == pl.id))
    parties = ctx.db.scalar(select(func.count()).select_from(Party).where(Party.price_list_id == pl.id))
    return dict(id=pl.id, name=pl.name, based_on=pl.based_on, adjust_pct=float(pl.adjust_pct), note=pl.note,
                is_active=pl.is_active, special_rates=items or 0, parties=parties or 0)


def default_rate(pl: PriceList, it: Item) -> Decimal:
    base = (it.mrp if pl.based_on == "MRP" and it.mrp else it.sale_price) or Decimal("0")
    return (base * (100 + pl.adjust_pct) / 100).quantize(CENT)


@router.get("/price-lists")
def list_price_lists(ctx: BCtx):
    ctx.need("items", "view")
    rows = ctx.db.scalars(select(PriceList).where(PriceList.business_id == ctx.bid).order_by(PriceList.name)).all()
    counts = dict(ctx.db.execute(select(PriceListItem.price_list_id, func.count()).where(
        PriceListItem.price_list_id.in_([r.id for r in rows])).group_by(PriceListItem.price_list_id)).all()) if rows else {}
    return [_out(ctx, r, counts) for r in rows]


class ListIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    based_on: Literal["SALE_PRICE", "MRP"] = "SALE_PRICE"
    adjust_pct: Decimal = Field(Decimal("0"), ge=-100, le=1000)
    note: str | None = Field(None, max_length=300)
    is_active: bool = True


@router.post("/price-lists", status_code=201)
def create(data: ListIn, ctx: BCtx):
    ctx.need("items", "edit")
    pl = PriceList(business_id=ctx.bid, **data.model_dump())
    ctx.db.add(pl)
    ctx.db.commit()
    return _out(ctx, pl)


@router.put("/price-lists/{pid}")
def update(pid: str, data: ListIn, ctx: BCtx):
    ctx.need("items", "edit")
    pl = _get(ctx, pid)
    for k, v in data.model_dump().items():
        setattr(pl, k, v)
    ctx.db.commit()
    return _out(ctx, pl)


@router.delete("/price-lists/{pid}", status_code=204)
def remove(pid: str, ctx: BCtx):
    ctx.need("items", "edit")
    pl = _get(ctx, pid)
    for p in ctx.db.scalars(select(Party).where(Party.price_list_id == pl.id)):
        p.price_list_id = None
    ctx.db.delete(pl)
    ctx.db.commit()


@router.get("/price-lists/{pid}/items")
def items(pid: str, ctx: BCtx):
    """Every goods/service item with its normal price, the list's default rate and any special rate."""
    ctx.need("items", "view")
    pl = _get(ctx, pid)
    special = {r.item_id: r.rate for r in ctx.db.scalars(select(PriceListItem).where(PriceListItem.price_list_id == pl.id))}
    rows = ctx.db.scalars(select(Item).where(Item.business_id == ctx.bid, Item.is_active.is_(True)).order_by(Item.name)).all()
    return [dict(item_id=i.id, name=i.name, code=i.code, unit=i.unit, sale_price=float(i.sale_price), mrp=float(i.mrp) if i.mrp else None,
                 tax_inclusive=i.sale_price_tax_inclusive, default_rate=float(default_rate(pl, i)),
                 special_rate=float(special[i.id]) if i.id in special else None) for i in rows]


class RatesIn(BaseModel):
    rates: dict[str, Decimal | None]  # item_id → special rate (None removes it)


@router.put("/price-lists/{pid}/items")
def set_rates(pid: str, data: RatesIn, ctx: BCtx):
    ctx.need("items", "edit")
    pl = _get(ctx, pid)
    ids = list(data.rates)
    valid = set(ctx.db.scalars(select(Item.id).where(Item.business_id == ctx.bid, Item.id.in_(ids))))
    existing = {r.item_id: r for r in ctx.db.scalars(select(PriceListItem).where(PriceListItem.price_list_id == pl.id,
                                                                                PriceListItem.item_id.in_(ids)))}
    for item_id, rate in data.rates.items():
        if item_id not in valid:
            continue
        if rate is None:
            if item_id in existing:
                ctx.db.delete(existing[item_id])
        elif rate < 0:
            raise HTTPException(422, "Rates cannot be negative")
        elif item_id in existing:
            existing[item_id].rate = rate.quantize(CENT)
        else:
            ctx.db.add(PriceListItem(price_list_id=pl.id, item_id=item_id, rate=rate.quantize(CENT)))
    ctx.db.commit()
    return _out(ctx, pl)


@router.delete("/price-lists/{pid}/items", status_code=204)
def clear_rates(pid: str, ctx: BCtx):
    ctx.need("items", "edit")
    pl = _get(ctx, pid)
    ctx.db.execute(delete(PriceListItem).where(PriceListItem.price_list_id == pl.id))
    ctx.db.commit()


@router.get("/parties/{party_id}/rates")
def party_rates(party_id: str, ctx: BCtx):
    """Selling rates for this customer (from their price list); items not listed use the list's rule."""
    ctx.need("sales", "view")
    party = ctx.db.get(Party, party_id)
    if party is None or party.business_id != ctx.bid:
        raise HTTPException(404, "Party not found")
    if not party.price_list_id:
        return {"price_list": None, "rates": {}}
    pl = ctx.db.get(PriceList, party.price_list_id)
    if pl is None or not pl.is_active:
        return {"price_list": None, "rates": {}}
    special = {r.item_id: r.rate for r in ctx.db.scalars(select(PriceListItem).where(PriceListItem.price_list_id == pl.id))}
    rates = {i.id: float(special.get(i.id, default_rate(pl, i)))
             for i in ctx.db.scalars(select(Item).where(Item.business_id == ctx.bid, Item.is_active.is_(True)))}
    return {"price_list": {"id": pl.id, "name": pl.name, "adjust_pct": float(pl.adjust_pct), "based_on": pl.based_on}, "rates": rates}


@router.get("/items/{item_id}/last-rate")
def last_rate(item_id: str, party_id: str, ctx: BCtx, type: str = "SALE"):
    """The rate this item was last billed to / bought from this party."""
    ctx.need("sales" if type == "SALE" else "purchases", "view")
    vtype = VoucherType.SALE if type == "SALE" else VoucherType.PURCHASE
    row = ctx.db.execute(select(VoucherLine.rate, VoucherLine.discount_pct, VoucherLine.tax_inclusive, Voucher.date, Voucher.number)
                         .join(Voucher, Voucher.id == VoucherLine.voucher_id)
                         .where(Voucher.business_id == ctx.bid, Voucher.party_id == party_id, Voucher.type == vtype,
                                Voucher.cancelled.is_(False), VoucherLine.item_id == item_id)
                         .order_by(Voucher.date.desc(), Voucher.created_at.desc()).limit(1)).first()
    if not row:
        return None
    rate, disc, incl, date, number = row
    return {"rate": float(rate), "discount_pct": float(disc), "tax_inclusive": incl, "date": date, "number": number}
