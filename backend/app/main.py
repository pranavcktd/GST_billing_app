from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .gst.constants import GST_RATES, UQC
from .gst.states import STATES
from . import audit
from .routers import (
    auth,
    billing,
    businesses,
    einvoice,
    exports,
    godowns,
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

app = FastAPI(title="GST Billing API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


audit.install(app)


@app.exception_handler(IntegrityError)
async def integrity_error(_: Request, exc: IntegrityError):
    msg = "This record conflicts with an existing one"
    if "uq_voucher_number" in str(exc.orig) or "uq_payment_number" in str(exc.orig):
        msg = "This document number is already used — please retry or choose another number"
    return JSONResponse(status_code=409, content={"detail": msg})


for r in (auth, businesses, parties, items, vouchers, payments, reports, uploads, cashbank, loans, expenses,
          utilities, godowns, einvoice, billing, exports):
    app.include_router(r.router, prefix="/api")


@app.get("/api/meta")
def meta():
    return {
        "states": [{"code": c, "name": n} for c, n in STATES.items()],
        "gst_rates": [float(r) for r in GST_RATES],
        "units": [{"code": c, "name": n} for c, n in UQC.items()],
    }


@app.get("/health")
def health():
    return {"ok": True}
