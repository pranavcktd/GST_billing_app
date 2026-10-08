"""WhatsApp Business API: admin settings, delivery webhook, sending invoices and payment reminders (see services/whatsapp.py).

Plans include WhatsApp messages each month (`whatsapp_quota`, whole account); beyond them each message uses API credits.
Sign-in codes are free for businesses (the platform pays for them).
"""

import datetime as dt

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..deps import DB, BCtx, SuperAdmin
from ..models import Party, ReminderLog, Voucher, WhatsAppMessage
from ..permissions import voucher_module
from ..services import invoice_pdf
from ..services import plans as P
from ..services import reminders as R
from ..services import whatsapp as W
from ..services.platform_audit import log
from .auth import frontend_url

router = APIRouter(tags=["whatsapp"])
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


# ================================================================ super admin
class SettingsIn(BaseModel):
    enabled: bool | None = None
    sandbox: bool | None = None
    provider: str | None = Field(None, pattern="^(SPRINGEDGE|META|OTHER)$")
    base_url: str | None = Field(None, max_length=200, pattern=r"^(https://\S+)?$")
    api_version: str | None = Field(None, max_length=20)
    auth_header: str | None = Field(None, max_length=40, pattern=r"^[A-Za-z0-9-]+$")
    phone_number_id: str | None = Field(None, max_length=40)
    api_key: str | None = Field(None, max_length=500)
    clear_api_key: bool = False
    new_webhook_key: bool = False
    login_enabled: bool | None = None
    signup_verify: bool | None = None
    otp_template: str | None = Field(None, max_length=80)
    otp_lang: str | None = Field(None, max_length=10)
    otp_button: bool | None = None
    invoice_template: str | None = Field(None, max_length=80)
    invoice_lang: str | None = Field(None, max_length=10)
    reminder_template: str | None = Field(None, max_length=80)
    reminder_lang: str | None = Field(None, max_length=10)


def _admin_view(db, request: Request) -> dict:
    s = W.public_settings(db)
    month = dt.datetime.now(dt.UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    counts = dict(db.execute(select(WhatsAppMessage.kind, func.count(WhatsAppMessage.id))
                             .where(WhatsAppMessage.created_at >= month, WhatsAppMessage.status.not_in(["FAILED", "SANDBOX"]))
                             .group_by(WhatsAppMessage.kind)).all())
    recent = db.scalars(select(WhatsAppMessage).order_by(WhatsAppMessage.created_at.desc()).limit(30)).all()
    hook = f"{frontend_url(request)}/api/whatsapp/webhook?key={s['webhook_key']}" if s.get("webhook_key") else None
    return {"settings": s, "webhook_url": hook, "this_month": counts,
            "recent": [dict(at=m.created_at, kind=m.kind, to=W.masked(m.to), template=m.template, status=m.status, error=m.error,
                            ref=m.ref, preview=m.preview) for m in recent]}


@router.get("/admin/whatsapp")
def get_settings(db: DB, admin: SuperAdmin, request: Request):
    return _admin_view(db, request)


@router.put("/admin/whatsapp")
def put_settings(data: SettingsIn, db: DB, admin: SuperAdmin, request: Request):
    W.save_settings(db, data.model_dump())
    changed = [k for k, v in data.model_dump().items() if v not in (None, False)]
    log(db, admin, "CONFIG", "whatsapp", "WhatsApp API settings: " + ", ".join(changed), request=request)
    db.commit()
    return _admin_view(db, request)


class TestIn(BaseModel):
    phone: str = Field(max_length=20)


@router.post("/admin/whatsapp/test")
def test_message(data: TestIn, db: DB, admin: SuperAdmin):
    """Sends the sign-in code template with a test code, to check the key, number id and template."""
    to = W.normalize(data.phone)
    if not to:
        raise HTTPException(422, "Enter a 10-digit Indian mobile number")
    try:
        m = W.send_otp(db, to, "123456")
    except W.ProviderError as e:
        raise HTTPException(502, e.message) from e
    db.commit()
    return {"sent": True, "to": W.masked(to), "message_id": m.wamid, "sandbox": m.status == "SANDBOX"}


# ================================================================ provider webhook (delivery status)
@router.get("/whatsapp/webhook")
def webhook_verify(db: DB, request: Request):
    """Meta-style subscription check: echo hub.challenge when hub.verify_token is our webhook key."""
    q = request.query_params
    if q.get("hub.verify_token") and q.get("hub.verify_token") == W.settings(db).get("webhook_key"):
        return Response(q.get("hub.challenge") or "", media_type="text/plain")
    raise HTTPException(403, "Invalid verify token")


@router.post("/whatsapp/webhook")
async def webhook(request: Request, db: DB, key: str | None = None):
    if not key or key != W.settings(db).get("webhook_key"):
        raise HTTPException(403, "Invalid key")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "Expected JSON") from None
    return {"updated": W.update_status(db, payload if isinstance(payload, dict) else {})}


# ================================================================ businesses
def _month_start() -> dt.datetime:
    return dt.datetime.now(IST).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def usage(db, business_id: str) -> dict:
    account = P.account_of(db, business_id)
    quota = int(P.business_plan(db, business_id).get("whatsapp_quota") or 0)
    used = db.scalar(select(func.count(WhatsAppMessage.id)).where(
        WhatsAppMessage.account_id == account, WhatsAppMessage.kind.in_(["INVOICE", "REMINDER"]),
        WhatsAppMessage.status.not_in(["FAILED", "SANDBOX"]), WhatsAppMessage.created_at >= _month_start())) or 0
    return {"account": account, "quota": quota, "used": int(used), "left": max(quota - int(used), 0)}


def _before_send(ctx: BCtx) -> bool:
    """Plan and credits check; True when this message is beyond the monthly messages (charged in credits)."""
    s = W.settings(ctx.db)
    if not W.active(s):
        raise HTTPException(503, "Sending from WhatsApp is not set up yet — use 'Open in my WhatsApp' instead.")
    plan = P.business_plan(ctx.db, ctx.bid)
    if not plan.get("whatsapp_quota") and plan.get("einvoice") != "API":
        raise P.UpgradeRequired("Sending invoices from WhatsApp comes with the Starter plan", "STARTER")
    if W.sandbox(s):
        return False  # simulated: free
    u = usage(ctx.db, ctx.bid)
    if u["left"] > 0:
        return False
    P.credits_ensure(ctx.db, ctx.bid, "WHATSAPP")
    return True


@router.get("/whatsapp/status")
def status(ctx: BCtx):
    u = usage(ctx.db, ctx.bid)
    s = W.settings(ctx.db)
    return {"send": W.active(s), "sandbox": W.sandbox(s), "quota": u["quota"], "used": u["used"], "left": u["left"]}


class SendIn(BaseModel):
    phone: str | None = Field(None, max_length=20)


@router.post("/vouchers/{vid}/whatsapp")
def send_voucher(vid: str, data: SendIn, ctx: BCtx, request: Request):
    """The document as a PDF from the platform's WhatsApp number, to the party's (or the given) mobile."""
    v = ctx.db.get(Voucher, vid)
    if not v or v.business_id != ctx.bid:
        raise HTTPException(404, "Document not found")
    ctx.need(voucher_module(v.type), "view")
    if v.cancelled:
        raise HTTPException(400, "This document is cancelled")
    party = ctx.db.get(Party, v.party_id) if v.party_id else None
    to = W.normalize(data.phone or (party.phone if party else None))
    if not to:
        raise HTTPException(422, "Enter the customer's 10-digit mobile number")
    charged = _before_send(ctx)
    token = R._ensure_token(v)
    ctx.db.flush()
    url = f"{frontend_url(request)}/api/public/invoice/{token}/pdf"
    params = [v.party_name or "Customer", v.number, f"₹{float(v.grand_total):,.2f}", ctx.business.name]
    try:
        m = W.send_document(ctx.db, to, url, invoice_pdf.filename(v), params, business_id=ctx.bid,
                            account_id=P.account_of(ctx.db, ctx.bid), ref=v.number, by=ctx.user.name)
    except W.ProviderError as e:
        raise HTTPException(502, e.message) from e
    if charged:
        P.credits_charge(ctx.db, ctx.bid, "WHATSAPP", v.number, ctx.user.name)
    log(ctx.db, ctx.user, "ACTION", "whatsapp", f"Sent {v.number} on WhatsApp to {W.masked(to)}", entity_id=v.id,
        business_id=ctx.bid, request=request)
    ctx.db.commit()
    return {"sent": True, "to": W.masked(to), "message_id": m.wamid, "charged_credits": charged, "sandbox": m.status == "SANDBOX",
            "preview": m.preview}


@router.post("/reminders/whatsapp-send/{party_id}")
def send_reminder(party_id: str, ctx: BCtx, request: Request, data: SendIn | None = None, voucher_id: str | None = None):
    """Payment reminder from the platform's WhatsApp number (template), with a link to the bill."""
    ctx.need("sales", "view")
    party = ctx.db.get(Party, party_id)
    if party is None or party.business_id != ctx.bid:
        raise HTTPException(404, "Party not found")
    vs = R.open_invoices(ctx.db, ctx.business, [party_id])
    if voucher_id:
        vs = [v for v in vs if v.id == voucher_id]
    if not vs:
        raise HTTPException(400, "No unpaid invoices for this party")
    to = W.normalize((data.phone if data else None) or party.phone)
    if not to:
        raise HTTPException(422, "Enter the customer's 10-digit mobile number")
    charged = _before_send(ctx)
    rows = R._rows(vs, R.settings(ctx.business), dt.date.today())
    total = sum((r["balance"] for r in rows), 0)
    link = f"{frontend_url(request)}/i/{R._ensure_token(rows[0]['v'])}"
    ref = rows[0]["number"] if len(rows) == 1 else f"{len(rows)} invoices"
    try:
        m = W.send_reminder(ctx.db, to, [party.name, f"₹{float(total):,.2f}", ctx.business.name, link], business_id=ctx.bid,
                        account_id=P.account_of(ctx.db, ctx.bid), ref=ref, by=ctx.user.name)
    except W.ProviderError as e:
        raise HTTPException(502, e.message) from e
    if charged:
        P.credits_charge(ctx.db, ctx.bid, "WHATSAPP", ref, ctx.user.name)
    for v in vs:
        ctx.db.add(ReminderLog(business_id=ctx.bid, party_id=party.id, voucher_id=v.id, stage="MANUAL", channel="WHATSAPP",
                               sent_to=W.masked(to), status="SENT", automatic=False, amount=R._balance(v), by_name=ctx.user.name))
    log(ctx.db, ctx.user, "ACTION", "reminder", f"WhatsApp reminder to {party.name} ({W.masked(to)})", business_id=ctx.bid, request=request)
    ctx.db.commit()
    return {"sent": True, "to": W.masked(to), "charged_credits": charged, "sandbox": m.status == "SANDBOX", "preview": m.preview}
