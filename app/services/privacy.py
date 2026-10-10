"""Privacy & legal: consent to the current Terms / Privacy Policy, DPDP rights requests, grievance redressal and the
security-incident register.

* Consent: the version in force is `legal_version` (Admin → GST config → Legal & privacy). Every acceptance is kept
  (who, which version, when, from where, how). When the version changes, users are asked to accept again.
* Requests (DPDP Act ss.11-14 and the grievance officer under the IT Rules): access, correction, erasure, grievance,
  withdrawal of consent. Acknowledged at once; the super admin works them from Admin → Privacy & security.
  Erasure removes the person's own login details; business records stay as long as tax and company law require
  (CGST s.36: 72 months; Companies Act s.128: 8 years) — the DPDP Act s.8(7) allows that.
* Incidents: recorded by the super admin; affected businesses (the data fiduciaries) are e-mailed without delay.
"""

import datetime as dt
import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Business, DataRequest, LegalAcceptance, Membership, SecurityIncident, User
from . import config_store as C

KINDS = {"ACCESS": "A copy of my personal data", "CORRECTION": "Correct my personal data", "ERASURE": "Erase my personal data / close my account",
         "WITHDRAW": "Withdraw consent", "GRIEVANCE": "A grievance or complaint"}
RESOLVE_DAYS = {"GRIEVANCE": 15, "ACCESS": 30, "CORRECTION": 30, "ERASURE": 30, "WITHDRAW": 30}


def legal() -> dict:
    try:
        return dict(C.get("legal") or {})
    except KeyError:
        return {}


def current_version() -> str:
    return str(legal().get("version") or "1")


def accepted(user: User) -> bool:
    return (user.legal_version or "") == current_version()


def accept(db: Session, user: User, method: str, ip: str | None) -> None:
    v = current_version()
    user.legal_version = v
    db.add(LegalAcceptance(user_id=user.id, version=v, method=method, ip=ip))


# ---------------------------------------------------------------- requests
def create_request(db: Session, user: User, kind: str, details: str, business_id: str | None) -> DataRequest:
    if kind not in KINDS:
        raise HTTPException(422, "Choose what you are asking for")
    if business_id and not db.scalar(select(Membership.id).where(Membership.user_id == user.id, Membership.business_id == business_id)):
        business_id = None
    r = DataRequest(user_id=user.id, user_email=user.email, user_name=user.name, business_id=business_id, kind=kind,
                    details=(details or "").strip()[:4000], status="OPEN",
                    due_on=dt.date.today() + dt.timedelta(days=RESOLVE_DAYS[kind]))
    db.add(r)
    db.flush()
    _mail_grievance(db, f"New {KINDS[kind].lower()} request from {user.email}",
                    f"<p><b>{user.name}</b> ({user.email}) raised a request: <b>{KINDS[kind]}</b>.</p>"
                    f"<p>{(details or '').strip()[:2000]}</p><p>Reference {r.id[:8].upper()} · respond by {r.due_on:%d %b %Y}.</p>")
    return r


def out(r: DataRequest) -> dict:
    return dict(id=r.id, ref=r.id[:8].upper(), kind=r.kind, kind_label=KINDS.get(r.kind, r.kind), details=r.details,
                status=r.status, response=r.response, created_at=r.created_at, due_on=r.due_on, closed_at=r.closed_at,
                user_email=r.user_email, user_name=r.user_name, handled_by=r.handled_by)


def erase_user(db: Session, user: User, by: str) -> str:
    """Remove a person's own login details. Their businesses' books stay (statutory retention)."""
    if user.platform_role == "SUPERADMIN":
        raise HTTPException(400, "A super admin cannot be erased this way")
    owned = db.scalar(select(Business.id).where(Business.owner_id == user.id).limit(1))
    tag = secrets.token_hex(4)
    user.name, user.email, user.phone = "Erased user", f"erased-{tag}@invalid.local", None
    user.mobile = user.mobile_verified_at = user.google_sub = user.totp_secret_enc = None
    user.totp_enabled, user.is_active = False, False
    user.token_version = (user.token_version or 0) + 1
    from ..security import hash_password

    user.password_hash = hash_password(secrets.token_urlsafe(24))
    return ("Login details erased. " + ("The businesses this person owned keep their books of account for the period tax and "
            "company law require; transfer or close them separately." if owned else "")).strip() + f" (by {by})"


# ---------------------------------------------------------------- incidents
def notify_incident(db: Session, inc: SecurityIncident, business_ids: list[str] | None) -> int:
    """E-mail the owners (data fiduciaries) of the affected businesses (all businesses when none are listed)."""
    from . import mailer

    cfg = mailer.system_smtp(db)
    if not cfg:
        raise HTTPException(503, "Set up the platform e-mail (Admin → Email) to notify businesses")
    q = select(Business, User).join(User, User.id == Business.owner_id)
    if business_ids:
        q = q.where(Business.id.in_(business_ids))
    sent = set()
    g = legal()
    for biz, owner in db.execute(q):
        if owner.email in sent or owner.email.endswith("@invalid.local"):
            continue
        mailer.send(cfg, [owner.email], f"Security notice: {inc.title}", mailer.layout("Security notice", f"""
            <p>Dear {owner.name},</p>
            <p>We are informing you, as the data fiduciary for <b>{biz.name}</b>, about a security incident on our platform.</p>
            <p><b>What happened:</b> {inc.description}</p>
            <p><b>Detected:</b> {inc.detected_at:%d %b %Y %H:%M} · <b>Data that may be affected:</b> {inc.affected or "being assessed"}</p>
            <p><b>What we are doing:</b> {inc.actions or "Investigating and containing the incident."}</p>
            <p>Under the Digital Personal Data Protection Act, 2023, informing the Data Protection Board and the affected
            individuals is your responsibility as data fiduciary; we will give you the information you need for that.</p>
            <p>Questions: {g.get("grievance_officer", "Grievance Officer")} · {g.get("grievance_email", "")}</p>"""))
        sent.add(owner.email)
    inc.notified_at = dt.datetime.now(dt.UTC)
    inc.notified_count = len(sent)
    return len(sent)


def _mail_grievance(db: Session, subject: str, html: str) -> None:
    from . import mailer

    to = legal().get("grievance_email")
    cfg = mailer.system_smtp(db)
    if cfg and to:
        try:
            mailer.send(cfg, [to], subject, mailer.layout("Privacy request", html))
        except Exception:  # noqa: BLE001 — the request is saved; e-mail is a convenience
            pass
