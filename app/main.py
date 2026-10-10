import logging
import os
import threading

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from . import audit
from .deps import DB
from .services import config_store, engagement
from .services import edit_log  # noqa: F401 — registers the audit-trail hook and triggers
from .services import notify  # noqa: F401 — registers the send-alert-e-mails-after-commit hook
from .services import signup as signup_service
from .services import maintenance as maintenance_service
from .services import whatsapp as wa_service
from .routers import (
    admin_payments,
    analytics,
    maintenance,
    auth,
    helpdesk,
    support,
    team,
    notifications,
    billing,
    businesses,
    compliance,
    compliance_calendar,
    documents,
    dsc,
    integrations,
    mail,
    manufacturing,
    practice,
    privacy,
    price_lists,
    recurring,
    reminders,
    search,
    site,
    staff,
    gstin,
    einvoice,
    exports,
    admin,
    godowns,
    platform,
    sharing,
    smtp,
    cashbank,
    expenses,
    items,
    loans,
    parties,
    payroll,
    payments,
    reports,
    uploads,
    utilities,
    whatsapp,
    vouchers,
)

app = FastAPI(title="SmartHisab API", version="0.1.0", dependencies=[Depends(config_store.refresh_dep)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


audit.install(app)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


def _backup_loop():
    """Hourly: automatic full backup (daily), recurring invoices, payment reminders (daily), old analytics removed."""
    import time

    from .db import SessionLocal
    from .services.backup import maybe_auto_full_backup

    while True:
        time.sleep(3600)
        db = SessionLocal()
        try:
            maybe_auto_full_backup(db)
        except Exception:  # noqa: BLE001
            logging.getLogger("gst_billing").exception("automatic full backup failed")
            db.rollback()
        try:
            from .services.recurring import run_all as run_recurring
            run_recurring(db)
        except Exception:  # noqa: BLE001
            logging.getLogger("gst_billing").exception("recurring invoices failed")
            db.rollback()
        try:
            from .services.reminders import maybe_run_daily
            maybe_run_daily(db)
        except Exception:  # noqa: BLE001
            logging.getLogger("gst_billing").exception("payment reminders failed")
            db.rollback()
        try:
            from .routers.analytics import purge_old
            purge_old(db)  # analytics older than the kept period
        except Exception:  # noqa: BLE001
            logging.getLogger("gst_billing").exception("analytics clean-up failed")
        finally:
            db.close()


@app.on_event("startup")
def _start_scheduler():
    if os.environ.get("DISABLE_SCHEDULER") != "1":
        threading.Thread(target=_backup_loop, daemon=True, name="auto-backup").start()


@app.exception_handler(IntegrityError)
async def integrity_error(_: Request, exc: IntegrityError):
    msg = "This record conflicts with an existing one"
    if "uq_voucher_number" in str(exc.orig) or "uq_payment_number" in str(exc.orig):
        msg = "This document number is already used — please retry or choose another number"
    return JSONResponse(status_code=409, content={"detail": msg})


for r in (admin_payments, analytics, maintenance, notifications, helpdesk, support, team, auth, payroll, businesses, compliance, compliance_calendar, documents, dsc, gstin, integrations, mail, manufacturing, practice, privacy, price_lists, recurring, reminders, search, site, staff, parties, items, vouchers, payments, reports, uploads, cashbank, loans, expenses,
          utilities, godowns, einvoice, billing, exports, platform, admin, smtp, sharing, whatsapp):
    app.include_router(r.router, prefix="/api")
app.include_router(expenses.admin_router, prefix="/api")


@app.get("/api/meta")
def meta(db: DB):
    cfg = config_store.public()
    return {
        "states": [{"code": c, "name": n} for c, n in cfg["states"].items()],
        "gst_rates": cfg["gst_rates"],
        "units": [{"code": c, "name": n} for c, n in cfg["uqc"].items()],
        "config": cfg,
        "whatsapp": wa_service.flags(db),
        "signup": signup_service.flags(db),
        **engagement.public(db),  # analytics on/off, live chat (tawk.to) widget
        "maintenance": maintenance_service.state(db),  # planned downtime: login page notice and countdown
    }


@app.get("/health")
def health():
    return {"ok": True}
