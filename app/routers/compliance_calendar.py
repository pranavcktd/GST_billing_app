"""Compliance calendar of a business: GST, income tax / TDS, MCA / LLP and PF / ESI filings with due dates."""

import datetime as dt
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import BCtx
from ..models import ComplianceFiling, GstReturnStatus
from ..services import compliance_calendar as CC
from ..services import config_store as C

router = APIRouter(prefix="/compliance", tags=["compliance calendar"])


def _rules() -> list[dict]:
    return C.get("compliance_rules") or CC.DEFAULT_RULES


def _biz(ctx: BCtx):
    """The business, with its GST registration date picked up from an earlier GSTIN lookup when not saved yet."""
    from .businesses import _fill_registration_date

    if ctx.business.gstin and not ctx.business.gst_registration_date:
        _fill_registration_date(ctx.db, ctx.business)
    return ctx.business


def _done(ctx: BCtx) -> dict[tuple[str, str], dict]:
    rows = ctx.db.scalars(select(ComplianceFiling).where(ComplianceFiling.business_id == ctx.bid)).all()
    return {(r.rule_code, r.period_key): dict(id=r.id, done_on=r.done_on, reference=r.reference, note=r.note, by=r.by,
                                              source=r.source) for r in rows}


@router.get("/calendar")
def get_calendar(ctx: BCtx, ahead_days: int = 120):
    ctx.need("reports_gst", "view")
    return CC.calendar_for(_biz(ctx), _rules(), _done(ctx), ahead_days=min(max(ahead_days, 15), 400))


@router.post("/sync")
def sync_status(ctx: BCtx, fy: int | None = None):
    """Fetch GST return filing status from the GST data service (see services/filing_sync.py); `fy` = one year only."""
    from ..services import filing_sync

    ctx.need("reports_gst", "view")
    return filing_sync.sync(ctx.db, ctx.business, _rules(), ctx.user.name, only_fy=fy)


@router.get("/register")
def get_register(ctx: BCtx, law: str = "GST", fy: int | None = None):
    """Month / quarter / year table of one law for one financial year, plus (GST) what the portal returned."""
    ctx.need("reports_gst", "view")
    today = dt.date.today()
    fy = fy or (today.year if today.month >= 4 else today.year - 1)
    if not 2017 <= fy <= today.year + 1:
        raise HTTPException(422, "Choose a financial year from 2017-18")
    out = CC.register(_biz(ctx), _rules(), _done(ctx), fy, law.upper())
    if law.upper() == "GST":
        rows = ctx.db.scalars(select(GstReturnStatus).where(GstReturnStatus.business_id == ctx.bid, GstReturnStatus.fy == out["fy_label"])
                              .order_by(GstReturnStatus.return_period, GstReturnStatus.return_type)).all()
        out["portal"] = [dict(return_type=r.return_type, return_period=r.return_period, status=r.status, filed=r.filed,
                              filed_on=r.filed_on, arn=r.arn, mode=r.mode) for r in rows]
        out["portal_fetched_at"] = max((r.fetched_at for r in rows), default=None)
    return out


@router.get("/sync/available")
def sync_available(ctx: BCtx):
    from ..services import gstin_verify as G

    s = G.settings(ctx.db)
    ok = bool(s.get("enabled") and G._key(s) and s.get("filing_sync"))
    cs = ctx.business.compliance_settings or {}
    return {"available": ok and bool(ctx.business.gstin) and ctx.business.gst_type.value in ("REGULAR", "COMPOSITION"),
            "last_sync_at": cs.get("last_sync_at"), "min_hours": int(s.get("filing_sync_hours") or 24)}


@router.get("/summary")
def get_summary(ctx: BCtx):
    """Counts for the dashboard: overdue and due within 15 days, plus the next three items."""
    if not ctx.can("reports_gst", "view"):
        return {"summary": None, "next": []}
    cal = CC.calendar_for(_biz(ctx), _rules(), _done(ctx), ahead_days=30)
    pending = [i for i in cal["items"] if i["status"] in ("OVERDUE", "DUE_SOON")]
    return {"summary": cal["summary"], "next": pending[:3]}


class SettingsIn(BaseModel):
    gst_filing: Literal["MONTHLY", "QUARTERLY"] = "MONTHLY"
    tax_audit: bool = False
    tds: bool = False
    pf: bool = False
    esi: bool = False
    employees: int | None = Field(None, ge=0, le=1000000)
    track_from: dt.date | None = None


@router.put("/settings")
def put_settings(data: SettingsIn, ctx: BCtx):
    ctx.need("settings", "edit")
    old = {k: v for k, v in (ctx.business.compliance_settings or {}).items() if k != "payroll"}
    ctx.business.compliance_settings = {**old, **data.model_dump(mode="json"), "profile_done": True,
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
