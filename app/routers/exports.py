"""File exports (GSTR-1 JSON, Tally XML) and the audit log."""

import datetime as dt
import json
import re
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..deps import DB, BCtx, CurrentUser
from ..gst.constants import BusinessGstType
from ..models import AuditLog, Membership
from ..services import config_store, gst_returns, gstr1_json, gstr2b, table_export, tally
from ..services.plans import require_feature

router = APIRouter(tags=["exports"])


@router.get("/exports/gstr1-json")
def gstr1(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    ctx.need("reports_gst", "export")
    require_feature(ctx.db, ctx.bid, "gst_json")
    if ctx.business.gst_type != BusinessGstType.REGULAR or not ctx.business.gstin:
        raise HTTPException(400, "GSTR-1 applies to regular GST registered businesses")
    data = gstr1_json.build(ctx.db, ctx.business, date_from, date_to)
    return Response(json.dumps(data, indent=1), media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="GSTR1_{ctx.business.gstin}_{date_to:%m%Y}.json"'})


@router.get("/exports/gstr3b-json")
def gstr3b(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    ctx.need("reports_gst", "export")
    require_feature(ctx.db, ctx.bid, "gst_json")
    if ctx.business.gst_type != BusinessGstType.REGULAR or not ctx.business.gstin:
        raise HTTPException(400, "GSTR-3B applies to regular GST registered businesses")
    data = gst_returns.gstr3b_json(ctx.db, ctx.business, date_from, date_to)
    return Response(json.dumps(data, indent=1), media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="GSTR3B_{ctx.business.gstin}_{date_to:%m%Y}.json"'})


@router.get("/exports/tally")
def tally_xml(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    ctx.need("reports_financial", "export")
    require_feature(ctx.db, ctx.bid, "tally")
    xml = tally.export(ctx.db, ctx.business, date_from, date_to)
    return Response(xml, media_type="application/xml", headers={
        "Content-Disposition": f'attachment; filename="tally-{date_from}-{date_to}.xml"'})


@router.get("/audit")
def audit_log(ctx: BCtx, limit: int = 100, offset: int = 0, entity: str | None = None, user_id: str | None = None,
              date_from: dt.date | None = None, date_to: dt.date | None = None):
    ctx.need("audit", "view")
    require_feature(ctx.db, ctx.bid, "audit_view")
    q = select(AuditLog).where(AuditLog.business_id == ctx.bid)
    if entity:
        q = q.where(func.lower(AuditLog.entity).contains(entity.lower()))
    if user_id:
        q = q.where(AuditLog.user_id == user_id)
    if date_from:
        q = q.where(AuditLog.created_at >= dt.datetime.combine(date_from, dt.time.min, dt.timezone.utc))
    if date_to:
        q = q.where(AuditLog.created_at < dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min, dt.timezone.utc))
    total = ctx.db.scalar(select(func.count()).select_from(q.subquery()))
    rows = ctx.db.scalars(q.order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).offset(offset)).all()
    return {"total": total, "rows": [dict(id=a.id, created_at=a.created_at, user=a.user_name, action=a.action,
                                          entity=a.entity, entity_id=a.entity_id, summary=a.summary, ip=a.ip)
                                     for a in rows]}


@router.post("/reconcile/gstr2b")
async def reconcile_2b(ctx: BCtx, file: UploadFile = File(...), date_from: dt.date = Form(...), date_to: dt.date = Form(...)):
    ctx.need("reports_gst", "view")
    require_feature(ctx.db, ctx.bid, "gstr2b")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "File too large")
    return gstr2b.reconcile(ctx.db, ctx.business, content, date_from, date_to)


# ---------------------------------------------------------------- any table → Excel / PDF
class TableDoc(BaseModel):
    title: str = Field(max_length=200)
    subtitle: str | None = Field(None, max_length=500)
    filename: str | None = Field(None, max_length=120)
    summary: list[dict] = Field(default_factory=list, max_length=50)
    sections: list[dict] = Field(default_factory=list, max_length=60)


XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/export/table")
def export_table(doc: TableDoc, db: DB, user: CurrentUser, format: Literal["xlsx", "pdf"] = "xlsx",
                 x_business_id: Annotated[str | None, Header()] = None):
    """Turns the table the user is looking at into an Excel or PDF file (the data comes from the page)."""
    rows = sum(len(s.get("rows") or []) for s in doc.sections)
    if rows > table_export.MAX_ROWS:
        raise HTTPException(413, f"Too many rows to export at once ({rows}); narrow the filters")
    business = None
    if x_business_id:
        m = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.business_id == x_business_id))
        business = m.business.name + (f" · GSTIN {m.business.gstin}" if m and m.business.gstin else "") if m else None
    data = doc.model_dump()
    brand = config_store.app_name()
    content = table_export.to_pdf(data, business, brand) if format == "pdf" else table_export.to_xlsx(data, business, brand)
    name = re.sub(r"[^\w.-]+", "-", doc.filename or doc.title).strip("-")[:100] or "export"
    return Response(content, media_type="application/pdf" if format == "pdf" else XLSX_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="{name}.{format}"'})
