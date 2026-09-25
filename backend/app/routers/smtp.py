"""SMTP settings per level: platform (super admin), reseller, business. Password is write-only (encrypted)."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from ..deps import DB, BCtx, Reseller, SuperAdmin
from ..models import SmtpConfig
from ..security import encrypt_secret
from ..services import mailer
from ..services.platform_audit import log
from ..services.plans import account_of

router = APIRouter(tags=["email"])


class SmtpIn(BaseModel):
    host: str = Field(min_length=3, max_length=200)
    port: int = Field(587, ge=1, le=65535)
    security: Literal["STARTTLS", "SSL", "NONE"] = "STARTTLS"
    username: str | None = None
    password: str | None = None  # leave empty to keep the saved password
    from_email: EmailStr
    from_name: str | None = Field(None, max_length=120)


class TestIn(BaseModel):
    to: EmailStr


def _out(row: SmtpConfig | None, effective: mailer.Smtp | None) -> dict:
    return {
        "configured": row is not None,
        "settings": None if row is None else dict(host=row.host, port=row.port, security=row.security, username=row.username,
                                                   from_email=row.from_email, from_name=row.from_name,
                                                   password_set=bool(row.password_enc)),
        "effective_source": effective.source if effective else None,
        "effective_from": effective.from_email if effective else None,
    }


def _save(db, scope: str, owner_id: str, data: SmtpIn) -> SmtpConfig:
    row = db.scalar(select(SmtpConfig).where(SmtpConfig.scope == scope, SmtpConfig.owner_id == owner_id))
    if row is None:
        row = SmtpConfig(scope=scope, owner_id=owner_id)
        db.add(row)
    for k in ("host", "port", "security", "username", "from_email", "from_name"):
        setattr(row, k, getattr(data, k))
    if data.password:
        row.password_enc = encrypt_secret(data.password)
    db.flush()
    return row


def _remove(db, scope: str, owner_id: str) -> None:
    row = db.scalar(select(SmtpConfig).where(SmtpConfig.scope == scope, SmtpConfig.owner_id == owner_id))
    if row:
        db.delete(row)


def _test(cfg: mailer.Smtp | None, to: str, who: str) -> dict:
    mailer.send(cfg, [to], "Test e-mail from GST Billing",
                mailer.layout("It works!", f"<p>This test e-mail was sent using the <b>{cfg.source.lower() if cfg else ''}</b> "
                                           f"mail settings of {who}.</p>"))
    return {"sent": True, "via": cfg.source if cfg else None}


# ---------------------------------------------------------------- platform (super admin) — used for password resets
@router.get("/admin/smtp")
def platform_get(db: DB, _: SuperAdmin):
    return _out(db.scalar(select(SmtpConfig).where(SmtpConfig.scope == "PLATFORM")), mailer.system_smtp(db))


@router.put("/admin/smtp")
def platform_put(data: SmtpIn, db: DB, me: SuperAdmin, request: Request):
    _save(db, "PLATFORM", "", data)
    log(db, me, "UPDATE", "email settings", f"Platform SMTP set to {data.host} as {data.from_email}", request=request)
    db.commit()
    return platform_get(db, me)


@router.delete("/admin/smtp", status_code=204)
def platform_delete(db: DB, me: SuperAdmin, request: Request):
    _remove(db, "PLATFORM", "")
    log(db, me, "DELETE", "email settings", "Platform SMTP removed", request=request)
    db.commit()


@router.post("/admin/smtp/test")
def platform_test(data: TestIn, db: DB, _: SuperAdmin):
    return _test(mailer.system_smtp(db), data.to, "the platform")


# ---------------------------------------------------------------- reseller — used for their customers' business mail
@router.get("/reseller/smtp")
def reseller_get(db: DB, me: Reseller):
    row = db.scalar(select(SmtpConfig).where(SmtpConfig.scope == "RESELLER", SmtpConfig.owner_id == me.id))
    return _out(row, mailer._from_row(row, "RESELLER") or mailer.system_smtp(db))


@router.put("/reseller/smtp")
def reseller_put(data: SmtpIn, db: DB, me: Reseller, request: Request):
    _save(db, "RESELLER", me.id, data)
    log(db, me, "UPDATE", "email settings", f"Reseller SMTP set to {data.host}", request=request)
    db.commit()
    return reseller_get(db, me)


@router.delete("/reseller/smtp", status_code=204)
def reseller_delete(db: DB, me: Reseller):
    _remove(db, "RESELLER", me.id)
    db.commit()


@router.post("/reseller/smtp/test")
def reseller_test(data: TestIn, db: DB, me: Reseller):
    row = db.scalar(select(SmtpConfig).where(SmtpConfig.scope == "RESELLER", SmtpConfig.owner_id == me.id))
    return _test(mailer._from_row(row, "RESELLER") or mailer.system_smtp(db), data.to, me.name)


# ---------------------------------------------------------------- business — invoices, reminders, backups
@router.get("/smtp")
def business_get(ctx: BCtx):
    ctx.need("settings", "view")
    row = ctx.db.scalar(select(SmtpConfig).where(SmtpConfig.scope == "BUSINESS", SmtpConfig.owner_id == ctx.bid))
    return _out(row, mailer.business_smtp(ctx.db, ctx.bid, account_of(ctx.db, ctx.bid)))


@router.put("/smtp")
def business_put(data: SmtpIn, ctx: BCtx):
    ctx.need("settings", "edit")
    _save(ctx.db, "BUSINESS", ctx.bid, data)
    ctx.db.commit()
    return business_get(ctx)


@router.delete("/smtp", status_code=204)
def business_delete(ctx: BCtx):
    ctx.need("settings", "edit")
    _remove(ctx.db, "BUSINESS", ctx.bid)
    ctx.db.commit()


@router.post("/smtp/test")
def business_test(data: TestIn, ctx: BCtx):
    ctx.need("settings", "edit")
    return _test(mailer.business_smtp(ctx.db, ctx.bid, account_of(ctx.db, ctx.bid)), data.to, ctx.business.name)

