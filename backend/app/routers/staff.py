"""Staff sign-ins of a business: who signed in, when and from where; approvals; sign-in rules."""

import datetime as dt
import ipaddress
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from ..deps import BCtx
from ..models import Membership, StaffSession, User
from ..services import staff_access as SA
from ..services.platform_audit import client_ip, log

router = APIRouter(prefix="/staff", tags=["staff"])

_HM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _device(ua: str | None) -> str:
    ua = ua or ""
    os_ = next((n for k, n in (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"),
                                ("Mac OS", "Mac"), ("Linux", "Linux")) if k in ua), "")
    br = next((n for k, n in (("Edg/", "Edge"), ("OPR/", "Opera"), ("Chrome/", "Chrome"), ("Firefox/", "Firefox"),
                               ("Safari/", "Safari")) if k in ua), "")
    return " · ".join(x for x in (br, os_) if x) or "Unknown device"


@router.get("/sessions")
def sessions(ctx: BCtx, status: str | None = None, limit: int = 200):
    ctx.need("users", "view")
    q = (select(StaffSession, User, Membership.role).join(User, User.id == StaffSession.user_id)
         .join(Membership, (Membership.user_id == StaffSession.user_id) & (Membership.business_id == StaffSession.business_id), isouter=True)
         .where(StaffSession.business_id == ctx.bid).order_by(StaffSession.last_seen.desc()).limit(min(limit, 1000)))
    if status:
        q = q.where(StaffSession.status == status)
    return [dict(id=s.id, user_id=u.id, name=u.name, email=u.email, role=role.value if role else None, status=s.status,
                 ip=s.ip, device=_device(s.user_agent), first_seen=s.first_seen, last_seen=s.last_seen,
                 requested_at=s.requested_at, decided_by=s.decided_by, decided_at=s.decided_at, valid_until=s.valid_until)
            for s, u, role in ctx.db.execute(q).all()]


@router.get("/pending")
def pending(ctx: BCtx):
    """Number of sign-ins waiting for approval (top-bar badge for owners / admins)."""
    if not ctx.can("users", "edit"):
        return {"count": 0}
    return {"count": ctx.db.scalar(select(func.count()).select_from(StaffSession).where(
        StaffSession.business_id == ctx.bid, StaffSession.status == "PENDING")) or 0}


@router.post("/sessions/{session_id}/{action}")
def decide(session_id: str, action: str, ctx: BCtx, request: Request):
    ctx.need("users", "edit")
    if action not in ("approve", "deny"):
        raise HTTPException(404, "Unknown action")
    s = ctx.db.get(StaffSession, session_id)
    if not s or s.business_id != ctx.bid:
        raise HTTPException(404, "Sign-in not found")
    u = ctx.db.get(User, s.user_id)
    SA.decide(ctx.db, s, action == "approve", ctx.user, ctx.business)
    log(ctx.db, ctx.user, "STAFF", "staff", f"{'Approved' if action == 'approve' else 'Blocked'} sign-in of {u.email} "
        f"to {ctx.business.name} from {s.ip or 'unknown address'}", entity_id=s.id, request=request)
    ctx.db.commit()
    return {"status": s.status}


class PolicyIn(BaseModel):
    approval: bool = False
    approval_hours: int = Field(12, ge=1, le=168)
    ip_allowlist: list[str] = Field(default_factory=list, max_length=30)
    hours_from: str | None = None
    hours_to: str | None = None
    include_admins: bool = False

    @field_validator("ip_allowlist")
    @classmethod
    def _ips(cls, v):
        out = []
        for x in v:
            x = x.strip()
            if not x:
                continue
            try:
                ipaddress.ip_network(x, strict=False)
            except ValueError:
                raise ValueError(f"'{x}' is not an IP address or range (e.g. 203.0.113.7 or 203.0.113.0/24)") from None
            out.append(x)
        return out

    @field_validator("hours_from", "hours_to")
    @classmethod
    def _hm(cls, v):
        if v in (None, ""):
            return None
        if not _HM.match(v):
            raise ValueError("Use 24-hour time like 09:00")
        return v


@router.get("/policy")
def get_policy(ctx: BCtx, request: Request):
    ctx.need("users", "view")
    return {**SA.policy(ctx.business), "your_ip": client_ip(request)}


@router.put("/policy")
def put_policy(data: PolicyIn, ctx: BCtx, request: Request):
    ctx.need("users", "edit")
    if (data.hours_from is None) != (data.hours_to is None):
        raise HTTPException(422, "Give both the start and the end time, or neither")
    ctx.business.staff_access = data.model_dump()
    log(ctx.db, ctx.user, "STAFF", "staff", f"Changed staff sign-in rules of {ctx.business.name}", request=request)
    ctx.db.commit()
    return SA.policy(ctx.business)
