"""Subscription transactions: what was bought, receipts, failures and the alerts to the owner and the platform team.

Every checkout is recorded (services/plans.create_order) — paid, failed, closed without paying (CANCELLED) or still
open (CREATED). Paid ones get a receipt number. The account owner and the platform team (super admin + team members
with the 'payments' area) get an alert under the bell and by e-mail when a payment succeeds or fails.
"""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Business, SubscriptionPayment, User
from . import config_store, notify
from . import plans as P

STATUS_LABEL = {"CREATED": "Not completed", "PAID": "Successful", "FAILED": "Failed", "CANCELLED": "Cancelled"}


def cycle_label(cycle: str) -> str:
    if cycle.startswith("YEARS_"):
        return f"{cycle[6:]} years"
    return {"MONTHLY": "1 month", "YEARLY": "1 year"}.get(cycle, cycle.lower())


def describe(pay: SubscriptionPayment) -> str:
    n = P.credit_pack(pay.plan)
    if n is not None:
        return f"{n} API credits (prepaid pack)"
    if pay.plan == P.ADDON["code"]:
        return f"Add-on: {P.ADDON['name']} (1 year)"
    name = P.PLANS.get(pay.plan, {}).get("name", pay.plan)
    return f"{name} plan — {cycle_label(pay.cycle)}"


def split(pay: SubscriptionPayment) -> tuple[Decimal, Decimal, Decimal]:
    """(taxable value, GST, GST %) inside the amount paid."""
    rate = Decimal(str(pay.gst_rate if pay.gst_rate is not None else config_store.get("subscription_gst_rate")))
    base = (Decimal(pay.amount) * 100 / (100 + rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return base, Decimal(pay.amount) - base, rate


def next_receipt_no(db: Session) -> str:
    today = dt.date.today()
    fy = today.year if today.month >= 4 else today.year - 1
    prefix = f"SR{str(fy)[2:]}{str(fy + 1)[2:]}-"
    last = db.scalar(select(func.max(SubscriptionPayment.receipt_no)).where(SubscriptionPayment.receipt_no.like(prefix + "%")))
    n = int(last[len(prefix):]) + 1 if last else 1
    return f"{prefix}{n:05d}"


def _business(db: Session, pay: SubscriptionPayment) -> Business | None:
    if pay.business_id:
        b = db.get(Business, pay.business_id)
        if b:
            return b
    return db.scalar(select(Business).where(Business.owner_id == pay.account_id).order_by(Business.created_at).limit(1))


def row(db: Session, pay: SubscriptionPayment, owner: User | None = None) -> dict:
    owner = owner or db.get(User, pay.account_id)
    biz = _business(db, pay)
    base, gst, rate = split(pay)
    return dict(id=pay.id, created_at=pay.created_at, paid_at=pay.paid_at, item=describe(pay), plan=pay.plan, cycle=pay.cycle,
                amount=float(pay.amount), taxable=float(base), gst=float(gst), gst_rate=float(rate),
                status=pay.status, status_label=STATUS_LABEL.get(pay.status, pay.status), mode=pay.mode or "LIVE",
                method=pay.method, order_id=pay.order_id, payment_id=pay.payment_id, receipt_no=pay.receipt_no,
                error_code=pay.error_code, error_reason=pay.error_reason,
                account_id=pay.account_id, owner_name=owner.name if owner else None, owner_email=owner.email if owner else None,
                owner_phone=(owner.mobile or owner.phone) if owner else None,
                business_id=biz.id if biz else None, business_name=biz.name if biz else None)


def receipt(db: Session, pay: SubscriptionPayment) -> dict:
    """Everything a receipt shows: seller (our company), buyer (the business), item, tax and payment details."""
    biz = _business(db, pay)
    company = config_store.effective()["company"]
    seller_gstin = company.get("gstin") or ""
    buyer_gstin = (biz.gstin or "") if biz else ""
    intra = bool(seller_gstin) and bool(buyer_gstin) and seller_gstin[:2] == buyer_gstin[:2]
    address = None
    if biz:
        address = ", ".join(str(x) for x in (getattr(biz, k, None) for k in ("address", "city", "state", "pincode")) if x) or None
    return {**row(db, pay), "seller": {**company, "brand": config_store.app_name()},
            "buyer": dict(name=biz.name if biz else None, gstin=buyer_gstin or None, address=address),
            "tax_split": "CGST_SGST" if intra else "IGST"}


def _amount(pay: SubscriptionPayment) -> str:
    return f"₹{Decimal(pay.amount):,.2f}"


def _owner_alert(db: Session, pay: SubscriptionPayment, ok: bool) -> None:
    owner = db.get(User, pay.account_id)
    if not owner:
        return
    if ok:
        notify.users(db, [owner], "PAYMENT_OK", f"Payment received — {_amount(pay)}",
                     f"Thank you! We received {_amount(pay)} for {describe(pay)}.\nReceipt {pay.receipt_no}"
                     f"{' · payment id ' + pay.payment_id if pay.payment_id else ''}.",
                     link=f"/receipt/{pay.id}")
    else:
        notify.users(db, [owner], "PAYMENT_FAILED", f"Payment failed — {_amount(pay)}",
                     f"Your payment of {_amount(pay)} for {describe(pay)} did not go through"
                     f"{': ' + pay.error_reason if pay.error_reason else ''}.\n"
                     "If money was debited, your bank returns it automatically (usually within 5–7 working days). "
                     "You can try again from Subscription.", link="/billing")


def _team_alert(db: Session, pay: SubscriptionPayment, kind: str) -> None:
    owner = db.get(User, pay.account_id)
    name = owner.name if owner else pay.account_id
    who = f"{owner.name} ({owner.email})" if owner else pay.account_id
    test = "" if (pay.mode or "LIVE") == "LIVE" else f" [{pay.mode}]"
    reason = f" — {pay.error_reason}" if pay.error_reason else ""
    title, body = {
        "PAYMENT_OK": (f"Payment received{test}: {_amount(pay)} — {name}",
                       f"{who} paid {_amount(pay)} for {describe(pay)}. Receipt {pay.receipt_no}."),
        "PAYMENT_FAILED": (f"Payment failed{test}: {_amount(pay)} — {name}",
                           f"{who} tried to pay {_amount(pay)} for {describe(pay)}{reason}. A lead worth a call."),
        "PAYMENT_CANCELLED": (f"Checkout closed{test}: {_amount(pay)} — {name}",
                              f"{who} opened the payment for {describe(pay)} but closed it without paying."),
    }[kind]
    notify.team(db, "payments", kind, title, body, link=f"/admin?tab=Transactions&id={pay.id}",
                email=kind != "PAYMENT_CANCELLED")


def paid(db: Session, pay: SubscriptionPayment) -> None:
    """Called once when a payment turns PAID (plans.activate)."""
    pay.paid_at = pay.paid_at or dt.datetime.now(dt.UTC)
    pay.error_code = pay.error_reason = None
    if not pay.receipt_no:
        pay.receipt_no = next_receipt_no(db)
    _owner_alert(db, pay, True)
    _team_alert(db, pay, "PAYMENT_OK")


def failed(db: Session, pay: SubscriptionPayment, reason: str | None = None, code: str | None = None,
           payment_id: str | None = None, cancelled: bool = False) -> bool:
    """Record a failed (or closed) checkout and alert — once per change. A paid order is never marked failed.
    Returns whether anything changed."""
    status = "CANCELLED" if cancelled else "FAILED"
    if pay.status == "PAID" or (pay.status == "FAILED" and cancelled):  # closing the window after a failure keeps the failure
        return False
    if pay.status == status and (not payment_id or payment_id == pay.payment_id):
        return False
    pay.status = status
    pay.payment_id = payment_id or pay.payment_id
    pay.error_code = code[:60] if code else None
    pay.error_reason = (reason or ("Checkout closed without paying" if cancelled else ""))[:300] or None
    if not cancelled:
        _owner_alert(db, pay, False)
    _team_alert(db, pay, "PAYMENT_CANCELLED" if cancelled else "PAYMENT_FAILED")
    return True
