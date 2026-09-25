"""Platform levels: Super Admin (SaaS owner) and Resellers (channel partners).

Neither level can read a tenant's operational data (invoices, parties, books) through the API —
they only see account metadata, plans, usage counts and licences.
"""

import datetime as dt
import secrets
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, text

from ..config import get_settings
from ..deps import DB, Reseller, SuperAdmin
from ..gst.constants import PlatformRole, VoucherType
from ..models import Business, LicenseSale, Subscription, SubscriptionPayment, User, Voucher
from ..security import hash_password
from ..services import plans as P
from ..services import razorpay_cfg as rz
from ..services.platform_audit import log

router = APIRouter(tags=["platform"])
PAID = ["STARTER", "PROFESSIONAL", "ENTERPRISE"]


def _account_row(db, sub: Subscription, owner: User) -> dict:
    businesses = db.scalars(select(Business).where(Business.owner_id == owner.id)).all()
    ids = [b.id for b in businesses]
    month = dt.datetime.now(dt.timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    reseller = db.get(User, sub.reseller_id) if sub.reseller_id else None
    return dict(
        account_id=owner.id, name=owner.name, email=owner.email, phone=owner.phone, active=owner.is_active,
        created_at=owner.created_at, plan=P.current(db, owner.id).plan, status=sub.status,
        valid_until=sub.valid_until, extra_businesses=sub.extra_businesses, feature_flags=sub.feature_flags or {},
        businesses=[dict(id=b.id, name=b.name, gstin=b.gstin) for b in businesses],
        users=len(P.account_user_ids(db, owner.id)),
        invoices_this_month=(db.scalar(select(func.count(Voucher.id)).where(
            Voucher.business_id.in_(ids), Voucher.type == VoucherType.SALE, Voucher.created_at >= month)) or 0) if ids else 0,
        reseller=reseller.name if reseller else None,
    )


# ================================================================ super admin
@router.get("/admin/stats")
def stats(db: DB, _: SuperAdmin):
    subs = db.scalars(select(Subscription)).all()
    by_plan = {c: 0 for c in P.ORDER}
    mrr = Decimal("0")
    trials = 0
    for s in subs:
        plan = P.current(db, s.account_id).plan
        by_plan[plan] += 1
        if s.status == "TRIAL":
            trials += 1
        elif s.status == "ACTIVE" and plan in PAID:
            mrr += P.PLANS[plan]["yearly"] / 12
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    db.commit()
    return dict(
        accounts=len(subs), businesses=db.scalar(select(func.count(Business.id))),
        users=db.scalar(select(func.count(User.id))), trials=trials, by_plan=by_plan,
        mrr=float(mrr.quantize(Decimal("1"))),
        invoices_30d=db.scalar(select(func.count(Voucher.id)).where(Voucher.type == VoucherType.SALE,
                                                                    Voucher.created_at >= since)),
        signups_30d=db.scalar(select(func.count(User.id)).where(User.created_at >= since)),
        revenue_30d=float(db.scalar(select(func.coalesce(func.sum(SubscriptionPayment.amount), 0)).where(
            SubscriptionPayment.status == "PAID", SubscriptionPayment.created_at >= since,
            func.coalesce(SubscriptionPayment.mode, "LIVE") == "LIVE")) or 0),  # test / simulated payments are not revenue
    )


@router.get("/admin/accounts")
def accounts(db: DB, _: SuperAdmin, search: str | None = None, plan: str | None = None, limit: int = 100):
    q = select(Subscription, User).join(User, User.id == Subscription.account_id).order_by(User.created_at.desc())
    if search:
        like = f"%{search}%"
        q = q.where(User.name.ilike(like) | User.email.ilike(like) | User.phone.ilike(like))
    rows = [_account_row(db, s, u) for s, u in db.execute(q.limit(min(limit, 500)))]
    db.commit()
    return [r for r in rows if not plan or r["plan"] == plan]


class SubscriptionAdminIn(BaseModel):
    plan: Literal["FREE", "STARTER", "PROFESSIONAL", "ENTERPRISE"]
    status: Literal["TRIAL", "ACTIVE", "EXPIRED"] = "ACTIVE"
    valid_until: dt.date | None = None
    extra_businesses: int = Field(0, ge=0, le=1000)
    feature_flags: dict | None = None  # any plan key, e.g. {"api_quota": 2000, "report:batch": true}


@router.put("/admin/accounts/{account_id}/subscription")
def set_subscription(account_id: str, data: SubscriptionAdminIn, db: DB, me: SuperAdmin):
    sub = db.get(Subscription, account_id)
    if not sub:
        raise HTTPException(404, "Account not found")
    for k, v in data.model_dump().items():
        setattr(sub, k, v)
    owner = db.get(User, account_id)
    log(db, me, "UPDATE", "subscription", f"{owner.email}: plan {data.plan} {data.status} till {data.valid_until}"
        + (f", flags {data.feature_flags}" if data.feature_flags else ""), entity_id=account_id)
    db.commit()
    return _account_row(db, sub, db.get(User, account_id))


class ResellerIn(BaseModel):
    email: EmailStr
    commission_pct: Decimal = Field(Decimal("20"), ge=0, le=90)


@router.get("/admin/resellers")
def resellers(db: DB, _: SuperAdmin):
    out = []
    for u in db.scalars(select(User).where(User.platform_role == PlatformRole.RESELLER.value).order_by(User.name)):
        sales = db.scalars(select(LicenseSale).where(LicenseSale.reseller_id == u.id)).all()
        out.append(dict(id=u.id, name=u.name, email=u.email, phone=u.phone, commission_pct=float(u.reseller_commission_pct or 0),
                        accounts=db.scalar(select(func.count()).select_from(Subscription).where(Subscription.reseller_id == u.id)),
                        sales=float(sum((s.amount for s in sales), Decimal("0"))),
                        commission_due=float(sum((s.commission for s in sales if s.payout_status == "PENDING"), Decimal("0")))))
    return out


@router.post("/admin/resellers", status_code=201)
def add_reseller(data: ResellerIn, db: DB, me: SuperAdmin):
    u = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not u:
        raise HTTPException(404, "The person must sign up first, then you can make them a reseller")
    if u.platform_role == PlatformRole.SUPERADMIN.value:
        raise HTTPException(400, "This user is a super admin")
    u.platform_role, u.reseller_commission_pct = PlatformRole.RESELLER.value, data.commission_pct
    log(db, me, "UPDATE", "user", f"Made {u.email} a reseller ({data.commission_pct}% commission)", entity_id=u.id)
    db.commit()
    return {"id": u.id}


@router.delete("/admin/resellers/{user_id}", status_code=204)
def remove_reseller(user_id: str, db: DB, me: SuperAdmin):
    u = db.get(User, user_id)
    if u and u.platform_role == PlatformRole.RESELLER.value:
        u.platform_role = None
        log(db, me, "UPDATE", "user", f"Removed reseller access of {u.email}", entity_id=u.id)
        db.commit()


@router.get("/admin/licenses")
def all_licenses(db: DB, _: SuperAdmin, status: str | None = None):
    q = select(LicenseSale).order_by(LicenseSale.created_at.desc()).limit(500)
    if status:
        q = q.where(LicenseSale.payout_status == status)
    return [_license_row(db, x) for x in db.scalars(q)]


@router.post("/admin/licenses/{license_id}/paid")
def mark_paid(license_id: str, db: DB, me: SuperAdmin):
    x = db.get(LicenseSale, license_id)
    if not x:
        raise HTTPException(404, "Not found")
    x.payout_status, x.paid_on = "PAID", dt.date.today()
    log(db, me, "UPDATE", "payout", f"Commission {x.commission} marked paid", entity_id=x.id)
    db.commit()
    return _license_row(db, x)


@router.get("/admin/health")
def health(db: DB, _: SuperAdmin):
    s = get_settings()
    try:
        db.execute(text("select 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    return dict(
        app_env=s.app_env, database=db_ok, database_engine=db.bind.dialect.name,
        einvoice_provider=s.einvoice_provider, gsp_configured=bool(s.gsp_base_url and s.gsp_client_id),
        razorpay_live=(rz.creds(db) or {}).get("mode") == "LIVE", razorpay_webhook=bool(rz.webhook_secrets(db)),
        email_configured=bool(s.smtp_host), cloudinary_configured=bool(s.cloudinary_url),
        superadmins=sorted(s.superadmins),
    )


# ================================================================ resellers
def _license_row(db, x: LicenseSale) -> dict:
    acc = db.get(User, x.account_id)
    res = db.get(User, x.reseller_id)
    return dict(id=x.id, created_at=x.created_at, reseller=res.name if res else None,
                account=acc.name if acc else None, account_email=acc.email if acc else None, plan=x.plan,
                months=x.months, amount=float(x.amount), commission=float(x.commission),
                payout_status=x.payout_status, paid_on=x.paid_on)


def _my_account(db, me: User, account_id: str) -> Subscription:
    sub = db.get(Subscription, account_id)
    if not sub or (sub.reseller_id != me.id and me.platform_role != PlatformRole.SUPERADMIN.value):
        raise HTTPException(404, "Account not found in your portfolio")
    return sub


@router.get("/reseller/accounts")
def my_accounts(db: DB, me: Reseller):
    rows = db.execute(select(Subscription, User).join(User, User.id == Subscription.account_id)
                      .where(Subscription.reseller_id == me.id).order_by(User.created_at.desc())).all()
    out = [_account_row(db, s, u) for s, u in rows]
    for r in out:
        r.pop("feature_flags", None)
    db.commit()
    return out


class NewAccountIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = None


@router.post("/reseller/accounts", status_code=201)
def register_account(data: NewAccountIn, db: DB, me: Reseller):
    """Create a login for a new business owner. They set up their business after first sign-in."""
    if db.scalar(select(User).where(func.lower(User.email) == data.email.lower())):
        raise HTTPException(409, "An account with this email already exists")
    temp = secrets.token_urlsafe(8)
    u = User(name=data.name, email=data.email.lower(), phone=data.phone, password_hash=hash_password(temp))
    db.add(u)
    db.flush()
    u.must_change_password = True
    db.add(Subscription(account_id=u.id, plan="FREE", status="ACTIVE", reseller_id=me.id))
    log(db, me, "CREATE", "user", f"Reseller registered owner {u.email}", entity_id=u.id)
    db.commit()
    return {"account_id": u.id, "email": u.email, "temporary_password": temp}


class LicenseIn(BaseModel):
    account_id: str
    plan: Literal["STARTER", "PROFESSIONAL", "ENTERPRISE"]
    months: Literal[1, 3, 6, 12, 24, 36]


@router.post("/reseller/licenses", status_code=201)
def issue_license(data: LicenseIn, db: DB, me: Reseller):
    sub = _my_account(db, me, data.account_id)
    p = P.PLANS[data.plan]
    years, rest = divmod(data.months, 12)
    base = p["yearly"] * years + p["monthly"] * rest
    amount = P.with_gst(base)
    pct = me.reseller_commission_pct or Decimal("0")
    commission = (base * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    P.current(db, sub.account_id)
    P.extend(sub, data.plan, years * 365 + rest * 30)
    sale = LicenseSale(reseller_id=me.id, account_id=sub.account_id, plan=data.plan, months=data.months,
                       amount=amount, commission=commission)
    db.add(sale)
    log(db, me, "CREATE", "licence", f"Issued {data.plan} x {data.months} months to account {sub.account_id}",
        entity_id=sub.account_id)
    db.commit()
    return _license_row(db, sale)


@router.get("/reseller/licenses")
def my_licenses(db: DB, me: Reseller):
    rows = [_license_row(db, x) for x in db.scalars(select(LicenseSale).where(LicenseSale.reseller_id == me.id)
                                                    .order_by(LicenseSale.created_at.desc()))]
    return {"rows": rows, "commission_pct": float(me.reseller_commission_pct or 0),
            "total_sales": sum(r["amount"] for r in rows),
            "commission_earned": sum(r["commission"] for r in rows),
            "commission_pending": sum(r["commission"] for r in rows if r["payout_status"] == "PENDING")}



# ---------------------------------------------------------------- reseller: manage own customers' logins
class ResellerUserAction(BaseModel):
    action: Literal["reset_email", "reset_temp", "activate", "deactivate"]


@router.post("/reseller/accounts/{account_id}/user")
def reseller_user_action(account_id: str, data: ResellerUserAction, db: DB, me: Reseller, request: Request):
    from .auth import issue_reset

    _my_account(db, me, account_id)
    u = db.get(User, account_id)
    if data.action == "reset_email":
        issue_reset(db, u, request, actor=me)
        out = {"sent": True}
    elif data.action == "reset_temp":
        temp = secrets.token_urlsafe(9)
        u.password_hash, u.must_change_password = hash_password(temp), True
        u.token_version = (u.token_version or 0) + 1
        out = {"temporary_password": temp}
    else:
        u.is_active = data.action == "activate"
        if not u.is_active:
            u.token_version = (u.token_version or 0) + 1
        out = {"active": u.is_active}
    log(db, me, "ACTION", "user", f"Reseller {data.action.replace('_', ' ')} for {u.email}", entity_id=u.id, request=request)
    db.commit()
    return out
