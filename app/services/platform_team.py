"""The company's own team (support, technical, finance, sales) working in the admin panel.

A team member is a user with platform_role TEAM and a list of admin *areas* they may open. The super admin has every
area. Areas are deliberately limited to day-to-day work; platform settings, keys, pricing, backups and the team itself
stay with the super admin.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..gst.constants import PlatformRole
from ..models import User

AREAS = {
    "helpdesk": "Helpdesk — answer and resolve tickets",
    "payments": "Transactions, receipts & leads",
    "analytics": "Visitors & module usage",
    "accounts": "Accounts & businesses (view only)",
    "website": "Website content & policies",
}
TEAMS = {"SUPPORT": "Support", "TECH": "Technical", "FINANCE": "Finance", "SALES": "Sales", "ADMIN": "Deputy admin"}
TEAM_AREAS = {  # suggested areas when a member joins a team (the super admin can change them)
    "SUPPORT": ["helpdesk"], "TECH": ["helpdesk", "analytics"], "FINANCE": ["payments"],
    "SALES": ["payments", "analytics", "accounts"], "ADMIN": list(AREAS),
}


def is_superadmin(user: User | None) -> bool:
    return bool(user) and user.platform_role == PlatformRole.SUPERADMIN.value


def areas_of(user: User | None) -> list[str]:
    if is_superadmin(user):
        return list(AREAS)
    if user and user.is_active and user.platform_role == PlatformRole.TEAM.value:
        return [a for a in (user.platform_areas or []) if a in AREAS]
    return []


def has_area(user: User | None, area: str) -> bool:
    return area in areas_of(user)


def members(db: Session, area: str) -> list[User]:
    """Super admins and active team members who work in this area (they get its alerts)."""
    listed = list(get_settings().superadmins)  # SUPERADMIN_EMAILS, even before their first sign-in saves the role
    rows = db.scalars(select(User).where(User.is_active.is_(True), or_(
        User.platform_role == PlatformRole.SUPERADMIN.value, User.platform_role == PlatformRole.TEAM.value,
        func.lower(User.email).in_(listed) if listed else False))).all()
    return [u for u in rows if has_area(u, area) or u.email.lower() in listed]
