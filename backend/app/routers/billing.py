"""Subscription plans and payments (Razorpay). The subscription belongs to the account owner."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from ..config import get_settings
from ..deps import DB, BCtx
from ..gst.constants import Role
from ..models import SubscriptionPayment
from ..services import config_store
from ..services import plans as P

router = APIRouter(prefix="/billing", tags=["billing"])


def _plan_out(code: str) -> dict:
    p = P.PLANS[code]
    return dict(code=code, name=p["name"], audience=p["audience"], highlights=p["highlights"],
                monthly=float(p["monthly"]), yearly=float(p["yearly"]),
                monthly_with_gst=float(P.with_gst(p["monthly"])), yearly_with_gst=float(P.with_gst(p["yearly"])),
                **{k: p[k] for k in ("invoices_per_month", "invoices_per_year", "businesses", "users", "godowns",
                                     "einvoice", "gst_json", "gstr2b", "api_quota", "audit_view", "custom_themes",
                                     "watermark", "barcode", "custom_roles", "tally", "backup_mb")})


@router.get("/plans")
def plans():
    """Public — used by the landing / pricing page."""
    return {"plans": [_plan_out(c) for c in P.ORDER], "trial_days": int(config_store.get("trial_days")), "trial_plan": P.TRIAL_PLAN,
            "gst_rate": float(config_store.get("subscription_gst_rate")),
            "addon": {"code": P.ADDON["code"], "name": P.ADDON["name"], "yearly": float(P.ADDON["yearly"]),
                      "yearly_with_gst": float(P.with_gst(P.ADDON["yearly"]))}}


@router.get("/status")
def status(ctx: BCtx):
    account = P.account_of(ctx.db, ctx.bid)
    sub = P.current(ctx.db, account)
    plan = P.plan_of(ctx.db, account)
    ctx.db.commit()
    owner = ctx.role == Role.OWNER
    history = ctx.db.scalars(select(SubscriptionPayment).where(SubscriptionPayment.account_id == account)
                             .order_by(SubscriptionPayment.created_at.desc()).limit(24)).all() if owner else []
    return {
        "plan": {**_plan_out(sub.plan), "businesses": plan["businesses"]}, "status": sub.status,
        "valid_until": sub.valid_until, "extra_businesses": sub.extra_businesses,
        "usage": P.usage(ctx.db, ctx.bid), "is_owner": owner, "payments_live": P.payments_live(),
        "dev_mode": get_settings().is_dev and not P.payments_live(),
        "payments": [dict(id=h.id, plan=h.plan, cycle=h.cycle, amount=float(h.amount), status=h.status,
                          order_id=h.order_id, payment_id=h.payment_id, created_at=h.created_at) for h in history],
    }


class OrderIn(BaseModel):
    plan: Literal["STARTER", "PROFESSIONAL", "ENTERPRISE", "ADDON_BUSINESSES"]
    cycle: Literal["MONTHLY", "YEARLY"] = "YEARLY"


@router.post("/order")
def create_order(data: OrderIn, ctx: BCtx):
    ctx.require(Role.OWNER)
    account = P.account_of(ctx.db, ctx.bid)
    pay = P.create_order(ctx.db, account, data.plan, data.cycle)
    ctx.db.commit()
    return {"order_id": pay.order_id, "amount": float(pay.amount), "amount_paise": int(pay.amount * 100),
            "currency": "INR", "key_id": get_settings().razorpay_key_id, "live": P.payments_live(),
            "business_name": ctx.business.name, "email": ctx.user.email, "phone": ctx.user.phone}


class VerifyIn(BaseModel):
    order_id: str
    payment_id: str | None = None
    signature: str | None = None
    simulate: bool = False


@router.post("/verify")
def verify(data: VerifyIn, ctx: BCtx):
    ctx.require(Role.OWNER)
    account = P.account_of(ctx.db, ctx.bid)
    pay = ctx.db.scalar(select(SubscriptionPayment).where(SubscriptionPayment.order_id == data.order_id,
                                                          SubscriptionPayment.account_id == account))
    if not pay:
        raise HTTPException(404, "Order not found")
    if data.simulate:
        if not (get_settings().is_dev and not P.payments_live() and pay.order_id.startswith("dev_order_")):
            raise HTTPException(400, "Simulated payments are only available in local development")
        payment_id = "dev_pay_" + pay.order_id[-8:]
    else:
        if not P.signature_ok(data.order_id, data.payment_id or "", data.signature or ""):
            pay.status = "FAILED"
            ctx.db.commit()
            raise HTTPException(400, "Payment could not be verified — if money was debited it will be refunded")
        payment_id = data.payment_id
    sub = P.activate(ctx.db, pay, payment_id)
    ctx.db.commit()
    return {"plan": sub.plan, "status": sub.status, "valid_until": sub.valid_until,
            "extra_businesses": sub.extra_businesses}


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request, db: DB):
    """Razorpay webhook (payment.captured / order.paid) — activates even if the browser was closed."""
    body = await request.body()
    if not P.webhook_signature_ok(body, request.headers.get("x-razorpay-signature", "")):
        raise HTTPException(400, "Bad signature")
    event = await request.json()
    entity = (event.get("payload", {}).get("payment", {}) or {}).get("entity", {})
    order_id, payment_id = entity.get("order_id"), entity.get("id")
    if event.get("event") in ("payment.captured", "order.paid") and order_id:
        pay = db.scalar(select(SubscriptionPayment).where(SubscriptionPayment.order_id == order_id))
        if pay:
            P.activate(db, pay, payment_id)
            db.commit()
    return {"ok": True}
