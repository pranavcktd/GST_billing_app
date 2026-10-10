"""Super admin: e-mail senders (API providers) and which business uses which. See services/mailer.py."""

import datetime as dt
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update

from ..deps import DB, SuperAdmin
from ..models import Business, MailSender
from ..security import encrypt_secret
from ..services import mailer
from ..services.platform_audit import log

router = APIRouter(prefix="/admin/mail", tags=["e-mail"])


def _out(db, s: MailSender) -> dict:
    used = db.scalar(select(func.count(Business.id)).where(Business.mail_sender_id == s.id)) or 0
    return dict(id=s.id, label=s.label, provider=s.provider, provider_label=mailer.PROVIDERS.get(s.provider, s.provider),
                region=s.region, from_email=s.from_email,
                from_name=s.from_name, reply_to=s.reply_to, is_default=s.is_default, active=s.active, secret_set=bool(s.secret_enc),
                last_test_at=s.last_test_at, last_error=s.last_error, businesses=used)


@router.get("/senders")
def senders(db: DB, _: SuperAdmin):
    rows = db.scalars(select(MailSender).order_by(MailSender.is_default.desc(), MailSender.created_at)).all()
    return {"senders": [_out(db, s) for s in rows], "providers": mailer.PROVIDERS}


class SenderIn(BaseModel):
    label: str = Field(min_length=2, max_length=80)
    provider: Literal["BREVO", "ZEPTOMAIL", "RESEND", "SENDGRID", "POSTMARK"]
    secret: str | None = Field(None, max_length=500)  # API key; blank = keep
    region: Literal["IN", "COM", "EU"] | None = None
    from_email: EmailStr
    from_name: str | None = Field(None, max_length=120)
    reply_to: EmailStr | None = None
    active: bool = True
    is_default: bool = False


def _apply(s: MailSender, data: SenderIn) -> None:
    for k in ("label", "provider", "region", "from_name", "active"):
        setattr(s, k, getattr(data, k))
    s.from_email, s.reply_to = str(data.from_email), str(data.reply_to) if data.reply_to else None
    if data.secret:
        s.secret_enc = encrypt_secret(data.secret.strip())
    if not s.secret_enc:
        raise HTTPException(422, "Enter the provider's API key")


def _make_default(db, s: MailSender) -> None:
    db.execute(update(MailSender).where(MailSender.id != s.id).values(is_default=False))
    s.is_default = True


@router.post("/senders", status_code=201)
def add_sender(data: SenderIn, db: DB, me: SuperAdmin, request: Request):
    s = MailSender()
    _apply(s, data)
    db.add(s)
    db.flush()
    if data.is_default or not db.scalar(select(MailSender.id).where(MailSender.is_default.is_(True), MailSender.id != s.id)):
        _make_default(db, s)
    log(db, me, "CONFIG", "mail", f"E-mail sender added: {s.label} ({s.provider}, {s.from_email})", request=request)
    db.commit()
    return _out(db, s)


@router.put("/senders/{sid}")
def edit_sender(sid: str, data: SenderIn, db: DB, me: SuperAdmin, request: Request):
    s = db.get(MailSender, sid)
    if not s:
        raise HTTPException(404, "Sender not found")
    _apply(s, data)
    if data.is_default:
        _make_default(db, s)
    log(db, me, "CONFIG", "mail", f"E-mail sender updated: {s.label}", request=request)
    db.commit()
    return _out(db, s)


@router.delete("/senders/{sid}", status_code=204)
def delete_sender(sid: str, db: DB, me: SuperAdmin, request: Request):
    s = db.get(MailSender, sid)
    if not s:
        raise HTTPException(404, "Sender not found")
    if s.is_default and db.scalar(select(func.count(MailSender.id))) > 1:
        raise HTTPException(400, "Make another sender the default first")
    db.execute(update(Business).where(Business.mail_sender_id == s.id).values(mail_sender_id=None))
    log(db, me, "DELETE", "mail", f"E-mail sender removed: {s.label}", request=request)
    db.delete(s)
    db.commit()


class TestIn(BaseModel):
    to: EmailStr


@router.post("/senders/{sid}/test")
def test_sender(sid: str, data: TestIn, db: DB, me: SuperAdmin):
    s = db.get(MailSender, sid)
    if not s:
        raise HTTPException(404, "Sender not found")
    cfg = mailer.from_sender(s, "PLATFORM")
    s.last_test_at = dt.datetime.now(dt.UTC)
    try:
        mailer.send(cfg, [str(data.to)], f"Test e-mail from {s.label}", mailer.layout(
            "E-mail is working", f"<p>This test was sent through <b>{mailer.PROVIDERS[s.provider]}</b> from {s.from_email}.</p>"))
        s.last_error = None
    except HTTPException as e:
        s.last_error = str(e.detail)[:300]
        db.commit()
        raise
    db.commit()
    return {"sent": True, "to": str(data.to)}


class AssignIn(BaseModel):
    sender_id: str | None = None  # None = platform default


@router.put("/businesses/{business_id}")
def assign(business_id: str, data: AssignIn, db: DB, me: SuperAdmin, request: Request):
    biz = db.get(Business, business_id)
    if not biz:
        raise HTTPException(404, "Business not found")
    if data.sender_id and not db.get(MailSender, data.sender_id):
        raise HTTPException(404, "Sender not found")
    biz.mail_sender_id = data.sender_id
    s = db.get(MailSender, data.sender_id) if data.sender_id else None
    log(db, me, "CONFIG", "mail", f"E-mail for {biz.name}: {s.label + ' (' + s.from_email + ')' if s else 'platform default'}",
        business_id=biz.id, request=request)
    db.commit()
    return {"mail_sender_id": biz.mail_sender_id}
