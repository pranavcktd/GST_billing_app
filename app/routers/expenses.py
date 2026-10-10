"""Expense categories and expense items (the expense documents themselves are vouchers of type EXPENSE)."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from ..deps import BCtx, DB, SuperAdmin
from ..gst.constants import ExpenseKind, VoucherType
from ..models import ExpenseCategory, ExpenseItem, Voucher, VoucherLine
from ..services import config_store
from ..services import expense_templates as ET
from ..services.platform_audit import log
from ..schemas import ExpenseCategoryIn, ExpenseCategoryOut, ExpenseItemIn, ExpenseItemOut

router = APIRouter(prefix="/expenses", tags=["expenses"])

DEFAULT_CATEGORIES = [
    ("Manufacturing Expenses", ExpenseKind.DIRECT),
    ("Freight & Transport Inward", ExpenseKind.DIRECT),
    ("Labour / Wages", ExpenseKind.DIRECT),
    ("Rent", ExpenseKind.INDIRECT),
    ("Salary", ExpenseKind.INDIRECT),
    ("Electricity", ExpenseKind.INDIRECT),
    ("Petrol & Fuel", ExpenseKind.INDIRECT),
    ("Transport & Travel", ExpenseKind.INDIRECT),
    ("Tea & Refreshments", ExpenseKind.INDIRECT, True),
    ("Telephone & Internet", ExpenseKind.INDIRECT),
    ("Repairs & Maintenance", ExpenseKind.INDIRECT),
    ("Printing & Stationery", ExpenseKind.INDIRECT),
    ("Professional Fees", ExpenseKind.INDIRECT),
    ("Bank Charges", ExpenseKind.INDIRECT),
    ("Advertisement", ExpenseKind.INDIRECT),
    ("Miscellaneous", ExpenseKind.INDIRECT),
]


def seed_categories(db, business_id: str) -> None:
    """Old built-in set — used only when restoring old backups (new businesses import from the standard list)."""
    blocked = {n.lower() for n in config_store.get("blocked_itc_categories")}
    for name, kind, *_ in DEFAULT_CATEGORIES:
        db.add(ExpenseCategory(business_id=business_id, name=name, kind=kind, itc_blocked=name.lower() in blocked))


def _owned(ctx: BCtx, model, obj_id: str, label: str):
    obj = ctx.db.get(model, obj_id)
    if not obj or obj.business_id != ctx.bid:
        raise HTTPException(404, f"{label} not found")
    return obj


@router.get("/categories", response_model=list[ExpenseCategoryOut])
def list_categories(ctx: BCtx):
    ctx.need("expenses", "view")
    totals = dict(ctx.db.execute(
        select(Voucher.expense_category_id, func.sum(Voucher.grand_total))
        .where(Voucher.business_id == ctx.bid, Voucher.type == VoucherType.EXPENSE, Voucher.cancelled.is_(False))
        .group_by(Voucher.expense_category_id)).all())
    out = []
    for c in ctx.db.scalars(select(ExpenseCategory).where(ExpenseCategory.business_id == ctx.bid)
                            .order_by(ExpenseCategory.name)):
        o = ExpenseCategoryOut.model_validate(c)
        o.total = totals.get(c.id) or 0
        out.append(o)
    return out


@router.post("/categories", response_model=ExpenseCategoryOut, status_code=201)
def create_category(data: ExpenseCategoryIn, ctx: BCtx):
    ctx.need("expenses", "create")
    c = ExpenseCategory(business_id=ctx.bid, **data.model_dump())
    ctx.db.add(c)
    ctx.db.commit()
    return c


@router.put("/categories/{cat_id}", response_model=ExpenseCategoryOut)
def update_category(cat_id: str, data: ExpenseCategoryIn, ctx: BCtx):
    ctx.need("expenses", "edit")
    c = _owned(ctx, ExpenseCategory, cat_id, "Category")
    c.name, c.kind, c.itc_blocked = data.name, data.kind, data.itc_blocked
    ctx.db.commit()
    return c


@router.delete("/categories/{cat_id}", status_code=204)
def delete_category(cat_id: str, ctx: BCtx):
    ctx.need("expenses", "delete")
    c = _owned(ctx, ExpenseCategory, cat_id, "Category")
    if ctx.db.scalar(select(Voucher.id).where(Voucher.expense_category_id == c.id).limit(1)):
        c.is_active = False
    else:
        ctx.db.delete(c)
    ctx.db.commit()


@router.get("/items", response_model=list[ExpenseItemOut])
def list_items(ctx: BCtx):
    ctx.need("expenses", "view")
    return ctx.db.scalars(select(ExpenseItem).where(ExpenseItem.business_id == ctx.bid)
                          .order_by(ExpenseItem.name)).all()


@router.post("/items", response_model=ExpenseItemOut, status_code=201)
def create_item(data: ExpenseItemIn, ctx: BCtx):
    ctx.need("expenses", "create")
    if data.category_id:
        _owned(ctx, ExpenseCategory, data.category_id, "Category")
    it = ExpenseItem(business_id=ctx.bid, **data.model_dump())
    ctx.db.add(it)
    ctx.db.commit()
    return it


@router.put("/items/{item_id}", response_model=ExpenseItemOut)
def update_item(item_id: str, data: ExpenseItemIn, ctx: BCtx):
    ctx.need("expenses", "edit")
    it = _owned(ctx, ExpenseItem, item_id, "Expense item")
    if data.category_id:
        _owned(ctx, ExpenseCategory, data.category_id, "Category")
    for k, v in data.model_dump().items():
        setattr(it, k, v)
    ctx.db.commit()
    return it


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, ctx: BCtx):
    ctx.need("expenses", "delete")
    it = _owned(ctx, ExpenseItem, item_id, "Expense item")
    if ctx.db.scalar(select(VoucherLine.id).where(VoucherLine.expense_item_id == it.id).limit(1)):
        it.is_active = False
    else:
        ctx.db.delete(it)
    ctx.db.commit()


# ---------------------------------------------------------------- standard categories (services/expense_templates.py)
@router.get("/templates")
def templates(ctx: BCtx):
    ctx.need("expenses", "view")
    return ET.for_business(ctx.db, ctx.business)


class ImportIn(BaseModel):
    names: list[str] | None = None  # None = all


@router.post("/templates/import")
def import_templates(data: ImportIn, ctx: BCtx):
    ctx.need("expenses", "create")
    out = ET.import_into(ctx.db, ctx.business, data.names)
    ctx.db.commit()
    return out


@router.post("/templates/skip")
def skip_templates(ctx: BCtx):
    ctx.need("expenses", "view")
    ctx.business.expense_setup = ctx.business.expense_setup or "SKIPPED"
    ctx.db.commit()
    return {"choice": ctx.business.expense_setup}


admin_router = APIRouter(prefix="/admin/expense-templates", tags=["super admin"])


@admin_router.get("")
def admin_templates(db: DB, _: SuperAdmin):
    return {"categories": ET.get(db), "built_in": ET.get(db) is ET.BUILT_IN, "gst_rates": [float(r) for r in config_store.rates_on()]}


class TemplatesIn(BaseModel):
    categories: list[dict[str, Any]]


@admin_router.put("")
def save_templates(data: TemplatesIn, db: DB, me: SuperAdmin, request: Request):
    cats = ET.save(db, data.categories)
    log(db, me, "CONFIG", "expense templates", f"Standard expense categories saved ({len(cats)} categories)", request=request)
    db.commit()
    return admin_templates(db, me)


@admin_router.delete("")
def reset_templates(db: DB, me: SuperAdmin, request: Request):
    ET.reset(db)
    log(db, me, "CONFIG", "expense templates", "Standard expense categories reset to the built-in list", request=request)
    db.commit()
    return admin_templates(db, me)
