"""Admin → Transactions: every subscription checkout (paid, failed, cancelled, open), totals, and leads — people who
tried to pay but have not. Super admin, or team members with the 'payments' area."""

import datetime as dt

from fastapi import APIRouter
from sqlalchemy import func, or_, select

from ..deps import DB, platform_area
from ..models import Business, Subscription, SubscriptionPayment, User
from ..services import payment_records as PR

router = APIRouter(prefix="/admin/payments", tags=["admin transactions"])
Finance = platform_area("payments")


def _filtered(status: str | None, mode: str | None, q: str | None, start: dt.date | None, end: dt.date | None):
    stmt = select(SubscriptionPayment, User).join(User, User.id == SubscriptionPayment.account_id)
    if status:
        stmt = stmt.where(SubscriptionPayment.status == status)
    if mode:
        stmt = stmt.where(func.coalesce(SubscriptionPayment.mode, "LIVE") == mode)
    if start:
        stmt = stmt.where(SubscriptionPayment.created_at >= dt.datetime.combine(start, dt.time(), dt.UTC))
    if end:
        stmt = stmt.where(SubscriptionPayment.created_at < dt.datetime.combine(end + dt.timedelta(days=1), dt.time(), dt.UTC))
    if q:
        like = f"%{q.strip()}%"
        owned = select(Business.owner_id).where(or_(Business.name.ilike(like), Business.gstin.ilike(like)))
        stmt = stmt.where(or_(User.name.ilike(like), User.email.ilike(like), User.mobile.ilike(like), User.phone.ilike(like),
                              SubscriptionPayment.order_id.ilike(like), SubscriptionPayment.payment_id.ilike(like),
                              SubscriptionPayment.receipt_no.ilike(like), SubscriptionPayment.account_id.in_(owned)))
    return stmt


@router.get("")
def transactions(db: DB, _: Finance, status: str | None = None, mode: str | None = None, q: str | None = None,
                 start: dt.date | None = None, end: dt.date | None = None, limit: int = 100, offset: int = 0):
    base = _filtered(None, mode, q, start, end).subquery()
    by_status = {s: dict(count=int(n), amount=float(a or 0)) for s, n, a in db.execute(
        select(base.c.status, func.count(), func.sum(base.c.amount)).group_by(base.c.status)).all()}
    rows = db.execute(_filtered(status, mode, q, start, end).order_by(SubscriptionPayment.created_at.desc())
                      .limit(min(limit, 500)).offset(offset)).all()
    total = db.scalar(select(func.count()).select_from(_filtered(status, mode, q, start, end).subquery())) or 0
    return {"total": total, "summary": {s: by_status.get(s, dict(count=0, amount=0.0)) for s in PR.STATUS_LABEL},
            "rows": [PR.row(db, p, u) for p, u in rows]}


@router.get("/leads")
def leads(db: DB, _: Finance, days: int = 90):
    """Accounts whose latest checkout failed, was closed or never finished, with no successful payment after it."""
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=min(days, 730))
    attempts = db.scalars(select(SubscriptionPayment).where(SubscriptionPayment.created_at >= since)
                          .order_by(SubscriptionPayment.created_at)).all()
    latest: dict[str, SubscriptionPayment] = {}
    tries: dict[str, int] = {}
    paid_after: dict[str, dt.datetime] = {}
    for p in attempts:
        if p.status == "PAID":  # an older order paid later also counts: compare by when it was paid
            when = p.paid_at or p.created_at
            paid_after[p.account_id] = max(when, paid_after.get(p.account_id, when))
        else:
            latest[p.account_id] = p
            tries[p.account_id] = tries.get(p.account_id, 0) + 1
    out = []
    for acc, p in latest.items():
        if acc in paid_after and paid_after[acc] >= p.created_at:
            continue
        u, sub = db.get(User, acc), db.get(Subscription, acc)
        if not u:
            continue
        r = PR.row(db, p, u)
        out.append({**r, "attempts": tries[acc], "current_plan": sub.plan if sub else None,
                    "current_status": sub.status if sub else None, "valid_until": sub.valid_until if sub else None,
                    "signed_up": u.created_at, "last_login_at": u.last_login_at})
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return out


@router.get("/{payment_id}")
def transaction(payment_id: str, db: DB, _: Finance):
    from fastapi import HTTPException

    pay = db.get(SubscriptionPayment, payment_id)
    if not pay:
        raise HTTPException(404, "Transaction not found")
    history = db.scalars(select(SubscriptionPayment).where(SubscriptionPayment.account_id == pay.account_id)
                         .order_by(SubscriptionPayment.created_at.desc()).limit(50)).all()
    return {**PR.receipt(db, pay), "account_history": [PR.row(db, h) for h in history]}
