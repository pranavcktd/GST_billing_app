"""Privacy centre (every signed-in user) and the super admin's privacy & security desk. See services/privacy.py."""

import datetime as dt
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import DB, CurrentUser, SuperAdmin
from ..models import AuditLog, DataRequest, LegalAcceptance, Membership, SecurityIncident, User
from ..services import privacy as PV
from ..services.platform_audit import log

router = APIRouter(tags=["privacy"])


# ---------------------------------------------------------------- the user
@router.get("/privacy/my-data")
def my_data(db: DB, user: CurrentUser):
    """Your personal data held by the platform (DPDP Act s.11), as a JSON file."""
    import json

    ms = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    data = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "account": {"name": user.name, "email": user.email, "phone": user.phone, "whatsapp_mobile": user.mobile,
                    "created_at": user.created_at, "last_login_at": user.last_login_at, "two_factor": user.totp_enabled,
                    "signed_in_with_google": bool(user.google_sub)},
        "businesses": [{"business": m.business.name, "role": m.role.value, "status": m.status} for m in ms],
        "consents": [{"version": a.version, "method": a.method, "accepted_at": a.accepted_at, "ip": a.ip}
                     for a in db.scalars(select(LegalAcceptance).where(LegalAcceptance.user_id == user.id))],
        "recent_activity": [{"at": a.created_at, "action": a.action, "summary": a.summary, "ip": a.ip}
                            for a in db.scalars(select(AuditLog).where(AuditLog.user_id == user.id)
                                                .order_by(AuditLog.created_at.desc()).limit(200))],
        "requests": [PV.out(r) for r in db.scalars(select(DataRequest).where(DataRequest.user_id == user.id))],
        "note": "Business records (invoices, books of account) belong to the business and can be exported from "
                "Utilities → Backup & restore by its owner.",
    }
    body = json.dumps(data, default=str, indent=2).encode()
    return Response(body, media_type="application/json", headers={"Content-Disposition": 'attachment; filename="my-personal-data.json"'})


class RequestIn(BaseModel):
    kind: Literal["ACCESS", "CORRECTION", "ERASURE", "WITHDRAW", "GRIEVANCE"]
    details: str = Field("", max_length=4000)
    business_id: str | None = None


@router.post("/privacy/requests", status_code=201)
def raise_request(data: RequestIn, db: DB, user: CurrentUser):
    r = PV.create_request(db, user, data.kind, data.details, data.business_id)
    db.commit()
    return PV.out(r)


@router.get("/privacy/requests")
def my_requests(db: DB, user: CurrentUser):
    return [PV.out(r) for r in db.scalars(select(DataRequest).where(DataRequest.user_id == user.id)
                                         .order_by(DataRequest.created_at.desc()))]


# ---------------------------------------------------------------- super admin
@router.get("/admin/privacy-requests")
def all_requests(db: DB, admin: SuperAdmin, status: str | None = None):
    q = select(DataRequest).order_by(DataRequest.created_at.desc()).limit(500)
    if status:
        q = q.where(DataRequest.status == status)
    return [PV.out(r) for r in db.scalars(q)]


class RequestUpdate(BaseModel):
    status: Literal["OPEN", "IN_PROGRESS", "CLOSED", "REJECTED"]
    response: str = Field("", max_length=4000)
    erase: bool = False  # ERASURE: erase the person's login details now


@router.put("/admin/privacy-requests/{rid}")
def update_request(rid: str, data: RequestUpdate, db: DB, admin: SuperAdmin, request: Request):
    r = db.get(DataRequest, rid)
    if not r:
        raise HTTPException(404, "Request not found")
    note = data.response.strip()
    if data.erase:
        if r.kind != "ERASURE" or not r.user_id:
            raise HTTPException(400, "Only an erasure request can erase an account")
        u = db.get(User, r.user_id)
        note = (note + "\n" if note else "") + PV.erase_user(db, u, admin.name)
    r.status, r.response, r.handled_by = data.status, note or r.response, admin.name
    r.closed_at = dt.datetime.now(dt.UTC) if data.status in ("CLOSED", "REJECTED") else None
    if data.status in ("CLOSED", "REJECTED") and r.user_email and not r.user_email.endswith("@invalid.local"):
        from ..services import mailer

        cfg = mailer.system_smtp(db)
        if cfg:
            try:
                mailer.send(cfg, [r.user_email], f"Your request {r.id[:8].upper()} — {data.status.lower()}", mailer.layout(
                    "Your privacy request", f"<p>Your request <b>{PV.KINDS[r.kind]}</b> (ref. {r.id[:8].upper()}) is "
                                            f"<b>{data.status.lower()}</b>.</p><p>{(r.response or '').replace(chr(10), '<br>')}</p>"))
            except Exception:  # noqa: BLE001
                pass
    log(db, admin, "UPDATE", "privacy-request", f"{r.kind} request {r.id[:8].upper()} of {r.user_email}: {data.status}"
        + (" (login erased)" if data.erase else ""), request=request)
    db.commit()
    return PV.out(r)


class IncidentIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=8000)
    affected: str = Field("", max_length=4000)
    actions: str = Field("", max_length=4000)
    severity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    status: Literal["OPEN", "CONTAINED", "CLOSED"] = "OPEN"
    detected_at: dt.datetime | None = None


def _inc(i: SecurityIncident) -> dict:
    return dict(id=i.id, title=i.title, description=i.description, affected=i.affected, actions=i.actions, severity=i.severity,
                status=i.status, detected_at=i.detected_at, notified_at=i.notified_at, notified_count=i.notified_count,
                created_by=i.created_by, created_at=i.created_at)


@router.get("/admin/incidents")
def incidents(db: DB, admin: SuperAdmin):
    return [_inc(i) for i in db.scalars(select(SecurityIncident).order_by(SecurityIncident.detected_at.desc()))]


@router.post("/admin/incidents", status_code=201)
def add_incident(data: IncidentIn, db: DB, admin: SuperAdmin, request: Request):
    i = SecurityIncident(**data.model_dump(exclude={"detected_at"}), detected_at=data.detected_at or dt.datetime.now(dt.UTC),
                         created_by=admin.name)
    db.add(i)
    log(db, admin, "CREATE", "security-incident", f"Security incident recorded: {data.title} ({data.severity})", request=request)
    db.commit()
    return _inc(i)


@router.put("/admin/incidents/{iid}")
def edit_incident(iid: str, data: IncidentIn, db: DB, admin: SuperAdmin, request: Request):
    i = db.get(SecurityIncident, iid)
    if not i:
        raise HTTPException(404, "Incident not found")
    for k, v in data.model_dump(exclude={"detected_at"}).items():
        setattr(i, k, v)
    if data.detected_at:
        i.detected_at = data.detected_at
    log(db, admin, "UPDATE", "security-incident", f"Security incident updated: {i.title} — {i.status}", request=request)
    db.commit()
    return _inc(i)


class NotifyIn(BaseModel):
    business_ids: list[str] = Field(default_factory=list, max_length=5000)  # empty = every business


@router.post("/admin/incidents/{iid}/notify")
def notify(iid: str, data: NotifyIn, db: DB, admin: SuperAdmin, request: Request):
    i = db.get(SecurityIncident, iid)
    if not i:
        raise HTTPException(404, "Incident not found")
    n = PV.notify_incident(db, i, data.business_ids or None)
    log(db, admin, "ACTION", "security-incident", f"Businesses notified of '{i.title}': {n}", request=request)
    db.commit()
    return _inc(i)
