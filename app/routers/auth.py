"""Sign-up, sign-in (lockout + optional 2FA), password reset and session security."""

import datetime as dt
import hashlib
import logging
import secrets

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from ..config import get_settings
from ..deps import DB, CurrentUser
from ..models import Membership, PasswordReset, User
from ..permissions import effective
from ..schemas import LoginIn, MeOut, MyBusinessOut, RegisterIn, TokenOut, UserOut
from ..security import (
    create_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    totp_new_secret,
    totp_ok,
    totp_uri,
    verify_password,
)
from ..services import config_store, mailer
from ..services.platform_audit import log

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("gst_billing.auth")

MAX_FAILED = 5
LOCK_MINUTES = 15
RESET_MINUTES = 30


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _aware(t: dt.datetime | None) -> dt.datetime | None:
    return t if t is None or t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def me_payload(db, user: User) -> MeOut:
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    return MeOut(
        user=UserOut.model_validate(user),
        platform_role=user.platform_role,
        last_login_at=user.last_login_at,
        previous_login_at=user.previous_login_at,
        totp_enabled=user.totp_enabled,
        must_change_password=user.must_change_password,
        businesses=[
            MyBusinessOut(id=m.business.id, name=m.business.name, gstin=m.business.gstin,
                          gst_type=m.business.gst_type, role=m.role, owned=m.business.owner_id == user.id,
                          permissions=effective(m.role, m.permissions))
            for m in memberships
        ],
    )


def token_for(user: User) -> str:
    return create_token(user.id, user.token_version or 0)


def frontend_url(request: Request) -> str:
    s = get_settings()
    if s.app_url:
        return s.app_url.rstrip("/")
    origin = request.headers.get("origin") or request.headers.get("referer") or "http://localhost:3000"
    return "/".join(origin.split("/")[:3])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: DB, request: Request):
    email = data.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(name=data.name, email=email, phone=data.phone, password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    log(db, user, "CREATE", "user", f"Signed up: {email}", entity_id=user.id, request=request)
    db.commit()
    return TokenOut(token=token_for(user), **me_payload(db, user).model_dump())


class LoginWithOtp(LoginIn):
    otp: str | None = None


@router.post("/login", response_model=TokenOut)
def login(data: LoginWithOtp, db: DB, request: Request):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if user and _aware(user.locked_until) and _aware(user.locked_until) > now():
        mins = int((_aware(user.locked_until) - now()).total_seconds() // 60) + 1
        raise HTTPException(status.HTTP_423_LOCKED, f"Too many wrong attempts — try again in {mins} minute(s) or reset your password")
    temp_row = None
    if user and not verify_password(data.password, user.password_hash):
        temp_row = _match_temp_password(db, user, data.password)
    if not user or (temp_row is None and not verify_password(data.password, user.password_hash)):
        if user:
            user.failed_logins = (user.failed_logins or 0) + 1
            locked = user.failed_logins >= MAX_FAILED
            if locked:
                user.locked_until, user.failed_logins = now() + dt.timedelta(minutes=LOCK_MINUTES), 0
            log(db, user, "LOCKED" if locked else "LOGIN_FAIL", "login",
                f"{'Account locked after repeated' if locked else 'Failed'} sign-in: {user.email}", entity_id=user.id, request=request)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        log(db, user, "LOGIN_FAIL", "login", f"Sign-in to disabled account: {user.email}", entity_id=user.id, request=request)
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled — contact your administrator")
    if user.totp_enabled:
        if not data.otp:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"message": "Enter the 6-digit code from your authenticator app",
                                                                "code": "OTP_REQUIRED"})
        if not totp_ok(decrypt_secret(user.totp_secret_enc), data.otp):
            user.failed_logins = (user.failed_logins or 0) + 1
            log(db, user, "LOGIN_FAIL", "login", f"Wrong 2FA code: {user.email}", entity_id=user.id, request=request)
            db.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"message": "The code is not correct", "code": "OTP_REQUIRED"})
    if temp_row is not None:
        # the temporary password becomes the password until the user sets a new one (forced next)
        user.password_hash, user.must_change_password = temp_row.temp_hash, True
        user.token_version = (user.token_version or 0) + 1
        temp_row.used_at = now()
        log(db, user, "LOGIN", "password", f"Signed in with an e-mailed temporary password: {user.email}", entity_id=user.id, request=request)
    user.failed_logins, user.locked_until = 0, None
    user.previous_login_at, user.last_login_at = user.last_login_at, now()
    log(db, user, "LOGIN", "login", f"Signed in: {user.email}", entity_id=user.id, request=request)
    db.commit()
    return TokenOut(token=token_for(user), **me_payload(db, user).model_dump())


@router.get("/me", response_model=MeOut)
def me(db: DB, user: CurrentUser):
    return me_payload(db, user)


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


@router.put("/password")
def change_password(data: PasswordIn, db: DB, user: CurrentUser, request: Request):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is not correct")
    user.password_hash = hash_password(data.new_password)
    user.token_version = (user.token_version or 0) + 1  # other devices are signed out
    user.must_change_password = False
    log(db, user, "UPDATE", "user", "Changed own password (other sessions signed out)", entity_id=user.id, request=request)
    db.commit()
    return {"ok": True, "token": token_for(user)}


@router.post("/logout-all")
def logout_all(db: DB, user: CurrentUser, request: Request):
    user.token_version = (user.token_version or 0) + 1
    log(db, user, "ACTION", "login", "Signed out of all devices", entity_id=user.id, request=request)
    db.commit()
    return {"ok": True, "token": token_for(user)}


# ---------------------------------------------------------------- forgot / reset password
class ForgotIn(BaseModel):
    email: EmailStr


def issue_reset(db, user: User, request: Request, actor: User | None = None) -> str:
    """Create a one-time reset link (valid 30 minutes) and e-mail it via the platform SMTP."""
    recent = db.scalar(select(func.count(PasswordReset.id)).where(
        PasswordReset.user_id == user.id, PasswordReset.created_at >= now() - dt.timedelta(hours=1))) or 0
    if recent >= 5:
        raise HTTPException(429, "Too many reset requests — please wait an hour")
    token = secrets.token_urlsafe(32)
    db.add(PasswordReset(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                         expires_at=now() + dt.timedelta(minutes=RESET_MINUTES),
                         requested_ip=request.client.host if request.client else None))
    link = f"{frontend_url(request)}/reset-password?token={token}"
    body = mailer.layout("Reset your password", f"""
        <p>Hello {user.name},</p>
        <p>{'Your administrator requested' if actor else 'We received'} a request to reset the password of your {config_store.app_name()} account.</p>
        <p style="text-align:center;margin:24px 0"><a href="{link}" style="background:#1f65bb;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none">Set a new password</a></p>
        <p>This link works once and expires in {RESET_MINUTES} minutes. If you did not ask for it, ignore this e-mail — your password stays the same.</p>""")
    cfg = mailer.system_smtp(db)
    if cfg:
        mailer.send(cfg, [user.email], f"Reset your {config_store.app_name()} password", body)
    else:
        logger.warning("SMTP not configured — password reset link for %s: %s", user.email, link)
    return link


TEMP_MINUTES = 60


def _match_temp_password(db, user: User, password: str) -> PasswordReset | None:
    rows = db.scalars(select(PasswordReset).where(
        PasswordReset.user_id == user.id, PasswordReset.temp_hash.is_not(None), PasswordReset.used_at.is_(None),
        PasswordReset.expires_at > now()).order_by(PasswordReset.created_at.desc()).limit(3)).all()
    return next((r for r in rows if verify_password(password, r.temp_hash)), None)


def _temp_password() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"  # no look-alikes (0/O, 1/l/I)
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


@router.post("/forgot")
def forgot(data: ForgotIn, db: DB, request: Request):
    """E-mails a temporary password from the platform (super admin) mailbox; the user must set a new
    password after signing in with it. The current password keeps working until the temporary one is
    used, so nobody can lock a user out just by knowing their e-mail. Always answers the same way,
    so it never reveals whether an e-mail is registered."""
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    out: dict = {"ok": True, "message": "If this e-mail is registered, a temporary password has been sent to it. "
                                        "Sign in with it — you will then be asked to choose a new password."}
    if not (user and user.is_active):
        return out
    recent = db.scalar(select(func.count(PasswordReset.id)).where(
        PasswordReset.user_id == user.id, PasswordReset.created_at >= now() - dt.timedelta(hours=1))) or 0
    if recent >= 3:
        return out  # quietly rate-limited (same answer)
    temp = _temp_password()
    db.add(PasswordReset(user_id=user.id, token_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
                         temp_hash=hash_password(temp), expires_at=now() + dt.timedelta(minutes=TEMP_MINUTES),
                         requested_ip=request.client.host if request.client else None))
    log(db, user, "ACTION", "password", f"Temporary password e-mailed (forgot password): {user.email}", entity_id=user.id, request=request)
    db.commit()
    app = config_store.app_name()
    body = mailer.layout("Your temporary password", f"""
        <p>Hello {user.name},</p>
        <p>We received a request to reset the password of your {app} account. Use this temporary password to sign in:</p>
        <p style="text-align:center;margin:24px 0"><span style="font-family:monospace;font-size:22px;letter-spacing:2px;background:#f3f4f6;padding:10px 16px;border-radius:6px">{temp}</span></p>
        <p>It works once and expires in {TEMP_MINUTES} minutes. After signing in you will be asked to set a new password.</p>
        <p>If you did not ask for this, ignore this e-mail — your current password keeps working.</p>
        <p><a href="{frontend_url(request)}/login">Sign in to {app}</a></p>""")
    cfg = mailer.system_smtp(db)
    if cfg:
        try:
            mailer.send(cfg, [user.email], f"Your {app} temporary password", body)
        except Exception:  # noqa: BLE001
            logger.exception("Could not e-mail the temporary password to %s", user.email)
    elif get_settings().is_dev:
        out["dev_temp_password"] = temp  # local development without SMTP
    else:
        logger.warning("SMTP not configured — temporary password for %s could not be sent", user.email)
    return out


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/reset")
def reset(data: ResetIn, db: DB, request: Request):
    row = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == hashlib.sha256(data.token.encode()).hexdigest()))
    if not row or row.used_at or _aware(row.expires_at) < now():
        raise HTTPException(400, "This reset link is invalid or has expired — request a new one")
    user = db.get(User, row.user_id)
    user.password_hash = hash_password(data.new_password)
    user.token_version = (user.token_version or 0) + 1
    user.failed_logins, user.locked_until, user.must_change_password = 0, None, False
    row.used_at = now()
    log(db, user, "UPDATE", "password", f"Password reset via e-mail link: {user.email}", entity_id=user.id, request=request)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- two-factor authentication
@router.post("/2fa/setup")
def twofa_setup(db: DB, user: CurrentUser):
    if user.totp_enabled:
        raise HTTPException(400, "Two-factor sign-in is already on — turn it off first to set up a new phone")
    secret = totp_new_secret()
    user.totp_secret_enc = encrypt_secret(secret)
    db.commit()
    return {"secret": secret, "otpauth_url": totp_uri(secret, user.email)}


class OtpIn(BaseModel):
    code: str
    password: str | None = None


@router.post("/2fa/enable")
def twofa_enable(data: OtpIn, db: DB, user: CurrentUser, request: Request):
    if not user.totp_secret_enc or not totp_ok(decrypt_secret(user.totp_secret_enc), data.code):
        raise HTTPException(400, "The code is not correct — check the time on your phone and try again")
    user.totp_enabled = True
    log(db, user, "UPDATE", "security", "Two-factor sign-in turned on", entity_id=user.id, request=request)
    db.commit()
    return {"totp_enabled": True}


@router.post("/2fa/disable")
def twofa_disable(data: OtpIn, db: DB, user: CurrentUser, request: Request):
    if not data.password or not verify_password(data.password, user.password_hash):
        raise HTTPException(400, "Password is not correct")
    if user.totp_enabled and not totp_ok(decrypt_secret(user.totp_secret_enc), data.code):
        raise HTTPException(400, "The code is not correct")
    user.totp_enabled, user.totp_secret_enc = False, None
    log(db, user, "UPDATE", "security", "Two-factor sign-in turned off", entity_id=user.id, request=request)
    db.commit()
    return {"totp_enabled": False}
