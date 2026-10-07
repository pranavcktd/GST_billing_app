"""Selling more than is in stock.

Each business chooses (Settings → Business → Stock control):
    WARN  (default) — the bill is saved only after the user confirms "sell anyway" (`allow_negative`)
    BLOCK           — owners / admins / store managers may confirm; other staff need a manager's approval PIN
    ALLOW           — no check

Checked for documents that take goods out: sale invoices (incl. POS), delivery challans and purchase returns.
Stock is counted per godown (the bill's godown); an edited bill's own earlier quantities are already reversed
because the check runs after the bill's new stock movements are written. Services are never checked.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from ..deps import Ctx
from ..gst.constants import Role
from ..models import Item, StockMovement, Voucher
from .godowns import stock_by_godown
from .platform_audit import log

MODES = ("WARN", "BLOCK", "ALLOW")
ZERO = Decimal("0")


def _qty(x: Decimal) -> str:
    return f"{x.normalize():f}" if x == x.to_integral() else f"{x:.3f}".rstrip("0").rstrip(".")


def shortages(ctx: Ctx, v: Voucher) -> list[dict]:
    """Goods this document takes out that leave the stock (in that godown) below zero."""
    out_moves = ctx.db.scalars(select(StockMovement).where(StockMovement.voucher_id == v.id, StockMovement.qty < 0)).all()
    if not out_moves:
        return []
    taken: dict[tuple[str, str | None], Decimal] = {}
    for m in out_moves:
        key = (m.item_id, m.godown_id)
        taken[key] = taken.get(key, ZERO) - m.qty
    stock = stock_by_godown(ctx.db, ctx.bid)
    from .godowns import default_godown

    default_id = default_godown(ctx.db, ctx.bid).id
    result = []
    for (item_id, godown_id), qty in taken.items():
        after = stock.get((item_id, godown_id or default_id), ZERO)
        if after < 0:
            item = ctx.db.get(Item, item_id)
            result.append(dict(item_id=item_id, name=item.name if item else "Item", unit=(item.unit if item else "") or "",
                               available=float(after + qty), qty=float(qty), after=float(after)))
    return result


def enforce(ctx: Ctx, v: Voucher, allow: bool, request=None) -> None:
    mode = (getattr(ctx.business, "stock_control", None) or "WARN").upper()
    if mode == "ALLOW":
        return
    short = shortages(ctx, v)
    if not short:
        return
    text = "; ".join(f"{s['name']}: {_qty(Decimal(str(s['available'])))} in stock, billing {_qty(Decimal(str(s['qty'])))} {s['unit']}".strip()
                     for s in short)
    manager = ctx.role in (Role.OWNER, Role.ADMIN, Role.MANAGER)
    pin_ok = ctx.approval_pin_valid()
    if (mode == "WARN" and allow) or (mode == "BLOCK" and ((allow and manager) or pin_ok)):
        log(ctx.db, ctx.user, "STOCK", "voucher", f"Billed below stock on {v.number}: {text}" + (" (approved with PIN)" if pin_ok else ""),
            entity_id=v.id, business_id=ctx.bid, request=request)
        return
    if mode == "BLOCK" and not manager:
        raise HTTPException(403, {"message": f"Not enough stock — {text}. A manager's approval is needed to bill below stock",
                                  "code": "APPROVAL_REQUIRED"})
    raise HTTPException(409, {"message": f"Not enough stock — {text}", "code": "STOCK_SHORT", "mode": mode, "shortages": short})
