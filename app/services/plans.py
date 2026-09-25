"""Subscription tiers, limits and Razorpay payments.

A subscription belongs to the *account* (the owner user) and covers every business that
account owns. Prices exclude 18% GST. Edit PLANS / REPORT_MIN_PLAN to change the offer.
Super admins can override any plan key per account via Subscription.feature_flags.
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
from ..gst.constants import Role, VoucherType
from ..gst.fy import fy_range
from . import config_store
from . import razorpay_cfg as rz
from ..models import Backup, Business, Godown, Membership, Subscription, SubscriptionPayment, Voucher

TRIAL_PLAN = "ENTERPRISE"
ADDON_CODE = "ADDON_BUSINESSES"
# trial length and GST on fees come from the admin configuration (config_store)
ORDER = ["FREE", "STARTER", "PROFESSIONAL", "ENTERPRISE"]

PLANS: dict[str, dict] = {
    "FREE": dict(
        name="Free", audience="Micro-traders, self-employed", monthly=Decimal("0"), yearly=Decimal("0"),
        invoices_per_month=30, invoices_per_year=300, businesses=1, users=1, godowns=1,
        einvoice=None, gst_json=False, gstr2b=False, api_quota=0, audit_view=False, custom_themes=False,
        watermark=True, barcode=False, custom_roles=False, tally=False, backup_mb=100,
        highlights=["30 invoices / month", "1 business, owner only", "B2B & B2C GST invoices",
                    "Day book & sales report", "App watermark on bills"]),
    "STARTER": dict(
        name="Starter", audience="Small retail & service shops", monthly=Decimal("199"), yearly=Decimal("1999"),
        invoices_per_month=250, invoices_per_year=None, businesses=1, users=2, godowns=1,
        einvoice="JSON", gst_json=True, gstr2b=False, api_quota=0, audit_view=False, custom_themes=False,
        watermark=False, barcode=False, custom_roles=False, tally=False, backup_mb=1024,
        highlights=["250 invoices / month", "2 users (owner + billing)", "GSTR-1 JSON, e-invoice & e-way bill JSON",
                    "P&L, balance sheet, inventory reports", "No watermark", "1 GB cloud backup"]),
    "PROFESSIONAL": dict(
        name="Professional", audience="Growing MSMEs, multi-branch", monthly=Decimal("499"), yearly=Decimal("4999"),
        invoices_per_month=None, invoices_per_year=None, businesses=3, users=5, godowns=3,
        einvoice="API", gst_json=True, gstr2b=True, api_quota=500, audit_view=True, custom_themes=True,
        watermark=False, barcode=False, custom_roles=False, tally=True, backup_mb=5120,
        highlights=["Unlimited invoices", "Up to 3 businesses, 5 users", "Direct e-invoice & e-way bill (500/month)",
                    "GSTR-2B matching", "Audit trail & ledgers", "Custom invoice themes & logo", "Tally export"]),
    "ENTERPRISE": dict(
        name="Enterprise", audience="Wholesalers, manufacturers, CAs", monthly=Decimal("999"), yearly=Decimal("9999"),
        invoices_per_month=None, invoices_per_year=None, businesses=10, users=None, godowns=None,
        einvoice="API", gst_json=True, gstr2b=True, api_quota=5000, audit_view=True, custom_themes=True,
        watermark=False, barcode=True, custom_roles=True, tally=True, backup_mb=20480,
        highlights=["Unlimited invoices & users", "10 businesses (+ add-on packs)", "High-volume e-invoice API",
                    "Custom roles & permissions", "Barcode labels, custom thermal", "Batch & serial reconciliation"]),
}
ADDON = dict(code=ADDON_CODE, name="5 extra businesses", businesses=5, yearly=Decimal("2999"))

# lowest plan that includes each report (anything not listed needs STARTER)
REPORT_MIN_PLAN = {
    **{s: "FREE" for s in ("sale", "purchase", "day-book", "payments", "party-statement", "all-parties", "low-stock")},
    **{s: "PROFESSIONAL" for s in ("party-ledger", "gstr2", "gst-transactions", "gstr9", "bill-profit", "party-pnl",
                                   "item-pnl", "capital", "gstr4", "loan-statement", "loans", "tds-payable", "tds-receivable",
                                   "form-27eq")},
    **{s: "ENTERPRISE" for s in ("batch", "serial", "godown-stock", "pending-order-items")},
}
FEATURE_LABEL = {
    "gst_json": "GST JSON exports", "gstr2b": "GSTR-2B matching", "audit_view": "The audit trail",
    "custom_themes": "Custom invoice themes & logo", "barcode": "Barcode labels", "custom_roles": "Custom roles",
    "tally": "Tally export", "einvoice": "e-Invoice & e-Way bill",
}


class UpgradeRequired(HTTPException):
    def __init__(self, message: str, plan: str):
        super().__init__(402, {"message": message, "code": "UPGRADE", "plan": plan,
                               "plan_name": PLANS[plan]["name"]})


def with_gst(amount: Decimal) -> Decimal:
    rate = config_store.get("subscription_gst_rate")
    return (amount * (100 + rate) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rank(plan: str) -> int:
    return ORDER.index(plan)


def _lowest(pred) -> str:
    return next((c for c in ORDER if pred(PLANS[c])), ORDER[-1])


# ---------------------------------------------------------------- account & subscription
def account_of(db: Session, business_id: str) -> str | None:
    biz = db.get(Business, business_id)
    if biz and biz.owner_id:
        return biz.owner_id
    return db.scalar(select(Membership.user_id).where(Membership.business_id == business_id,
                                                      Membership.role == Role.OWNER).limit(1))


def start_trial(db: Session, account_id: str) -> Subscription:
    sub = db.get(Subscription, account_id)
    if sub is None:
        sub = Subscription(account_id=account_id, plan=TRIAL_PLAN, status="TRIAL",
                           valid_until=dt.date.today() + dt.timedelta(days=int(config_store.get("trial_days"))))
        db.add(sub)
        db.flush()
    return sub


def current(db: Session, account_id: str) -> Subscription:
    """The subscription, downgraded to FREE once it lapses."""
    sub = db.get(Subscription, account_id)
    if sub is None:
        sub = Subscription(account_id=account_id, plan="FREE", status="ACTIVE")
        db.add(sub)
        db.flush()
    if sub.plan != "FREE" and sub.valid_until and sub.valid_until < dt.date.today():
        sub.status, sub.plan = "EXPIRED", "FREE"
        db.flush()
    return sub


def plan_of(db: Session, account_id: str | None) -> dict:
    if not account_id:
        return {**PLANS["FREE"], "code": "FREE"}
    sub = current(db, account_id)
    p = {**PLANS[sub.plan], "code": sub.plan, **(sub.feature_flags or {})}
    if p["businesses"] is not None:
        p["businesses"] += sub.extra_businesses or 0
    return p


def business_plan(db: Session, business_id: str) -> dict:
    return plan_of(db, account_of(db, business_id))


def require_feature(db: Session, business_id: str, key: str) -> None:
    if not business_plan(db, business_id).get(key):
        need = _lowest(lambda p: p.get(key))
        raise UpgradeRequired(f"{FEATURE_LABEL.get(key, key)} is available from the {PLANS[need]['name']} plan", need)


def require_einvoice(db: Session, business_id: str, level: str) -> None:
    """level: JSON (download files) or API (direct generation)."""
    have = business_plan(db, business_id).get("einvoice")
    ok = have == "API" or (have == "JSON" and level == "JSON")
    if not ok:
        need = _lowest(lambda p: p["einvoice"] == "API" or (p["einvoice"] == "JSON" and level == "JSON"))
        what = "Direct e-invoice / e-way bill generation" if level == "API" else "e-Invoice & e-way bill JSON"
        raise UpgradeRequired(f"{what} is available from the {PLANS[need]['name']} plan", need)


def check_api_quota(db: Session, business_id: str) -> None:
    acc = account_of(db, business_id)
    cap = business_plan(db, business_id)["api_quota"]
    start = dt.datetime.now(dt.timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ids = _account_business_ids(db, acc)
    used = (db.scalar(select(func.count(Voucher.id)).where(Voucher.business_id.in_(ids), Voucher.ack_date >= start)) or 0) \
        + (db.scalar(select(func.count(Voucher.id)).where(Voucher.business_id.in_(ids), Voucher.ewb_date >= start)) or 0)
    if used >= cap:
        raise UpgradeRequired(f"Monthly e-invoice / e-way bill API quota of {cap} is used up", "ENTERPRISE")


def _account_business_ids(db: Session, account_id: str | None) -> list[str]:
    if not account_id:
        return []
    return list(db.scalars(select(Business.id).where(Business.owner_id == account_id)))


def _invoice_count(db: Session, ids: list[str], since: dt.datetime) -> int:
    return db.scalar(select(func.count(Voucher.id)).where(
        Voucher.business_id.in_(ids), Voucher.type == VoucherType.SALE, Voucher.created_at >= since)) or 0


def check_invoice_limit(db: Session, business_id: str) -> None:
    acc = account_of(db, business_id)
    plan = plan_of(db, acc)
    ids = _account_business_ids(db, acc) or [business_id]
    now = dt.datetime.now(dt.timezone.utc)
    if plan["invoices_per_month"] is not None:
        used = _invoice_count(db, ids, now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
        if used >= plan["invoices_per_month"]:
            nxt = _lowest(lambda p: p["invoices_per_month"] is None or p["invoices_per_month"] > plan["invoices_per_month"])
            raise UpgradeRequired(f"You've used all {plan['invoices_per_month']} invoices of this month on the "
                                  f"{plan['name']} plan. Upgrade to keep billing.", nxt)
    if plan.get("invoices_per_year") is not None:
        fy_start = fy_range(now.date())[0]
        used = _invoice_count(db, ids, dt.datetime.combine(fy_start, dt.time.min, dt.timezone.utc))
        if used >= plan["invoices_per_year"]:
            raise UpgradeRequired(f"The {plan['name']} plan allows {plan['invoices_per_year']} invoices per year.",
                                  "STARTER")


def check_business_limit(db: Session, account_id: str) -> None:
    plan = plan_of(db, account_id)
    owned = len(_account_business_ids(db, account_id))
    if plan["businesses"] is not None and owned >= plan["businesses"]:
        nxt = _lowest(lambda p: p["businesses"] is not None and p["businesses"] > plan["businesses"]) \
            if plan["code"] != "ENTERPRISE" else "ENTERPRISE"
        msg = (f"Your {plan['name']} plan allows {plan['businesses']} business(es)."
               + (" Buy an add-on pack for 5 more." if plan["code"] == "ENTERPRISE" else ""))
        raise UpgradeRequired(msg, nxt)


def account_user_ids(db: Session, account_id: str | None) -> set[str]:
    ids = _account_business_ids(db, account_id)
    return set(db.scalars(select(Membership.user_id).where(Membership.business_id.in_(ids)))) if ids else set()


def check_user_limit(db: Session, business_id: str, new_user_id: str | None = None) -> None:
    acc = account_of(db, business_id)
    plan = plan_of(db, acc)
    users = account_user_ids(db, acc)
    if new_user_id in users:
        return  # already counted (works in another business of the same account)
    if plan["users"] is not None and len(users) >= plan["users"]:
        nxt = _lowest(lambda p: p["users"] is None or p["users"] > plan["users"])
        raise UpgradeRequired(f"Your {plan['name']} plan allows {plan['users']} user(s) in total", nxt)


def check_godown_limit(db: Session, business_id: str) -> None:
    plan = business_plan(db, business_id)
    used = db.scalar(select(func.count(Godown.id)).where(Godown.business_id == business_id,
                                                         Godown.is_active.is_(True))) or 0
    if plan["godowns"] is not None and used >= plan["godowns"]:
        raise UpgradeRequired(f"Your {plan['name']} plan allows {plan['godowns']} godown(s)",
                              _lowest(lambda p: p["godowns"] is None or p["godowns"] > plan["godowns"]))


def check_report(db: Session, business_id: str, slug: str) -> None:
    need = REPORT_MIN_PLAN.get(slug, "STARTER")
    plan = business_plan(db, business_id)
    if rank(plan["code"]) < rank(need) and not plan.get(f"report:{slug}"):
        raise UpgradeRequired(f"This report is available from the {PLANS[need]['name']} plan", need)


def backup_bytes(db: Session, account_id: str | None) -> int:
    ids = _account_business_ids(db, account_id)
    return int(db.scalar(select(func.coalesce(func.sum(Backup.size), 0)).where(Backup.business_id.in_(ids))) or 0) if ids else 0


def check_backup_quota(db: Session, business_id: str, extra_bytes: int) -> None:
    acc = account_of(db, business_id)
    plan = plan_of(db, acc)
    if backup_bytes(db, acc) + extra_bytes > plan["backup_mb"] * 1024 * 1024:
        raise UpgradeRequired(f"Cloud backup storage of {plan['backup_mb']} MB is full — delete old backups or upgrade",
                              _lowest(lambda p: p["backup_mb"] > plan["backup_mb"]))


def usage(db: Session, business_id: str) -> dict:
    acc = account_of(db, business_id)
    ids = _account_business_ids(db, acc) or [business_id]
    now = dt.datetime.now(dt.timezone.utc)
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return dict(
        invoices_this_month=_invoice_count(db, ids, month),
        invoices_this_year=_invoice_count(db, ids, dt.datetime.combine(fy_range(now.date())[0], dt.time.min, dt.timezone.utc)),
        businesses=len(ids), users=len(account_user_ids(db, acc)),
        godowns=db.scalar(select(func.count(Godown.id)).where(Godown.business_id == business_id,
                                                              Godown.is_active.is_(True))) or 0,
        api_calls_this_month=(db.scalar(select(func.count(Voucher.id)).where(Voucher.business_id.in_(ids),
                                                                              Voucher.ack_date >= month)) or 0)
        + (db.scalar(select(func.count(Voucher.id)).where(Voucher.business_id.in_(ids), Voucher.ewb_date >= month)) or 0),
        backup_mb=round(backup_bytes(db, acc) / 1024 / 1024, 1),
    )


# ---------------------------------------------------------------- payments
def price(plan: str, cycle: str) -> Decimal:
    if plan == ADDON["code"]:
        return with_gst(ADDON["yearly"])
    if plan not in PLANS or plan == "FREE":
        raise HTTPException(400, "Choose a paid plan")
    if cycle not in ("MONTHLY", "YEARLY"):
        raise HTTPException(400, "Invalid billing cycle")
    return with_gst(PLANS[plan]["monthly" if cycle == "MONTHLY" else "yearly"])


def payments_live(db: Session) -> bool:
    """Razorpay keys are configured (Test or Live) — real checkout instead of the dev simulation."""
    return rz.creds(db) is not None


def create_order(db: Session, account_id: str, plan: str, cycle: str) -> SubscriptionPayment:
    if plan == ADDON["code"] and current(db, account_id).plan != "ENTERPRISE":
        raise HTTPException(400, "Business add-on packs are for the Enterprise plan")
    amount = price(plan, cycle)
    c = rz.creds(db)
    if c:
        try:
            r = rz.request("POST", "/orders", c, json={
                "amount": int(amount * 100), "currency": "INR", "receipt": uuid.uuid4().hex[:20],
                "notes": {"account_id": account_id, "plan": plan, "cycle": cycle}})
        except httpx.HTTPError:
            raise HTTPException(502, "Could not reach Razorpay — please try again") from None
        if r.status_code >= 300:
            raise HTTPException(502, "Could not start the payment with Razorpay — please try again")
        order_id, mode = r.json()["id"], c["mode"]
    elif get_settings().is_dev:
        order_id, mode = "dev_order_" + uuid.uuid4().hex[:16], "DEV"
    else:
        raise HTTPException(503, "Online payments are not configured")
    pay = SubscriptionPayment(account_id=account_id, plan=plan, cycle=cycle, amount=amount, order_id=order_id,
                              status="CREATED", mode=mode)
    db.add(pay)
    db.flush()
    return pay


def signature_ok(db: Session, order_id: str, payment_id: str, signature: str) -> bool:
    c = rz.creds(db)
    secret = (c or {}).get("key_secret") or ""
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return bool(secret) and hmac.compare_digest(expected, signature or "")


def webhook_signature_ok(db: Session, body: bytes, signature: str) -> bool:
    for secret in rz.webhook_secrets(db):
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, signature or ""):
            return True
    return False


def confirm_with_razorpay(db: Session, pay: SubscriptionPayment, payment_id: str) -> None:
    """Server-side check after the checkout: the payment belongs to this order, the amount matches and
    the money is captured (captures it when the Razorpay account uses manual capture)."""
    c = rz.creds(db)
    if not c:
        raise HTTPException(503, "Online payments are not configured")
    try:
        r = rz.request("GET", f"/payments/{payment_id}", c)
    except httpx.HTTPError:
        raise HTTPException(502, "Could not confirm the payment with Razorpay — it will be applied once confirmed, "
                                 "or contact support") from None
    if r.status_code != 200:
        raise HTTPException(400, "Payment not found at Razorpay")
    p = r.json()
    paise = int(pay.amount * 100)
    if p.get("order_id") != pay.order_id or int(p.get("amount") or 0) != paise:
        raise HTTPException(400, "Payment does not match this order")
    status = p.get("status")
    if status == "authorized":
        cap = rz.request("POST", f"/payments/{payment_id}/capture", c, json={"amount": paise, "currency": "INR"})
        if cap.status_code >= 300:
            raise HTTPException(502, "Payment authorised but could not be captured — please contact support")
    elif status != "captured":
        raise HTTPException(400, f"Payment is {status} — not completed")
    pay.method = (p.get("method") or "")[:20] or None


def extend(sub: Subscription, plan: str, days: int) -> None:
    """Activate / extend a plan. Remaining paid time carries over."""
    today = dt.date.today()
    start = sub.valid_until if (sub.status == "ACTIVE" and sub.valid_until and sub.valid_until > today) else today
    sub.plan, sub.status, sub.valid_until = plan, "ACTIVE", start + dt.timedelta(days=days)


def activate(db: Session, pay: SubscriptionPayment, payment_id: str) -> Subscription:
    """Mark the payment paid and apply it. Safe to call twice for the same payment."""
    sub = current(db, pay.account_id)
    if pay.status == "PAID":
        return sub
    pay.status, pay.payment_id = "PAID", payment_id
    if pay.plan == ADDON["code"]:
        sub.extra_businesses = (sub.extra_businesses or 0) + ADDON["businesses"]
    else:
        extend(sub, pay.plan, 365 if pay.cycle == "YEARLY" else 30)
    db.flush()
    return sub
