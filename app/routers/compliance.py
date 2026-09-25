"""Compliance centre: platform configuration, plans, HSN/SAC master and GST rate-change notices.

Super admin (/admin/...): edit effective-dated settings, plan prices/limits, the HSN master, and
publish rate notices. Businesses: see published notices, preview the items affected and apply the
new rates in one click; search / copy codes from the platform HSN master.
"""

import datetime as dt
import io
import re
from decimal import Decimal

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select

from ..deps import DB, BCtx, SuperAdmin
from ..models import HsnCode, Item, MasterHsn, RateNotice, RateNoticeAction
from ..services import config_store as C
from ..services import plans as P
from ..services.importer import F, read_rows
from ..services.platform_audit import log

router = APIRouter(tags=["compliance"])


def _err(e: Exception):
    raise HTTPException(422, str(e)) from e


# ================================================================ configuration
@router.get("/admin/config")
def get_config(db: DB, admin: SuperAdmin, on: dt.date | None = None):
    return {
        "fields": [dict(key=f.key, group=f.group, label=f.label, type=f.type, default=f.default, help=f.help)
                   for f in C.FIELDS],
        "effective": C.public(on),
        "on": (on or dt.date.today()).isoformat(),
        "versions": C.versions(),
    }


class VersionIn(BaseModel):
    effective_from: dt.date
    values: dict
    note: str | None = Field(None, max_length=300)


@router.post("/admin/config/versions", status_code=201)
def add_version(data: VersionIn, db: DB, admin: SuperAdmin, request: Request):
    try:
        v = C.add_version(db, data.effective_from, data.values, data.note, admin.email)
    except C.ConfigError as e:
        _err(e)
    labels = ", ".join(C.BY_KEY[k].label for k in v["values"])
    log(db, admin, "CONFIG", "config", f"Changed from {data.effective_from:%d-%m-%Y}: {labels}"[:300],
        entity_id=v["id"], request=request)
    db.commit()
    return v


@router.delete("/admin/config/versions/{version_id}", status_code=204)
def delete_version(version_id: str, db: DB, admin: SuperAdmin, request: Request):
    try:
        v = C.delete_version(db, version_id)
    except C.ConfigError as e:
        _err(e)
    log(db, admin, "DELETE", "config", f"Removed configuration change of {v['effective_from']}",
        entity_id=version_id, request=request)
    db.commit()


# ================================================================ plans
def _plain(d: dict) -> dict:
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in d.items()}


@router.get("/admin/plans-config")
def plans_config(db: DB, admin: SuperAdmin):
    defaults = C.plan_defaults()
    return {
        "order": P.ORDER, "keys": list(C.PLAN_KEYS), "addon_code": P.ADDON_CODE,
        "plans": {c: _plain(P.PLANS[c]) for c in P.ORDER},
        "addon": _plain(P.ADDON),
        "defaults": {**{c: _plain(v) for c, v in defaults.get("plans", {}).items()},
                     P.ADDON_CODE: _plain(defaults.get("addon", {}))},
        "overrides": C.plan_overrides(),
    }


@router.put("/admin/plans-config/{code}")
def update_plan(code: str, values: dict, db: DB, admin: SuperAdmin, request: Request):
    try:
        diff = C.set_plan_overrides(db, code, values)
    except (C.ConfigError, ValueError) as e:
        _err(e)
    log(db, admin, "CONFIG", "plan", f"Plan {code}: " + (", ".join(diff) or "reset to defaults"), request=request)
    db.commit()
    return plans_config(db, admin)


# ================================================================ HSN / SAC master (platform)
class MasterHsnIn(BaseModel):
    code: str = Field(pattern=r"^\d{4,8}$")
    description: str | None = Field(None, max_length=1000)
    gst_rate: Decimal
    cess_rate: Decimal = Decimal("0")
    effective_from: dt.date | None = None


def _m_out(h: MasterHsn) -> dict:
    return dict(code=h.code, description=h.description, gst_rate=float(h.gst_rate), cess_rate=float(h.cess_rate),
                effective_from=h.effective_from)


def _search(db, search: str | None, limit: int):
    q = select(MasterHsn).order_by(MasterHsn.code)
    if search:
        s = search.strip()
        q = q.where(or_(MasterHsn.code.like(f"{s}%"), MasterHsn.description.ilike(f"%{s}%")))
    return [_m_out(h) for h in db.scalars(q.limit(limit))]


@router.get("/admin/hsn")
def admin_hsn(db: DB, admin: SuperAdmin, search: str | None = None, limit: int = 200):
    return {"total": db.scalar(select(func.count()).select_from(MasterHsn)), "rows": _search(db, search, min(limit, 1000))}


def _check_rate(rate: Decimal) -> None:
    if rate not in C.all_rates():
        raise HTTPException(422, f"GST rate {rate}% is not a configured slab")


@router.post("/admin/hsn", status_code=201)
def admin_hsn_upsert(data: MasterHsnIn, db: DB, admin: SuperAdmin, request: Request):
    _check_rate(data.gst_rate)
    h = db.get(MasterHsn, data.code) or MasterHsn(code=data.code)
    for k, v in data.model_dump().items():
        setattr(h, k, v)
    db.add(h)
    log(db, admin, "UPDATE", "hsn-master", f"HSN {data.code} at {data.gst_rate}%", entity_id=data.code, request=request)
    db.commit()
    return _m_out(h)


@router.delete("/admin/hsn/{code}", status_code=204)
def admin_hsn_delete(code: str, db: DB, admin: SuperAdmin, request: Request):
    h = db.get(MasterHsn, code)
    if h is None:
        raise HTTPException(404, "Not found")
    db.delete(h)
    log(db, admin, "DELETE", "hsn-master", f"HSN {code}", entity_id=code, request=request)
    db.commit()


HSN_FIELDS = [
    F("code", "HSN/SAC Code", True, "4-8 digits", "7323"),
    F("description", "Description", False, "", "Table, kitchen or other household articles of iron or steel"),
    F("gst_rate", "GST %", True, "", "18"),
    F("cess_rate", "Cess %", False, "", "0"),
    F("effective_from", "Effective From", False, "YYYY-MM-DD or DD/MM/YYYY", "2025-09-22"),
]


def _xlsx(rows: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "HSN master"
    ws.append([f.header for f in HSN_FIELDS])
    for r in rows:
        ws.append([r["code"], r["description"], r["gst_rate"], r["cess_rate"],
                   r["effective_from"].isoformat() if r["effective_from"] else None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@router.get("/admin/hsn/export")
def admin_hsn_export(db: DB, admin: SuperAdmin):
    rows = [_m_out(h) for h in db.scalars(select(MasterHsn).order_by(MasterHsn.code))]
    return Response(_xlsx(rows or [dict(code="7323", description="Sample", gst_rate=18, cess_rate=0, effective_from=None)]),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="hsn-master.xlsx"'})


@router.post("/admin/hsn/import")
async def admin_hsn_import(db: DB, admin: SuperAdmin, request: Request, file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "File is larger than 20 MB")
    from ..services.importer import date as parse_date
    from ..services.importer import num
    rates = C.all_rates()
    created = updated = 0
    errors = []
    try:
        rows = read_rows(file.filename or "hsn.xlsx", content, HSN_FIELDS)
    except Exception as e:  # noqa: BLE001
        _err(e)
    existing = {h.code: h for h in db.scalars(select(MasterHsn))}
    for n, r in rows:
        try:
            code = re.sub(r"\D", "", str(r.get("code") or ""))
            if not 4 <= len(code) <= 8:
                raise ValueError("HSN/SAC must be 4-8 digits")
            rate = num(r.get("gst_rate"), "GST %")
            if rate not in rates:
                raise ValueError(f"GST {rate}% is not a configured slab")
            h = existing.get(code)
            if h is None:
                h = existing[code] = MasterHsn(code=code)
                db.add(h)
                created += 1
            else:
                updated += 1
            h.description = r.get("description") or h.description
            h.gst_rate = rate
            h.cess_rate = num(r.get("cess_rate"), "Cess %", Decimal("0"))
            h.effective_from = parse_date(r.get("effective_from"), "Effective From")
        except Exception as e:  # noqa: BLE001
            if len(errors) < 200:
                errors.append({"row": n, "error": getattr(e, "detail", None) or str(e)})
    log(db, admin, "IMPORT", "hsn-master", f"HSN master import: {created} added, {updated} updated, {len(errors)} errors",
        request=request)
    db.commit()
    return {"created": created, "updated": updated, "errors": errors}


# business side: search the platform master and copy codes into the business's own master
@router.get("/hsn-master")
def hsn_master_search(ctx: BCtx, search: str | None = None):
    return _search(ctx.db, search, 50)


class CopyIn(BaseModel):
    codes: list[str] = Field(default_factory=list)  # empty = the codes used on the business's items


@router.post("/hsn-master/copy")
def hsn_master_copy(data: CopyIn, ctx: BCtx):
    ctx.need("settings", "edit")
    codes = set(data.codes) or {c for c in ctx.db.scalars(
        select(Item.hsn_sac).where(Item.business_id == ctx.bid, Item.hsn_sac.is_not(None)))}
    masters = ctx.db.scalars(select(MasterHsn).where(MasterHsn.code.in_(codes))).all() if codes else []
    mine = {h.code: h for h in ctx.db.scalars(select(HsnCode).where(HsnCode.business_id == ctx.bid))}
    n = 0
    for m in masters:
        h = mine.get(m.code) or HsnCode(business_id=ctx.bid, code=m.code)
        h.description, h.gst_rate, h.cess_rate, h.effective_from = m.description, m.gst_rate, m.cess_rate, m.effective_from
        ctx.db.add(h)
        n += 1
    ctx.db.commit()
    return {"copied": n, "not_found": sorted(codes - {m.code for m in masters})}


# ================================================================ rate-change notices
class ChangeIn(BaseModel):
    hsn_prefix: str = Field(pattern=r"^\d{2,8}$")
    description: str | None = Field(None, max_length=300)
    new_rate: Decimal
    new_cess: Decimal | None = None


class NoticeIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    reference: str | None = Field(None, max_length=100)
    effective_from: dt.date
    changes: list[ChangeIn] = Field(min_length=1, max_length=2000)
    note: str | None = None


def _n_out(n: RateNotice) -> dict:
    return dict(id=n.id, title=n.title, reference=n.reference, effective_from=n.effective_from, changes=n.changes,
                note=n.note, published_at=n.published_at, created_by=n.created_by, created_at=n.created_at)


def _changes_json(changes: list[ChangeIn]) -> list[dict]:
    allowed = C.all_rates()
    out = []
    for c in changes:
        if c.new_rate not in allowed:
            raise HTTPException(422, f"GST {c.new_rate}% is not a configured slab (add it in Configuration first)")
        out.append(dict(hsn_prefix=c.hsn_prefix, description=c.description, new_rate=float(c.new_rate),
                        new_cess=float(c.new_cess) if c.new_cess is not None else None))
    return out


@router.get("/admin/rate-notices")
def admin_notices(db: DB, admin: SuperAdmin):
    applied = dict(db.execute(select(RateNoticeAction.notice_id, func.count())
                              .where(RateNoticeAction.action == "APPLIED").group_by(RateNoticeAction.notice_id)).all())
    return [{**_n_out(n), "businesses_applied": applied.get(n.id, 0)}
            for n in db.scalars(select(RateNotice).order_by(RateNotice.effective_from.desc(), RateNotice.created_at.desc()))]


@router.post("/admin/rate-notices", status_code=201)
def admin_notice_create(data: NoticeIn, db: DB, admin: SuperAdmin, request: Request):
    n = RateNotice(title=data.title, reference=data.reference, effective_from=data.effective_from,
                   changes=_changes_json(data.changes), note=data.note, created_by=admin.email)
    db.add(n)
    db.flush()
    log(db, admin, "CREATE", "rate-notice", f"Draft rate notice: {n.title}", entity_id=n.id, request=request)
    db.commit()
    return _n_out(n)


def _notice(db, notice_id: str) -> RateNotice:
    n = db.get(RateNotice, notice_id)
    if n is None:
        raise HTTPException(404, "Notice not found")
    return n


@router.put("/admin/rate-notices/{notice_id}")
def admin_notice_update(notice_id: str, data: NoticeIn, db: DB, admin: SuperAdmin, request: Request):
    n = _notice(db, notice_id)
    if n.published_at:
        raise HTTPException(400, "A published notice cannot be edited — publish a new one instead")
    n.title, n.reference, n.effective_from, n.note = data.title, data.reference, data.effective_from, data.note
    n.changes = _changes_json(data.changes)
    log(db, admin, "UPDATE", "rate-notice", f"Rate notice: {n.title}", entity_id=n.id, request=request)
    db.commit()
    return _n_out(n)


@router.post("/admin/rate-notices/{notice_id}/publish")
def admin_notice_publish(notice_id: str, db: DB, admin: SuperAdmin, request: Request, update_master: bool = True):
    """Publish to every business; optionally update matching codes in the platform HSN master."""
    n = _notice(db, notice_id)
    if n.published_at:
        raise HTTPException(400, "Already published")
    n.published_at = dt.datetime.now(dt.UTC)
    updated = 0
    if update_master:
        for c in n.changes:
            for h in db.scalars(select(MasterHsn).where(MasterHsn.code.like(f"{c['hsn_prefix']}%"))):
                h.gst_rate = Decimal(str(c["new_rate"]))
                if c.get("new_cess") is not None:
                    h.cess_rate = Decimal(str(c["new_cess"]))
                h.effective_from = n.effective_from
                updated += 1
    log(db, admin, "PUBLISH", "rate-notice", f"Published rate notice: {n.title} ({updated} master codes updated)",
        entity_id=n.id, request=request)
    db.commit()
    return {**_n_out(n), "master_updated": updated}


@router.delete("/admin/rate-notices/{notice_id}", status_code=204)
def admin_notice_delete(notice_id: str, db: DB, admin: SuperAdmin, request: Request):
    n = _notice(db, notice_id)
    log(db, admin, "DELETE", "rate-notice", f"Rate notice: {n.title}", entity_id=n.id, request=request)
    db.execute(delete(RateNoticeAction).where(RateNoticeAction.notice_id == n.id))
    db.delete(n)
    db.commit()


def _match(changes: list[dict], hsn: str | None) -> dict | None:
    """The most specific change (longest prefix) matching an HSN code."""
    if not hsn:
        return None
    best = None
    for c in changes:
        if hsn.startswith(c["hsn_prefix"]) and (best is None or len(c["hsn_prefix"]) > len(best["hsn_prefix"])):
            best = c
    return best


def _affected(ctx: BCtx, n: RateNotice) -> list[dict]:
    out = []
    for it in ctx.db.scalars(select(Item).where(Item.business_id == ctx.bid, Item.hsn_sac.is_not(None)).order_by(Item.name)):
        c = _match(n.changes, it.hsn_sac)
        if c is None:
            continue
        new_cess = Decimal(str(c["new_cess"])) if c.get("new_cess") is not None else it.cess_rate
        new_rate = Decimal(str(c["new_rate"]))
        if new_rate != it.gst_rate or new_cess != it.cess_rate:
            out.append(dict(id=it.id, name=it.name, hsn=it.hsn_sac, old_rate=float(it.gst_rate), new_rate=float(new_rate),
                            old_cess=float(it.cess_rate), new_cess=float(new_cess)))
    return out


@router.get("/rate-notices")
def notices(ctx: BCtx, include_done: bool = False):
    acts = {a.notice_id: a for a in ctx.db.scalars(select(RateNoticeAction).where(RateNoticeAction.business_id == ctx.bid))}
    out = []
    for n in ctx.db.scalars(select(RateNotice).where(RateNotice.published_at.is_not(None))
                            .order_by(RateNotice.effective_from.desc())):
        a = acts.get(n.id)
        if a and not include_done:
            continue
        out.append({**_n_out(n), "affected": len(_affected(ctx, n)), "status": a.action if a else "PENDING",
                    "action_at": a.at if a else None, "action_by": a.by_name if a else None})
    return out


@router.get("/rate-notices/{notice_id}/preview")
def notice_preview(notice_id: str, ctx: BCtx):
    n = _notice(ctx.db, notice_id)
    if not n.published_at:
        raise HTTPException(404, "Notice not found")
    return {**_n_out(n), "items": _affected(ctx, n)}


class ApplyIn(BaseModel):
    item_ids: list[str] | None = None  # None = every affected item


@router.post("/rate-notices/{notice_id}/apply")
def notice_apply(notice_id: str, data: ApplyIn, ctx: BCtx):
    ctx.need("items", "edit")
    n = _notice(ctx.db, notice_id)
    if not n.published_at:
        raise HTTPException(404, "Notice not found")
    chosen = set(data.item_ids) if data.item_ids is not None else None
    changed = 0
    for row in _affected(ctx, n):
        if chosen is not None and row["id"] not in chosen:
            continue
        it = ctx.db.get(Item, row["id"])
        it.gst_rate, it.cess_rate = Decimal(str(row["new_rate"])), Decimal(str(row["new_cess"]))
        changed += 1
    # keep the business's own HSN master in step
    for h in ctx.db.scalars(select(HsnCode).where(HsnCode.business_id == ctx.bid)):
        c = _match(n.changes, h.code)
        if c:
            h.gst_rate = Decimal(str(c["new_rate"]))
            if c.get("new_cess") is not None:
                h.cess_rate = Decimal(str(c["new_cess"]))
            h.effective_from = n.effective_from
    _mark(ctx, n, "APPLIED", changed)
    return {"items_changed": changed}


@router.post("/rate-notices/{notice_id}/dismiss")
def notice_dismiss(notice_id: str, ctx: BCtx):
    ctx.need("items", "edit")
    _mark(ctx, _notice(ctx.db, notice_id), "DISMISSED", 0)
    return {"ok": True}


def _mark(ctx: BCtx, n: RateNotice, action: str, changed: int) -> None:
    a = ctx.db.get(RateNoticeAction, (n.id, ctx.bid)) or RateNoticeAction(notice_id=n.id, business_id=ctx.bid)
    a.action, a.items_changed, a.by_name, a.at = action, changed, ctx.user.name, dt.datetime.now(dt.UTC)
    ctx.db.add(a)
    ctx.db.commit()
