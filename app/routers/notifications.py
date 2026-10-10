"""The bell: a person's alerts (payments, tickets ...). See services/notify.py."""

import datetime as dt

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select, update

from ..deps import DB, CurrentUser
from ..models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def my_notifications(db: DB, user: CurrentUser, limit: int = 30):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.created_at.desc()).limit(min(limit, 100))).all()
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id,
                                                                 Notification.read_at.is_(None))) or 0
    return {"unread": unread, "items": [dict(id=n.id, kind=n.kind, title=n.title, body=n.body, link=n.link,
                                             read=n.read_at is not None, created_at=n.created_at) for n in rows]}


@router.get("/unread")
def unread_count(db: DB, user: CurrentUser):
    return {"unread": db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id,
                                                                          Notification.read_at.is_(None))) or 0}


class ReadIn(BaseModel):
    ids: list[str] | None = None  # None = all


@router.post("/read")
def mark_read(data: ReadIn, db: DB, user: CurrentUser):
    q = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if data.ids is not None:
        q = q.where(Notification.id.in_(data.ids))
    db.execute(q.values(read_at=dt.datetime.now(dt.UTC)))
    db.commit()
    return {"ok": True}
