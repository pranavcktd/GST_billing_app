"""Manufacturing: bills of materials and production entries.

A production consumes raw materials (CONSUMPTION stock movements, out) and adds the finished item
(PRODUCTION movement, in) at cost = materials at their weighted-average cost + other costs
(labour / overheads) for the batch. Profit and the balance sheet stay consistent because closing
stock is valued the same way everywhere.
"""

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import BCtx
from ..gst.constants import ItemType, StockMoveType
from ..models import Bom, BomLine, Item, Production, StockMovement
from ..reports.accounting import avg_costs
from ..services.godowns import resolve_godown, stock_by_godown
from ..services.numbering import allocate_number
from ..services.platform_audit import log

router = APIRouter(tags=["manufacturing"])
CENT = Decimal("0.01")


def _item(ctx: BCtx, iid: str) -> Item:
    it = ctx.db.get(Item, iid)
    if it is None or it.business_id != ctx.bid:
        raise HTTPException(404, "Item not found")
    return it


def _bom(ctx: BCtx, bid: str) -> Bom:
    b = ctx.db.get(Bom, bid)
    if b is None or b.business_id != ctx.bid:
        raise HTTPException(404, "Bill of materials not found")
    return b


def _bom_out(ctx: BCtx, b: Bom, names: dict | None = None) -> dict:
    names = names if names is not None else {i.id: i for i in ctx.db.scalars(select(Item).where(Item.business_id == ctx.bid))}
    it = names.get(b.item_id)
    return dict(id=b.id, name=b.name, item_id=b.item_id, item=it.name if it else None, unit=it.unit if it else None,
                output_qty=float(b.output_qty), other_cost=float(b.other_cost), notes=b.notes, is_active=b.is_active,
                lines=[dict(item_id=l.item_id, item=names[l.item_id].name if l.item_id in names else None,
                            unit=names[l.item_id].unit if l.item_id in names else None, qty=float(l.qty)) for l in b.lines])


# ---------------------------------------------------------------- bills of materials
class BomLineIn(BaseModel):
    item_id: str
    qty: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class BomIn(BaseModel):
    item_id: str
    name: str | None = Field(None, max_length=200)
    output_qty: Decimal = Field(Decimal("1"), gt=0, max_digits=14, decimal_places=3)
    other_cost: Decimal = Field(Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(None, max_length=2000)
    is_active: bool = True
    lines: list[BomLineIn] = Field(min_length=1, max_length=200)


def _apply_bom(ctx: BCtx, b: Bom, data: BomIn) -> None:
    out_item = _item(ctx, data.item_id)
    if out_item.type != ItemType.GOODS:
        raise HTTPException(422, "The finished item must be goods")
    seen = set()
    for l in data.lines:
        it = _item(ctx, l.item_id)
        if it.id == out_item.id:
            raise HTTPException(422, "An item cannot be a material of itself")
        if it.id in seen:
            raise HTTPException(422, f"{it.name} is listed twice")
        seen.add(it.id)
    b.item_id, b.name = out_item.id, data.name or f"{out_item.name} — standard"
    b.output_qty, b.other_cost, b.notes, b.is_active = data.output_qty, data.other_cost, data.notes, data.is_active
    b.lines = [BomLine(item_id=l.item_id, qty=l.qty, sort_order=i) for i, l in enumerate(data.lines)]


@router.get("/boms")
def list_boms(ctx: BCtx):
    ctx.need("items", "view")
    names = {i.id: i for i in ctx.db.scalars(select(Item).where(Item.business_id == ctx.bid))}
    return [_bom_out(ctx, b, names) for b in ctx.db.scalars(select(Bom).where(Bom.business_id == ctx.bid).order_by(Bom.name))]


@router.post("/boms", status_code=201)
def create_bom(data: BomIn, ctx: BCtx):
    ctx.need("items", "create")
    b = Bom(business_id=ctx.bid)
    _apply_bom(ctx, b, data)
    ctx.db.add(b)
    ctx.db.commit()
    return _bom_out(ctx, b)


@router.put("/boms/{bom_id}")
def update_bom(bom_id: str, data: BomIn, ctx: BCtx):
    ctx.need("items", "edit")
    b = _bom(ctx, bom_id)
    _apply_bom(ctx, b, data)
    ctx.db.commit()
    return _bom_out(ctx, b)


@router.delete("/boms/{bom_id}", status_code=204)
def delete_bom(bom_id: str, ctx: BCtx):
    ctx.need("items", "delete")
    ctx.db.delete(_bom(ctx, bom_id))
    ctx.db.commit()


def _plan(ctx: BCtx, b: Bom, qty: Decimal, date: dt.date, godown_id: str) -> dict:
    """Materials needed for `qty` of the finished item, stock in the godown, cost at average rates."""
    factor = qty / b.output_qty
    costs = avg_costs(ctx.db, ctx.bid, date)
    stock = stock_by_godown(ctx.db, ctx.bid, as_of=date)
    rows, material = [], Decimal("0")
    for l in b.lines:
        it = ctx.db.get(Item, l.item_id)
        need = (l.qty * factor).quantize(Decimal("0.001"))
        rate = Decimal(costs.get(l.item_id, it.purchase_price or 0)).quantize(CENT)
        amount = (need * rate).quantize(CENT)
        have = stock.get((l.item_id, godown_id), Decimal("0")) if it.type == ItemType.GOODS else None
        material += amount
        rows.append(dict(item_id=it.id, name=it.name, unit=it.unit, qty=need, rate=rate, amount=amount,
                         in_stock=have, short=max(need - have, Decimal("0")) if have is not None else Decimal("0")))
    other = (b.other_cost * factor).quantize(CENT)
    total = material + other
    return dict(lines=rows, material_cost=material, other_cost=other, total_cost=total,
                unit_cost=(total / qty).quantize(CENT) if qty else Decimal("0"))


@router.get("/boms/{bom_id}/plan")
def plan(bom_id: str, ctx: BCtx, qty: Decimal, date: dt.date | None = None, godown_id: str | None = None):
    ctx.need("items", "view")
    b = _bom(ctx, bom_id)
    g = resolve_godown(ctx.db, ctx.bid, godown_id)
    return _plan(ctx, b, qty, date or dt.date.today(), g.id)


# ---------------------------------------------------------------- production
class ProductionIn(BaseModel):
    bom_id: str
    qty: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    date: dt.date
    godown_id: str | None = None
    other_cost: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)  # override the BOM's per-batch cost
    batch_no: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)
    allow_shortage: bool = False


def _p_out(p: Production, item_name: str | None = None) -> dict:
    return dict(id=p.id, number=p.number, date=p.date, item_id=p.item_id, item=item_name, qty=float(p.qty), batch_no=p.batch_no,
                material_cost=float(p.material_cost), other_cost=float(p.other_cost), unit_cost=float(p.unit_cost),
                total_cost=float(p.material_cost + p.other_cost), consumed=p.consumed, notes=p.notes, created_by=p.created_by)


@router.post("/productions", status_code=201)
def produce(data: ProductionIn, ctx: BCtx, request: Request):
    ctx.need("items", "create")
    b = _bom(ctx, data.bom_id)
    if not b.is_active:
        raise HTTPException(400, "This bill of materials is inactive")
    g = resolve_godown(ctx.db, ctx.bid, data.godown_id)
    pl = _plan(ctx, b, data.qty, data.date, g.id)
    shortages = [f"{r['name']}: need {r['qty']:f}, have {r['in_stock']:f}" for r in pl["lines"] if r["short"] > 0]
    if shortages and not data.allow_shortage:
        raise HTTPException(409, {"message": "Not enough stock of: " + "; ".join(shortages), "code": "SHORTAGE"})
    other = data.other_cost if data.other_cost is not None else pl["other_cost"]
    total = pl["material_cost"] + other
    number = allocate_number(ctx.db, ctx.bid, "PRODUCTION", "PRD", data.date,
                             lambda n: ctx.db.scalar(select(Production.id).where(Production.business_id == ctx.bid, Production.number == n)) is not None)
    p = Production(business_id=ctx.bid, number=number, date=data.date, bom_id=b.id, item_id=b.item_id, qty=data.qty, godown_id=g.id,
                   batch_no=data.batch_no, material_cost=pl["material_cost"], other_cost=other,
                   unit_cost=(total / data.qty).quantize(CENT), notes=data.notes, created_by=ctx.user.name,
                   consumed=[dict(item_id=r["item_id"], name=r["name"], unit=r["unit"], qty=float(r["qty"]), rate=float(r["rate"]),
                                  amount=float(r["amount"])) for r in pl["lines"]])
    ctx.db.add(p)
    ctx.db.flush()
    for r in pl["lines"]:
        it = ctx.db.get(Item, r["item_id"])
        if it.type != ItemType.GOODS:
            continue
        ctx.db.add(StockMovement(business_id=ctx.bid, item_id=r["item_id"], date=data.date, type=StockMoveType.CONSUMPTION,
                                 qty=-r["qty"], rate=r["rate"], godown_id=g.id, production_id=p.id, note=f"Used in {number}"))
    ctx.db.add(StockMovement(business_id=ctx.bid, item_id=b.item_id, date=data.date, type=StockMoveType.PRODUCTION, qty=data.qty,
                             rate=p.unit_cost, godown_id=g.id, production_id=p.id, batch_no=data.batch_no, note=f"Produced in {number}"))
    log(ctx.db, ctx.user, "CREATE", "production", f"Production {number}: {data.qty:f} × {b.name}", entity_id=p.id,
        business_id=ctx.bid, request=request)
    ctx.db.commit()
    return {**_p_out(p, ctx.db.get(Item, b.item_id).name), "shortages": shortages}


@router.get("/productions")
def list_productions(ctx: BCtx, date_from: dt.date | None = None, date_to: dt.date | None = None):
    ctx.need("items", "view")
    q = select(Production).where(Production.business_id == ctx.bid).order_by(Production.date.desc(), Production.created_at.desc())
    if date_from:
        q = q.where(Production.date >= date_from)
    if date_to:
        q = q.where(Production.date <= date_to)
    names = dict(ctx.db.execute(select(Item.id, Item.name).where(Item.business_id == ctx.bid)).all())
    return [_p_out(p, names.get(p.item_id)) for p in ctx.db.scalars(q.limit(1000))]


@router.delete("/productions/{pid}", status_code=204)
def delete_production(pid: str, ctx: BCtx, request: Request):
    """Undo a production: its stock movements are removed with it."""
    ctx.need("items", "delete")
    p = ctx.db.get(Production, pid)
    if p is None or p.business_id != ctx.bid:
        raise HTTPException(404, "Production not found")
    log(ctx.db, ctx.user, "DELETE", "production", f"Production {p.number} deleted", entity_id=p.id, business_id=ctx.bid, request=request)
    ctx.db.delete(p)
    ctx.db.commit()
