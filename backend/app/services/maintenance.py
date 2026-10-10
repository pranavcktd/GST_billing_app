"""Planned downtime (Admin → Maintenance).

The super admin schedules a window (or starts one now). Before it starts, every screen shows a countdown so people can
save their work. While it runs, everyone except super admins is signed out — every API call answers 503
{"code": "MAINTENANCE"} — and nobody else can sign in; the login page shows the message and when we expect to be back.
It ends when the super admin marks the platform live, or by itself at the end time when auto_end is on.
Business owners can be told by e-mail and WhatsApp (an approved WhatsApp template is needed for that).
"""

import datetime as dt
import threading
import time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..gst.constants import PlatformRole
from ..models import Business, PlatformSetting, User

KEY = "maintenance"
DEFAULT = {"active": False, "starts_at": None, "ends_at": None, "auto_end": True,
           "message": "We are upgrading the platform. Your data is safe — please sign in again after the maintenance.",
           "whatsapp_template": "", "whatsapp_lang": "en", "set_by": None, "notified": None}
_cache: dict = {"at": 0.0, "value": None}
_lock = threading.Lock()


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _parse(v: str | None) -> dt.datetime | None:
    if not v:
        return None
    t = dt.datetime.fromisoformat(v)
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def get(db: Session, fresh: bool = False) -> dict:
    """Saved settings (cached for 5 seconds — this is read on every request)."""
    with _lock:
        if not fresh and _cache["value"] is not None and time.monotonic() - _cache["at"] < 5:
            return _cache["value"]
    row = db.get(PlatformSetting, KEY)
    value = {**DEFAULT, **((row.value or {}) if row else {})}
    with _lock:
        _cache.update(at=time.monotonic(), value=value)
    return value


def clear_cache() -> None:
    with _lock:
        _cache.update(at=0.0, value=None)


def state(db: Session, fresh: bool = False) -> dict:
    """active: maintenance is on right now; scheduled: a window is set for later."""
    s = get(db, fresh)
    start, end = _parse(s["starts_at"]), _parse(s["ends_at"])
    t = now()
    on = bool(s["active"]) and (start is None or start <= t) and not (s["auto_end"] and end is not None and end <= t)
    upcoming = bool(s["active"]) and start is not None and start > t
    return {"active": on, "scheduled": upcoming, "starts_at": s["starts_at"], "ends_at": s["ends_at"],
            "message": s["message"], "auto_end": s["auto_end"]}


def save(db: Session, values: dict, by: str) -> dict:
    s = get(db, fresh=True)
    s = {**s, **{k: v for k, v in values.items() if k in DEFAULT}, "set_by": by}
    row = db.get(PlatformSetting, KEY) or PlatformSetting(key=KEY)
    row.value = s
    db.add(row)
    db.flush()
    clear_cache()
    return s


def blocks(user: User | None) -> bool:
    return not (user and user.platform_role == PlatformRole.SUPERADMIN.value)


def _detail(st: dict) -> dict:
    return {"code": "MAINTENANCE", "message": st["message"], "ends_at": st["ends_at"]}


def guard_request(db: Session, user: User) -> None:
    """Called for every signed-in request (deps.current_user)."""
    st = state(db)
    if st["active"] and blocks(user):
        raise HTTPException(503, _detail(st))


def guard_login(db: Session, user: User) -> None:
    st = state(db, fresh=True)
    if st["active"] and blocks(user):
        raise HTTPException(503, _detail(st))


def owners(db: Session) -> list[User]:
    """Active business owners (the people told about downtime)."""
    ids = select(Business.owner_id).where(Business.owner_id.is_not(None)).distinct()
    return list(db.scalars(select(User).where(User.id.in_(ids), User.is_active.is_(True))).all())


def when_text(st: dict) -> str:
    def fmt(v):
        t = _parse(v)
        return t.astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %I:%M %p IST") if t else None
    start, end = fmt(st.get("starts_at")), fmt(st.get("ends_at"))
    if start and end:
        return f"from {start} to about {end}"
    if start:
        return f"from {start}"
    return f"until about {end}" if end else "for a short while"
