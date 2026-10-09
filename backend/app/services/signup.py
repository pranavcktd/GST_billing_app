"""Sign-up options set by the super admin (Admin → Integrations → Sign-up):

    verify: OFF | WHATSAPP | EMAIL | EITHER   — prove the mobile (WhatsApp code) or e-mail (e-mail code) before the
            account and its free trial are created. A channel that is not set up is skipped, so sign-ups never break.
    google_enabled + google_client_id         — "Continue with Google" (Google Identity Services ID token, checked
            on the server). A new Google user goes straight to business details; an existing e-mail just signs in.

E-mail codes: 6 digits, 10 minutes, 3 tries, one per minute, 5 an hour per address and 20 an hour per IP; only a keyed
hash is kept. On a development server without an e-mail server the code is returned for the screen (sandbox).
"""

import datetime as dt
import hashlib
import hmac
import secrets

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import EmailOtp, PlatformSetting
from . import mailer
from . import whatsapp as W

KEY = "signup"
MODES = ("OFF", "WHATSAPP", "EMAIL", "EITHER")
CODE_MINUTES, ATTEMPTS, RESEND_SECONDS, PER_EMAIL_HOUR, PER_IP_HOUR = 10, 3, 60, 5, 20


def settings(db: Session) -> dict:
    row = db.get(PlatformSetting, KEY)
    if row and row.value:
        return {"verify": "OFF", "google_enabled": False, "google_client_id": "", **row.value}
    # before this setting existed: WhatsApp's "verify mobile at sign-up" switch
    return {"verify": "WHATSAPP" if W.settings(db).get("signup_verify") else "OFF", "google_enabled": False, "google_client_id": ""}


def save_settings(db: Session, values: dict) -> dict:
    s = settings(db)
    for k in ("verify", "google_enabled", "google_client_id"):
        if values.get(k) is not None:
            s[k] = values[k].strip() if isinstance(values[k], str) else values[k]
    row = db.get(PlatformSetting, KEY) or PlatformSetting(key=KEY)
    row.value = s
    db.add(row)
    db.commit()
    return s


def email_ready(db: Session) -> bool:
    return bool(mailer.system_smtp(db)) or get_settings().is_dev


def methods(db: Session) -> list[str]:
    """Channels a new user must choose from to verify (empty = no verification)."""
    mode = settings(db)["verify"]
    want = {"OFF": [], "WHATSAPP": ["WHATSAPP"], "EMAIL": ["EMAIL"], "EITHER": ["WHATSAPP", "EMAIL"]}.get(mode, [])
    have = {"WHATSAPP": W.flags(db)["send"], "EMAIL": email_ready(db)}
    out = [m for m in want if have[m]]
    if want and not out:  # the chosen channel is not set up: use whatever is
        out = [m for m in ("WHATSAPP", "EMAIL") if have[m]]
    return out


def flags(db: Session) -> dict:
    s = settings(db)
    return {"verify": methods(db), "google_client_id": s["google_client_id"] if s["google_enabled"] and s["google_client_id"] else None}


# ================================================================ e-mail codes
def _hash(email: str, code: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), f"mail:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _aware(t: dt.datetime) -> dt.datetime:
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def issue_email_code(db: Session, email: str, ip: str | None) -> dict:
    email = email.strip().lower()
    now = dt.datetime.now(dt.UTC)
    hour = now - dt.timedelta(hours=1)
    last = db.scalar(select(EmailOtp).where(EmailOtp.email == email).order_by(EmailOtp.created_at.desc()).limit(1))
    if last and (now - _aware(last.created_at)).total_seconds() < RESEND_SECONDS:
        raise HTTPException(429, f"Please wait {RESEND_SECONDS - int((now - _aware(last.created_at)).total_seconds())} seconds before asking for another code.")
    if (db.scalar(select(func.count(EmailOtp.id)).where(EmailOtp.email == email, EmailOtp.created_at >= hour)) or 0) >= PER_EMAIL_HOUR:
        raise HTTPException(429, "Too many codes for this e-mail — try again in an hour.")
    if ip and (db.scalar(select(func.count(EmailOtp.id)).where(EmailOtp.ip == ip, EmailOtp.created_at >= hour)) or 0) >= PER_IP_HOUR:
        raise HTTPException(429, "Too many codes requested — try again later.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(EmailOtp(email=email, code_hash=_hash(email, code), ip=ip, expires_at=now + dt.timedelta(minutes=CODE_MINUTES)))
    cfg = mailer.system_smtp(db)
    out = {"sent": True, "to": email, "expires_in": CODE_MINUTES * 60, "resend_in": RESEND_SECONDS}
    if cfg:
        from .config_store import app_name

        mailer.send(cfg, [email], f"{code} is your {app_name()} code", mailer.layout(
            "Confirm your e-mail", f"<p>Your verification code is</p><p style='font-size:28px;font-weight:700;letter-spacing:6px'>{code}</p>"
                                   f"<p>It works for {CODE_MINUTES} minutes. If you did not ask for it, ignore this e-mail.</p>"))
    elif get_settings().is_dev:
        out["sandbox_code"] = code  # development server without an e-mail server
    else:
        raise HTTPException(503, "E-mail is not set up on this platform yet.")
    db.commit()
    return out


def check_email_code(db: Session, email: str, code: str) -> None:
    email = email.strip().lower()
    now = dt.datetime.now(dt.UTC)
    row = db.scalar(select(EmailOtp).where(EmailOtp.email == email, EmailOtp.used_at.is_(None))
                    .order_by(EmailOtp.created_at.desc()).limit(1))
    if not row or _aware(row.expires_at) < now or row.attempts >= ATTEMPTS:
        raise HTTPException(400, "The e-mail code has expired — ask for a new one.")
    if not hmac.compare_digest(row.code_hash, _hash(email, (code or "").strip())):
        row.attempts += 1
        db.commit()
        left = ATTEMPTS - row.attempts
        raise HTTPException(400, f"The e-mail code is not correct — {left} tr{'y' if left == 1 else 'ies'} left." if left
                            else "The e-mail code is not correct — ask for a new one.")
    row.used_at = now


# ================================================================ Google
def _verify_google(credential: str, client_id: str) -> dict:
    """Single seam for tests: Google's library checks the signature, audience, issuer and expiry."""
    from google.auth.transport import requests as grequests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(credential, grequests.Request(), client_id)


def google_identity(db: Session, credential: str) -> dict:
    s = settings(db)
    if not (s["google_enabled"] and s["google_client_id"]):
        raise HTTPException(503, "Google sign-in is not switched on.")
    try:
        info = _verify_google(credential, s["google_client_id"])
    except ValueError as e:
        raise HTTPException(401, "Google sign-in could not be verified — please try again.") from e
    if not info.get("email") or not info.get("email_verified"):
        raise HTTPException(401, "Your Google account has no verified e-mail address.")
    return {"email": info["email"].lower(), "name": info.get("name") or info["email"].split("@")[0], "sub": info.get("sub")}
