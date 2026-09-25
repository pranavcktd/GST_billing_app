from decimal import Decimal

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..deps import BCtx
from ..gst.constants import ItemType, StockMoveType
from ..models import Godown, Item, StockMovement, StockTransfer, Voucher
from ..schemas import GodownIn, GodownOut, StockTransferIn
from ..services.godowns import default_godown, godown_stock_values, resolve_godown, stock_by_godown
from ..services.numbering import allocate_number
from ..services.plans import check_godown_limit

router = APIRouter(tags=["godowns"])


def _owned(ctx: BCtx, gid: str) -> Godown:
    g = ctx.db.get(Godown, gid)
    if not g or g.business_id != ctx.bid:
        raise HTTPException(404, "Godown not found")
    return g


@router.get("/godowns", response_model=list[GodownOut])
def list_godowns(ctx: BCtx):
    if not any(ctx.can(m, "create") for m in ("sales", "purchases")):
        ctx.need("items", "view")
    default_godown(ctx.db, ctx.bid)
    ctx.db.commit()
    values = godown_stock_values(ctx.db, ctx.bid)
    out = []
    for g in ctx.db.scalars(select(Godown).where(Godown.business_id == ctx.bid)
                            .order_by(Godown.is_default.desc(), Godown.name)):
        o = GodownOut.model_validate(g)
        o.stock_value = values.get(g.id, Decimal("0"))
        out.append(o)
    return out


@router.post("/godowns", response_model=GodownOut, status_code=201)
def create_godown(data: GodownIn, ctx: BCtx):
    ctx.need("items", "create")
    default_godown(ctx.db, ctx.bid)
    check_godown_limit(ctx.db, ctx.bid)
    g = Godown(business_id=ctx.bid, **data.model_dump())
    ctx.db.add(g)
    ctx.db.commit()
    return g


@router.put("/godowns/{gid}", response_model=GodownOut)
def update_godown(gid: str, data: GodownIn, ctx: BCtx):
    ctx.need("items", "edit")
    g = _owned(ctx, gid)
    g.name, g.address = data.name, data.address
    ctx.db.commit()
    return g


@router.delete("/godowns/{gid}", status_code=204)
def delete_godown(gid: str, ctx: BCtx):
    ctx.need("items", "delete")
    g = _owned(ctx, gid)
    if g.is_default:
        raise HTTPException(400, "The main godown cannot be deleted")
    if any(q for (_, gd), q in stock_by_godown(ctx.db, ctx.bid).items() if gd == g.id):
        raise HTTPException(400, "Move the stock out of this godown first")
    used = ctx.db.scalar(select(StockMovement.id).where(StockMovement.godown_id == g.id).limit(1)) or \
        ctx.db.scalar(select(Voucher.id).where(Voucher.godown_id == g.id).limit(1))
    if used:
        g.is_active = False
    else:
        ctx.db.delete(g)
    ctx.db.commit()


@router.get("/items/{item_id}/godowns")
def item_godown_stock(item_id: str, ctx: BCtx):
    ctx.need("items", "view")
    it = ctx.db.get(Item, item_id)
    if not it or it.business_id != ctx.bid:
        raise HTTPException(404, "Item not found")
    names = {g.id: g.name for g in ctx.db.scalars(select(Godown).where(Godown.business_id == ctx.bid))}
    return [{"godown_id": gid, "godown": names.get(gid, ""), "qty": float(q)}
            for (_, gid), q in stock_by_godown(ctx.db, ctx.bid, item_id=item_id).items() if q]


# ---------------------------------------------------------------- stock transfers
@router.get("/stock-transfers")
def list_transfers(ctx: BCtx):
    ctx.need("items", "view")
    names = {g.id: g.name for g in ctx.db.scalars(select(Godown).where(Godown.business_id == ctx.bid))}
    out = []
    for t in ctx.db.scalars(select(StockTransfer).where(StockTransfer.business_id == ctx.bid)
                            .order_by(StockTransfer.date.desc(), StockTransfer.created_at.desc()).limit(500)):
        moves = ctx.db.scalars(select(StockMovement).where(StockMovement.transfer_id == t.id,
                                                           StockMovement.qty > 0)).all()
        items = {i.id: i.name for i in ctx.db.scalars(select(Item).where(Item.id.in_([m.item_id for m in moves])))}
        out.append(dict(id=t.id, number=t.number, date=t.date, from_godown=names.get(t.from_godown_id),
                        to_godown=names.get(t.to_godown_id), note=t.note,
                        lines=[dict(item=items.get(m.item_id), qty=float(m.qty), batch_no=m.batch_no) for m in moves]))
    return out


@router.post("/stock-transfers", status_code=201)
def create_transfer(data: StockTransferIn, ctx: BCtx):
    ctx.need("items", "create")
    src = resolve_godown(ctx.db, ctx.bid, data.from_godown_id)
    dst = resolve_godown(ctx.db, ctx.bid, data.to_godown_id)
    if src.id == dst.id:
        raise HTTPException(400, "Choose two different godowns")
    items = {i.id: i for i in ctx.db.scalars(select(Item).where(
        Item.business_id == ctx.bid, Item.id.in_([l.item_id for l in data.lines])))}
    stock = stock_by_godown(ctx.db, ctx.bid, as_of=data.date)
    for l in data.lines:
        it = items.get(l.item_id)
        if not it or it.type != ItemType.GOODS:
            raise HTTPException(400, "Only stock items can be transferred")
        available = stock.get((it.id, src.id), Decimal("0"))
        if l.qty > available:
            raise HTTPException(400, f"Only {available.normalize()} {it.unit} of {it.name} in {src.name}")
    t = StockTransfer(business_id=ctx.bid, date=data.date, from_godown_id=src.id, to_godown_id=dst.id, note=data.note,
                      number=allocate_number(ctx.db, ctx.bid, "STOCK_TRANSFER", ctx.business.transfer_prefix, data.date,
                                             lambda n: ctx.db.scalar(select(StockTransfer.id).where(
                                                 StockTransfer.business_id == ctx.bid, StockTransfer.number == n)) is not None))
    ctx.db.add(t)
    ctx.db.flush()
    for l in data.lines:
        it = items[l.item_id]
        for gid, sign in ((src.id, -1), (dst.id, 1)):
            ctx.db.add(StockMovement(business_id=ctx.bid, item_id=it.id, date=data.date, type=StockMoveType.TRANSFER,
                                     qty=sign * l.qty, rate=it.purchase_price, godown_id=gid, transfer_id=t.id,
                                     batch_no=l.batch_no, note=f"Transfer {t.number}"))
    ctx.db.commit()
    return {"id": t.id, "number": t.number}


@router.delete("/stock-transfers/{tid}", status_code=204)
def delete_transfer(tid: str, ctx: BCtx):
    ctx.need("items", "delete")
    t = ctx.db.get(StockTransfer, tid)
    if not t or t.business_id != ctx.bid:
        raise HTTPException(404, "Transfer not found")
    ctx.db.delete(t)
    ctx.db.commit()

