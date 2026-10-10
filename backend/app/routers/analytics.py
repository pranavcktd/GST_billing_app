"""First-party analytics: website visits, plan interest and which modules people use (services/engagement.py).

Public: POST /track/visit, /track/event. Signed in: POST /track/usage. Admin → Analytics (analytics area) reads them.
"""

import datetime as dt
import re
import uuid
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import distinct, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..deps import DB, CurrentUser, SuperAdmin, platform_area
from ..models import Business, Membership, ModuleUsage, SiteEvent, SiteVisit, Subscription, SubscriptionPayment, User
from ..security import decode_token_full
from ..services import engagement as E
from ..services.platform_audit import log

router = APIRouter(tags=["analytics"])
Analyst = platform_area("analytics")
BOTS = re.compile(r"bot|crawl|spider|slurp|preview|headless|lighthouse|monitor|curl|python|wget", re.I)
VISITOR = r"^[A-Za-z0-9-]{8,40}$"


def _device(ua: str) -> str:
    if re.search(r"ipad|tablet", ua, re.I):
        return "tablet"
    return "mobile" if re.search(r"mobi|android|iphone", ua, re.I) else "desktop"


def _skip(db, ua: str | None, dnt: str | None) -> bool:
    s = E.get(db)["analytics"]
    return not s["enabled"] or not ua or bool(BOTS.search(ua)) or (s["respect_dnt"] and dnt == "1")


def _user_id(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    decoded = decode_token_full(auth[7:]) if auth.lower().startswith("bearer ") else None
    return decoded[0] if decoded else None


class VisitIn(BaseModel):
    visitor: str = Field(pattern=VISITOR)
    path: str = Field(max_length=500)
    referrer: str | None = Field(None, max_length=500)
    utm_source: str | None = Field(None, max_length=200)
    utm_campaign: str | None = Field(None, max_length=200)


@router.post("/track/visit", status_code=204)
def visit(data: VisitIn, db: DB, request: Request, user_agent: Annotated[str | None, Header()] = None,
          dnt: Annotated[str | None, Header()] = None):
    if _skip(db, user_agent, dnt):
        return
    ref = urlparse(data.referrer or "").hostname
    own = urlparse(str(request.base_url)).hostname
    db.add(SiteVisit(day=dt.date.today(), visitor=data.visitor, user_id=_user_id(request), path=data.path.split("?")[0][:200],
                     referrer=(ref or None) if ref != own else None, utm_source=(data.utm_source or "")[:60] or None,
                     utm_campaign=(data.utm_campaign or "")[:60] or None, device=_device(user_agent or "")))
    db.commit()


class EventIn(BaseModel):
    visitor: str | None = Field(None, pattern=VISITOR)
    kind: Literal["PRICING_VIEW", "PLAN_CLICK", "CYCLE", "SIGNUP_START"]
    plan: str | None = Field(None, max_length=30)
    cycle: str | None = Field(None, max_length=12)
    page: str | None = Field(None, max_length=200)


@router.post("/track/event", status_code=204)
def event(data: EventIn, db: DB, request: Request, user_agent: Annotated[str | None, Header()] = None,
          dnt: Annotated[str | None, Header()] = None):
    uid = _user_id(request)
    if not uid and _skip(db, user_agent, dnt):  # signed-in users' plan interest is product use, kept like module use
        return
    if not uid and not data.visitor:
        return
    db.add(SiteEvent(day=dt.date.today(), visitor=data.visitor, user_id=uid, kind=data.kind, plan=data.plan,
                     cycle=data.cycle, page=(data.page or "").split("?")[0][:200] or None))
    db.commit()


class UsageIn(BaseModel):
    module: str = Field(min_length=2, max_length=80)


@router.post("/track/usage", status_code=204)
def usage(data: UsageIn, db: DB, user: CurrentUser, x_business_id: Annotated[str | None, Header()] = None):
    """A signed-in person opened a module. One row per person, business, module and day."""
    if not E.get(db)["analytics"]["enabled"]:
        return
    bid = x_business_id if x_business_id and db.scalar(select(Membership.id).where(
        Membership.user_id == user.id, Membership.business_id == x_business_id)) else ""
    now = dt.datetime.now(dt.UTC)
    stmt = pg_insert(ModuleUsage).values(id=uuid.uuid4().hex, day=dt.date.today(), user_id=user.id,
                                         business_id=bid, module=data.module.strip(), views=1, last_at=now)
    db.execute(stmt.on_conflict_do_update(constraint="uq_module_usage",
                                          set_={"views": ModuleUsage.views + 1, "last_at": now}))
    db.commit()


# ================================================================ admin
def _since(days: int) -> dt.date:
    return dt.date.today() - dt.timedelta(days=max(1, min(days, 730)) - 1)


@router.get("/admin/analytics")
def overview(db: DB, _: Analyst, days: int = 30):
    since = _since(days)
    V, Ev, U = SiteVisit, SiteEvent, ModuleUsage
    per_day = {d: dict(day=d, visitors=int(v), views=int(n)) for d, v, n in db.execute(
        select(V.day, func.count(distinct(V.visitor)), func.count()).where(V.day >= since).group_by(V.day)).all()}
    active_day = dict(db.execute(select(U.day, func.count(distinct(U.user_id))).where(U.day >= since).group_by(U.day)).all())
    series = []
    d = since
    while d <= dt.date.today():
        series.append({**per_day.get(d, dict(day=d, visitors=0, views=0)), "active_users": int(active_day.get(d, 0))})
        d += dt.timedelta(days=1)

    def top(col, limit=10):
        return [dict(key=k or "(direct)", visitors=int(v), views=int(n)) for k, v, n in db.execute(
            select(col, func.count(distinct(V.visitor)), func.count()).where(V.day >= since).group_by(col)
            .order_by(func.count(distinct(V.visitor)).desc()).limit(limit)).all()]

    unique = db.scalar(select(func.count(distinct(V.visitor))).where(V.day >= since)) or 0
    start = dt.datetime.combine(since, dt.time(), dt.UTC)
    staff = User.platform_role.is_(None)
    signups = db.scalar(select(func.count(User.id)).where(User.created_at >= start, staff)) or 0
    with_business = db.scalar(select(func.count(distinct(Business.owner_id))).join(User, User.id == Business.owner_id)
                              .where(User.created_at >= start)) or 0
    paid = db.scalar(select(func.count(distinct(SubscriptionPayment.account_id))).where(
        SubscriptionPayment.status == "PAID", SubscriptionPayment.created_at >= start,
        func.coalesce(SubscriptionPayment.mode, "LIVE") == "LIVE")) or 0

    plans: dict[str, dict] = {}
    for kind, plan, cycle, who, n, people in db.execute(
            select(Ev.kind, Ev.plan, Ev.cycle, Ev.user_id.is_not(None), func.count(),
                   func.count(distinct(func.coalesce(Ev.user_id, Ev.visitor)))).where(Ev.day >= since)
            .group_by(Ev.kind, Ev.plan, Ev.cycle, Ev.user_id.is_not(None))).all():
        if kind != "PLAN_CLICK" or not plan:
            continue
        p = plans.setdefault(plan, dict(plan=plan, clicks=0, visitors=0, users=0, cycles={}))
        p["clicks"] += n
        p["users" if who else "visitors"] += people
        p["cycles"][cycle or "-"] = p["cycles"].get(cycle or "-", 0) + n
    pricing_views = dict(db.execute(select(Ev.user_id.is_not(None), func.count(distinct(func.coalesce(Ev.user_id, Ev.visitor))))
                                    .where(Ev.day >= since, Ev.kind == "PRICING_VIEW").group_by(Ev.user_id.is_not(None))).all())

    modules = [dict(module=m, views=int(v), users=int(u), businesses=int(b)) for m, v, u, b in db.execute(
        select(U.module, func.sum(U.views), func.count(distinct(U.user_id)), func.count(distinct(U.business_id)))
        .where(U.day >= since).group_by(U.module).order_by(func.count(distinct(U.user_id)).desc(), func.sum(U.views).desc())).all()]

    def active(n: int) -> int:
        return db.scalar(select(func.count(distinct(U.user_id))).where(U.day > dt.date.today() - dt.timedelta(days=n))) or 0

    return {"days": days, "since": since, "series": series,
            "totals": dict(visitors=unique, views=sum(x["views"] for x in series), signups=signups, set_up_business=with_business,
                           paid_accounts=paid, dau=active(1), wau=active(7), mau=active(30)),
            "pages": top(V.path), "referrers": top(V.referrer), "campaigns": top(V.utm_source), "devices": top(V.device, 3),
            "plans": sorted(plans.values(), key=lambda p: -p["clicks"]),
            "pricing_views": dict(visitors=int(pricing_views.get(False, 0)), users=int(pricing_views.get(True, 0))),
            "modules": modules, "settings": E.admin_view(db)["analytics"]}


@router.get("/admin/analytics/users")
def users(db: DB, _: Analyst, days: int = 30, q: str | None = None, module: str | None = None, limit: int = 200):
    """Who uses what: each person's activity and favourite modules in the period."""
    since = _since(days)
    U = ModuleUsage
    stmt = select(U.user_id, func.sum(U.views), func.count(distinct(U.day)), func.max(U.last_at)).where(U.day >= since)
    if module:
        stmt = stmt.where(U.module == module)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(U.user_id.in_(select(User.id).where((User.name.ilike(like)) | (User.email.ilike(like)))))
    rows = db.execute(stmt.group_by(U.user_id).order_by(func.sum(U.views).desc()).limit(min(limit, 500))).all()
    ids = [r[0] for r in rows]
    people = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids))).all()}
    subs = {s.account_id: s for s in db.scalars(select(Subscription).where(Subscription.account_id.in_(ids))).all()}
    tops: dict[str, list] = {}
    for uid, m, v in db.execute(select(U.user_id, U.module, func.sum(U.views)).where(U.day >= since, U.user_id.in_(ids))
                                .group_by(U.user_id, U.module).order_by(func.sum(U.views).desc())).all():
        tops.setdefault(uid, []).append(dict(module=m, views=int(v)))
    biz_names: dict[str, list] = {}
    for uid, name in db.execute(select(Membership.user_id, Business.name).join(Business, Business.id == Membership.business_id)
                                .where(Membership.user_id.in_(ids))).all():
        biz_names.setdefault(uid, []).append(name)
    out = []
    for uid, views, active_days, last in rows:
        u = people.get(uid)
        if not u:
            continue
        s = subs.get(uid)
        out.append(dict(user_id=uid, name=u.name, email=u.email, businesses=biz_names.get(uid, []),
                        plan=s.plan if s else None, plan_status=s.status if s else None, views=int(views),
                        active_days=int(active_days), last_at=last, modules=tops.get(uid, [])[:6], module_count=len(tops.get(uid, []))))
    return out


@router.get("/admin/analytics/users/{user_id}")
def user_detail(user_id: str, db: DB, _: Analyst, days: int = 90):
    since = _since(days)
    U = ModuleUsage
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    names = dict(db.execute(select(Business.id, Business.name).where(Business.id.in_(
        select(U.business_id).where(U.user_id == user_id)))).all())
    by_module = [dict(module=m, business=names.get(b, "—") if b else "—", views=int(v), days=int(dd), last_at=last)
                 for m, b, v, dd, last in db.execute(
                     select(U.module, U.business_id, func.sum(U.views), func.count(distinct(U.day)), func.max(U.last_at))
                     .where(U.user_id == user_id, U.day >= since).group_by(U.module, U.business_id)
                     .order_by(func.sum(U.views).desc())).all()]
    per_day = [dict(day=d, views=int(v)) for d, v in db.execute(
        select(U.day, func.sum(U.views)).where(U.user_id == user_id, U.day >= since).group_by(U.day).order_by(U.day)).all()]
    plan_interest = [dict(kind=k, plan=p, cycle=c, at=a) for k, p, c, a in db.execute(
        select(SiteEvent.kind, SiteEvent.plan, SiteEvent.cycle, SiteEvent.created_at).where(SiteEvent.user_id == user_id)
        .order_by(SiteEvent.created_at.desc()).limit(20)).all()]
    return {"user": dict(id=u.id, name=u.name, email=u.email, created_at=u.created_at, last_login_at=u.last_login_at),
            "modules": by_module, "per_day": per_day, "plan_interest": plan_interest}


# ================================================================ settings
class AnalyticsIn(BaseModel):
    enabled: bool = True
    respect_dnt: bool = True
    keep_days: int = Field(400, ge=30, le=1500)


@router.put("/admin/analytics/settings")
def save_analytics(data: AnalyticsIn, db: DB, me: SuperAdmin, request: Request):
    E.save(db, analytics=data.model_dump())
    log(db, me, "CONFIG", "analytics", f"Analytics {'on' if data.enabled else 'off'}; keep {data.keep_days} days", request=request)
    db.commit()
    return E.admin_view(db)


class ChatIn(BaseModel):
    enabled: bool = False
    property_id: str = Field("", max_length=40)
    widget_id: str = Field("default", max_length=40)
    show_on: Literal["WEBSITE", "APP", "BOTH"] = "BOTH"
    pass_user: bool = True
    secure_key: str | None = Field(None, max_length=200)  # None = keep, "" = remove


@router.get("/admin/live-chat")
def get_chat(db: DB, _: SuperAdmin):
    return E.admin_view(db)["live_chat"]


@router.put("/admin/live-chat")
def save_chat(data: ChatIn, db: DB, me: SuperAdmin, request: Request):
    values = data.model_dump(exclude={"secure_key"} if data.secure_key is None else set())
    try:
        E.save(db, live_chat=values)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    log(db, me, "CONFIG", "live chat", f"Live chat {'on' if data.enabled else 'off'} (tawk.to {data.property_id or '-'}, {data.show_on.lower()})",
        request=request)
    db.commit()
    return E.admin_view(db)["live_chat"]


@router.get("/track/chat-identity")
def chat_identity(db: DB, user: CurrentUser):
    """Name, e-mail and (with secure mode) the hash tawk.to needs to show the agent who is chatting."""
    lc = E.get(db)["live_chat"]
    if not lc["pass_user"]:
        return {"name": None, "email": None, "hash": None}
    return {"name": user.name, "email": user.email, "hash": E.chat_hash(db, user.email)}


def purge_old(db) -> int:
    """Drop analytics older than keep_days (called by the daily job)."""
    keep = int(E.get(db)["analytics"]["keep_days"])
    cutoff = dt.date.today() - dt.timedelta(days=keep)
    n = 0
    for model in (SiteVisit, SiteEvent, ModuleUsage):
        n += db.query(model).filter(model.day < cutoff).delete(synchronize_session=False)
    db.commit()
    return n

