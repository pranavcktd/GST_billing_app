"""Outgoing e-mail through e-mail API providers (Brevo, ZeptoMail, Resend, SendGrid, Postmark) or SMTP.

Senders are managed by the super admin (Admin → Email): one is the platform default; any business can be given its
own sender (for example billing@its-own-domain) — businesses do not configure e-mail themselves.

Which sender a business e-mail (invoice, reminder, backup) uses:
    the sender assigned to the business → the account's reseller SMTP → the platform default sender
    → the old platform SMTP setting → server .env (SMTP_*)
A business using a platform sender sends as "<Business name>" from the platform address, with replies going to the
business's own e-mail. System e-mails (sign-in codes, password resets) use the platform default.
"""

import base64
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from . import config_store
from ..models import Business, MailSender, SmtpConfig, Subscription
from ..security import decrypt_secret

PROVIDERS = {
    "BREVO": "Brevo (Sendinblue)", "ZEPTOMAIL": "ZeptoMail (Zoho)", "RESEND": "Resend", "SENDGRID": "SendGrid",
    "POSTMARK": "Postmark", "SMTP": "SMTP server (legacy)",
}
ZEPTO_HOSTS = {"IN": "https://api.zeptomail.in", "COM": "https://api.zeptomail.com", "EU": "https://api.zeptomail.eu"}


@dataclass
class Smtp:  # name kept for callers; now any sender (API or SMTP)
    host: str
    port: int
    security: str
    username: str | None
    password: str | None  # SMTP password, or the provider's API key
    from_email: str
    from_name: str | None
    source: str  # BUSINESS / RESELLER / PLATFORM / ENV
    kind: str = "SMTP"  # SMTP / BREVO / ZEPTOMAIL / RESEND / SENDGRID / POSTMARK
    region: str | None = None
    reply_to: str | None = None
    label: str | None = None


def _from_row(row: SmtpConfig | None, source: str) -> Smtp | None:
    if not row:
        return None
    return Smtp(row.host, row.port, row.security, row.username,
                decrypt_secret(row.password_enc) if row.password_enc else None, row.from_email, row.from_name, source)


def from_sender(s: MailSender | None, source: str) -> Smtp | None:
    if not s or not s.active:
        return None
    return Smtp(s.host or "", s.port or 587, s.security or "STARTTLS", s.username,
                decrypt_secret(s.secret_enc) if s.secret_enc else None, s.from_email, s.from_name, source,
                kind=s.provider, region=s.region, reply_to=s.reply_to, label=s.label)


def _row(db: Session, scope: str, owner_id: str = "") -> SmtpConfig | None:
    return db.scalar(select(SmtpConfig).where(SmtpConfig.scope == scope, SmtpConfig.owner_id == owner_id))


def env_smtp() -> Smtp | None:
    s = get_settings()
    if not s.smtp_host:
        return None
    return Smtp(s.smtp_host, s.smtp_port, "STARTTLS", s.smtp_user, s.smtp_password,
                s.smtp_from or s.smtp_user or "", None, "ENV")


def default_sender(db: Session) -> MailSender | None:
    return db.scalar(select(MailSender).where(MailSender.is_default.is_(True), MailSender.active.is_(True)).limit(1))


def system_smtp(db: Session) -> Smtp | None:
    """Platform mail: the default sender, else the older platform SMTP setting, else server .env."""
    return from_sender(default_sender(db), "PLATFORM") or _from_row(_row(db, "PLATFORM"), "PLATFORM") or env_smtp()


def business_smtp(db: Session, business_id: str, account_id: str | None) -> Smtp | None:
    biz = db.get(Business, business_id)
    if biz is not None and biz.mail_sender_id:
        found = from_sender(db.get(MailSender, biz.mail_sender_id), "BUSINESS")
        if found:
            return found
    if account_id:
        sub = db.get(Subscription, account_id)
        if sub and sub.reseller_id:
            found = _from_row(_row(db, "RESELLER", sub.reseller_id), "RESELLER")
            if found:
                return found
    cfg = system_smtp(db)
    if cfg and biz is not None:  # the platform address, under the business's name; replies go to the business
        cfg.from_name = biz.name[:120]
        cfg.reply_to = biz.email or cfg.reply_to
    return cfg


# ================================================================ sending
def _http_post(url: str, headers: dict, body: dict) -> httpx.Response:
    """Single seam for tests."""
    return httpx.post(url, headers=headers, json=body, timeout=30)


def _api_send(cfg: Smtp, to: list[str], subject: str, html: str, text: str | None, attachments, cc, reply_to) -> None:
    key = cfg.password or ""
    files = [(n, base64.b64encode(d).decode(), m) for n, d, m in attachments or []]
    reply = reply_to or cfg.reply_to
    k = cfg.kind
    if k == "BREVO":
        url, headers = "https://api.brevo.com/v3/smtp/email", {"api-key": key}
        body = {"sender": {"email": cfg.from_email, "name": cfg.from_name or cfg.from_email}, "to": [{"email": t} for t in to],
                "subject": subject, "htmlContent": html, **({"textContent": text} if text else {}),
                **({"cc": [{"email": c} for c in cc]} if cc else {}), **({"replyTo": {"email": reply}} if reply else {}),
                **({"attachment": [{"name": n, "content": c} for n, c, _ in files]} if files else {})}
    elif k == "ZEPTOMAIL":
        url = f"{ZEPTO_HOSTS.get(cfg.region or 'IN', ZEPTO_HOSTS['IN'])}/v1.1/email"
        headers = {"Authorization": key if key.lower().startswith("zoho-enczapikey") else f"Zoho-enczapikey {key}"}
        body = {"from": {"address": cfg.from_email, "name": cfg.from_name or cfg.from_email},
                "to": [{"email_address": {"address": t}} for t in to], "subject": subject, "htmlbody": html,
                **({"textbody": text} if text else {}), **({"cc": [{"email_address": {"address": c}} for c in cc]} if cc else {}),
                **({"reply_to": [{"address": reply}]} if reply else {}),
                **({"attachments": [{"name": n, "content": c, "mime_type": m} for n, c, m in files]} if files else {})}
    elif k == "RESEND":
        url, headers = "https://api.resend.com/emails", {"Authorization": f"Bearer {key}"}
        body = {"from": formataddr((cfg.from_name or "", cfg.from_email)), "to": to, "subject": subject, "html": html,
                **({"text": text} if text else {}), **({"cc": cc} if cc else {}), **({"reply_to": reply} if reply else {}),
                **({"attachments": [{"filename": n, "content": c} for n, c, _ in files]} if files else {})}
    elif k == "SENDGRID":
        url, headers = "https://api.sendgrid.com/v3/mail/send", {"Authorization": f"Bearer {key}"}
        body = {"personalizations": [{"to": [{"email": t} for t in to], **({"cc": [{"email": c} for c in cc]} if cc else {})}],
                "from": {"email": cfg.from_email, "name": cfg.from_name or cfg.from_email}, "subject": subject,
                "content": ([{"type": "text/plain", "value": text}] if text else []) + [{"type": "text/html", "value": html}],
                **({"reply_to": {"email": reply}} if reply else {}),
                **({"attachments": [{"content": c, "filename": n, "type": m, "disposition": "attachment"} for n, c, m in files]} if files else {})}
    elif k == "POSTMARK":
        url, headers = "https://api.postmarkapp.com/email", {"X-Postmark-Server-Token": key}
        body = {"From": formataddr((cfg.from_name or "", cfg.from_email)), "To": ", ".join(to), "Subject": subject, "HtmlBody": html,
                **({"TextBody": text} if text else {}), **({"Cc": ", ".join(cc)} if cc else {}), **({"ReplyTo": reply} if reply else {}),
                "MessageStream": "outbound",
                **({"Attachments": [{"Name": n, "Content": c, "ContentType": m} for n, c, m in files]} if files else {})}
    else:
        raise HTTPException(500, f"Unknown e-mail provider {k}")
    try:
        r = _http_post(url, {**headers, "Content-Type": "application/json", "Accept": "application/json"}, body)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"{PROVIDERS.get(k, k)} did not answer — please try again") from e
    if r.status_code >= 300:
        raise HTTPException(502, f"{PROVIDERS.get(k, k)} refused the e-mail: {_error_text(r)}")


def _error_text(r: httpx.Response) -> str:
    try:
        j = r.json()
    except ValueError:
        return r.text[:200] or f"HTTP {r.status_code}"
    if isinstance(j, dict):
        for key in ("message", "Message"):
            if j.get(key):
                return str(j[key])[:300]
        err = j.get("error")
        if isinstance(err, dict):
            details = err.get("details") or []
            return str(err.get("message") or (details[0].get("message") if details and isinstance(details[0], dict) else err))[:300]
        if isinstance(err, str):
            return err[:300]
        errs = j.get("errors")
        if isinstance(errs, list) and errs:
            return str(errs[0].get("message") if isinstance(errs[0], dict) else errs[0])[:300]
    return str(j)[:300]


def send(cfg: Smtp | None, to: list[str], subject: str, html: str, text: str | None = None,
         attachments: list[tuple[str, bytes, str]] | None = None, cc: list[str] | None = None,
         reply_to: str | None = None) -> None:
    if cfg is None:
        raise HTTPException(503, "E-mail is not set up yet — the platform administrator adds it in Admin → Email")
    if cfg.kind != "SMTP":
        return _api_send(cfg, to, subject, html, text, attachments, cc, reply_to)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg.from_name or "", cfg.from_email))
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if reply_to or cfg.reply_to:
        msg["Reply-To"] = reply_to or cfg.reply_to
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
<div style="background:#4f46e5;color:#fff;padding:14px 20px;border-radius:8px 8px 0 0;font-size:18px;font-weight:bold">{title}</div>
<div style="border:1px solid #e5e7eb;border-top:0;padding:20px;border-radius:0 0 8px 8px;font-size:14px;line-height:1.6">{body_html}</div>
<div style="color:#9ca3af;font-size:12px;text-align:center;padding:10px">{footer or f"Sent by {config_store.app_name()} · {config_store.effective()['company'].get('name', '')}"}</div></div>"""
