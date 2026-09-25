"""Request dependencies: authenticated user, the active business (tenant) and permissions."""

import datetime as dt
from dataclasses import dataclass, field
from typing import Annotated

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .gst.constants import PlatformRole, Role
from .models import Business, Membership, User
from .permissions import MODULES, effective
from .security import decode_token

DB = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


def current_user(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User:
    user_id = decode_token(creds.credentials) if creds else None
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if user.email.lower() in get_settings().superadmins and user.platform_role != PlatformRole.SUPERADMIN.value:
        user.platform_role = PlatformRole.SUPERADMIN.value
        db.commit()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def superadmin(user: CurrentUser) -> User:
    if user.platform_role != PlatformRole.SUPERADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin only")
    return user


def reseller(user: CurrentUser) -> User:
    if user.platform_role not in (PlatformRole.RESELLER.value, PlatformRole.SUPERADMIN.value):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Reseller access only")
    return user


SuperAdmin = Annotated[User, Depends(superadmin)]
Reseller = Annotated[User, Depends(reseller)]


@dataclass
class Ctx:
    db: Session
    user: User
    business: Business
    role: Role
    membership: Membership
    perms: dict = field(default_factory=dict)
    approval_pin: str | None = None

    @property
    def bid(self) -> str:
        return self.business.id

    def require(self, *roles: Role) -> None:
        if self.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission for this action")

    def can(self, module: str, action: str = "view") -> bool:
        return action in self.perms["modules"].get(module, [])

    def need(self, module: str, action: str = "view") -> None:
        if not self.can(module, action):
            verb = {"view": "view", "create": "create", "edit": "edit", "delete": "delete", "export": "export"}[action]
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Your role cannot {verb} {MODULES[module].split(' (')[0].lower()}")

    def flag(self, name: str) -> bool:
        return name in self.perms["flags"]

    def need_past_edit(self, doc_date: dt.date) -> None:
        """Editing/cancelling an entry dated before today needs the edit_past right or a manager's approval PIN."""
        if doc_date >= dt.date.today() or self.flag("edit_past"):
            return
        pin = (self.approval_pin or "").strip()
        if pin:
            approvers = self.db.scalars(select(Membership).where(
                Membership.business_id == self.bid, Membership.approval_pin_hash.is_not(None),
                Membership.role.in_([Role.OWNER, Role.ADMIN, Role.MANAGER]))).all()
            if any(bcrypt.checkpw(pin.encode(), m.approval_pin_hash.encode()) for m in approvers):
                return
            raise HTTPException(status.HTTP_403_FORBIDDEN, {"message": "Approval PIN is not correct",
                                                            "code": "APPROVAL_REQUIRED"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, {
            "message": "Changing an older entry needs a manager's approval PIN", "code": "APPROVAL_REQUIRED"})


def business_ctx(
    db: DB, user: CurrentUser, x_business_id: Annotated[str | None, Header()] = None,
    x_approval_pin: Annotated[str | None, Header()] = None,
) -> Ctx:
    """Every tenant-scoped endpoint depends on this: it proves the user belongs to the business."""
    if not x_business_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "X-Business-Id header is required")
    m = db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.business_id == x_business_id)
    )
    if not m:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this business")
    return Ctx(db=db, user=user, business=m.business, role=m.role, membership=m,
               perms=effective(m.role, m.permissions), approval_pin=x_approval_pin)


BCtx = Annotated[Ctx, Depends(business_ctx)]

# Company-administration actions (settings, staff, deleting companies)
MANAGERS = (Role.OWNER, Role.ADMIN)
