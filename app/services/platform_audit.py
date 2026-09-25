"""Audit entries for platform-level and security events (logins, user management, backups, settings)."""

from fastapi import Request
from sqlalchemy.orm import Session

from ..models import AuditLog, User


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)


def log(db: Session, actor: User | None, action: str, entity: str, summary: str, *, entity_id: str | None = None,
        business_id: str | None = None, request: Request | None = None) -> None:
    """Adds to the session; the caller commits (so the entry is saved together with the change)."""
    db.add(AuditLog(business_id=business_id, user_id=actor.id if actor else None,
                    user_name=actor.name if actor else None, action=action[:12], entity=entity[:40],
                    entity_id=entity_id, summary=summary[:300], ip=client_ip(request)))
