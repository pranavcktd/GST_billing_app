"""e-Invoice (IRN) and e-Way Bill endpoints."""

import datetime as dt
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import BCtx
from ..models import Voucher
from ..schemas import TransportIn, VoucherDetailOut
from ..services import einvoice as ei
from ..permissions import voucher_module
from ..services.plans import check_api_quota, require_einvoice
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
    v = _get(ctx, vid, "export")
    return _json_file([ei.einvoice_payload(ctx.db, ctx.business, v)], f"einvoice-{_safe(v.number)}.json")


@router.get("/einvoice/bulk-json")
def einvoice_bulk(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    """All B2B invoices / credit notes of the period that have no IRN yet (for the IRP bulk upload tool)."""
    ctx.need("sales", "export")
    require_einvoice(ctx.db, ctx.bid, "JSON")
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
    v = _get(ctx, vid, "edit")
    check_api_quota(ctx.db, ctx.bid)
    if v.einvoice_status == "GENERATED":
        raise HTTPException(400, "IRN already generated")
    payload = ei.einvoice_payload(ctx.db, ctx.business, v)
    p = ei.provider(ctx.business)
    res = p.generate_irn(ctx.business, v, payload)
    v.irn, v.ack_no, v.ack_date, v.signed_qr = res["irn"], res["ack_no"], res["ack_date"], res["signed_qr"]
    v.einvoice_status, v.einvoice_sandbox = "GENERATED", p.sandbox
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
    ei.provider(ctx.business).cancel_irn(ctx.business, v, data.reason, data.remark)
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
    if v.type not in ei.EINVOICE_TYPES:
        raise HTTPException(400, "Not an e-invoice document")
    v.irn, v.ack_no, v.ack_date, v.signed_qr = data.irn.lower(), data.ack_no, data.ack_date, data.signed_qr
    v.einvoice_status, v.einvoice_sandbox = "GENERATED", False
    ctx.db.commit()
    return to_detail(ctx, v)


# ---------------------------------------------------------------- e-way bill
@router.get("/vouchers/{vid}/ewaybill/json")
def ewaybill_json(vid: str, ctx: BCtx):
    require_einvoice(ctx.db, ctx.bid, "JSON")
    v = _get(ctx, vid, "export")
    return _json_file(ei.ewaybill_payload(ctx.db, ctx.business, v), f"ewaybill-{_safe(v.number)}.json")


@router.post("/vouchers/{vid}/ewaybill", response_model=VoucherDetailOut)
def generate_ewb(vid: str, ctx: BCtx):
    require_einvoice(ctx.db, ctx.bid, "API")
    v = _get(ctx, vid, "edit")
    check_api_quota(ctx.db, ctx.bid)
    if v.ewb_no:
        raise HTTPException(400, "E-way bill already generated")
    p = ei.provider(ctx.business)
    res = p.generate_ewb(ctx.business, v, ei.ewaybill_payload(ctx.db, ctx.business, v))
    v.ewb_no, v.ewb_date, v.ewb_valid_till = res["ewb_no"], res["ewb_date"], res["valid_till"]
    v.einvoice_sandbox = v.einvoice_sandbox or p.sandbox
    ctx.db.commit()
    return to_detail(ctx, v)


class ManualEwb(BaseModel):
    ewb_no: str = Field(pattern=r"^\d{12}$")
    ewb_date: dt.datetime
    valid_till: dt.datetime | None = None


@router.put("/vouchers/{vid}/ewaybill", response_model=VoucherDetailOut)
def record_ewb(vid: str, data: ManualEwb, ctx: BCtx):
    v = _get(ctx, vid, "edit")
    v.ewb_no, v.ewb_date, v.ewb_valid_till = data.ewb_no, data.ewb_date, data.valid_till
    ctx.db.commit()
    return to_detail(ctx, v)

