"""Super Admin: user management across every level, platform audit trail and platform backups."""

import datetime as dt
import secrets
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select

from ..deps import DB, SuperAdmin
from ..gst.constants import PlatformRole, Role
from ..models import (
    AuditLog,
    Backup,
    Business,
    Membership,
    PlatformBackup,
    PlatformSetting,
    Subscription,
    User,
)
from ..security import hash_password
from ..services import backup as bk
from ..services import config_store, mailer
from ..services import plans as P
from ..services.platform_audit import log
from .auth import frontend_url, issue_reset

router = APIRouter(prefix="/admin", tags=["super admin"])

Level = Literal["SUPERADMIN", "RESELLER", "OWNER", "STAFF"]


def _level(db, u: User) -> str:
    if u.platform_role:
        return u.platform_role
    if db.scalar(select(Business.id).where(Business.owner_id == u.id).limit(1)) or db.get(Subscription, u.id):
        return "OWNER"
    if db.scalar(select(Membership.id).where(Membership.user_id == u.id).limit(1)):
        return "STAFF"
    return "USER"


def _user_row(db, u: User) -> dict:
    ms = db.execute(select(Membership, Business).join(Business, Business.id == Membership.business_id)
                    .where(Membership.user_id == u.id)).all()
    sub = db.get(Subscription, u.id)
    reseller = db.get(User, sub.reseller_id) if sub and sub.reseller_id else None
    locked = u.locked_until and (u.locked_until if u.locked_until.tzinfo else u.locked_until.replace(tzinfo=dt.timezone.utc)) > dt.datetime.now(dt.timezone.utc)
    return dict(id=u.id, name=u.name, email=u.email, phone=u.phone, level=_level(db, u), active=u.is_active,
                locked=bool(locked), totp=u.totp_enabled, last_login_at=u.last_login_at, created_at=u.created_at,
                commission_pct=float(u.reseller_commission_pct or 0) if u.platform_role == "RESELLER" else None,
                plan=P.current(db, u.id).plan if sub else None, reseller=reseller.name if reseller else None,
                memberships=[dict(business_id=b.id, business=b.name, role=m.role.value, owner=b.owner_id == u.id)
                             for m, b in ms])


def _get_user(db, user_id: str) -> User:
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u


def _superadmin_count(db) -> int:
    return db.scalar(select(func.count(User.id)).where(User.platform_role == PlatformRole.SUPERADMIN.value,
                                                       User.is_active.is_(True))) or 0


# ---------------------------------------------------------------- users
@router.get("/users")
def users(db: DB, _: SuperAdmin, search: str | None = None, level: str | None = None, status: str | None = None,
          limit: int = 200):
    q = select(User).order_by(User.created_at.desc())
    if search:
        like = f"%{search}%"
        q = q.where(or_(User.name.ilike(like), User.email.ilike(like), User.phone.ilike(like)))
    if status == "active":
        q = q.where(User.is_active.is_(True))
    elif status == "inactive":
        q = q.where(User.is_active.is_(False))
    rows = [_user_row(db, u) for u in db.scalars(q.limit(min(limit, 1000)))]
    db.commit()
    if level:
        rows = [r for r in rows if r["level"] == level]
    if status == "locked":
        rows = [r for r in rows if r["locked"]]
    return rows


@router.get("/hierarchy")
def hierarchy(db: DB, _: SuperAdmin):
    """Super admins → resellers → accounts (owners) → businesses → staff."""
    def account_node(owner: User) -> dict:
        sub = P.current(db, owner.id)
        businesses = []
        for b in db.scalars(select(Business).where(Business.owner_id == owner.id).order_by(Business.name)):
            staff = db.execute(select(Membership, User).join(User, User.id == Membership.user_id)
                               .where(Membership.business_id == b.id, Membership.user_id != owner.id)).all()
            businesses.append(dict(id=b.id, name=b.name, gstin=b.gstin,
                                   staff=[dict(id=u.id, name=u.name, email=u.email, role=m.role.value, active=u.is_active)
                                          for m, u in staff]))
        return dict(id=owner.id, name=owner.name, email=owner.email, active=owner.is_active, plan=sub.plan,
                    status=sub.status, businesses=businesses)

    subs = db.execute(select(Subscription, User).join(User, User.id == Subscription.account_id)).all()
    by_reseller: dict[str | None, list] = {}
    for s, u in subs:
        by_reseller.setdefault(s.reseller_id, []).append(account_node(u))
    admins = db.scalars(select(User).where(User.platform_role == "SUPERADMIN")).all()
    resellers = db.scalars(select(User).where(User.platform_role == "RESELLER").order_by(User.name)).all()
    db.commit()
    return {
        "superadmins": [dict(id=u.id, name=u.name, email=u.email, active=u.is_active) for u in admins],
        "resellers": [dict(id=r.id, name=r.name, email=r.email, active=r.is_active,
                           commission_pct=float(r.reseller_commission_pct or 0), accounts=by_reseller.get(r.id, []))
                      for r in resellers],
        "direct_accounts": by_reseller.get(None, []),
    }


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = None
    level: Level
    password: str | None = Field(None, min_length=8, max_length=128)  # blank = generate a temporary one
    commission_pct: Decimal = Field(Decimal("20"), ge=0, le=90)       # resellers
    plan: Literal["FREE", "STARTER", "PROFESSIONAL", "ENTERPRISE"] = "FREE"  # owners
    valid_days: int = Field(0, ge=0, le=3650)
    reseller_id: str | None = None                                     # owners under a reseller
    business_id: str | None = None                                     # staff
    role: Literal["ADMIN", "MANAGER", "BILLING", "INVENTORY", "ACCOUNTANT"] = "BILLING"
    send_email: bool = False


@router.post("/users", status_code=201)
def create_user(data: UserCreate, db: DB, me: SuperAdmin, request: Request):
    if db.scalar(select(User).where(func.lower(User.email) == data.email.lower())):
        raise HTTPException(409, "An account with this email already exists")
    temp = data.password or secrets.token_urlsafe(9)
    u = User(name=data.name, email=data.email.lower(), phone=data.phone, password_hash=hash_password(temp),
             must_change_password=not data.password)
    if data.level in ("SUPERADMIN", "RESELLER"):
        u.platform_role = data.level
        if data.level == "RESELLER":
            u.reseller_commission_pct = data.commission_pct
    db.add(u)
    db.flush()
    if data.level == "OWNER":
        if data.reseller_id and not db.scalar(select(User.id).where(User.id == data.reseller_id, User.platform_role == "RESELLER")):
            raise HTTPException(400, "Reseller not found")
        sub = Subscription(account_id=u.id, plan=data.plan, status="ACTIVE", reseller_id=data.reseller_id,
                           valid_until=dt.date.today() + dt.timedelta(days=data.valid_days) if data.valid_days else None)
        db.add(sub)
    if data.level == "STAFF":
        biz = db.get(Business, data.business_id) if data.business_id else None
        if not biz:
            raise HTTPException(400, "Choose the business this staff member works in")
        P.check_user_limit(db, biz.id, u.id)
        db.add(Membership(user_id=u.id, business_id=biz.id, role=Role(data.role)))
    log(db, me, "CREATE", "user", f"Created {data.level.lower()} {u.email}", entity_id=u.id, request=request)
    db.flush()
    emailed = False
    if data.send_email:
        cfg = mailer.system_smtp(db)
        if cfg:
            mailer.send(cfg, [u.email], f"Your {config_store.app_name()} account", mailer.layout(f"Welcome to {config_store.app_name()}", f"""
                <p>Hello {u.name},</p><p>An account has been created for you.</p>
                <p>Sign in at <a href="{frontend_url(request)}/login">{frontend_url(request)}/login</a><br>
                Email: <b>{u.email}</b><br>Temporary password: <b>{temp}</b></p>
                <p>Please change the password after signing in (Settings → Security).</p>"""))
            emailed = True
    db.commit()
    return {"id": u.id, "email": u.email, "temporary_password": None if data.password else temp, "emailed": emailed}


class UserEdit(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = None


@router.put("/users/{user_id}")
def edit_user(user_id: str, data: UserEdit, db: DB, me: SuperAdmin, request: Request):
    u = _get_user(db, user_id)
    if data.email.lower() != u.email and db.scalar(select(User).where(func.lower(User.email) == data.email.lower())):
        raise HTTPException(409, "Another account uses this email")
    changes = [f"{k}: {getattr(u, k)} → {v}" for k, v in (("name", data.name), ("email", data.email.lower()), ("phone", data.phone))
               if getattr(u, k) != v]
    u.name, u.email, u.phone = data.name, data.email.lower(), data.phone
    log(db, me, "UPDATE", "user", f"Edited {u.email}: " + "; ".join(changes), entity_id=u.id, request=request)
    db.commit()
    return _user_row(db, u)


class ResetIn(BaseModel):
    mode: Literal["email", "temp"] = "temp"


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: str, data: ResetIn, db: DB, me: SuperAdmin, request: Request):
    u = _get_user(db, user_id)
    u.failed_logins, u.locked_until = 0, None
    if data.mode == "email":
        link = issue_reset(db, u, request, actor=me)
        log(db, me, "ACTION", "password", f"Sent password reset link to {u.email}", entity_id=u.id, request=request)
        db.commit()
        return {"sent": True, "dev_link": link if not mailer.system_smtp(db) else None}
    temp = secrets.token_urlsafe(9)
    u.password_hash = hash_password(temp)
    u.token_version = (u.token_version or 0) + 1
    u.must_change_password = True
    log(db, me, "UPDATE", "password", f"Set temporary password for {u.email} (sessions signed out)", entity_id=u.id, request=request)
    db.commit()
    return {"temporary_password": temp}


class ActiveIn(BaseModel):
    active: bool


@router.put("/users/{user_id}/active")
def set_active(user_id: str, data: ActiveIn, db: DB, me: SuperAdmin, request: Request):
    u = _get_user(db, user_id)
    if u.id == me.id:
        raise HTTPException(400, "You cannot deactivate yourself")
    if not data.active and u.platform_role == "SUPERADMIN" and _superadmin_count(db) <= 1:
        raise HTTPException(400, "At least one active super admin is required")
    u.is_active = data.active
    if not data.active:
        u.token_version = (u.token_version or 0) + 1  # sign out immediately
    log(db, me, "UPDATE", "user", f"{'Activated' if data.active else 'Deactivated'} {u.email}", entity_id=u.id, request=request)
    db.commit()
    return {"active": u.is_active}


@router.post("/users/{user_id}/unlock")
def unlock(user_id: str, db: DB, me: SuperAdmin, request: Request):
    u = _get_user(db, user_id)
    u.failed_logins, u.locked_until = 0, None
    log(db, me, "UPDATE", "user", f"Unlocked {u.email}", entity_id=u.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/reset-2fa")
def reset_2fa(user_id: str, db: DB, me: SuperAdmin, request: Request):
    u = _get_user(db, user_id)
    u.totp_enabled, u.totp_secret_enc = False, None
    log(db, me, "UPDATE", "security", f"Turned off two-factor sign-in for {u.email}", entity_id=u.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/sign-out")
def sign_out_user(user_id: str, db: DB, me: SuperAdmin, request: Request):
    u = _get_user(db, user_id)
    u.token_version = (u.token_version or 0) + 1
    log(db, me, "ACTION", "login", f"Signed out {u.email} from all devices", entity_id=u.id, request=request)
    db.commit()
    return {"ok": True}


class PlatformRoleIn(BaseModel):
    role: Literal["SUPERADMIN", "RESELLER"] | None = None
    commission_pct: Decimal = Field(Decimal("20"), ge=0, le=90)


@router.put("/users/{user_id}/platform-role")
def set_platform_role(user_id: str, data: PlatformRoleIn, db: DB, me: SuperAdmin, request: Request):
    u = _get_user(db, user_id)
    if u.platform_role == "SUPERADMIN" and data.role != "SUPERADMIN":
        if u.id == me.id:
            raise HTTPException(400, "You cannot remove your own super admin access")
        if _superadmin_count(db) <= 1:
            raise HTTPException(400, "At least one active super admin is required")
    u.platform_role = data.role
    u.reseller_commission_pct = data.commission_pct if data.role == "RESELLER" else None
    log(db, me, "UPDATE", "user", f"Platform role of {u.email} set to {data.role or 'none'}", entity_id=u.id, request=request)
    db.commit()
    return _user_row(db, u)


@router.delete("/users/{user_id}")
def delete_user(user_id: str, db: DB, me: SuperAdmin, request: Request, force: bool = False):
    """Owners with businesses need force=true: their businesses are backed up first, then deleted."""
    u = _get_user(db, user_id)
    if u.id == me.id:
        raise HTTPException(400, "You cannot delete yourself")
    if u.platform_role == "SUPERADMIN" and _superadmin_count(db) <= 1:
        raise HTTPException(400, "At least one active super admin is required")
    owned = db.scalars(select(Business).where(Business.owner_id == u.id)).all()
    backup_id = None
    if owned:
        if not force:
            raise HTTPException(409, f"{u.name} owns {len(owned)} business(es). Transfer them to another owner, "
                                     "or delete with force (a backup is taken first).")
        blob = bk.account_snapshot(db, u)
        b = bk.create_platform_backup(db, "ACCOUNT", f"Before deleting {u.email}", blob, "SAFETY", me.id, u.id)
        backup_id = b.id
        for biz in owned:
            db.delete(biz)
    log(db, me, "DELETE", "user", f"Deleted user {u.email}" + (f" and {len(owned)} business(es) (backup kept)" if owned else ""),
        entity_id=u.id, request=request)
    db.flush()
    # database-level delete: memberships, subscription, reset tokens cascade; history keeps a blank user
    db.execute(sa_delete(User).where(User.id == u.id))
    db.commit()
    return {"deleted": True, "safety_backup_id": backup_id}


# ---------------------------------------------------------------- businesses (metadata only)
@router.get("/businesses")
def businesses(db: DB, _: SuperAdmin, search: str | None = None):
    q = select(Business, User).outerjoin(User, User.id == Business.owner_id).order_by(Business.created_at.desc())
    if search:
        like = f"%{search}%"
        q = q.where(or_(Business.name.ilike(like), Business.gstin.ilike(like), User.email.ilike(like)))
    out = []
    for b, owner in db.execute(q.limit(500)):
        out.append(dict(id=b.id, name=b.name, gstin=b.gstin, created_at=b.created_at,
                        owner=owner.name if owner else None, owner_email=owner.email if owner else None,
                        members=db.scalar(select(func.count(Membership.id)).where(Membership.business_id == b.id)),
                        backups=db.scalar(select(func.count(Backup.id)).where(Backup.business_id == b.id))))
    return out


class TransferIn(BaseModel):
    new_owner_email: EmailStr


@router.post("/businesses/{business_id}/transfer")
def transfer_business(business_id: str, data: TransferIn, db: DB, me: SuperAdmin, request: Request):
    biz = db.get(Business, business_id)
    new = db.scalar(select(User).where(func.lower(User.email) == data.new_owner_email.lower()))
    if not biz or not new:
        raise HTTPException(404, "Business or new owner not found")
    if not db.get(Subscription, new.id):
        P.start_trial(db, new.id)
    old_owner = biz.owner_id
    for m in db.scalars(select(Membership).where(Membership.business_id == biz.id)):
        if m.user_id == old_owner and m.role == Role.OWNER:
            m.role = Role.ADMIN
    m = db.scalar(select(Membership).where(Membership.business_id == biz.id, Membership.user_id == new.id))
    if m:
        m.role, m.permissions = Role.OWNER, None
    else:
        db.add(Membership(user_id=new.id, business_id=biz.id, role=Role.OWNER))
    biz.owner_id = new.id
    log(db, me, "UPDATE", "business", f"Transferred {biz.name} to {new.email}", entity_id=biz.id, request=request)
    log(db, me, "UPDATE", "business", f"Ownership transferred to {new.email} by platform admin", entity_id=biz.id,
        business_id=biz.id, request=request)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- audit trail
@router.get("/audit")
def platform_audit(db: DB, _: SuperAdmin, scope: Literal["platform", "business", "all"] = "platform",
                   business_id: str | None = None, user_id: str | None = None, action: str | None = None,
                   search: str | None = None, date_from: dt.date | None = None, date_to: dt.date | None = None,
                   limit: int = 100, offset: int = 0):
    q = select(AuditLog)
    if business_id:
        q = q.where(AuditLog.business_id == business_id)
    elif scope == "platform":
        q = q.where(AuditLog.business_id.is_(None))
    elif scope == "business":
        q = q.where(AuditLog.business_id.is_not(None))
    if user_id:
        q = q.where(or_(AuditLog.user_id == user_id, AuditLog.entity_id == user_id))
    if action:
        q = q.where(AuditLog.action == action)
    if search:
        q = q.where(AuditLog.summary.ilike(f"%{search}%"))
    if date_from:
        q = q.where(AuditLog.created_at >= dt.datetime.combine(date_from, dt.time.min, dt.timezone.utc))
    if date_to:
        q = q.where(AuditLog.created_at < dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min, dt.timezone.utc))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    names = {b.id: b.name for b in db.scalars(select(Business))}
    rows = db.scalars(q.order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).offset(offset)).all()
    return {"total": total, "rows": [dict(id=a.id, created_at=a.created_at, user=a.user_name, action=a.action,
                                          entity=a.entity, entity_id=a.entity_id, summary=a.summary, ip=a.ip,
                                          business=names.get(a.business_id)) for a in rows]}


# ---------------------------------------------------------------- backups
def _pb_row(b: PlatformBackup) -> dict:
    return dict(id=b.id, scope=b.scope, ref_id=b.ref_id, label=b.label, kind=b.kind, size=b.size, created_at=b.created_at)


@router.get("/backups")
def list_backups(db: DB, _: SuperAdmin):
    platform = [_pb_row(b) for b in db.scalars(select(PlatformBackup).order_by(PlatformBackup.created_at.desc()).limit(100))]
    names = {b.id: b.name for b in db.scalars(select(Business))}
    business = [dict(id=b.id, business_id=b.business_id, business=names.get(b.business_id), kind=b.kind, size=b.size,
                     created_at=b.created_at)
                for b in db.scalars(select(Backup).order_by(Backup.created_at.desc()).limit(200))]
    setting = db.get(PlatformSetting, "auto_full_backup")
    return {"platform": platform, "business": business,
            "auto_full_backup": (setting.value or {}).get("enabled", True) if setting else True}


class BackupIn(BaseModel):
    scope: Literal["FULL", "ACCOUNT", "BUSINESS"]
    ref_id: str | None = None  # account (owner user id) or business id
    include_business_backups: bool = False


@router.post("/backups", status_code=201)
def create_backup(data: BackupIn, db: DB, me: SuperAdmin, request: Request):
    if data.scope == "FULL":
        b = bk.create_platform_backup(db, "FULL", f"Full backup by {me.name}", bk.full_snapshot(db, data.include_business_backups),
                                      "MANUAL", me.id)
        out = _pb_row(b)
    elif data.scope == "ACCOUNT":
        owner = _get_user(db, data.ref_id or "")
        b = bk.create_platform_backup(db, "ACCOUNT", f"Account: {owner.name} ({owner.email})",
                                      bk.account_snapshot(db, owner), "MANUAL", me.id, owner.id)
        out = _pb_row(b)
    else:
        biz = db.get(Business, data.ref_id or "")
        if not biz:
            raise HTTPException(404, "Business not found")
        b = bk.create_backup(db, biz, me.id)
        out = dict(id=b.id, business_id=biz.id, business=biz.name, kind=b.kind, size=b.size, created_at=b.created_at)
    log(db, me, "CREATE", "backup", f"{data.scope.title()} backup created", request=request)
    db.commit()
    return out


@router.get("/backups/{backup_id}/download")
def download(backup_id: str, db: DB, me: SuperAdmin, request: Request, kind: Literal["platform", "business"] = "platform"):
    if kind == "platform":
        b = db.get(PlatformBackup, backup_id)
        if not b:
            raise HTTPException(404, "Backup not found")
        name = f"{b.scope.lower()}-backup-{b.created_at:%Y%m%d-%H%M}.gstbak"
    else:
        b = db.get(Backup, backup_id)
        if not b:
            raise HTTPException(404, "Backup not found")
        biz = db.get(Business, b.business_id)
        name = bk.filename(biz.name if biz else "business", b.created_at)
    log(db, me, "EXPORT", "backup", f"Downloaded {name}", request=request)
    db.commit()
    return Response(b.data, media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.delete("/backups/{backup_id}", status_code=204)
def delete_backup(backup_id: str, db: DB, me: SuperAdmin, request: Request, kind: Literal["platform", "business"] = "platform"):
    b = db.get(PlatformBackup if kind == "platform" else Backup, backup_id)
    if b:
        db.delete(b)
        log(db, me, "DELETE", "backup", f"Deleted {kind} backup {backup_id}", request=request)
        db.commit()


class AutoIn(BaseModel):
    enabled: bool


@router.put("/backups/auto")
def set_auto(data: AutoIn, db: DB, me: SuperAdmin, request: Request):
    s = db.get(PlatformSetting, "auto_full_backup") or PlatformSetting(key="auto_full_backup")
    s.value = {"enabled": data.enabled}
    db.merge(s)
    log(db, me, "UPDATE", "backup", f"Automatic daily full backup {'on' if data.enabled else 'off'}", request=request)
    db.commit()
    return {"enabled": data.enabled}


def _restore(db, me: User, request: Request, blob: bytes, source: str, owner_email: str | None, confirm: str | None):
    fmt, data = bk.detect(blob)
    if fmt == bk.FULL_FORMAT:
        if confirm != "RESTORE ALL DATA":
            raise HTTPException(400, {"message": "This is a FULL platform backup. Restoring replaces ALL current data. "
                                                 "Type RESTORE ALL DATA to confirm.", "code": "CONFIRM_FULL"})
        safety = bk.create_platform_backup(db, "FULL", f"Safety backup before restore by {me.name}",
                                           bk.full_snapshot(db, True), "SAFETY", me.id)
        db.commit()
        safety_id = safety.id
        counts = bk.restore_full(db, data, me)
        log(db, me, "ACTION", "backup", f"FULL platform restore from {source} (safety backup {safety_id})", request=request)
        db.commit()
        return {"restored": "FULL", "rows": counts, "safety_backup_id": safety_id}
    owner = db.scalar(select(User).where(func.lower(User.email) == (owner_email or "").lower()))
    if not owner:
        raise HTTPException(400, "Enter the email of the account owner to restore into")
    if not db.get(Subscription, owner.id):
        P.start_trial(db, owner.id)
    restored = [bk.restore_as_new(db, blob, owner.id, None)] if fmt == bk.FORMAT else bk.restore_account(db, data, owner.id)
    log(db, me, "ACTION", "backup", f"Restored {len(restored)} business(es) from {source} into {owner.email}", request=request)
    db.commit()
    return {"restored": "ACCOUNT" if fmt == bk.ACCOUNT_FORMAT else "BUSINESS",
            "businesses": [dict(id=b.id, name=b.name) for b in restored]}


@router.post("/backups/import")
async def import_backup(db: DB, me: SuperAdmin, request: Request, file: UploadFile = File(...),
                        owner_email: str | None = Form(None), confirm: str | None = Form(None)):
    """Business or account backup → new business(es) under `owner_email`.
    Full backup → replaces ALL data (confirm = "RESTORE ALL DATA"; a safety backup is taken first)."""
    return _restore(db, me, request, await file.read(), file.filename or "upload", owner_email, confirm)


class RestoreStored(BaseModel):
    owner_email: str | None = None
    confirm: str | None = None


@router.post("/backups/{backup_id}/restore")
def restore_stored(backup_id: str, data: RestoreStored, db: DB, me: SuperAdmin, request: Request,
                   kind: Literal["platform", "business"] = "platform"):
    b = db.get(PlatformBackup if kind == "platform" else Backup, backup_id)
    if not b:
        raise HTTPException(404, "Backup not found")
    return _restore(db, me, request, b.data, f"stored backup {backup_id}", data.owner_email, data.confirm)
