"""Subscription plans, limits and Razorpay payments.

Prices are exclusive of 18% GST. Change PLANS to change pricing or limits.
"""

import datetime as dt
import hashlib
import hmac
import uuid
from decimal import ROUND_HALF_UP, Decimal

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..gst.constants import VoucherType
from ..models import Godown, Membership, Subscription, SubscriptionPayment, Voucher

TRIAL_PLAN = "BUSINESS"
TRIAL_DAYS = 14
GST_RATE = Decimal("18")

PLANS: dict[str, dict] = {
    "FREE": dict(name="Starter", monthly=Decimal("0"), yearly=Decimal("0"), invoices_per_month=50, users=1,
                 godowns=1, einvoice=False, ewaybill=False, tally=False,
                 tagline="For new and very small shops"),
    "GROWTH": dict(name="Growth", monthly=Decimal("399"), yearly=Decimal("3999"), invoices_per_month=None, users=3,
                   godowns=2, einvoice=True, ewaybill=True, tally=True,
                   tagline="Unlimited billing for growing businesses"),
    "BUSINESS": dict(name="Business", monthly=Decimal("699"), yearly=Decimal("6999"), invoices_per_month=None,
                     users=10, godowns=None, einvoice=True, ewaybill=True, tally=True,
                     tagline="Multi-location, larger teams, e-invoicing"),
}
ORDER = ["FREE", "GROWTH", "BUSINESS"]
FEATURE_LABEL = {"einvoice": "e-Invoicing", "ewaybill": "e-Way Bill", "tally": "Tally export"}


def with_gst(amount: Decimal) -> Decimal:
    return (amount * (100 + GST_RATE) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def start_trial(db: Session, business_id: str) -> Subscription:
    sub = Subscription(business_id=business_id, plan=TRIAL_PLAN, status="TRIAL",
                       valid_until=dt.date.today() + dt.timedelta(days=TRIAL_DAYS))
    db.add(sub)
    return sub


def current(db: Session, business_id: str) -> Subscription:
    """The subscription, downgraded to FREE once it lapses."""
    sub = db.get(Subscription, business_id)
    if sub is None:
        sub = Subscription(business_id=business_id, plan="FREE", status="ACTIVE", valid_until=None)
        db.add(sub)
        db.flush()
    if sub.plan != "FREE" and sub.valid_until and sub.valid_until < dt.date.today():
        sub.status, sub.plan = "EXPIRED", "FREE"
        db.flush()
    return sub


def limits(db: Session, business_id: str) -> dict:
    return PLANS[current(db, business_id).plan]


def _upgrade_hint(feature_ok) -> str:
    for code in ORDER:
        if feature_ok(PLANS[code]):
            return PLANS[code]["name"]
    return PLANS[ORDER[-1]]["name"]


def require_feature(db: Session, business_id: str, feature: str) -> None:
    if not limits(db, business_id)[feature]:
        raise HTTPException(402, f"{FEATURE_LABEL.get(feature, feature)} is available on the "
                                 f"{_upgrade_hint(lambda p: p[feature])} plan — upgrade under Settings → Subscription")


def check_invoice_limit(db: Session, business_id: str) -> None:
    cap = limits(db, business_id)["invoices_per_month"]
    if cap is None:
        return
    start = dt.datetime.now(dt.timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = db.scalar(select(func.count(Voucher.id)).where(
        Voucher.business_id == business_id, Voucher.type == VoucherType.SALE, Voucher.created_at >= start)) or 0
    if used >= cap:
        raise HTTPException(402, f"Your plan allows {cap} sale invoices per month — upgrade for unlimited invoices")


def check_user_limit(db: Session, business_id: str) -> None:
    cap = limits(db, business_id)["users"]
    used = db.scalar(select(func.count(Membership.id)).where(Membership.business_id == business_id)) or 0
    if cap is not None and used >= cap:
        raise HTTPException(402, f"Your plan allows {cap} user(s) — upgrade to add more people")


def check_godown_limit(db: Session, business_id: str) -> None:
    cap = limits(db, business_id)["godowns"]
    used = db.scalar(select(func.count(Godown.id)).where(Godown.business_id == business_id,
                                                         Godown.is_active.is_(True))) or 0
    if cap is not None and used >= cap:
        raise HTTPException(402, f"Your plan allows {cap} godown(s) — upgrade for more locations")


def usage(db: Session, business_id: str) -> dict:
    start = dt.datetime.now(dt.timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return dict(
        invoices_this_month=db.scalar(select(func.count(Voucher.id)).where(
            Voucher.business_id == business_id, Voucher.type == VoucherType.SALE, Voucher.created_at >= start)) or 0,
        users=db.scalar(select(func.count(Membership.id)).where(Membership.business_id == business_id)) or 0,
        godowns=db.scalar(select(func.count(Godown.id)).where(Godown.business_id == business_id,
                                                              Godown.is_active.is_(True))) or 0,
    )


# ---------------------------------------------------------------- payments
def price(plan: str, cycle: str) -> Decimal:
    if plan not in PLANS or plan == "FREE":
        raise HTTPException(400, "Choose a paid plan")
    if cycle not in ("MONTHLY", "YEARLY"):
        raise HTTPException(400, "Invalid billing cycle")
    return with_gst(PLANS[plan]["monthly" if cycle == "MONTHLY" else "yearly"])


def payments_live() -> bool:
    s = get_settings()
    return bool(s.razorpay_key_id and s.razorpay_key_secret)


def create_order(db: Session, business_id: str, plan: str, cycle: str) -> SubscriptionPayment:
    amount = price(plan, cycle)
    s = get_settings()
    if payments_live():
        r = httpx.post("https://api.razorpay.com/v1/orders", auth=(s.razorpay_key_id, s.razorpay_key_secret),
                       json={"amount": int(amount * 100), "currency": "INR", "receipt": uuid.uuid4().hex[:20],
                             "notes": {"business_id": business_id, "plan": plan, "cycle": cycle}}, timeout=20)
        if r.status_code >= 300:
            raise HTTPException(502, "Could not start the payment with Razorpay — please try again")
        order_id = r.json()["id"]
    elif s.is_dev:
        order_id = "dev_order_" + uuid.uuid4().hex[:16]
    else:
        raise HTTPException(503, "Online payments are not configured")
    pay = SubscriptionPayment(business_id=business_id, plan=plan, cycle=cycle, amount=amount, order_id=order_id,
                              status="CREATED")
    db.add(pay)
    db.flush()
    return pay


def signature_ok(order_id: str, payment_id: str, signature: str) -> bool:
    secret = get_settings().razorpay_key_secret or ""
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return bool(secret) and hmac.compare_digest(expected, signature or "")


def webhook_signature_ok(body: bytes, signature: str) -> bool:
    secret = get_settings().razorpay_webhook_secret or ""
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return bool(secret) and hmac.compare_digest(expected, signature or "")


def activate(db: Session, pay: SubscriptionPayment, payment_id: str) -> Subscription:
    """Mark the payment paid and extend the plan. Safe to call twice for the same payment."""
    sub = current(db, pay.business_id)
    if pay.status == "PAID":
        return sub
    pay.status, pay.payment_id = "PAID", payment_id
    days = 365 if pay.cycle == "YEARLY" else 30
    today = dt.date.today()
    # remaining paid time carries over when renewing or upgrading
    start = sub.valid_until if (sub.status == "ACTIVE" and sub.valid_until and sub.valid_until > today) else today
    sub.plan, sub.status, sub.valid_until = pay.plan, "ACTIVE", start + dt.timedelta(days=days)
    db.flush()
    return sub
