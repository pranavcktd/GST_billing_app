import datetime as dt

from fastapi import APIRouter, HTTPException
from sqlalchemy import or_, select

from ..deps import WRITERS, BCtx
from ..gst.constants import ItemType, StockMoveType
from ..models import Item, StockMovement, VoucherLine
from ..schemas import ItemIn, ItemOut, StockAdjustIn, StockMoveOut
from ..services.ledger import item_stock

router = APIRouter(prefix="/items", tags=["items"])


def _get(ctx: BCtx, item_id: str) -> Item:
    it = ctx.db.get(Item, item_id)
    if not it or it.business_id != ctx.bid:
        raise HTTPException(404, "Item not found")
    return it


def _out(it: Item, stock) -> ItemOut:
    o = ItemOut.model_validate(it)
    o.stock = stock
    return o


@router.get("", response_model=list[ItemOut])
def list_items(ctx: BCtx, search: str | None = None, include_inactive: bool = False):
    q = select(Item).where(Item.business_id == ctx.bid).order_by(Item.name)
    if not include_inactive:
        q = q.where(Item.is_active.is_(True))
    if search:
        like = f"%{search}%"
        q = q.where(or_(Item.name.ilike(like), Item.code.ilike(like), Item.hsn_sac.ilike(like)))
    items = ctx.db.scalars(q).all()
    stock = item_stock(ctx.db, ctx.bid)
    return [_out(i, stock.get(i.id, 0)) for i in items]


@router.post("", response_model=ItemOut, status_code=201)
def create_item(data: ItemIn, ctx: BCtx):
    ctx.require(*WRITERS)
    fields = data.model_dump(exclude={"opening_stock", "opening_stock_date"})
    it = Item(business_id=ctx.bid, **fields)
    ctx.db.add(it)
    ctx.db.flush()
    if data.type == ItemType.GOODS and data.opening_stock:
        ctx.db.add(StockMovement(
            business_id=ctx.bid, item_id=it.id, date=data.opening_stock_date or dt.date.today(),
            type=StockMoveType.OPENING, qty=data.opening_stock, rate=data.purchase_price, note="Opening stock",
        ))
    ctx.db.commit()
    return _out(it, data.opening_stock if data.type == ItemType.GOODS else 0)


def _ean13(body12: str) -> str:
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body12))
    return body12 + str((10 - total % 10) % 10)


@router.post("/assign-codes")
def assign_codes(ctx: BCtx):
    """Give every item without a code an in-store EAN-13 barcode (prefix 2xx, reserved for internal use)."""
    ctx.require(*WRITERS)
    used = {c for c in ctx.db.scalars(select(Item.code).where(Item.business_id == ctx.bid, Item.code.is_not(None)))}
    seq, count = 1, 0
    for it in ctx.db.scalars(select(Item).where(Item.business_id == ctx.bid, Item.code.is_(None)).order_by(Item.name)):
        while True:
            code = _ean13(f"2{seq:011d}")
            seq += 1
            if code not in used:
                break
        it.code = code
        used.add(code)
        count += 1
    ctx.db.commit()
    return {"assigned": count}


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: str, ctx: BCtx):
    it = _get(ctx, item_id)
    return _out(it, item_stock(ctx.db, ctx.bid, [it.id]).get(it.id, 0))


@router.put("/{item_id}", response_model=ItemOut)
def update_item(item_id: str, data: ItemIn, ctx: BCtx):
    ctx.require(*WRITERS)
    it = _get(ctx, item_id)
    for k, v in data.model_dump(exclude={"opening_stock", "opening_stock_date"}).items():
        setattr(it, k, v)
    ctx.db.commit()
    return _out(it, item_stock(ctx.db, ctx.bid, [it.id]).get(it.id, 0))


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: str, ctx: BCtx):
    ctx.require(*WRITERS)
    it = _get(ctx, item_id)
    if ctx.db.scalar(select(VoucherLine.id).where(VoucherLine.item_id == it.id).limit(1)):
        it.is_active = False
    else:
        ctx.db.delete(it)
    ctx.db.commit()


@router.post("/{item_id}/adjust", response_model=ItemOut)
def adjust_stock(item_id: str, data: StockAdjustIn, ctx: BCtx):
    ctx.require(*WRITERS)
    it = _get(ctx, item_id)
    if it.type != ItemType.GOODS:
        raise HTTPException(400, "Stock is not tracked for services")
    ctx.db.add(StockMovement(
        business_id=ctx.bid, item_id=it.id, date=data.date, type=StockMoveType.ADJUSTMENT,
        qty=data.qty if data.direction == "ADD" else -data.qty, rate=it.purchase_price, note=data.note,
    ))
    ctx.db.commit()
    return _out(it, item_stock(ctx.db, ctx.bid, [it.id]).get(it.id, 0))


@router.get("/{item_id}/movements", response_model=list[StockMoveOut])
def movements(item_id: str, ctx: BCtx):
    it = _get(ctx, item_id)
    return ctx.db.scalars(
        select(StockMovement).where(StockMovement.item_id == it.id)
        .order_by(StockMovement.date.desc(), StockMovement.created_at.desc()).limit(500)
    ).all()
