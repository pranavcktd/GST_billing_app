"""WhatsApp Business API: sign-in codes (OTP), invoices and payment reminders sent from the platform's number.

Any vendor that speaks the Meta Cloud API message format can be plugged in by the super admin
(Admin → Integrations → WhatsApp): Spring Edge, Meta itself, or another provider.
    POST {base_url}/{api_version}/{phone_number_id}/messages      header  {auth_header}: {api_key}
Messages outside a customer conversation must use templates approved by Meta, so every message here is a template:
    otp_template       body {{1}} = code   (+ copy-code button when `otp_button` is on — Meta "Authentication" templates)
    invoice_template   document header (the PDF) + body {{1}} customer, {{2}} document no., {{3}} amount, {{4}} business
    reminder_template  body {{1}} customer, {{2}} amount due, {{3}} business, {{4}} link to the bill
Delivery statuses arrive at /api/whatsapp/webhook?key=<webhook_key> and are matched by message id (wamid).

Settings: platform_settings["whatsapp_api"].
"""

import datetime as dt
import hashlib
import hmac
import secrets

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import PhoneOtp, PlatformSetting, WhatsAppMessage
from ..security import decrypt_secret, encrypt_secret

KEY = "whatsapp_api"
PRESETS = {
    "SPRINGEDGE": dict(label="Spring Edge", base_url="", api_version="v3", auth_header="apikey"),
    "META": dict(label="Meta WhatsApp Cloud API", base_url="https://graph.facebook.com", api_version="v21.0", auth_header="Bearer"),
    "OTHER": dict(label="Other (Meta-compatible API)", base_url="", api_version="v1", auth_header="apikey"),
}
DEFAULTS = dict(
    enabled=False, provider="SPRINGEDGE", base_url="", api_version="v3", auth_header="apikey", phone_number_id="",
    api_key_enc=None, webhook_key=None,
    login_enabled=True, signup_verify=False,
    otp_template="login_otp", otp_lang="en", otp_button=True,
    invoice_template="invoice_document", invoice_lang="en",
    reminder_template="payment_reminder", reminder_lang="en",
)
EDITABLE = ("enabled", "provider", "base_url", "api_version", "auth_header", "phone_number_id", "login_enabled", "signup_verify",
            "otp_template", "otp_lang", "otp_button", "invoice_template", "invoice_lang", "reminder_template", "reminder_lang")

OTP_MINUTES = 5
OTP_ATTEMPTS = 3
OTP_RESEND_SECONDS = 60
OTP_PER_PHONE_HOUR = 5
OTP_PER_IP_HOUR = 20


# ================================================================ settings
def settings(db: Session) -> dict:
    row = db.get(PlatformSetting, KEY)
    return {**DEFAULTS, **((row.value or {}) if row else {})}


def _key(s: dict) -> str | None:
    try:
        return decrypt_secret(s["api_key_enc"]) if s.get("api_key_enc") else None
    except Exception:  # noqa: BLE001 — key encrypted with an old secret
        return None


def ready(s: dict) -> bool:
    return bool(s.get("enabled") and s.get("base_url") and s.get("phone_number_id") and _key(s))


def public_settings(db: Session) -> dict:
    s = settings(db)
    key = _key(s)
    return {k: v for k, v in s.items() if k != "api_key_enc"} | {
        "api_key_set": bool(key), "api_key_hint": f"{key[:4]}…{key[-4:]}" if key and len(key) > 10 else None,
        "ready": ready(s), "presets": PRESETS}


def save_settings(db: Session, values: dict) -> dict:
    s = settings(db)
    for k in EDITABLE:
        if k in values and values[k] is not None:
            s[k] = values[k].strip() if isinstance(values[k], str) else values[k]
    if values.get("api_key"):
        s["api_key_enc"] = encrypt_secret(values["api_key"].strip())
    if values.get("clear_api_key"):
        s["api_key_enc"] = None
    if not s.get("webhook_key") or values.get("new_webhook_key"):
        s["webhook_key"] = secrets.token_urlsafe(24)
    s["base_url"] = str(s["base_url"]).rstrip("/")
    s["api_version"] = str(s["api_version"]).strip("/")
    row = db.get(PlatformSetting, KEY) or PlatformSetting(key=KEY)
    row.value = s
    db.add(row)
    db.commit()
    return public_settings(db)


def flags(db: Session) -> dict:
    """What the sign-in / sign-up pages may offer (public)."""
    s = settings(db)
    on = ready(s)
    return {"login": on and bool(s["login_enabled"]), "signup_verify": on and bool(s["signup_verify"]), "send": on}


# ================================================================ phone numbers
def normalize(phone: str | None) -> str | None:
    """Indian mobile as 91XXXXXXXXXX (what the API wants), else None."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return "91" + digits
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return digits
    return None


def masked(phone: str) -> str:
    return f"+91 {phone[2:4]}••••••{phone[-2:]}" if len(phone) == 12 else phone


# ================================================================ sending
class ProviderError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _http_post(url: str, headers: dict, body: dict) -> httpx.Response:
    """Single seam for tests."""
    return httpx.post(url, headers=headers, json=body, timeout=20)


def _send(db: Session, s: dict, to: str, template: str, lang: str, components: list[dict], *, kind: str,
          business_id: str | None = None, account_id: str | None = None, ref: str | None = None, by: str | None = None) -> WhatsAppMessage:
    if not ready(s):
        raise HTTPException(503, "WhatsApp messaging is not set up by the platform administrator.")
    key = _key(s)
    auth = {"Authorization": f"Bearer {key}"} if s["auth_header"] == "Bearer" else {s["auth_header"]: key}
    url = f"{s['base_url']}/{s['api_version']}/{s['phone_number_id']}/messages"
    body = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "template",
            "template": {"name": template, "language": {"code": lang}, "components": components}}
    msg = WhatsAppMessage(business_id=business_id, account_id=account_id, kind=kind, to=to, template=template, ref=ref, by=by)
    try:
        r = _http_post(url, {**auth, "Content-Type": "application/json", "Accept": "application/json"}, body)
        data = r.json() if r.content else {}
    except (httpx.HTTPError, ValueError) as e:
        msg.status, msg.error = "FAILED", f"WhatsApp service did not answer ({type(e).__name__})"
        db.add(msg)
        db.commit()
        raise ProviderError(502, "The WhatsApp service did not answer — please try again in a minute.") from e
    if r.status_code >= 400 or not (data.get("messages") or []):
        err = (data.get("error") or {}) if isinstance(data.get("error"), dict) else {"message": data.get("error") or data.get("message")}
        text = err.get("error_user_msg") or err.get("message") or f"HTTP {r.status_code}"
        msg.status, msg.error = "FAILED", str(text)[:300]
        db.add(msg)
        db.commit()
        raise ProviderError(r.status_code if r.status_code >= 400 else 502, f"WhatsApp did not accept the message: {text}")
    msg.wamid, msg.status = data["messages"][0].get("id"), "SENT"
    db.add(msg)
    return msg


def send_otp(db: Session, to: str, code: str) -> WhatsAppMessage:
    s = settings(db)
    comps: list[dict] = [{"type": "body", "parameters": [{"type": "text", "text": code}]}]
    if s["otp_button"]:
        comps.append({"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": code}]})
    return _send(db, s, to, s["otp_template"], s["otp_lang"], comps, kind="OTP")


def send_document(db: Session, to: str, pdf_url: str, filename: str, params: list[str], **meta) -> WhatsAppMessage:
    s = settings(db)
    comps = [{"type": "header", "parameters": [{"type": "document", "document": {"link": pdf_url, "filename": filename}}]},
             {"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]
    return _send(db, s, to, s["invoice_template"], s["invoice_lang"], comps, kind="INVOICE", **meta)


def send_reminder(db: Session, to: str, params: list[str], **meta) -> WhatsAppMessage:
    s = settings(db)
    comps = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]
    return _send(db, s, to, s["reminder_template"], s["reminder_lang"], comps, kind="REMINDER", **meta)


def update_status(db: Session, payload: dict) -> int:
    """Delivery statuses from the provider's webhook (Meta format: entry[].changes[].value.statuses[], or statuses[])."""
    statuses = list(payload.get("statuses") or [])
    for entry in payload.get("entry") or []:
        for ch in entry.get("changes") or []:
            statuses += (ch.get("value") or {}).get("statuses") or []
    n = 0
    for st in statuses:
        m = db.scalar(select(WhatsAppMessage).where(WhatsAppMessage.wamid == st.get("id"))) if st.get("id") else None
        if not m:
            continue
        m.status = str(st.get("status") or "").upper()[:10] or m.status
        if st.get("errors"):
            m.error = str((st["errors"][0] or {}).get("title") or st["errors"][0])[:300]
        m.updated_at = dt.datetime.now(dt.UTC)
        n += 1
    db.commit()
    return n


# ================================================================ one-time codes
def _hash(phone: str, code: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_otp(db: Session, phone: str, purpose: str, ip: str | None) -> dict:
    now = dt.datetime.now(dt.UTC)
    hour = now - dt.timedelta(hours=1)
    last = db.scalar(select(PhoneOtp).where(PhoneOtp.phone == phone).order_by(PhoneOtp.created_at.desc()).limit(1))
    if last and (now - _aware(last.created_at)).total_seconds() < OTP_RESEND_SECONDS:
        wait = OTP_RESEND_SECONDS - int((now - _aware(last.created_at)).total_seconds())
        raise HTTPException(429, f"Please wait {wait} seconds before asking for another code.")
    if (db.scalar(select(func.count(PhoneOtp.id)).where(PhoneOtp.phone == phone, PhoneOtp.created_at >= hour)) or 0) >= OTP_PER_PHONE_HOUR:
        raise HTTPException(429, "Too many codes for this number — try again in an hour.")
    if ip and (db.scalar(select(func.count(PhoneOtp.id)).where(PhoneOtp.ip == ip, PhoneOtp.created_at >= hour)) or 0) >= OTP_PER_IP_HOUR:
        raise HTTPException(429, "Too many codes requested — try again later.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    row = PhoneOtp(phone=phone, purpose=purpose, code_hash=_hash(phone, code), ip=ip,
                   expires_at=now + dt.timedelta(minutes=OTP_MINUTES))
    db.add(row)
    db.flush()
    try:
        send_otp(db, phone, code)
    except ProviderError as e:
        db.delete(row)
        db.commit()
        raise HTTPException(502, e.message) from e
    db.commit()
    return {"sent": True, "to": masked(phone), "expires_in": OTP_MINUTES * 60, "resend_in": OTP_RESEND_SECONDS}


def check_otp(db: Session, phone: str, purpose: str, code: str) -> None:
    """Raises unless `code` is the latest unused, unexpired code for this number and purpose (3 tries)."""
    now = dt.datetime.now(dt.UTC)
    row = db.scalar(select(PhoneOtp).where(PhoneOtp.phone == phone, PhoneOtp.purpose == purpose, PhoneOtp.used_at.is_(None))
                    .order_by(PhoneOtp.created_at.desc()).limit(1))
    if not row or _aware(row.expires_at) < now or row.attempts >= OTP_ATTEMPTS:
        raise HTTPException(400, "The code has expired — ask for a new one.")
    if not hmac.compare_digest(row.code_hash, _hash(phone, (code or "").strip())):
        row.attempts += 1
        db.commit()
        left = OTP_ATTEMPTS - row.attempts
        raise HTTPException(400, f"The code is not correct — {left} tr{'y' if left == 1 else 'ies'} left." if left else
                            "The code is not correct — ask for a new one.")
    row.used_at = now


def _aware(t: dt.datetime) -> dt.datetime:
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)
