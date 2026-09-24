"""Request dependencies: authenticated user and the active business (tenant)."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .gst.constants import Role
from .models import Business, Membership, User
from .security import decode_token

DB = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


def current_user(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User:
    user_id = decode_token(creds.credentials) if creds else None
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


@dataclass
class Ctx:
    db: Session
    user: User
    business: Business
    role: Role

    @property
    def bid(self) -> str:
        return self.business.id

    def require(self, *roles: Role) -> None:
        if self.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission for this action")


def business_ctx(
    db: DB, user: CurrentUser, x_business_id: Annotated[str | None, Header()] = None
) -> Ctx:
    """Every tenant-scoped endpoint depends on this: it proves the user belongs to the business."""
    if not x_business_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "X-Business-Id header is required")
    m = db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.business_id == x_business_id)
    )
    if not m:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this business")
    return Ctx(db=db, user=user, business=m.business, role=m.role)


BCtx = Annotated[Ctx, Depends(business_ctx)]

# Roles allowed to create/edit transactions and masters (accountants are read-only).
WRITERS = (Role.OWNER, Role.ADMIN, Role.STAFF)
MANAGERS = (Role.OWNER, Role.ADMIN)
