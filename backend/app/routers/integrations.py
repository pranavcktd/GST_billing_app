"""Super admin: Razorpay (subscriptions) settings and the payments received."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..config import get_settings
from ..deps import DB, SuperAdmin
from ..models import SubscriptionPayment, User
from ..services import razorpay_cfg as rz
from ..services.platform_audit import log

router = APIRouter(prefix="/admin", tags=["integrations"])


class KeySet(BaseModel):
    key_id: str | None = Field(None, max_length=60)
    key_secret: str | None = Field(None, max_length=200)
    webhook_secret: str | None = Field(None, max_length=200)
    clear: bool = False


class RazorpayIn(BaseModel):
    mode: Literal["TEST", "LIVE"] | None = None
    TEST: KeySet | None = None
    LIVE: KeySet | None = None


def _payments(db) -> list[dict]:
    rows = db.execute(select(SubscriptionPayment, User.email).join(User, User.id == SubscriptionPayment.account_id)
                      .order_by(SubscriptionPayment.created_at.desc()).limit(50)).all()
    return [dict(id=p.id, account=email, plan=p.plan, cycle=p.cycle, amount=float(p.amount), status=p.status,
                 mode=p.mode or "LIVE", method=p.method, order_id=p.order_id, payment_id=p.payment_id,
                 created_at=p.created_at) for p, email in rows]


def _out(db, request: Request) -> dict:
    base = (get_settings().app_url or str(request.base_url)).rstrip("/")
    return {"settings": rz.public(db), "webhook_url": f"{base}/api/billing/webhook", "payments": _payments(db)}


@router.get("/razorpay")
def get_razorpay(db: DB, admin: SuperAdmin, request: Request):
    return _out(db, request)


@router.put("/razorpay")
def put_razorpay(data: RazorpayIn, db: DB, admin: SuperAdmin, request: Request):
    try:
        rz.save(db, data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    parts = [f"mode {data.mode}"] if data.mode else []
    for m in ("TEST", "LIVE"):
        k = getattr(data, m)
        if k:
            parts.append(f"{m.lower()} keys " + ("removed" if k.clear else "updated"))
    log(db, admin, "CONFIG", "razorpay", "Razorpay settings: " + ", ".join(parts or ["saved"]), request=request)
    db.commit()
    return _out(db, request)


@router.post("/razorpay/test")
def test_razorpay(db: DB, admin: SuperAdmin):
    return rz.test_connection(db)
