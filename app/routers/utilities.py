"""Utilities: bulk import, HSN/SAC master, tax slab updates, backup & restore, company members."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

import bcrypt

from ..deps import DB, BCtx, CurrentUser
from ..gst.constants import GST_RATES, Role
from ..models import Backup, Business, HsnCode, Item, Membership, User
from ..services import backup as bk
from ..services import data_wipe as wipe_svc
from ..services import excel_backup as xb
from ..services.importer import ENTITIES, run_import, template
from ..permissions import ACTIONS, DEFAULTS, FLAGS, MODULES, ROLE_LABELS, effective, normalise
from ..services.plans import check_backup_quota, check_business_limit, check_user_limit, require_feature

router = APIRouter(tags=["utilities"])

IMPORT_MODULE = {"parties": "parties", "items": "items", "stock": "items", "hsn": "settings", "expense-items": "expenses",
                 "payments-in": "payments_in", "payments-out": "payments_out", "expenses": "expenses",
                 "purchases": "purchases", "purchase-orders": "purchases", "debit-notes": "purchases"}


def import_module(entity: str) -> str:
    return IMPORT_MODULE.get(entity, "sales")
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
    ctx.need(import_module(entity), "create")
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
    """Readable by every member — item forms look codes up here."""
    q = select(HsnCode).where(HsnCode.business_id == ctx.bid).order_by(HsnCode.code)
    if search:
        q = q.where((HsnCode.code.like(f"{search}%")) | (HsnCode.description.ilike(f"%{search}%")))
    return [_hsn_out(h) for h in ctx.db.scalars(q.limit(500))]


@router.post("/hsn", status_code=201)
def upsert_hsn(data: HsnIn, ctx: BCtx):
    ctx.need("settings", "edit")
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
    ctx.need("settings", "edit")
    h = ctx.db.get(HsnCode, hsn_id)
    if not h or h.business_id != ctx.bid:
        raise HTTPException(404, "Not found")
    ctx.db.delete(h)
    ctx.db.commit()


@router.post("/hsn/apply-to-items")
def apply_hsn_rates(ctx: BCtx):
    """Update every item's GST/cess rate from the HSN master (new bills only; old bills keep their rates)."""
    ctx.need("settings", "edit")
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
    ctx.need("settings", "edit")
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
                filename=bk.filename(biz_name, b.created_at), excel_filename=xb.zip_name(biz_name, b.created_at))


@router.get("/backups/settings")
def backup_settings(ctx: BCtx):
    """Which backup options the super admin has enabled for this business."""
    return {"excel": xb.allowed(ctx.db, ctx.business)}


@router.get("/backups")
def list_backups(ctx: BCtx):
    ctx.need("backup", "view")
    rows = ctx.db.scalars(select(Backup).where(Backup.business_id == ctx.bid)
                          .order_by(Backup.created_at.desc()).limit(50)).all()
    return [_backup_out(b, ctx.business.name) for b in rows]


@router.post("/backups", status_code=201)
def create_backup(ctx: BCtx, bg: BackgroundTasks, email: bool = False):
    ctx.need("backup", "create")
    check_backup_quota(ctx.db, ctx.bid, 0)
    b = bk.create_backup(ctx.db, ctx.business, ctx.user.id)
    if email:
        to = ctx.business.backup_email or ctx.user.email
        bk.email_backup(ctx.db, ctx.business, to, b.data, b.created_at)  # raise early if SMTP is missing
        b.emailed_to = to
    ctx.db.commit()
    return _backup_out(b, ctx.business.name)


@router.get("/backups/{backup_id}/download")
def download_backup(backup_id: str, ctx: BCtx):
    ctx.need("backup", "export")
    b = ctx.db.get(Backup, backup_id)
    if not b or b.business_id != ctx.bid:
        raise HTTPException(404, "Backup not found")
    return Response(b.data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{bk.filename(ctx.business.name, b.created_at)}"'})


@router.get("/backups/{backup_id}/excel")
def download_backup_excel(backup_id: str, ctx: BCtx):
    """The backup as a .zip of Excel files (plus the exact backup inside, so the zip can be restored too)."""
    ctx.need("backup", "export")
    xb.require(ctx.db, ctx.business)
    b = ctx.db.get(Backup, backup_id)
    if not b or b.business_id != ctx.bid:
        raise HTTPException(404, "Backup not found")
    return Response(xb.build_zip(b.data), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{xb.zip_name(ctx.business.name, b.created_at)}"'})


@router.delete("/backups/{backup_id}", status_code=204)
def delete_backup(backup_id: str, ctx: BCtx):
    ctx.need("backup", "delete")
    b = ctx.db.get(Backup, backup_id)
    if not b or b.business_id != ctx.bid:
        raise HTTPException(404, "Backup not found")
    if b.kind == "WIPE":
        raise HTTPException(403, "This backup was taken before data was cleared and is kept as the record of it — it cannot be deleted.")
    ctx.db.delete(b)
    ctx.db.commit()


@router.post("/backups/restore", status_code=201)
async def restore_backup(db: DB, user: CurrentUser, file: UploadFile = File(...), name: str | None = Form(None),
                         mode: Literal["auto", "exact", "excel"] = Form("auto"), dry_run: bool = Form(False)):
    """Restore a backup file (.gstbak) or an Excel backup (.zip) as a NEW company owned by the current user
    (live data is never overwritten). `dry_run` checks an Excel restore and saves nothing."""
    blob = await file.read()
    if len(blob) > 200 * 1024 * 1024:
        raise HTTPException(400, "Backup file is too large")
    check_business_limit(db, user.id)
    if xb.is_zip(blob):
        if not xb.allowed_for_user(db, user):
            raise HTTPException(403, "Restoring Excel backups is not enabled for your account — ask the platform administrator.")
        res = xb.restore_zip(db, user, blob, name, mode, dry_run)
        if not res["ok"] and not dry_run:
            raise HTTPException(422, {"message": "The Excel files have errors — nothing was restored", "code": "RESTORE_ERRORS",
                                      "errors": res["errors"], "summary": res.get("summary")})
        if res.get("business_id") and res["method"] == "exact":
            db.commit()
        return {"id": res.get("business_id"), "name": res.get("business_name"), **res}
    biz = bk.restore_as_new(db, blob, user.id, name)
    db.commit()
    return {"id": biz.id, "name": biz.name, "method": "exact", "ok": True}


@router.post("/backups/{backup_id}/restore", status_code=201)
def restore_saved_backup(backup_id: str, ctx: BCtx):
    ctx.require(Role.OWNER)
    b = ctx.db.get(Backup, backup_id)
    if not b or b.business_id != ctx.bid:
        raise HTTPException(404, "Backup not found")
    check_business_limit(ctx.db, ctx.user.id)
    biz = bk.restore_as_new(ctx.db, b.data, ctx.user.id,
                            f"{ctx.business.name} (restored {b.created_at:%d-%m-%Y %H:%M})")
    ctx.db.commit()
    return {"id": biz.id, "name": biz.name}


# ---------------------------------------------------------------- clear data (after testing, before going live)
class WipeIn(BaseModel):
    groups: list[str] = Field(min_length=1, max_length=20)
    confirm_name: str = Field(max_length=200)
    test_data: bool = False  # "these are test / practice entries" — needed to clear bills


@router.get("/data-wipe")
def data_wipe_options(ctx: BCtx):
    ctx.require(Role.OWNER)
    return {"groups": wipe_svc.options(), "counts": wipe_svc.counts(ctx.db, ctx.bid), "business_name": ctx.business.name,
            "backup_email": ctx.business.backup_email or ctx.user.email}


@router.post("/data-wipe")
def data_wipe(data: WipeIn, ctx: BCtx):
    """Owner only: clear the chosen data of this business. A backup is saved (and e-mailed) first."""
    ctx.require(Role.OWNER)
    return wipe_svc.wipe(ctx.db, ctx.business, data.groups, data.confirm_name, ctx.user, test_data=data.test_data)


# ---------------------------------------------------------------- company members
@router.get("/members")
def list_members(ctx: BCtx):
    ctx.need("users", "view")
    rows = ctx.db.execute(select(Membership, User).join(User, User.id == Membership.user_id)
                          .where(Membership.business_id == ctx.bid).order_by(User.name)).all()
    others = _other_business_counts(ctx, [u.id for _, u in rows])
    return [dict(id=m.id, user_id=u.id, name=u.name, email=u.email, phone=u.phone, role=m.role.value, you=u.id == ctx.user.id,
                 custom=bool(m.permissions), permissions=effective(m.role, m.permissions),
                 has_pin=bool(m.approval_pin_hash), status=m.status, last_login_at=u.last_login_at,
                 other_businesses=others.get(u.id, 0), managed=_managed(ctx, u, others.get(u.id, 0)))
            for m, u in rows]


def _other_business_counts(ctx, user_ids: list[str]) -> dict[str, int]:
    rows = ctx.db.execute(select(Membership.user_id, func.count()).where(
        Membership.user_id.in_(user_ids), Membership.business_id != ctx.bid).group_by(Membership.user_id)).all()
    return {uid: n for uid, n in rows}


def _managed(ctx, u: User, other_businesses: int) -> bool:
    """This business may set the person's password: it created the login and they work nowhere else."""
    return u.created_by_business_id == ctx.bid and other_businesses == 0 and not u.platform_role


@router.get("/permissions/meta")
def permissions_meta(ctx: BCtx):
    """Modules, actions, flags and the default matrix of each role (for the permission editor)."""
    return {"modules": MODULES, "actions": list(ACTIONS), "flags": list(FLAGS),
            "roles": {r.value: {"label": ROLE_LABELS[r], "defaults": DEFAULTS[r]} for r in Role},
            "mine": ctx.perms, "role": ctx.role.value}


class PermissionsIn(BaseModel):
    modules: dict[str, list[str]] | None = None  # null = back to role defaults
    flags: list[str] = []


@router.put("/members/{member_id}/permissions")
def set_permissions(member_id: str, data: PermissionsIn, ctx: BCtx):
    ctx.need("users", "edit")
    require_feature(ctx.db, ctx.bid, "custom_roles")
    m = ctx.db.get(Membership, member_id)
    if not m or m.business_id != ctx.bid or m.role == Role.OWNER:
        raise HTTPException(404, "Member not found")
    m.permissions = normalise(data.model_dump()) if data.modules is not None else None
    ctx.db.commit()
    return {"permissions": effective(m.role, m.permissions)}


class PinIn(BaseModel):
    pin: Annotated[str, Field(pattern=r"^\d{4,6}$")] | None = None


@router.put("/me/approval-pin")
def set_approval_pin(data: PinIn, ctx: BCtx):
    """Managers set a 4–6 digit PIN to approve staff edits of older entries."""
    if ctx.role not in (Role.OWNER, Role.ADMIN, Role.MANAGER):
        raise HTTPException(403, "Only owners, admins and store managers can approve edits")
    ctx.membership.approval_pin_hash = bcrypt.hashpw(data.pin.encode(), bcrypt.gensalt()).decode() if data.pin else None
    ctx.db.commit()
    return {"has_pin": bool(data.pin)}


STAFF_ROLES = Literal["ADMIN", "MANAGER", "BILLING", "INVENTORY", "ACCOUNTANT"]


class MemberIn(BaseModel):
    email: EmailStr
    role: STAFF_ROLES
    name: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, max_length=20)
    password: str | None = Field(None, min_length=8, max_length=128)  # optional; generated when empty


def _temp_password() -> str:
    import secrets

    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


@router.post("/members", status_code=201)
def add_member(data: MemberIn, ctx: BCtx, request: Request):
    """Add a staff member. A new e-mail gets a login created here (temporary password, changed at first
    sign-in). An e-mail that already has a login — e.g. an accountant who also works for other businesses —
    is invited instead: they keep their own password and accept the invitation after signing in."""
    from ..security import hash_password
    from ..services import mailer
    from ..services.platform_audit import log as plog

    ctx.need("users", "create")
    if data.role == "ADMIN" and ctx.role != Role.OWNER:
        raise HTTPException(403, "Only the owner can add business admins")
    email = data.email.lower().strip()
    u = ctx.db.scalar(select(User).where(func.lower(User.email) == email))
    if u and ctx.db.scalar(select(Membership).where(Membership.user_id == u.id, Membership.business_id == ctx.bid)):
        raise HTTPException(409, "This person already has access to this business")
    check_user_limit(ctx.db, ctx.bid, u.id if u else None)
    if u is None:
        if not (data.name or "").strip():
            raise HTTPException(422, "Enter the staff member's name")
        password = data.password or _temp_password()
        u = User(name=data.name.strip(), email=email, phone=(data.phone or "").strip() or None,
                 password_hash=hash_password(password), must_change_password=True, created_by_business_id=ctx.bid)
        ctx.db.add(u)
        ctx.db.flush()
        ctx.db.add(Membership(user_id=u.id, business_id=ctx.bid, role=Role(data.role), status="ACTIVE", invited_by=ctx.user.name))
        plog(ctx.db, ctx.user, "STAFF", "staff", f"Created staff login {email} ({data.role}) for {ctx.business.name}",
             entity_id=u.id, request=request)
        ctx.db.commit()
        mailed = False
        try:
            from .auth import frontend_url
            from html import escape

            from ..services import config_store

            cfg = mailer.business_smtp(ctx.db, ctx.bid, None) or mailer.system_smtp(ctx.db)
            if cfg:
                body = mailer.layout(f"Your login for {escape(ctx.business.name)}", f"""
                    <p>Hello {escape(u.name)},</p>
                    <p>{escape(ctx.user.name)} has created a {config_store.app_name()} login for you to work in <b>{escape(ctx.business.name)}</b>.</p>
                    <p>Sign in at <a href="{frontend_url(request)}/login">{frontend_url(request)}/login</a><br>
                    E-mail: <b>{escape(email)}</b><br>Temporary password: <b style="font-family:monospace">{password}</b></p>
                    <p>You will choose your own password at the first sign-in.</p>""")
                mailer.send(cfg, [email], f"Your login for {ctx.business.name}", body)
                mailed = True
        except Exception:  # noqa: BLE001 — no mail server: the owner shares the details
            pass
        return {"created": True, "invited": False, "email": email, "temp_password": password, "mailed": mailed}
    ctx.db.add(Membership(user_id=u.id, business_id=ctx.bid, role=Role(data.role), status="INVITED", invited_by=ctx.user.name))
    plog(ctx.db, ctx.user, "STAFF", "staff", f"Invited existing login {email} ({data.role}) to {ctx.business.name}",
         entity_id=u.id, request=request)
    ctx.db.commit()
    return {"created": False, "invited": True, "email": email, "name": u.name}


class RoleIn(BaseModel):
    role: STAFF_ROLES


@router.put("/members/{member_id}")
def change_role(member_id: str, data: RoleIn, ctx: BCtx):
    ctx.need("users", "edit")
    m = ctx.db.get(Membership, member_id)
    if not m or m.business_id != ctx.bid or m.role == Role.OWNER:
        raise HTTPException(404, "Member not found")
    m.role = Role(data.role)
    ctx.db.commit()
    return {"ok": True}


@router.delete("/members/{member_id}", status_code=204)
def remove_member(member_id: str, ctx: BCtx):
    ctx.need("users", "delete")
    m = ctx.db.get(Membership, member_id)
    if not m or m.business_id != ctx.bid:
        raise HTTPException(404, "Member not found")
    if m.role == Role.OWNER:
        raise HTTPException(400, "The owner cannot be removed")
    ctx.db.delete(m)
    ctx.db.commit()


@router.post("/members/{member_id}/reset-password")
def member_reset(member_id: str, ctx: BCtx, request: Request):
    """Owner / admin e-mails a password-reset link to a staff member of this business."""
    from ..services import mailer
    from .auth import issue_reset

    from ..config import get_settings

    ctx.need("users", "edit")
    m = ctx.db.get(Membership, member_id)
    if not m or m.business_id != ctx.bid or m.role == Role.OWNER:
        raise HTTPException(404, "Member not found")
    u = ctx.db.get(User, m.user_id)
    # the link goes only to the person's own mailbox, so a shared staff member is never locked out elsewhere
    link = issue_reset(ctx.db, u, request, actor=ctx.user)
    ctx.db.commit()
    show = get_settings().is_dev and not mailer.system_smtp(ctx.db)
    return {"sent": True, "dev_link": link if show else None}


@router.post("/members/{member_id}/temp-password")
def member_temp_password(member_id: str, ctx: BCtx, request: Request):
    """Set a new temporary password for a login this business created — only while the person works for no
    other business (otherwise they reset it themselves from the sign-in page)."""
    from ..security import hash_password
    from ..services.platform_audit import log as plog

    ctx.need("users", "edit")
    m = ctx.db.get(Membership, member_id)
    if not m or m.business_id != ctx.bid or m.role == Role.OWNER:
        raise HTTPException(404, "Member not found")
    u = ctx.db.get(User, m.user_id)
    if not _managed(ctx, u, _other_business_counts(ctx, [u.id]).get(u.id, 0)):
        raise HTTPException(403, "This person also uses their login for other businesses (or created it themselves). "
                                 "Send them a reset link instead — only they can change their password.")
    password = _temp_password()
    u.password_hash, u.must_change_password = hash_password(password), True
    u.token_version = (u.token_version or 0) + 1
    plog(ctx.db, ctx.user, "STAFF", "staff", f"Set a temporary password for {u.email}", entity_id=u.id, request=request)
    ctx.db.commit()
    return {"temp_password": password, "email": u.email}


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



