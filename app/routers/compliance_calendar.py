"""Compliance calendar of a business: GST, income tax / TDS, MCA / LLP and PF / ESI filings with due dates."""

import datetime as dt
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import BCtx
from ..models import ComplianceFiling
from ..services import compliance_calendar as CC
from ..services import config_store as C

router = APIRouter(prefix="/compliance", tags=["compliance calendar"])


def _rules() -> list[dict]:
    return C.get("compliance_rules") or CC.DEFAULT_RULES


def _done(ctx: BCtx) -> dict[tuple[str, str], dict]:
    rows = ctx.db.scalars(select(ComplianceFiling).where(ComplianceFiling.business_id == ctx.bid)).all()
    return {(r.rule_code, r.period_key): dict(id=r.id, done_on=r.done_on, reference=r.reference, note=r.note, by=r.by,
                                              source=r.source) for r in rows}


@router.get("/calendar")
def get_calendar(ctx: BCtx, ahead_days: int = 120):
    ctx.need("reports_gst", "view")
    return CC.calendar_for(ctx.business, _rules(), _done(ctx), ahead_days=min(max(ahead_days, 15), 400))


@router.post("/sync")
def sync_status(ctx: BCtx):
    """Fetch GST return filing status from the GST data service (see services/filing_sync.py)."""
    from ..services import filing_sync

    ctx.need("reports_gst", "view")
    return filing_sync.sync(ctx.db, ctx.business, _rules(), ctx.user.name)


@router.get("/sync/available")
def sync_available(ctx: BCtx):
    from ..services import gstin_verify as G

    s = G.settings(ctx.db)
    ok = bool(s.get("enabled") and G._key(s) and s.get("filing_sync", True))
    cs = ctx.business.compliance_settings or {}
    return {"available": ok and bool(ctx.business.gstin) and ctx.business.gst_type.value in ("REGULAR", "COMPOSITION"),
            "last_sync_at": cs.get("last_sync_at"), "min_hours": int(s.get("filing_sync_hours") or 24)}


@router.get("/summary")
def get_summary(ctx: BCtx):
    """Counts for the dashboard: overdue and due within 15 days, plus the next three items."""
    if not ctx.can("reports_gst", "view"):
        return {"summary": None, "next": []}
    cal = CC.calendar_for(ctx.business, _rules(), _done(ctx), ahead_days=30)
    pending = [i for i in cal["items"] if i["status"] in ("OVERDUE", "DUE_SOON")]
    return {"summary": cal["summary"], "next": pending[:3]}


class SettingsIn(BaseModel):
    gst_filing: Literal["MONTHLY", "QUARTERLY"] = "MONTHLY"
    tax_audit: bool = False
    tds: bool = False
    payroll: bool = False
    track_from: dt.date | None = None


@router.put("/settings")
def put_settings(data: SettingsIn, ctx: BCtx):
    ctx.need("settings", "edit")
    ctx.business.compliance_settings = {**(ctx.business.compliance_settings or {}), **data.model_dump(mode="json"),
                                        "track_from": (data.track_from or CC.settings(ctx.business)["track_from"]).__str__()}
    ctx.db.commit()
    return CC.settings(ctx.business)


class FilingIn(BaseModel):
    rule_code: str = Field(min_length=1, max_length=30)
    period_key: str = Field(min_length=4, max_length=20)
    done_on: dt.date
    reference: str | None = Field(None, max_length=100)
    note: str | None = Field(None, max_length=300)


@router.post("/tasks", status_code=201)
def mark_done(data: FilingIn, ctx: BCtx):
    ctx.need("reports_gst", "view")
    if data.rule_code not in {r["code"] for r in _rules()}:
        raise HTTPException(404, "Unknown filing")
    row = ctx.db.scalar(select(ComplianceFiling).where(
        ComplianceFiling.business_id == ctx.bid, ComplianceFiling.rule_code == data.rule_code,
        ComplianceFiling.period_key == data.period_key)) or ComplianceFiling(business_id=ctx.bid)
    for k, v in data.model_dump().items():
        setattr(row, k, v)
    row.reference = (data.reference or "").strip() or None
    row.note = (data.note or "").strip() or None
    row.by = ctx.user.name
    ctx.db.add(row)
    ctx.db.commit()
    return {"id": row.id}


@router.delete("/tasks/{task_id}", status_code=204)
def undo(task_id: str, ctx: BCtx):
    ctx.need("reports_gst", "view")
    row = ctx.db.get(ComplianceFiling, task_id)
    if not row or row.business_id != ctx.bid:
        raise HTTPException(404, "Not found")
    ctx.db.delete(row)
    ctx.db.commit()
