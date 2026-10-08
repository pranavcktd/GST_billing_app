"""e-Invoice (IRN) and e-Way Bill endpoints."""

import datetime as dt
import json
from typing import Literal

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..config import get_settings
from ..deps import BCtx
from ..models import Voucher
from ..schemas import TransportIn, VoucherDetailOut
from ..services import einvoice as ei
from ..services import ewaybill as ewb
from ..permissions import voucher_module
from ..services.plans import credits_charge, credits_ensure, require_einvoice
from ..services.vouchers import to_detail

router = APIRouter(tags=["e-invoice"])


def _get(ctx: BCtx, vid: str, action: str = "view") -> Voucher:
    v = ctx.db.get(Voucher, vid)
    if not v or v.business_id != ctx.bid:
        raise HTTPException(404, "Document not found")
    ctx.need(voucher_module(v.type), action)
    return v


def _json_file(data, name: str) -> Response:
    return Response(json.dumps(data, indent=2, ensure_ascii=False), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _safe(number: str) -> str:
    return number.replace("/", "-")


@router.put("/vouchers/{vid}/transport", response_model=VoucherDetailOut)
def update_transport(vid: str, data: TransportIn, ctx: BCtx):
    """Transport details can be added/changed even after the bill is final (before the e-way bill)."""
    v = _get(ctx, vid, "edit")
    v.transport = data.model_dump(mode="json", exclude_none=True)
    ctx.db.commit()
    return to_detail(ctx, v)


# ---------------------------------------------------------------- e-invoice
@router.get("/vouchers/{vid}/einvoice/json")
def einvoice_json(vid: str, ctx: BCtx):
    require_einvoice(ctx.db, ctx.bid, "JSON")
    _need_einvoicing(ctx)
    v = _get(ctx, vid, "export")
    return _json_file([ei.einvoice_payload(ctx.db, ctx.business, v)], f"einvoice-{_safe(v.number)}.json")


@router.get("/einvoice/bulk-json")
def einvoice_bulk(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    """All B2B invoices / credit notes of the period that have no IRN yet (for the IRP bulk upload tool)."""
    ctx.need("sales", "export")
    require_einvoice(ctx.db, ctx.bid, "JSON")
    _need_einvoicing(ctx)
    docs = ctx.db.scalars(select(Voucher).where(
        Voucher.business_id == ctx.bid, Voucher.type.in_(list(ei.EINVOICE_TYPES)), Voucher.cancelled.is_(False),
        Voucher.party_gstin.is_not(None), Voucher.irn.is_(None), Voucher.date >= date_from, Voucher.date <= date_to)
        .order_by(Voucher.date, Voucher.number)).all()
    payloads, skipped = [], []
    for v in docs:
        try:
            payloads.append(ei.einvoice_payload(ctx.db, ctx.business, v))
        except HTTPException as e:
            skipped.append(f"{v.number}: {e.detail}")
    if not payloads:
        raise HTTPException(400, "No invoices ready for e-invoicing in this period" +
                            (f".\n{skipped[0]}" if skipped else ""))
    return _json_file(payloads, f"einvoices-{date_from}-{date_to}.json")


@router.post("/vouchers/{vid}/einvoice", response_model=VoucherDetailOut)
def generate_irn(vid: str, ctx: BCtx):
    require_einvoice(ctx.db, ctx.bid, "API")
    _need_einvoicing(ctx)
    v = _get(ctx, vid, "edit")
    if v.einvoice_status == "GENERATED":
        raise HTTPException(400, "IRN already generated")
    payload = ei.einvoice_payload(ctx.db, ctx.business, v)
    p = ei.provider(ctx.db, ctx.business)
    if not p.sandbox:
        credits_ensure(ctx.db, ctx.bid, "EINVOICE")
    res = p.generate_irn(ctx.business, v, payload)
    if not p.sandbox:
        credits_charge(ctx.db, ctx.bid, "EINVOICE", v.number, ctx.user.name)
    v.irn, v.ack_no, v.ack_date, v.signed_qr = res["irn"], res["ack_no"], res["ack_date"], res["signed_qr"]
    v.einvoice_status, v.einvoice_sandbox = "GENERATED", p.sandbox
    if res.get("ewb_no") and not v.ewb_no:  # the IRP can issue the e-way bill in the same call
        v.ewb_no, v.ewb_date, v.ewb_valid_till = res["ewb_no"], res.get("ewb_date"), res.get("ewb_valid_till")
    ctx.db.commit()
    return to_detail(ctx, v)


class CancelIrn(BaseModel):
    reason: Literal["1", "2", "3", "4"] = "2"  # 1 duplicate, 2 data entry mistake, 3 order cancelled, 4 other
    remark: str = Field("", max_length=100)


@router.post("/vouchers/{vid}/einvoice/cancel", response_model=VoucherDetailOut)
def cancel_irn(vid: str, data: CancelIrn, ctx: BCtx):
    v = _get(ctx, vid, "delete")
    if v.einvoice_status != "GENERATED":
        raise HTTPException(400, "No active IRN on this document")
    ack = v.ack_date if v.ack_date.tzinfo else v.ack_date.replace(tzinfo=dt.timezone.utc)
    if dt.datetime.now(dt.timezone.utc) - ack > dt.timedelta(hours=24):
        raise HTTPException(400, "An IRN can be cancelled only within 24 hours — issue a credit note instead")
    p = ei.provider(ctx.db, ctx.business)
    if not p.sandbox:
        credits_ensure(ctx.db, ctx.bid, "CANCEL")
    p.cancel_irn(ctx.business, v, data.reason, data.remark)
    if not p.sandbox:
        credits_charge(ctx.db, ctx.bid, "CANCEL", v.number, ctx.user.name)
    v.einvoice_status = "CANCELLED"
    ctx.db.commit()
    return to_detail(ctx, v)


class ManualIrn(BaseModel):
    irn: str = Field(min_length=64, max_length=64)
    ack_no: str = Field(min_length=1, max_length=20)
    ack_date: dt.datetime
    signed_qr: str | None = None


@router.put("/vouchers/{vid}/einvoice", response_model=VoucherDetailOut)
def record_irn(vid: str, data: ManualIrn, ctx: BCtx):
    """Save an IRN obtained from the portal (offline / bulk upload route)."""
    v = _get(ctx, vid, "edit")
    _need_einvoicing(ctx)
    if v.type not in ei.EINVOICE_TYPES:
        raise HTTPException(400, "Not an e-invoice document")
    v.irn, v.ack_no, v.ack_date, v.signed_qr = data.irn.lower(), data.ack_no, data.ack_date, data.signed_qr
    v.einvoice_status, v.einvoice_sandbox = "GENERATED", False
    ctx.db.commit()
    return to_detail(ctx, v)


# ---------------------------------------------------------------- e-way bill
def _need_goods(v: Voucher) -> None:
    if not ewb.is_goods(v):
        raise HTTPException(400, "This bill has only services (SAC codes) — an e-way bill is needed only when goods move")


def _need_einvoicing(ctx: BCtx) -> None:
    if not ctx.business.einvoice_applicable:
        raise HTTPException(400, "e-Invoicing is not turned on for your business. If your turnover is above the limit, "
                                 "tick 'e-Invoicing applies to us' in Settings > e-Invoice.")


@router.get("/vouchers/{vid}/ewaybill/json")
def ewaybill_json(vid: str, ctx: BCtx):
    require_einvoice(ctx.db, ctx.bid, "JSON")
    v = _get(ctx, vid, "export")
    _need_goods(v)
    return _json_file(ei.ewaybill_payload(ctx.db, ctx.business, v), f"ewaybill-{_safe(v.number)}.json")


@router.post("/vouchers/{vid}/ewaybill", response_model=VoucherDetailOut)
def generate_ewb(vid: str, ctx: BCtx):
    require_einvoice(ctx.db, ctx.bid, "API")
    v = _get(ctx, vid, "edit")
    _need_goods(v)
    if v.ewb_no:
        raise HTTPException(400, "E-way bill already generated")
    p = ei.provider(ctx.db, ctx.business)
    payload = ei.ewaybill_payload(ctx.db, ctx.business, v)
    if not p.sandbox:
        credits_ensure(ctx.db, ctx.bid, "EWAYBILL")
    res = p.generate_ewb(ctx.business, v, payload)
    if not p.sandbox:
        credits_charge(ctx.db, ctx.bid, "EWAYBILL", v.number, ctx.user.name)
    v.ewb_no, v.ewb_date, v.ewb_valid_till = res["ewb_no"], res["ewb_date"], res["valid_till"]
    v.einvoice_sandbox = v.einvoice_sandbox or p.sandbox
    ctx.db.commit()
    return to_detail(ctx, v)


class CancelEwb(BaseModel):
    reason: Literal["1", "2", "3", "4"] = "2"  # 1 duplicate, 2 data entry mistake, 3 order cancelled, 4 other
    remark: str = Field("", max_length=50)


@router.post("/vouchers/{vid}/ewaybill/cancel", response_model=VoucherDetailOut)
def cancel_ewb(vid: str, data: CancelEwb, ctx: BCtx):
    """Cancel an e-way bill within 24 hours of generating it (portal rule); generated ones go through the provider."""
    v = _get(ctx, vid, "delete")
    if not v.ewb_no:
        raise HTTPException(400, "No e-way bill on this document")
    when = v.ewb_date if (v.ewb_date and v.ewb_date.tzinfo) else (v.ewb_date.replace(tzinfo=dt.timezone.utc) if v.ewb_date else None)
    if when and dt.datetime.now(dt.timezone.utc) - when > dt.timedelta(hours=24):
        raise HTTPException(400, "An e-way bill can be cancelled only within 24 hours of generating it")
    p = ei.provider(ctx.db, ctx.business)
    if not p.sandbox:
        credits_ensure(ctx.db, ctx.bid, "CANCEL")
    p.cancel_ewb(ctx.business, v, data.reason, data.remark)
    if not p.sandbox:
        credits_charge(ctx.db, ctx.bid, "CANCEL", v.number, ctx.user.name)
    v.ewb_no, v.ewb_date, v.ewb_valid_till = None, None, None
    ctx.db.commit()
    return to_detail(ctx, v)


@router.get("/einvoice/setup")
def einvoice_setup(ctx: BCtx):
    """What the business needs to know to generate e-invoices / e-way bills from the app."""
    from ..services import gstin_verify as G
    from ..services.plans import business_plan

    s = G.settings(ctx.db)
    live = bool(s.get("einv_live") and G._key(s))
    b = ctx.business
    return {"live": live, "test_mode": bool(s.get("einv_test_mode", True)) if live else None,
            "sandbox": not live and get_settings().is_dev,
            "gsp_name": s.get("gsp_name") or None, "plan": business_plan(ctx.db, ctx.bid).get("einvoice"),
            "einvoice_user_set": bool(b.einvoice_username and b.einvoice_password_enc),
            "ewb_user_set": bool(b.ewb_username and b.ewb_password_enc), "einvoice_applicable": b.einvoice_applicable}


@router.get("/einvoice/pending")
def einvoice_pending(ctx: BCtx, days: int = 60):
    """Documents of the last `days` that still need an e-way bill or an IRN (dashboard / reminders)."""
    ctx.need("sales", "view")
    since = dt.date.today() - dt.timedelta(days=min(max(days, 1), 365))
    docs = ctx.db.scalars(select(Voucher).where(
        Voucher.business_id == ctx.bid, Voucher.cancelled.is_(False), Voucher.date >= since,
        Voucher.type.in_(list(set(ei.EWB_DOC_TYPES) | set(ei.EINVOICE_TYPES)))).order_by(Voucher.date.desc())).all()
    biz = ctx.business
    out = []
    for v in docs:
        need_ewb = bool(biz.gstin and ewb.needs_ewb(v))
        need_irn = ei.irn_required(biz, v)
        if need_ewb or need_irn:
            out.append(dict(id=v.id, type=v.type.value, number=v.number, date=v.date, party_name=v.party_name,
                            total=float(v.grand_total), ewb=need_ewb, irn=need_irn))
    return {"count": len(out), "ewb": sum(1 for x in out if x["ewb"]), "irn": sum(1 for x in out if x["irn"]), "items": out[:20]}


class ManualEwb(BaseModel):
    ewb_no: str = Field(pattern=r"^\d{12}$")
    ewb_date: dt.datetime
    valid_till: dt.datetime | None = None


@router.put("/vouchers/{vid}/ewaybill", response_model=VoucherDetailOut)
def record_ewb(vid: str, data: ManualEwb, ctx: BCtx):
    v = _get(ctx, vid, "edit")
    _need_goods(v)
    v.ewb_no, v.ewb_date = data.ewb_no, data.ewb_date
    v.ewb_valid_till = data.valid_till or ewb.valid_till(data.ewb_date, (v.transport or {}).get("distance_km"))
    ctx.db.commit()
    return to_detail(ctx, v)


# ---------------------------------------------------------------- e-way bill register (no API needed)
@router.get("/ewaybills")
def ewb_list(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    ctx.need("sales", "view")
    return ewb.listing(ctx.db, ctx.business, date_from, date_to)


class BulkIn(BaseModel):
    voucher_ids: list[str] = Field(min_length=1, max_length=500)


@router.post("/ewaybills/bulk-json")
def ewb_bulk(data: BulkIn, ctx: BCtx):
    """One JSON file for the portal's 'Generate Bulk' upload; bills with missing details are listed."""
    require_einvoice(ctx.db, ctx.bid, "JSON")
    ctx.need("sales", "export")
    payload, skipped = ewb.bulk(ctx.db, ctx.business, data.voucher_ids)
    return {"json": payload, "count": len(payload["billLists"]), "skipped": skipped}


@router.post("/ewaybills/import")
async def ewb_import(ctx: BCtx, file: UploadFile = File(...)):
    """Upload the e-way bill list downloaded from the portal: numbers and validity are filled on matching bills."""
    ctx.need("sales", "edit")
    content = await file.read()
    try:
        rows = ewb.parse_import(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return ewb.apply_import(ctx.db, ctx.business, rows)

