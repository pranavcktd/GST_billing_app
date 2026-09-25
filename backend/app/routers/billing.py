"""Subscription plans and payments (Razorpay)."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from ..config import get_settings
from ..deps import DB, BCtx
from ..gst.constants import Role
from ..models import SubscriptionPayment
from ..services import plans as P

router = APIRouter(prefix="/billing", tags=["billing"])


def _plan_out(code: str) -> dict:
    p = P.PLANS[code]
    return dict(code=code, name=p["name"], tagline=p["tagline"], monthly=float(p["monthly"]),
                yearly=float(p["yearly"]), monthly_with_gst=float(P.with_gst(p["monthly"])),
                yearly_with_gst=float(P.with_gst(p["yearly"])), invoices_per_month=p["invoices_per_month"],
                users=p["users"], godowns=p["godowns"], einvoice=p["einvoice"], ewaybill=p["ewaybill"], tally=p["tally"])


@router.get("/plans")
def plans():
    """Public — used by the landing page."""
    return {"plans": [_plan_out(c) for c in P.ORDER], "trial_days": P.TRIAL_DAYS, "trial_plan": P.TRIAL_PLAN,
            "gst_rate": float(P.GST_RATE)}


@router.get("/status")
def status(ctx: BCtx):
    sub = P.current(ctx.db, ctx.bid)
    ctx.db.commit()
    history = ctx.db.scalars(select(SubscriptionPayment).where(SubscriptionPayment.business_id == ctx.bid)
                             .order_by(SubscriptionPayment.created_at.desc()).limit(24)).all()
    return {
        "plan": _plan_out(sub.plan), "status": sub.status, "valid_until": sub.valid_until,
        "usage": P.usage(ctx.db, ctx.bid), "payments_live": P.payments_live(),
        "dev_mode": get_settings().is_dev and not P.payments_live(),
        "payments": [dict(id=h.id, plan=h.plan, cycle=h.cycle, amount=float(h.amount), status=h.status,
                          order_id=h.order_id, payment_id=h.payment_id, created_at=h.created_at) for h in history],
    }


class OrderIn(BaseModel):
    plan: Literal["GROWTH", "BUSINESS"]
    cycle: Literal["MONTHLY", "YEARLY"]


@router.post("/order")
def create_order(data: OrderIn, ctx: BCtx):
    ctx.require(Role.OWNER, Role.ADMIN)
    pay = P.create_order(ctx.db, ctx.bid, data.plan, data.cycle)
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
    ctx.require(Role.OWNER, Role.ADMIN)
    pay = ctx.db.scalar(select(SubscriptionPayment).where(SubscriptionPayment.order_id == data.order_id,
                                                          SubscriptionPayment.business_id == ctx.bid))
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
    return {"plan": sub.plan, "status": sub.status, "valid_until": sub.valid_until}


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request, db: DB):
    """Razorpay webhook (event: payment.captured / order.paid) — activates even if the browser closed."""
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
