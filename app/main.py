import logging
import os
import threading

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from . import audit
from .services import config_store
from .routers import (
    auth,
    billing,
    businesses,
    compliance,
    integrations,
    search,
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
    payments,
    reports,
    uploads,
    utilities,
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
    """Daily automatic full platform backup (checked hourly)."""
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


for r in (auth, businesses, compliance, gstin, integrations, search, parties, items, vouchers, payments, reports, uploads, cashbank, loans, expenses,
          utilities, godowns, einvoice, billing, exports, platform, admin, smtp, sharing):
    app.include_router(r.router, prefix="/api")


@app.get("/api/meta")
def meta():
    cfg = config_store.public()
    return {
        "states": [{"code": c, "name": n} for c, n in cfg["states"].items()],
        "gst_rates": cfg["gst_rates"],
        "units": [{"code": c, "name": n} for c, n in cfg["uqc"].items()],
        "config": cfg,
    }


@app.get("/health")
def health():
    return {"ok": True}
