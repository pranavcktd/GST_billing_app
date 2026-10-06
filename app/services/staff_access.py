"""Staff sign-in control for a business.

Every person has ONE login (their e-mail), whichever businesses they work for; access is per business
(a membership). An owner can therefore never change a shared staff member's password — that would lock
the person out of their other employers' businesses.

Each business may restrict how its staff (everyone except the owner; admins optionally) get in:
    approval       — every new sign-in (device / session) waits until the owner or an admin approves it
    approval_hours — how long an approval lasts (default 12 h, i.e. a working day)
    ip_allowlist   — only from these IP addresses / ranges (the office internet connection)
    hours_from/to  — only during these hours (India time)
    include_admins — apply the rules to business admins as well

Whether or not rules are set, the first use of the business in every session is recorded, so the owner
always sees which staff signed in, when and from where.

Settings: businesses.staff_access (JSON). Sessions: staff_sessions.
"""

import datetime as dt
import ipaddress

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..gst.constants import Role
from ..models import Business, Membership, StaffSession, User
from .platform_audit import client_ip

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
DEFAULT_POLICY = {"approval": False, "approval_hours": 12, "ip_allowlist": [], "hours_from": None, "hours_to": None,
                  "include_admins": False}
TOUCH_EVERY = dt.timedelta(minutes=5)


def policy(biz: Business) -> dict:
    return {**DEFAULT_POLICY, **(biz.staff_access or {})}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _aware(d: dt.datetime | None) -> dt.datetime | None:
    return d.replace(tzinfo=dt.UTC) if d and d.tzinfo is None else d


def ip_allowed(ip: str | None, allow: list[str]) -> bool:
    if not allow:
        return True
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in allow:
        try:
            if addr in ipaddress.ip_network(entry.strip(), strict=False):
                return True
        except ValueError:
            continue
    return False


def within_hours(p: dict, now: dt.datetime | None = None) -> bool:
    if not p.get("hours_from") or not p.get("hours_to"):
        return True
    t = (now or _now()).astimezone(IST).strftime("%H:%M")
    a, b = p["hours_from"], p["hours_to"]
    return a <= t <= b if a <= b else (t >= a or t <= b)  # overnight window, e.g. 20:00–06:00


def _block(code: str, message: str):
    raise HTTPException(status.HTTP_403_FORBIDDEN, {"code": code, "message": message})


def check(db: Session, request: Request | None, user: User, m: Membership, biz: Business) -> None:
    """Called for every request a non-owner makes in a business (see deps.business_ctx)."""
    if m.role == Role.OWNER or request is None:
        return
    p = policy(biz)
    applies = m.role != Role.ADMIN or p["include_admins"]
    sid = getattr(request.state, "sid", None) or "legacy"
    ip = client_ip(request)
    row = db.scalar(select(StaffSession).where(StaffSession.business_id == biz.id, StaffSession.user_id == user.id,
                                               StaffSession.sid == sid))
    now = _now()
    if row is None:
        row = StaffSession(business_id=biz.id, user_id=user.id, sid=sid, ip=ip,
                           user_agent=(request.headers.get("user-agent") or "")[:300],
                           status="PENDING" if applies and p["approval"] else "AUTO", first_seen=now, last_seen=now)
        db.add(row)
        db.commit()
    elif now - (_aware(row.last_seen) or now) > TOUCH_EVERY:
        row.last_seen, row.ip = now, ip or row.ip
        db.commit()
    if not applies:
        return
    if not ip_allowed(ip, p["ip_allowlist"]):
        _block("IP_NOT_ALLOWED", f"{biz.name} allows staff to sign in only from its office network (your address: {ip or 'unknown'}).")
    if not within_hours(p, now):
        _block("OUTSIDE_HOURS", f"{biz.name} allows staff sign-in only between {p['hours_from']} and {p['hours_to']}.")
    if p["approval"]:
        if row.status == "AUTO" or (row.status == "APPROVED" and row.valid_until and _aware(row.valid_until) < now):
            row.status, row.valid_until, row.decided_by, row.decided_at = "PENDING", None, None, None
            row.requested_at = now
            db.commit()
        if row.status == "PENDING":
            _block("ACCESS_PENDING", f"Waiting for the owner of {biz.name} to approve this sign-in.")
        if row.status == "DENIED":
            _block("ACCESS_DENIED", f"The owner of {biz.name} did not approve this sign-in. Sign out and ask them, then sign in again.")


def decide(db: Session, row: StaffSession, approve: bool, by: User, biz: Business) -> None:
    p = policy(biz)
    row.status = "APPROVED" if approve else "DENIED"
    row.decided_by, row.decided_at = by.name, _now()
    row.valid_until = _now() + dt.timedelta(hours=int(p["approval_hours"] or 12)) if approve else None
    db.commit()
