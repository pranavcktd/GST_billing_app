"""Sign-up, sign-in (lockout + optional 2FA), password reset and session security."""

import datetime as dt
from typing import Literal
import hashlib
import logging
import secrets

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from ..config import get_settings
from ..deps import DB, CurrentUser
from ..models import Membership, PasswordReset, Subscription, User
from ..permissions import effective
from ..schemas import LoginIn, InvitationOut, MeOut, MyBusinessOut, RegisterIn, TokenOut, UserOut
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
from ..services import config_store, mailer, platform_team
from ..services import privacy as PV
from ..services import signup as SU
from ..services import whatsapp as W
from ..services.platform_audit import client_ip, log

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("gst_billing.auth")

MAX_FAILED = 5
LOCK_MINUTES = 15
RESET_MINUTES = 30


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _aware(t: dt.datetime | None) -> dt.datetime | None:
    return t if t is None or t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _practice_limit(db, user: User) -> int:
    if user.platform_role == "SUPERADMIN":
        return 100000
    sub = db.get(Subscription, user.id)
    try:
        return int(((sub.feature_flags or {}) if sub else {}).get("practice_clients") or 0)
    except (TypeError, ValueError):
        return 0


def me_payload(db, user: User) -> MeOut:
    rows = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    memberships = [m for m in rows if m.status == "ACTIVE"]
    return MeOut(
        invitations=[InvitationOut(id=m.id, business_id=m.business_id, business_name=m.business.name, role=m.role, invited_by=m.invited_by)
                     for m in rows if m.status == "INVITED"],
        user=UserOut.model_validate(user),
        platform_role=user.platform_role,
        platform_areas=platform_team.areas_of(user),
        platform_team=user.platform_team,
        last_login_at=user.last_login_at,
        previous_login_at=user.previous_login_at,
        practice_clients=_practice_limit(db, user),
        totp_enabled=user.totp_enabled,
        must_change_password=user.must_change_password,
        legal_ok=PV.accepted(user), legal_version=PV.current_version(),
        businesses=[
            MyBusinessOut(id=m.business.id, name=m.business.name, gstin=m.business.gstin,
                          gst_type=m.business.gst_type, role=m.role, owned=m.business.owner_id == user.id,
                          permissions=effective(m.role, m.permissions), modules=m.business.modules,
                          entity_type=m.business.entity_type or "PROPRIETORSHIP")
            for m in memberships
        ],
    )


@router.post("/invitations/{membership_id}/{action}")
def answer_invitation(membership_id: str, action: Literal["accept", "decline"], db: DB, user: CurrentUser, request: Request):
    """A person who already has a login decides whether to join a business that added them as staff."""
    m = db.get(Membership, membership_id)
    if not m or m.user_id != user.id or m.status != "INVITED":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    name = m.business.name
    if action == "accept":
        m.status = "ACTIVE"
    else:
        db.delete(m)
    log(db, user, "STAFF", "invitation", f"{'Accepted' if action == 'accept' else 'Declined'} invitation to {name}",
        entity_id=membership_id, request=request)
    db.commit()
    return me_payload(db, user)


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
    mobile, email_ok = None, False
    ways = SU.methods(db)  # verification the super admin asks for (WhatsApp and / or e-mail code)
    if data.phone_code or (ways and not data.email_code and "WHATSAPP" in ways):
        # mobile number verified on WhatsApp before the account (and its free trial) is created
        mobile = W.normalize(data.phone)
        if not mobile:
            raise HTTPException(422, "Enter your 10-digit mobile number and the code sent to it on WhatsApp"
                                if ways == ["WHATSAPP"] else "Verify your mobile (WhatsApp code) or your e-mail (e-mail code)")
        if db.scalar(select(User).where(User.mobile == mobile)):
            raise HTTPException(status.HTTP_409_CONFLICT, "This mobile number is already linked to an account — sign in instead")
        W.check_otp(db, mobile, "SIGNUP", data.phone_code or "")
    elif data.email_code or ways:
        if "EMAIL" not in ways and not data.email_code:
            raise HTTPException(422, "Verify your mobile number with the WhatsApp code")
        if not data.email_code:
            raise HTTPException(422, "Enter the code sent to your e-mail" if ways == ["EMAIL"]
                                else "Verify your mobile (WhatsApp code) or your e-mail (e-mail code)")
        SU.check_email_code(db, email, data.email_code or "")
        email_ok = True
    if not data.accept_terms:
        raise HTTPException(422, "Please accept the Terms of Service and Privacy Policy to create an account")
    user = User(name=data.name, email=email, phone=data.phone, password_hash=hash_password(data.password),
                mobile=mobile, mobile_verified_at=now() if mobile else None, email_verified_at=now() if email_ok else None)
    db.add(user)
    db.flush()
    PV.accept(db, user, "SIGNUP", client_ip(request))
    db.flush()
    log(db, user, "CREATE", "user", f"Signed up: {email}", entity_id=user.id, request=request)
    db.commit()
    return TokenOut(token=token_for(user), **me_payload(db, user).model_dump())


# ---------------------------------------------------------------- e-mail code (sign-up) and Google
class EmailCodeIn(BaseModel):
    email: EmailStr


@router.post("/email-code")
def email_code(data: EmailCodeIn, db: DB, request: Request):
    """Verification code to the e-mail address, before an account is created."""
    if "EMAIL" not in SU.methods(db):
        raise HTTPException(400, "E-mail verification is not used for sign-up on this platform.")
    if db.scalar(select(User).where(func.lower(User.email) == data.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists — sign in instead")
    return SU.issue_email_code(db, str(data.email), client_ip(request))


class GoogleIn(BaseModel):
    credential: str = Field(min_length=20, max_length=5000)
    otp: str | None = None  # authenticator code when 2FA is on


@router.post("/google", response_model=TokenOut)
def google(data: GoogleIn, db: DB, request: Request):
    """Continue with Google: signs in the account with that e-mail, or creates one (nothing else asked — the next
    screen is business details)."""
    g = SU.google_identity(db, data.credential)
    user = db.scalar(select(User).where(User.google_sub == g["sub"])) if g["sub"] else None
    user = user or db.scalar(select(User).where(func.lower(User.email) == g["email"]))
    created = user is None
    if created:
        user = User(name=g["name"][:120], email=g["email"], password_hash=hash_password(secrets.token_urlsafe(24)),
                    google_sub=g["sub"], email_verified_at=now())
        db.add(user)
        db.flush()
        PV.accept(db, user, "GOOGLE", client_ip(request))  # "By continuing you agree…" is shown with the button
        log(db, user, "CREATE", "user", f"Signed up with Google: {user.email}", entity_id=user.id, request=request)
    else:
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled — contact your administrator")
        if user.totp_enabled:
            if not data.otp:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"message": "Enter the 6-digit code from your authenticator app",
                                                                    "code": "OTP_REQUIRED"})
            if not totp_ok(decrypt_secret(user.totp_secret_enc), data.otp):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"message": "The code is not correct", "code": "OTP_REQUIRED"})
        if not user.google_sub:
            user.google_sub = g["sub"]
        user.email_verified_at = user.email_verified_at or now()
        user.failed_logins, user.locked_until = 0, None
        user.previous_login_at, user.last_login_at = user.last_login_at, now()
        log(db, user, "LOGIN", "login", f"Signed in with Google: {user.email}", entity_id=user.id, request=request)
    db.commit()
    return TokenOut(token=token_for(user), **me_payload(db, user).model_dump())


# ---------------------------------------------------------------- WhatsApp codes
class PhoneIn(BaseModel):
    phone: str = Field(max_length=20)
    purpose: Literal["LOGIN", "SIGNUP"] = "LOGIN"


def _mobile(phone: str) -> str:
    m = W.normalize(phone)
    if not m:
        raise HTTPException(422, "Enter a 10-digit Indian mobile number")
    return m


@router.post("/otp/send")
def otp_send(data: PhoneIn, db: DB, request: Request):
    """Sign-in or sign-up code on WhatsApp. For sign-in the answer is the same whether or not the number has an account."""
    f = W.flags(db)
    if not (f["login"] if data.purpose == "LOGIN" else f["send"]):
        raise HTTPException(503, "WhatsApp codes are not available right now — use your e-mail and password.")
    mobile = _mobile(data.phone)
    user = db.scalar(select(User).where(User.mobile == mobile))
    if data.purpose == "SIGNUP" and user:
        raise HTTPException(status.HTTP_409_CONFLICT, "This mobile number is already linked to an account — sign in instead")
    if data.purpose == "LOGIN" and (not user or not user.is_active):
        # no message is sent (and nothing is charged) for numbers without an account
        return {"sent": True, "to": W.masked(mobile), "expires_in": W.OTP_MINUTES * 60, "resend_in": W.OTP_RESEND_SECONDS}
    return W.issue_otp(db, mobile, data.purpose, client_ip(request))


class OtpLoginIn(BaseModel):
    phone: str = Field(max_length=20)
    code: str = Field(min_length=4, max_length=8)
    otp: str | None = None  # authenticator code when 2FA is on


@router.post("/otp/login", response_model=TokenOut)
def otp_login(data: OtpLoginIn, db: DB, request: Request):
    if not W.flags(db)["login"]:
        raise HTTPException(503, "WhatsApp sign-in is not available right now — use your e-mail and password.")
    mobile = _mobile(data.phone)
    user = db.scalar(select(User).where(User.mobile == mobile))
    if user and _aware(user.locked_until) and _aware(user.locked_until) > now():
        mins = int((_aware(user.locked_until) - now()).total_seconds() // 60) + 1
        raise HTTPException(status.HTTP_423_LOCKED, f"Too many wrong attempts — try again in {mins} minute(s)")
    W.check_otp(db, mobile, "LOGIN", data.code)  # no account → no code was sent → "expired"
    if not user:
        raise HTTPException(400, "The code has expired — ask for a new one.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled — contact your administrator")
    if user.totp_enabled:
        if not data.otp:
            db.rollback()  # keep the WhatsApp code usable for the second step
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"message": "Enter the 6-digit code from your authenticator app",
                                                                "code": "OTP_REQUIRED"})
        if not totp_ok(decrypt_secret(user.totp_secret_enc), data.otp):
            db.rollback()
            user.failed_logins = (user.failed_logins or 0) + 1
            db.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"message": "The code is not correct", "code": "OTP_REQUIRED"})
    user.failed_logins, user.locked_until = 0, None
    user.previous_login_at, user.last_login_at = user.last_login_at, now()
    log(db, user, "LOGIN", "login", f"Signed in with WhatsApp code: {user.email}", entity_id=user.id, request=request)
    db.commit()
    return TokenOut(token=token_for(user), **me_payload(db, user).model_dump())


class MobileVerifyIn(BaseModel):
    phone: str = Field(max_length=20)
    code: str | None = Field(None, max_length=8)


@router.post("/mobile")
def link_mobile(data: MobileVerifyIn, db: DB, user: CurrentUser, request: Request):
    """Link a WhatsApp number to your account: without `code` a code is sent, with it the number is linked."""
    if not W.flags(db)["send"]:
        raise HTTPException(503, "WhatsApp is not set up on this platform yet.")
    mobile = _mobile(data.phone)
    other = db.scalar(select(User).where(User.mobile == mobile))
    if other and other.id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This mobile number is linked to another account")
    if not data.code:
        return W.issue_otp(db, mobile, "VERIFY", client_ip(request))
    W.check_otp(db, mobile, "VERIFY", data.code)
    user.mobile, user.mobile_verified_at = mobile, now()
    if not user.phone:
        user.phone = mobile[2:]
    log(db, user, "UPDATE", "user", f"Linked WhatsApp number {W.masked(mobile)}", entity_id=user.id, request=request)
    db.commit()
    return {"mobile": mobile}


@router.delete("/mobile")
def unlink_mobile(db: DB, user: CurrentUser, request: Request):
    user.mobile, user.mobile_verified_at = None, None
    log(db, user, "UPDATE", "user", "Removed WhatsApp sign-in number", entity_id=user.id, request=request)
    db.commit()
    return {"mobile": None}


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


@router.post("/legal/accept")
def accept_legal(db: DB, user: CurrentUser, request: Request):
    """Accept the Terms of Service and Privacy Policy now in force."""
    PV.accept(db, user, "PROMPT", client_ip(request))
    db.commit()
    return {"legal_version": user.legal_version, "legal_ok": True}


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
