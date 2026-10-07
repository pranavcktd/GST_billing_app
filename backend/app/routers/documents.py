"""Document vault of a business: upload files or save links, find them later, e-mail or share by WhatsApp."""

import datetime as dt
import html
import re
import secrets
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select

from ..deps import DB, BCtx, SuperAdmin
from ..models import Document, DocumentShare
from ..services import documents as D
from ..services import mailer
from ..services.plans import account_of
from ..services.platform_audit import log
from .auth import frontend_url

router = APIRouter(tags=["documents"])
URL_RE = re.compile(r"^https?://[^\s]{3,}$")


def _out(d: Document) -> dict:
    return dict(id=d.id, title=d.title, category=d.category, financial_year=d.financial_year, doc_date=d.doc_date,
                expiry_date=d.expiry_date, kind=d.kind, url=d.url if d.kind == "LINK" else None, file_name=d.file_name,
                content_type=d.content_type, size_bytes=d.size_bytes, notes=d.notes, uploaded_by=d.uploaded_by,
                created_at=d.created_at, expiry_status=D.expiry_status(d))


def _get(ctx: BCtx, doc_id: str) -> Document:
    d = ctx.db.get(Document, doc_id)
    if not d or d.business_id != ctx.bid:
        raise HTTPException(404, "Document not found")
    return d


def _fy_ok(fy: str | None) -> str | None:
    fy = (fy or "").strip() or None
    if fy and not re.fullmatch(r"\d{4}-\d{2}", fy):
        raise HTTPException(422, "Financial year like 2025-26")
    return fy


@router.get("/documents/meta")
def meta(ctx: BCtx):
    ctx.need("documents", "view")
    s = D.settings(ctx.db)
    return {"categories": D.CATEGORIES, "enabled": s["enabled"], "allow_links": s["allow_links"], "allow_upload": D.can_upload(s),
            "max_file_mb": s["max_file_mb"], "quota_mb": s["quota_mb"], "used_bytes": D.used_bytes(ctx.db, ctx.bid),
            "extensions": sorted(D.EXTENSIONS), "share_days": s["share_days"]}


@router.get("/documents")
def list_documents(ctx: BCtx, category: str | None = None, q: str | None = None, financial_year: str | None = None):
    ctx.need("documents", "view")
    query = select(Document).where(Document.business_id == ctx.bid).order_by(Document.created_at.desc())
    if category:
        query = query.where(Document.category == category)
    if financial_year:
        query = query.where(Document.financial_year == financial_year)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(Document.title.ilike(like), Document.notes.ilike(like), Document.file_name.ilike(like)))
    return [_out(d) for d in ctx.db.scalars(query.limit(2000))]


@router.post("/documents", status_code=201)
async def add_document(ctx: BCtx, request: Request, title: str = Form(..., min_length=1, max_length=200),
                       category: str = Form("Other"), financial_year: str | None = Form(None),
                       doc_date: dt.date | None = Form(None), expiry_date: dt.date | None = Form(None),
                       notes: str | None = Form(None, max_length=1000), url: str | None = Form(None),
                       file: UploadFile | None = File(None)):
    ctx.need("documents", "create")
    s = D.settings(ctx.db)
    if not s["enabled"]:
        raise HTTPException(403, "The document vault is switched off by the platform administrator")
    if category not in D.CATEGORIES:
        category = "Other"
    doc = Document(business_id=ctx.bid, title=title.strip(), category=category, financial_year=_fy_ok(financial_year),
                   doc_date=doc_date, expiry_date=expiry_date, notes=(notes or "").strip() or None, uploaded_by=ctx.user.name)
    if file is not None and file.filename:
        if not D.can_upload(s):
            raise HTTPException(403, "Uploading files is not available — save a link (e.g. Google Drive) instead")
        ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
        if ext not in D.EXTENSIONS:
            raise HTTPException(400, f"This file type is not allowed. Allowed: {', '.join(sorted(D.EXTENSIONS))}")
        data = await file.read()
        if not data:
            raise HTTPException(400, "The file is empty")
        if len(data) > int(s["max_file_mb"]) * 1024 * 1024:
            raise HTTPException(400, f"Files can be up to {s['max_file_mb']} MB")
        if D.used_bytes(ctx.db, ctx.bid) + len(data) > int(s["quota_mb"]) * 1024 * 1024:
            raise HTTPException(400, f"Storage full — this business can keep up to {s['quota_mb']} MB of files. Delete old files or save links instead.")
        doc.kind, doc.file_name, doc.file_ext = "FILE", file.filename[-200:], ext
        doc.content_type, doc.size_bytes = D.EXTENSIONS[ext], len(data)
        ctx.db.add(doc)
        ctx.db.flush()
        D.store(ctx.db, doc, data, s)
    elif url:
        if not s["allow_links"]:
            raise HTTPException(403, "Saving links is switched off by the platform administrator")
        url = url.strip()
        if not URL_RE.match(url) or len(url) > 1000:
            raise HTTPException(422, "Enter the full link, starting with https://")
        doc.kind, doc.url = "LINK", url
        ctx.db.add(doc)
    else:
        raise HTTPException(422, "Choose a file or paste a link")
    log(ctx.db, ctx.user, "CREATE", "document", f"Added document '{doc.title}'", entity_id=doc.id, business_id=ctx.bid, request=request)
    ctx.db.commit()
    return _out(doc)


class DocUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = "Other"
    financial_year: str | None = None
    doc_date: dt.date | None = None
    expiry_date: dt.date | None = None
    notes: str | None = Field(None, max_length=1000)
    url: str | None = None


@router.put("/documents/{doc_id}")
def update_document(doc_id: str, data: DocUpdate, ctx: BCtx):
    ctx.need("documents", "edit")
    d = _get(ctx, doc_id)
    d.title, d.category = data.title.strip(), data.category if data.category in D.CATEGORIES else "Other"
    d.financial_year, d.doc_date, d.expiry_date = _fy_ok(data.financial_year), data.doc_date, data.expiry_date
    d.notes = (data.notes or "").strip() or None
    if d.kind == "LINK" and data.url:
        if not URL_RE.match(data.url.strip()):
            raise HTTPException(422, "Enter the full link, starting with https://")
        d.url = data.url.strip()
    ctx.db.commit()
    return _out(d)


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str, ctx: BCtx, request: Request):
    ctx.need("documents", "delete")
    d = _get(ctx, doc_id)
    D.remove(ctx.db, d)
    log(ctx.db, ctx.user, "DELETE", "document", f"Deleted document '{d.title}'", entity_id=d.id, business_id=ctx.bid, request=request)
    ctx.db.delete(d)
    ctx.db.commit()


def _file_response(db, d: Document, download: bool):
    url = D.open_url(d)
    if url:
        return RedirectResponse(url, status_code=302)
    disp = "attachment" if download else "inline"
    return Response(D.read(db, d), media_type=d.content_type or "application/octet-stream",
                    headers={"Content-Disposition": f"{disp}; filename=\"{quote(d.file_name or 'document')}\"", "Cache-Control": "no-store",
                             "X-Content-Type-Options": "nosniff"})


@router.get("/documents/{doc_id}/file")
def get_file(doc_id: str, ctx: BCtx, download: bool = False):
    ctx.need("documents", "view")
    d = _get(ctx, doc_id)
    if d.kind != "FILE":
        raise HTTPException(400, "This document is a link")
    return _file_response(ctx.db, d, download)


def _share(ctx: BCtx, d: Document, request: Request) -> tuple[str, dt.datetime]:
    if d.kind == "LINK":
        return d.url, None
    days = int(D.settings(ctx.db)["share_days"] or 7)
    s = DocumentShare(token=secrets.token_urlsafe(24), document_id=d.id, business_id=ctx.bid, created_by=ctx.user.name,
                      expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=days))
    ctx.db.add(s)
    ctx.db.flush()
    return f"{frontend_url(request)}/api/public/documents/{s.token}", s.expires_at


@router.post("/documents/{doc_id}/share-link")
def share_link(doc_id: str, ctx: BCtx, request: Request):
    """A link anyone can open until it expires (files) — or the saved link itself (link documents)."""
    ctx.need("documents", "view")
    d = _get(ctx, doc_id)
    url, expires = _share(ctx, d, request)
    log(ctx.db, ctx.user, "ACTION", "document", f"Created a share link for '{d.title}'", entity_id=d.id, business_id=ctx.bid, request=request)
    ctx.db.commit()
    return {"url": url, "expires_at": expires}


class EmailIn(BaseModel):
    to: list[EmailStr] = Field(min_length=1, max_length=5)
    cc: list[EmailStr] = []
    message: str | None = Field(None, max_length=2000)
    attach: bool = True


@router.post("/documents/{doc_id}/email")
def email_document(doc_id: str, data: EmailIn, ctx: BCtx, request: Request):
    ctx.need("documents", "view")
    d = _get(ctx, doc_id)
    biz = ctx.business
    url, expires = _share(ctx, d, request)
    attachments = None
    if d.kind == "FILE" and data.attach and (d.size_bytes or 0) <= 10 * 1024 * 1024:
        attachments = [(d.file_name or "document", D.read(ctx.db, d), d.content_type or "application/octet-stream")]
    e = html.escape
    note = f"<p>{e(data.message).replace(chr(10), '<br>')}</p>" if data.message else ""
    until = f" (link valid till {expires:%d %b %Y})" if expires else ""
    body = mailer.layout(e(d.title), f"""<p>Hello,</p>{note}
        <p><b>{e(biz.name)}</b> has shared <b>{e(d.title)}</b>{f' ({e(d.financial_year)})' if d.financial_year else ''} with you.
        {'It is attached to this e-mail.' if attachments else ''}</p>
        <p style="text-align:center;margin:24px 0"><a href="{e(url)}" style="background:#1f65bb;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none">Open the document</a></p>
        <p style="font-size:12px;color:#6b7280">{e(until.strip(' ()').capitalize()) if until else ''}</p>""", footer=e(biz.name))
    cfg = mailer.business_smtp(ctx.db, ctx.bid, account_of(ctx.db, ctx.bid))
    mailer.send(cfg, [str(x) for x in data.to], f"{d.title} — from {biz.name}", body, cc=[str(x) for x in data.cc],
                reply_to=biz.email, attachments=attachments)
    log(ctx.db, ctx.user, "ACTION", "e-mail", f"E-mailed document '{d.title}' to {', '.join(map(str, data.to))}", entity_id=d.id,
        business_id=ctx.bid, request=request)
    ctx.db.commit()
    return {"sent": True, "via": cfg.source if cfg else None}


@router.get("/public/documents/{token}")
def public_document(token: str, db: DB):
    if len(token) < 20:
        raise HTTPException(404, "Link not found")
    s = db.get(DocumentShare, token)
    exp = s.expires_at.replace(tzinfo=dt.UTC) if s and s.expires_at.tzinfo is None else (s.expires_at if s else None)
    if not s or exp < dt.datetime.now(dt.UTC):
        raise HTTPException(404, "This link has expired — ask the sender for a new one")
    d = db.get(Document, s.document_id)
    if not d or d.kind != "FILE":
        raise HTTPException(404, "This document is no longer available")
    s.opened = (s.opened or 0) + 1
    db.commit()
    return _file_response(db, d, download=False)


# ---------------------------------------------------------------- super admin
class SettingsIn(BaseModel):
    enabled: bool | None = None
    allow_links: bool | None = None
    storage: str | None = None
    max_file_mb: int | None = Field(None, ge=1, le=100)
    quota_mb: int | None = Field(None, ge=1, le=100000)
    share_days: int | None = Field(None, ge=1, le=90)
    images_storage: str | None = None
    image_max_mb: int | None = Field(None, ge=1, le=20)


@router.get("/admin/documents-settings")
def get_admin_settings(db: DB, admin: SuperAdmin):
    from ..config import get_settings

    return {**D.settings(db), "cloudinary_configured": bool(get_settings().cloudinary_url)}


@router.put("/admin/documents-settings")
def put_admin_settings(data: SettingsIn, db: DB, admin: SuperAdmin, request: Request):
    out = D.save_settings(db, data.model_dump())
    log(db, admin, "CONFIG", "documents", f"Document vault settings: storage {out['storage']}, links {'on' if out['allow_links'] else 'off'}",
        request=request)
    db.commit()
    return out
