"""Admin → Helpdesk: the ticket queue for the company team (super admin, or team members with the helpdesk area)."""

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from ..deps import DB, platform_area
from ..models import Business, Subscription, Ticket, User
from ..services import helpdesk as HD
from ..services import platform_team
from .support import _read

router = APIRouter(prefix="/admin/helpdesk", tags=["helpdesk"])
Agent = platform_area("helpdesk")


def _get(db, ticket_id: str) -> Ticket:
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    return t


@router.get("")
def queue(db: DB, me: Agent, status: str | None = None, team: str | None = None, assigned: str | None = None,
          category: str | None = None, priority: str | None = None, q: str | None = None, limit: int = 200):
    """status: a status, or ACTIVE (= open, in progress, waiting). assigned: me / none / a user id."""
    stmt = select(Ticket)
    if status == "ACTIVE":
        stmt = stmt.where(Ticket.status.in_(["OPEN", "IN_PROGRESS", "WAITING"]))
    elif status:
        stmt = stmt.where(Ticket.status == status)
    for col, val in ((Ticket.team, team), (Ticket.category, category), (Ticket.priority, priority)):
        if val:
            stmt = stmt.where(col == val)
    if assigned == "me":
        stmt = stmt.where(Ticket.assigned_to == me.id)
    elif assigned == "none":
        stmt = stmt.where(Ticket.assigned_to.is_(None))
    elif assigned:
        stmt = stmt.where(Ticket.assigned_to == assigned)
    if q:
        like = f"%{q.strip()}%"
        num = q.strip().upper().removeprefix("T-")
        people = select(User.id).where(or_(User.name.ilike(like), User.email.ilike(like), User.mobile.ilike(like)))
        biz = select(Business.id).where(Business.name.ilike(like))
        stmt = stmt.where(or_(Ticket.subject.ilike(like), Ticket.user_id.in_(people), Ticket.business_id.in_(biz),
                              *([Ticket.number == int(num)] if num.isdigit() else [])))
    order = {"URGENT": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}
    rows = db.scalars(stmt.order_by(Ticket.last_activity_at.desc()).limit(min(limit, 500))).all()
    rows = sorted(rows, key=lambda t: (t.status in ("RESOLVED", "CLOSED"), order.get(t.priority, 2)))
    counts = dict(db.execute(select(Ticket.status, func.count()).group_by(Ticket.status)).all())
    mine = db.scalar(select(func.count(Ticket.id)).where(Ticket.assigned_to == me.id,
                                                         Ticket.status.in_(["OPEN", "IN_PROGRESS", "WAITING"]))) or 0
    unassigned = db.scalar(select(func.count(Ticket.id)).where(Ticket.assigned_to.is_(None),
                                                               Ticket.status.in_(["OPEN", "IN_PROGRESS", "WAITING"]))) or 0
    rated = db.execute(select(func.avg(Ticket.rating), func.count(Ticket.rating)).where(Ticket.rating.is_not(None))).one()
    return {"rows": [HD.summary(db, t, for_team=True) for t in rows],
            "counts": {s: int(counts.get(s, 0)) for s in HD.STATUSES}, "mine": mine, "unassigned": unassigned,
            "rating": {"average": round(float(rated[0]), 2) if rated[0] else None, "count": int(rated[1])}}


@router.get("/meta")
def meta(db: DB, me: Agent):
    return {"categories": HD.CATEGORIES, "priorities": HD.PRIORITIES, "statuses": HD.TEAM_STATUS_LABEL,
            "teams": {k: v for k, v in platform_team.TEAMS.items() if k != "ADMIN"},
            "agents": [dict(id=u.id, name=u.name, team=u.platform_team or "Super admin") for u in HD.agents(db)], "me": me.id}


@router.get("/{ticket_id}")
def ticket(ticket_id: str, db: DB, _: Agent):
    t = _get(db, ticket_id)
    who = db.get(User, t.user_id)
    sub = db.get(Subscription, t.user_id) if who else None
    others = db.scalars(select(Ticket).where(Ticket.user_id == t.user_id, Ticket.id != t.id)
                        .order_by(Ticket.created_at.desc()).limit(10)).all()
    return {**HD.detail(db, t, for_team=True),
            "requester": dict(signed_up=who.created_at if who else None, last_login_at=who.last_login_at if who else None,
                              plan=sub.plan if sub else None, plan_status=sub.status if sub else None),
            "other_tickets": [HD.summary(db, o, for_team=True) for o in others]}


@router.post("/{ticket_id}/messages")
async def reply(ticket_id: str, db: DB, me: Agent, body: Annotated[str, Form(min_length=1, max_length=10000)],
                internal: Annotated[bool, Form()] = False,
                status: Annotated[Literal["OPEN", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"] | None, Form()] = None,
                files: Annotated[list[UploadFile] | None, File()] = None):
    t = _get(db, ticket_id)
    uploads = await _read(files)
    m = HD.team_reply(db, t, me, body, internal, status)
    HD.add_files(db, t, m.id, me, uploads)
    db.commit()
    return ticket(ticket_id, db, me)


class UpdateIn(BaseModel):
    status: Literal["OPEN", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"] | None = None
    priority: Literal["LOW", "NORMAL", "HIGH", "URGENT"] | None = None
    team: Literal["SUPPORT", "TECH", "FINANCE", "SALES"] | None = None
    assigned_to: str | None = None
    unassign: bool = False


@router.put("/{ticket_id}")
def update(ticket_id: str, data: UpdateIn, db: DB, me: Agent):
    t = _get(db, ticket_id)
    if data.priority:
        t.priority = data.priority
    if data.team:
        t.team = data.team
    if data.unassign or data.assigned_to:
        HD.assign(db, t, me, None if data.unassign else data.assigned_to)
    if data.status:
        HD.set_status(db, t, me, data.status)
    db.commit()
    return ticket(ticket_id, db, me)
