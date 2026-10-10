"""Standard expense categories (with typical items) kept by the super admin (Admin → Masters → Expense categories).

A new business starts with none: the first time someone opens Expenses → Categories & Items, the app offers to import
the standard list. Imported rows are the business's own copies — editing the standard list later never changes them.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..gst.constants import ExpenseKind
from ..models import Business, ExpenseCategory, ExpenseItem, PlatformSetting
from . import config_store

KEY = "expense_templates"


def _c(name: str, kind: str = "INDIRECT", items: list[tuple[str, int]] | None = None, itc_blocked: bool = False) -> dict:
    return {"name": name, "kind": kind, "itc_blocked": itc_blocked,
            "items": [{"name": n, "gst_rate": r, "hsn_sac": None} for n, r in items or []]}


BUILT_IN = [
    _c("Manufacturing Expenses", "DIRECT", [("Factory power & fuel", 0), ("Consumables", 18)]),
    _c("Freight & Transport Inward", "DIRECT", [("Freight inward", 5), ("Loading & unloading", 0)]),
    _c("Labour / Wages", "DIRECT", [("Labour charges", 0)]),
    _c("Rent", items=[("Shop / office rent", 18)]),
    _c("Salary", items=[("Staff salary", 0)]),
    _c("Electricity", items=[("Electricity bill", 0)]),
    _c("Petrol & Fuel", items=[("Petrol", 0), ("Diesel", 0)]),
    _c("Transport & Travel", items=[("Taxi / cab", 5), ("Local conveyance", 0)]),
    _c("Tea & Refreshments", items=[("Tea & snacks", 5)], itc_blocked=True),
    _c("Telephone & Internet", items=[("Mobile recharge", 18), ("Internet / broadband", 18)]),
    _c("Repairs & Maintenance", items=[("Repairs", 18)]),
    _c("Printing & Stationery", items=[("Stationery", 18), ("Printing", 18)]),
    _c("Professional Fees", items=[("CA / accounting fees", 18), ("Legal fees", 18)]),
    _c("Bank Charges", items=[("Bank charges", 18)]),
    _c("Advertisement", items=[("Online ads", 18), ("Banners & pamphlets", 18)]),
    _c("Miscellaneous"),
]


def get(db: Session) -> list[dict]:
    row = db.get(PlatformSetting, KEY)
    return (row.value or {}).get("categories") if row and row.value else BUILT_IN


def save(db: Session, categories: list[dict]) -> list[dict]:
    rates = {Decimal(str(r)) for r in config_store.rates_on()}
    seen: set[str] = set()
    clean = []
    for c in categories:
        name = (c.get("name") or "").strip()[:100]
        if not name or name.lower() in seen:
            raise HTTPException(422, f"Category names must be filled in and different ({name or 'blank'})")
        seen.add(name.lower())
        items, item_names = [], set()
        for i in c.get("items") or []:
            iname = (i.get("name") or "").strip()[:120]
            if not iname:
                continue
            if iname.lower() in item_names:
                raise HTTPException(422, f"{name}: item “{iname}” is listed twice")
            item_names.add(iname.lower())
            rate = Decimal(str(i.get("gst_rate") or 0))
            if rate not in rates:
                raise HTTPException(422, f"{iname}: GST {rate}% is not a current GST rate")
            items.append({"name": iname, "gst_rate": float(rate), "hsn_sac": ((i.get("hsn_sac") or "").strip() or None)})
        clean.append({"name": name, "kind": "DIRECT" if c.get("kind") == "DIRECT" else "INDIRECT",
                      "itc_blocked": bool(c.get("itc_blocked")), "items": items})
    row = db.get(PlatformSetting, KEY) or PlatformSetting(key=KEY)
    row.value = {"categories": clean}
    db.add(row)
    return clean


def reset(db: Session) -> list[dict]:
    row = db.get(PlatformSetting, KEY)
    if row:
        db.delete(row)
    return BUILT_IN


def for_business(db: Session, biz: Business) -> dict:
    have_cats = {n.lower() for n in db.scalars(select(ExpenseCategory.name).where(ExpenseCategory.business_id == biz.id))}
    have_items = {n.lower() for n in db.scalars(select(ExpenseItem.name).where(ExpenseItem.business_id == biz.id))}
    cats = [{**c, "exists": c["name"].lower() in have_cats,
             "items": [{**i, "exists": i["name"].lower() in have_items} for i in c["items"]]} for c in get(db)]
    return {"choice": biz.expense_setup, "ask": biz.expense_setup is None and not have_cats, "categories": cats}


def import_into(db: Session, biz: Business, names: list[str] | None) -> dict:
    """Copy the chosen standard categories (all when names is None) and their items into the business; rows it already
    has (same name) are left as they are."""
    wanted = {n.lower() for n in names} if names is not None else None
    blocked = {n.lower() for n in config_store.get("blocked_itc_categories")}
    cats = {c.name.lower(): c for c in db.scalars(select(ExpenseCategory).where(ExpenseCategory.business_id == biz.id))}
    have_items = {n.lower() for n in db.scalars(select(ExpenseItem.name).where(ExpenseItem.business_id == biz.id))}
    added_c = added_i = 0
    for t in get(db):
        if wanted is not None and t["name"].lower() not in wanted:
            continue
        cat = cats.get(t["name"].lower())
        if cat is None:
            cat = ExpenseCategory(business_id=biz.id, name=t["name"], kind=ExpenseKind(t["kind"]),
                                  itc_blocked=t["itc_blocked"] or t["name"].lower() in blocked)
            db.add(cat)
            db.flush()
            cats[t["name"].lower()] = cat
            added_c += 1
        for i in t["items"]:
            if i["name"].lower() in have_items:
                continue
            db.add(ExpenseItem(business_id=biz.id, category_id=cat.id, name=i["name"], hsn_sac=i.get("hsn_sac"),
                               gst_rate=Decimal(str(i["gst_rate"])), rate=Decimal("0")))
            have_items.add(i["name"].lower())
            added_i += 1
    biz.expense_setup = "IMPORTED"
    db.flush()
    return {"categories_added": added_c, "items_added": added_i}


def count(db: Session, business_id: str) -> int:
    return db.scalar(select(func.count(ExpenseCategory.id)).where(ExpenseCategory.business_id == business_id)) or 0
