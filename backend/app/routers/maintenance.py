"""Admin → Maintenance: schedule / start planned downtime, tell business owners, mark the platform live again.
Super admin only. See services/maintenance.py."""

import datetime as dt
import logging
import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..deps import DB, SuperAdmin
from ..services import maintenance as MT
from ..services import mailer, notify
from ..services import whatsapp as W
from ..services.platform_audit import log

router = APIRouter(prefix="/admin/maintenance", tags=["maintenance"])
SYNC = False  # tests send notices inline instead of on a background thread
_log = logging.getLogger("gst_billing")


def _view(db) -> dict:
    s = MT.get(db, fresh=True)
    ws = W.settings(db)
    return {**MT.state(db, fresh=True), "whatsapp_template": s["whatsapp_template"], "whatsapp_lang": s["whatsapp_lang"],
            "set_by": s["set_by"], "notified": s["notified"], "owners": len(MT.owners(db)),
            "email_ready": mailer.system_smtp(db) is not None, "whatsapp_ready": W.ready(ws) or W.sandbox(ws)}


@router.get("")
def status(db: DB, _: SuperAdmin):
    return _view(db)


class WindowIn(BaseModel):
    starts_at: dt.datetime | None = None  # None = now
    ends_at: dt.datetime | None = None    # expected end (shown as a countdown)
    auto_end: bool = True                 # go live by itself at ends_at
    message: str = Field(min_length=5, max_length=500)
    whatsapp_template: str = Field("", max_length=100)
    whatsapp_lang: str = Field("en", max_length=10)
    notify_email: bool = True
    notify_whatsapp: bool = False


def _aware(t: dt.datetime | None) -> dt.datetime | None:
    return None if t is None else (t if t.tzinfo else t.replace(tzinfo=dt.UTC))


@router.put("")
def start(data: WindowIn, db: DB, me: SuperAdmin, request: Request):
    """Schedule a window (starts_at in the future) or start it now."""
    start_at, end_at = _aware(data.starts_at), _aware(data.ends_at)
    if end_at and end_at <= (start_at or MT.now()):
        raise HTTPException(422, "The end must be after the start")
    if data.notify_whatsapp and not data.whatsapp_template.strip():
        raise HTTPException(422, "Enter the approved WhatsApp template name to send the notice on WhatsApp")
    MT.save(db, {"active": True, "starts_at": start_at.isoformat() if start_at else MT.now().isoformat(),
                 "ends_at": end_at.isoformat() if end_at else None, "auto_end": data.auto_end, "message": data.message.strip(),
                 "whatsapp_template": data.whatsapp_template.strip(), "whatsapp_lang": data.whatsapp_lang or "en"}, me.email)
    st = MT.state(db, fresh=True)
    log(db, me, "CONFIG", "maintenance", f"Maintenance {'scheduled' if st['scheduled'] else 'started'} {MT.when_text(st)}", request=request)
    db.commit()
    if data.notify_email or data.notify_whatsapp:
        _send_notice(db, "start", data.notify_email, data.notify_whatsapp, me.email)
    return _view(db)


class EndIn(BaseModel):
    notify_email: bool = False
    notify_whatsapp: bool = False


@router.post("/end")
def end(data: EndIn, db: DB, me: SuperAdmin, request: Request):
    """Mark the platform live (or cancel a scheduled window)."""
    MT.save(db, {"active": False}, me.email)
    log(db, me, "CONFIG", "maintenance", "Platform marked live — maintenance ended", request=request)
    db.commit()
    if data.notify_email or data.notify_whatsapp:
        _send_notice(db, "end", data.notify_email, data.notify_whatsapp, me.email)
    return _view(db)


def _send_notice(db, kind: str, email: bool, whatsapp: bool, by: str) -> None:
    st = MT.state(db, fresh=True)
    s = MT.get(db, fresh=True)
    MT.save(db, {"notified": {"kind": kind, "at": MT.now().isoformat(), "email": email, "whatsapp": whatsapp,
                              "recipients": len(MT.owners(db))}}, by)
    db.commit()
    args = (db.get_bind(), kind, email, whatsapp, st, s["whatsapp_template"], s["whatsapp_lang"])
    if SYNC:
        _broadcast(*args)
    else:
        threading.Thread(target=_broadcast, args=args, daemon=True, name="maintenance-notice").start()


def _broadcast(bind, kind: str, email: bool, whatsapp: bool, st: dict, template: str, lang: str) -> None:
    """Tell every business owner. Runs on its own database session; one failure never stops the rest."""
    from ..services import config_store

    db = Session(bind=bind)
    try:
        app = config_store.app_name()
        cfg = mailer.system_smtp(db)
        ws = W.settings(db)
        when = MT.when_text(st)
        if kind == "start":
            subject = f"{app}: scheduled maintenance {when}"
            body = f"{st['message']}\nThe service will be unavailable {when}. Please save your work before it starts — you will be signed out."
        else:
            subject, body = f"{app} is back online", "Maintenance is complete and the service is available again. Thank you for your patience."
        for u in MT.owners(db):
            if email and cfg and u.email:
                try:
                    mailer.send(cfg, [u.email], subject, notify.email_html(subject, body, "/login", "Open " + app))
                except Exception as e:  # noqa: BLE001
                    _log.warning("maintenance e-mail to %s failed: %s", u.email, getattr(e, "detail", e))
            phone = W.normalize(u.mobile or u.phone)
            if whatsapp and template and phone and (W.ready(ws) or W.sandbox(ws)):
                try:
                    comps = [{"type": "body", "parameters": [{"type": "text", "text": t} for t in (st["message"], when)]}]
                    W._send(db, ws, phone, template, lang, comps, kind="NOTICE", account_id=u.id)
                    db.commit()
                except Exception as e:  # noqa: BLE001
                    db.rollback()
                    _log.warning("maintenance WhatsApp to %s failed: %s", phone, getattr(e, "detail", e))
    finally:
        db.close()
