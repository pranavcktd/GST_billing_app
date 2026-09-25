"""Outgoing e-mail with per-level SMTP.

Resolution order for business e-mails (invoices, backups):
    business SMTP → the account's reseller SMTP → platform SMTP → server .env (SMTP_*)
System e-mails (forgot password, new logins) use: platform SMTP → server .env.
"""

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from . import config_store
from ..models import SmtpConfig, Subscription
from ..security import decrypt_secret


@dataclass
class Smtp:
    host: str
    port: int
    security: str
    username: str | None
    password: str | None
    from_email: str
    from_name: str | None
    source: str  # BUSINESS / RESELLER / PLATFORM / ENV


def _from_row(row: SmtpConfig | None, source: str) -> Smtp | None:
    if not row:
        return None
    return Smtp(row.host, row.port, row.security, row.username,
                decrypt_secret(row.password_enc) if row.password_enc else None, row.from_email, row.from_name, source)


def _row(db: Session, scope: str, owner_id: str = "") -> SmtpConfig | None:
    return db.scalar(select(SmtpConfig).where(SmtpConfig.scope == scope, SmtpConfig.owner_id == owner_id))


def env_smtp() -> Smtp | None:
    s = get_settings()
    if not s.smtp_host:
        return None
    return Smtp(s.smtp_host, s.smtp_port, "STARTTLS", s.smtp_user, s.smtp_password,
                s.smtp_from or s.smtp_user or "", None, "ENV")


def system_smtp(db: Session) -> Smtp | None:
    return _from_row(_row(db, "PLATFORM"), "PLATFORM") or env_smtp()


def business_smtp(db: Session, business_id: str, account_id: str | None) -> Smtp | None:
    found = _from_row(_row(db, "BUSINESS", business_id), "BUSINESS")
    if found:
        return found
    if account_id:
        sub = db.get(Subscription, account_id)
        if sub and sub.reseller_id:
            found = _from_row(_row(db, "RESELLER", sub.reseller_id), "RESELLER")
            if found:
                return found
    return system_smtp(db)


def send(cfg: Smtp | None, to: list[str], subject: str, html: str, text: str | None = None,
         attachments: list[tuple[str, bytes, str]] | None = None, cc: list[str] | None = None,
         reply_to: str | None = None) -> None:
    if cfg is None:
        raise HTTPException(503, "E-mail is not set up — add SMTP details in Settings → Email")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg.from_name or "", cfg.from_email))
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text or "Please view this e-mail in an HTML-capable mail app.")
    msg.add_alternative(html, subtype="html")
    for name, data, mime in attachments or []:
        main, sub = mime.split("/", 1)
        msg.add_attachment(data, maintype=main, subtype=sub, filename=name)
    try:
        if cfg.security == "SSL":
            server = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=30, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(cfg.host, cfg.port, timeout=30)
            if cfg.security == "STARTTLS":
                server.starttls(context=ssl.create_default_context())
        with server:
            if cfg.username:
                server.login(cfg.username, cfg.password or "")
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise HTTPException(502, f"Could not send e-mail via {cfg.host}: {e}") from e


def layout(title: str, body_html: str, footer: str = "") -> str:
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:auto;color:#1c2430">
<div style="background:#1f65bb;color:#fff;padding:14px 20px;border-radius:8px 8px 0 0;font-size:18px;font-weight:bold">{title}</div>
<div style="border:1px solid #e5e7eb;border-top:0;padding:20px;border-radius:0 0 8px 8px;font-size:14px;line-height:1.6">{body_html}</div>
<div style="color:#9ca3af;font-size:12px;text-align:center;padding:10px">{footer or f"Sent by {config_store.app_name()} · {config_store.effective()['company'].get('name', '')}"}</div></div>"""
