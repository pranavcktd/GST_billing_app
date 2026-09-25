"""File exports (GSTR-1 JSON, Tally XML) and the audit log."""

import datetime as dt
import json

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import func, select

from ..deps import BCtx
from ..gst.constants import BusinessGstType
from ..models import AuditLog
from ..services import gst_returns, gstr1_json, gstr2b, tally
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
