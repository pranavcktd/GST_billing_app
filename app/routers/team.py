"""Admin → Team: the company's own staff (support, technical, finance, sales, deputy admin) and the admin areas each
may open. Super admin only. See services/platform_team.py."""

import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from ..deps import DB, SuperAdmin
from ..gst.constants import PlatformRole
from ..models import Ticket, User
from ..security import hash_password
from ..services import config_store, mailer, notify
from ..services import platform_team as PT
from ..services.platform_audit import log

router = APIRouter(prefix="/admin/team", tags=["team"])
TEAM = PlatformRole.TEAM.value


def _out(db, u: User) -> dict:
    open_tickets = db.scalar(select(func.count(Ticket.id)).where(
        Ticket.assigned_to == u.id, Ticket.status.in_(["OPEN", "IN_PROGRESS", "WAITING"]))) or 0
    return dict(id=u.id, name=u.name, email=u.email, phone=u.phone, team=u.platform_team,
                areas=[a for a in (u.platform_areas or []) if a in PT.AREAS], active=u.is_active, totp_enabled=u.totp_enabled,
                last_login_at=u.last_login_at, created_at=u.created_at, open_tickets=open_tickets)


@router.get("")
def members(db: DB, _: SuperAdmin):
    rows = db.scalars(select(User).where(User.platform_role == TEAM).order_by(User.platform_team, User.name)).all()
    admins = db.scalars(select(User).where(User.platform_role == PlatformRole.SUPERADMIN.value)).all()
    return {"members": [_out(db, u) for u in rows], "areas": PT.AREAS, "teams": PT.TEAMS, "team_areas": PT.TEAM_AREAS,
            "superadmins": [dict(id=u.id, name=u.name, email=u.email) for u in admins]}


class MemberIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(None, max_length=20)
    team: str = Field(pattern="^(SUPPORT|TECH|FINANCE|SALES|ADMIN)$")
    areas: list[str] = []


def _areas(areas: list[str]) -> list[str]:
    bad = [a for a in areas if a not in PT.AREAS]
    if bad:
        raise HTTPException(422, f"Unknown area: {', '.join(bad)}")
    return list(dict.fromkeys(areas))


@router.post("", status_code=201)
def add_member(data: MemberIn, db: DB, me: SuperAdmin, request: Request):
    """Add a team member. A new person gets a temporary password (shown once, and e-mailed when e-mail is set up);
    an existing login (e.g. an employee who also has a business account) simply gets team access."""
    areas = _areas(data.areas or PT.TEAM_AREAS[data.team])
    u = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    temp = None
    if u:
        if u.platform_role in (PlatformRole.SUPERADMIN.value, PlatformRole.RESELLER.value):
            raise HTTPException(400, f"{u.email} is a {u.platform_role.lower()} — use another e-mail for the team login")
        if u.platform_role == TEAM:
            raise HTTPException(409, "Already in the team")
    else:
        temp = secrets.token_urlsafe(9)
        u = User(name=data.name, email=data.email.lower(), phone=data.phone, password_hash=hash_password(temp),
                 must_change_password=True)
        db.add(u)
    u.platform_role, u.platform_team, u.platform_areas, u.is_active = TEAM, data.team, areas, True
    db.flush()
    log(db, me, "CREATE", "team", f"Team member added: {u.email} ({PT.TEAMS[data.team]}; {', '.join(areas)})",
        entity_id=u.id, request=request)
    app = config_store.app_name()
    text = (f"Hello {u.name},\nYou have been added to the {app} team ({PT.TEAMS[data.team]}). Sign in to open the admin panel."
            + (f"\nE-mail: {u.email}\nTemporary password: {temp}\nYou will be asked to choose a new password. "
               "Please also turn on two-step sign-in (Settings → Security)." if temp else ""))
    notify.queue_mail(db, [u.email], f"You have been added to the {app} team", notify.email_html(f"Welcome to the {app} team", text, "/admin", "Open the admin panel"))
    db.commit()
    return {**_out(db, u), "temporary_password": temp, "emailed": mailer.system_smtp(db) is not None}


class EditIn(BaseModel):
    team: str = Field(pattern="^(SUPPORT|TECH|FINANCE|SALES|ADMIN)$")
    areas: list[str]
    active: bool = True


@router.put("/{user_id}")
def edit_member(user_id: str, data: EditIn, db: DB, me: SuperAdmin, request: Request):
    u = db.get(User, user_id)
    if not u or u.platform_role != TEAM:
        raise HTTPException(404, "Team member not found")
    u.platform_team, u.platform_areas = data.team, _areas(data.areas)
    if u.is_active != data.active:
        u.is_active = data.active
        u.token_version = (u.token_version or 0) + 1  # signed out everywhere
    if "helpdesk" not in u.platform_areas or not data.active:
        _hand_back(db, u)
    log(db, me, "UPDATE", "team", f"Team member {u.email}: {PT.TEAMS[data.team]}; {', '.join(u.platform_areas) or 'no areas'}"
        f"{'' if data.active else '; deactivated'}", entity_id=u.id, request=request)
    db.commit()
    return _out(db, u)


def _hand_back(db, u: User) -> None:
    """Their open tickets go back to the queue."""
    for t in db.scalars(select(Ticket).where(Ticket.assigned_to == u.id, Ticket.status.in_(["OPEN", "IN_PROGRESS", "WAITING"]))):
        t.assigned_to = None


@router.delete("/{user_id}", status_code=204)
def remove_member(user_id: str, db: DB, me: SuperAdmin, request: Request):
    """Removes team access only — the login stays (it may own businesses). Open tickets go back to the queue."""
    u = db.get(User, user_id)
    if not u or u.platform_role != TEAM:
        raise HTTPException(404, "Team member not found")
    _hand_back(db, u)
    u.platform_role = u.platform_team = u.platform_areas = None  # takes effect on their next request
    log(db, me, "DELETE", "team", f"Team access removed: {u.email}", entity_id=u.id, request=request)
    db.commit()
