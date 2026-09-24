"""Utilities: bulk import, HSN/SAC master, tax slab updates, backup & restore, company members."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from ..deps import DB, MANAGERS, WRITERS, BCtx, CurrentUser
from ..gst.constants import GST_RATES, Role
from ..models import Backup, Business, HsnCode, Item, Membership, User
from ..services import backup as bk
from ..services.importer import ENTITIES, run_import, template

router = APIRouter(tags=["utilities"])
MAX_UPLOAD = 10 * 1024 * 1024


# ---------------------------------------------------------------- import
@router.get("/import/types")
def import_types(ctx: BCtx):
    return [{"entity": k, "title": v[1]} for k, v in ENTITIES.items()]


@router.get("/import/{entity}/template")
def import_template(entity: str, ctx: BCtx):
    title = ENTITIES.get(entity, (None, entity))[1]
    return Response(
        template(entity),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{title.replace(" ", "-").replace("/", "-")}-template.xlsx"'},
    )


@router.post("/import/{entity}")
async def import_data(entity: str, ctx: BCtx, file: UploadFile = File(...), dry_run: bool = Form(True)):
    ctx.require(*WRITERS)
    content = await file.read()
    if len(content) > MAX_UPLOAD:
        raise HTTPException(400, "File is larger than 10 MB — split it into smaller files")
    return run_import(ctx, entity, file.filename or "upload.xlsx", content, dry_run)


# ---------------------------------------------------------------- HSN / SAC master
class HsnIn(BaseModel):
    code: Annotated[str, Field(pattern=r"^\d{4,8}$")]
    description: str | None = None
    gst_rate: Decimal
    cess_rate: Decimal = Decimal("0")
    effective_from: dt.date | None = None


def _hsn_out(h: HsnCode) -> dict:
    return dict(id=h.id, code=h.code, description=h.description, gst_rate=float(h.gst_rate),
                cess_rate=float(h.cess_rate), effective_from=h.effective_from)


@router.get("/hsn")
def list_hsn(ctx: BCtx, search: str | None = None):
    q = select(HsnCode).where(HsnCode.business_id == ctx.bid).order_by(HsnCode.code)
    if search:
        q = q.where((HsnCode.code.like(f"{search}%")) | (HsnCode.description.ilike(f"%{search}%")))
    return [_hsn_out(h) for h in ctx.db.scalars(q.limit(500))]


@router.post("/hsn", status_code=201)
def upsert_hsn(data: HsnIn, ctx: BCtx):
    ctx.require(*WRITERS)
    if data.gst_rate not in GST_RATES:
        raise HTTPException(422, "Invalid GST rate")
    h = ctx.db.scalar(select(HsnCode).where(HsnCode.business_id == ctx.bid, HsnCode.code == data.code))
    if h is None:
        h = HsnCode(business_id=ctx.bid, code=data.code)
        ctx.db.add(h)
    for k, v in data.model_dump().items():
        setattr(h, k, v)
    ctx.db.commit()
    return _hsn_out(h)


@router.delete("/hsn/{hsn_id}", status_code=204)
def delete_hsn(hsn_id: str, ctx: BCtx):
    ctx.require(*WRITERS)
    h = ctx.db.get(HsnCode, hsn_id)
    if not h or h.business_id != ctx.bid:
        raise HTTPException(404, "Not found")
    ctx.db.delete(h)
    ctx.db.commit()


@router.post("/hsn/apply-to-items")
def apply_hsn_rates(ctx: BCtx):
    """Update every item's GST/cess rate from the HSN master (new bills only; old bills keep their rates)."""
    ctx.require(*MANAGERS)
    rates = {h.code: h for h in ctx.db.scalars(select(HsnCode).where(HsnCode.business_id == ctx.bid))}
    changed = []
    for it in ctx.db.scalars(select(Item).where(Item.business_id == ctx.bid, Item.hsn_sac.is_not(None))):
        h = rates.get(it.hsn_sac)
        if h and (it.gst_rate != h.gst_rate or it.cess_rate != h.cess_rate):
            changed.append(dict(item=it.name, hsn=it.hsn_sac, old=float(it.gst_rate), new=float(h.gst_rate)))
            it.gst_rate, it.cess_rate = h.gst_rate, h.cess_rate
    ctx.db.commit()
    return {"updated": len(changed), "items": changed}


class SlabUpdate(BaseModel):
    """Change GST rate on many items at once (e.g. after a GST council rate change)."""
    new_rate: Decimal
    from_rate: Decimal | None = None       # all items currently at this rate
    hsn_prefix: str | None = None           # and/or items whose HSN starts with this
    category: str | None = None             # and/or items in this category
    item_ids: list[str] | None = None       # or exactly these items
    preview: bool = True


@router.post("/tax-slab/update")
def update_tax_slab(data: SlabUpdate, ctx: BCtx):
    ctx.require(*MANAGERS)
    if data.new_rate not in GST_RATES:
        raise HTTPException(422, "Invalid GST rate")
    if not any([data.from_rate is not None, data.hsn_prefix, data.category, data.item_ids]):
        raise HTTPException(400, "Choose which items to update")
    q = select(Item).where(Item.business_id == ctx.bid, Item.is_active.is_(True))
    if data.from_rate is not None:
        q = q.where(Item.gst_rate == data.from_rate)
    if data.hsn_prefix:
        q = q.where(Item.hsn_sac.like(f"{data.hsn_prefix}%"))
    if data.category:
        q = q.where(func.lower(Item.category) == data.category.lower())
    if data.item_ids:
        q = q.where(Item.id.in_(data.item_ids))
    items = ctx.db.scalars(q.order_by(Item.name)).all()
    out = [dict(id=i.id, name=i.name, hsn=i.hsn_sac, old=float(i.gst_rate), new=float(data.new_rate)) for i in items]
    if not data.preview:
        for i in items:
            i.gst_rate = data.new_rate
        ctx.db.commit()
    return {"count": len(out), "items": out, "applied": not data.preview}


# ---------------------------------------------------------------- backup & restore
def _backup_out(b: Backup, biz_name: str) -> dict:
    return dict(id=b.id, kind=b.kind, size=b.size, created_at=b.created_at, emailed_to=b.emailed_to,
                filename=bk.filename(biz_name, b.created_at))


@router.get("/backups")
def list_backups(ctx: BCtx):
    ctx.require(*MANAGERS)
    rows = ctx.db.scalars(select(Backup).where(Backup.business_id == ctx.bid)
                          .order_by(Backup.created_at.desc()).limit(50)).all()
    return [_backup_out(b, ctx.business.name) for b in rows]


@router.post("/backups", status_code=201)
def create_backup(ctx: BCtx, bg: BackgroundTasks, email: bool = False):
    ctx.require(*MANAGERS)
    b = bk.create_backup(ctx.db, ctx.business, ctx.user.id)
    if email:
        to = ctx.business.backup_email or ctx.user.email
        bk.email_backup(to, ctx.business.name, b.data, b.created_at)  # raise early if SMTP is missing
        b.emailed_to = to
    ctx.db.commit()
    return _backup_out(b, ctx.business.name)


@router.get("/backups/{backup_id}/download")
def download_backup(backup_id: str, ctx: BCtx):
    ctx.require(*MANAGERS)
    b = ctx.db.get(Backup, backup_id)
    if not b or b.business_id != ctx.bid:
        raise HTTPException(404, "Backup not found")
    return Response(b.data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{bk.filename(ctx.business.name, b.created_at)}"'})


@router.delete("/backups/{backup_id}", status_code=204)
def delete_backup(backup_id: str, ctx: BCtx):
    ctx.require(*MANAGERS)
    b = ctx.db.get(Backup, backup_id)
    if not b or b.business_id != ctx.bid:
        raise HTTPException(404, "Backup not found")
    ctx.db.delete(b)
    ctx.db.commit()


@router.post("/backups/restore", status_code=201)
async def restore_backup(db: DB, user: CurrentUser, file: UploadFile = File(...), name: str | None = Form(None)):
    """Restore a backup file as a NEW company owned by the current user (live data is never overwritten)."""
    blob = await file.read()
    if len(blob) > 200 * 1024 * 1024:
        raise HTTPException(400, "Backup file is too large")
    biz = bk.restore_as_new(db, blob, user.id, name)
    db.commit()
    return {"id": biz.id, "name": biz.name}


@router.post("/backups/{backup_id}/restore", status_code=201)
def restore_saved_backup(backup_id: str, ctx: BCtx):
    ctx.require(Role.OWNER)
    b = ctx.db.get(Backup, backup_id)
    if not b or b.business_id != ctx.bid:
        raise HTTPException(404, "Backup not found")
    biz = bk.restore_as_new(ctx.db, b.data, ctx.user.id,
                            f"{ctx.business.name} (restored {b.created_at:%d-%m-%Y %H:%M})")
    ctx.db.commit()
    return {"id": biz.id, "name": biz.name}


# ---------------------------------------------------------------- company members
@router.get("/members")
def list_members(ctx: BCtx):
    rows = ctx.db.execute(select(Membership, User).join(User, User.id == Membership.user_id)
                          .where(Membership.business_id == ctx.bid).order_by(User.name)).all()
    return [dict(id=m.id, user_id=u.id, name=u.name, email=u.email, role=m.role.value, you=u.id == ctx.user.id)
            for m, u in rows]


class MemberIn(BaseModel):
    email: EmailStr
    role: Literal["ADMIN", "STAFF", "ACCOUNTANT"]


@router.post("/members", status_code=201)
def add_member(data: MemberIn, ctx: BCtx):
    ctx.require(Role.OWNER, Role.ADMIN)
    u = ctx.db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not u:
        raise HTTPException(404, "No account with this email — ask them to sign up first, then add them here")
    if ctx.db.scalar(select(Membership).where(Membership.user_id == u.id, Membership.business_id == ctx.bid)):
        raise HTTPException(409, "Already a member of this company")
    ctx.db.add(Membership(user_id=u.id, business_id=ctx.bid, role=Role(data.role)))
    ctx.db.commit()
    return {"ok": True}


class RoleIn(BaseModel):
    role: Literal["ADMIN", "STAFF", "ACCOUNTANT"]


@router.put("/members/{member_id}")
def change_role(member_id: str, data: RoleIn, ctx: BCtx):
    ctx.require(Role.OWNER)
    m = ctx.db.get(Membership, member_id)
    if not m or m.business_id != ctx.bid or m.role == Role.OWNER:
        raise HTTPException(404, "Member not found")
    m.role = Role(data.role)
    ctx.db.commit()
    return {"ok": True}


@router.delete("/members/{member_id}", status_code=204)
def remove_member(member_id: str, ctx: BCtx):
    ctx.require(Role.OWNER, Role.ADMIN)
    m = ctx.db.get(Membership, member_id)
    if not m or m.business_id != ctx.bid:
        raise HTTPException(404, "Member not found")
    if m.role == Role.OWNER:
        raise HTTPException(400, "The owner cannot be removed")
    ctx.db.delete(m)
    ctx.db.commit()


class DeleteCompany(BaseModel):
    confirm_name: str


@router.post("/company/delete", status_code=204)
def delete_company(data: DeleteCompany, ctx: BCtx):
    """Permanently delete the current company. The owner must type its exact name."""
    ctx.require(Role.OWNER)
    if data.confirm_name.strip() != ctx.business.name:
        raise HTTPException(400, "The name does not match")
    ctx.db.delete(ctx.db.get(Business, ctx.bid))
    ctx.db.commit()



