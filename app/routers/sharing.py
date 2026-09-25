"""Share documents: public view link (no login) and e-mail to the customer."""

import html
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from ..deps import DB, BCtx
from ..models import Business, Voucher
from ..permissions import voucher_module
from ..schemas import VoucherDetailOut
from ..services import mailer
from ..services.plans import account_of, business_plan
from ..services.platform_audit import log
from ..services.vouchers import to_detail
from .auth import frontend_url

router = APIRouter(tags=["sharing"])
PUBLIC_BUSINESS_FIELDS = ("name", "legal_name", "gst_type", "gstin", "state_code", "address", "city", "pincode", "phone",
                          "email", "logo_url", "signature_url", "bank_name", "bank_account_no", "bank_ifsc", "bank_branch",
                          "upi_id", "print_settings")


def _voucher(ctx: BCtx, vid: str) -> Voucher:
    v = ctx.db.get(Voucher, vid)
    if not v or v.business_id != ctx.bid:
        raise HTTPException(404, "Document not found")
    ctx.need(voucher_module(v.type), "view")
    return v


def _ensure_token(v: Voucher) -> str:
    if not v.share_token:
        v.share_token = secrets.token_urlsafe(24)
    return v.share_token


@router.post("/vouchers/{vid}/share-link")
def share_link(vid: str, ctx: BCtx, request: Request, regenerate: bool = False):
    v = _voucher(ctx, vid)
    if regenerate:
        v.share_token = None
    token = _ensure_token(v)
    ctx.db.commit()
    return {"token": token, "url": f"{frontend_url(request)}/i/{token}"}


@router.delete("/vouchers/{vid}/share-link", status_code=204)
def revoke_link(vid: str, ctx: BCtx):
    v = _voucher(ctx, vid)
    v.share_token = None
    ctx.db.commit()


class EmailIn(BaseModel):
    to: list[EmailStr] = Field(min_length=1, max_length=5)
    cc: list[EmailStr] = []
    subject: str | None = Field(None, max_length=200)
    message: str | None = Field(None, max_length=2000)


@router.post("/vouchers/{vid}/email")
def email_voucher(vid: str, data: EmailIn, ctx: BCtx, request: Request):
    v = _voucher(ctx, vid)
    biz = ctx.business
    link = f"{frontend_url(request)}/i/{_ensure_token(v)}"
    e = html.escape
    rows = "".join(f"<tr><td style='padding:4px 0'>{e(l.name)} × {float(l.qty):g}</td><td style='text-align:right'>₹{float(l.total):,.2f}</td></tr>"
                   for l in v.lines[:15])
    note = f"<p>{e(data.message).replace(chr(10), '<br>')}</p>" if data.message else ""
    due = f"<p><b>Balance due: ₹{float(v.grand_total - sum((a.amount for a in v.allocations), 0)):,.2f}</b>" \
          f"{f' — pay by UPI to <b>{e(biz.upi_id)}</b>' if biz.upi_id else ''}</p>" if v.type.value == "SALE" else ""
    body = mailer.layout(f"{e(v.party_name)} — {e(v.number)}", f"""
        <p>Dear {e(v.party_name)},</p>{note}
        <p>Please find the details of <b>{e(v.number)}</b> dated {v.date:%d %b %Y} from <b>{e(biz.name)}</b>.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px">{rows}
        <tr><td style="border-top:1px solid #e5e7eb;padding-top:6px"><b>Total</b></td><td style="border-top:1px solid #e5e7eb;text-align:right;padding-top:6px"><b>₹{float(v.grand_total):,.2f}</b></td></tr></table>
        {due}
        <p style="text-align:center;margin:24px 0"><a href="{link}" style="background:#1f65bb;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none">View / download the full document</a></p>""",
        footer=f"{e(biz.name)}{' · GSTIN ' + e(biz.gstin) if biz.gstin else ''}")
    cfg = mailer.business_smtp(ctx.db, ctx.bid, account_of(ctx.db, ctx.bid))
    mailer.send(cfg, [str(x) for x in data.to], data.subject or f"{to_detail(ctx, v).title} {v.number} from {biz.name}", body,
                cc=[str(x) for x in data.cc], reply_to=biz.email)
    log(ctx.db, ctx.user, "ACTION", "e-mail", f"E-mailed {v.number} to {', '.join(map(str, data.to))}", entity_id=v.id,
        business_id=ctx.bid, request=request)
    ctx.db.commit()
    return {"sent": True, "via": cfg.source if cfg else None, "link": link}


@router.get("/public/invoice/{token}")
def public_invoice(token: str, db: DB):
    """Read-only document for customers who received the link (no login)."""
    if len(token) < 20:
        raise HTTPException(404, "Link not found")
    v = db.scalar(select(Voucher).where(Voucher.share_token == token))
    if not v or v.cancelled:
        raise HTTPException(404, "This link is no longer valid")
    biz = db.get(Business, v.business_id)

    class _Ctx:  # to_detail only needs .db
        pass
    c = _Ctx()
    c.db = db
    detail = VoucherDetailOut.model_validate(to_detail(c, v)).model_dump(mode="json")
    detail.pop("share_token", None)
    plan = business_plan(db, biz.id)
    return {"voucher": detail,
            "business": {**{k: getattr(biz, k) for k in PUBLIC_BUSINESS_FIELDS},
                         "gst_type": biz.gst_type.value, "plan": {"watermark": plan["watermark"]}}}
