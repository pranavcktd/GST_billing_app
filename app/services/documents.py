"""Document vault: a business keeps important papers (ITR, balance sheet, audit report, GST / FSSAI / Udyam
certificates, licences, agreements, bills…) as uploaded files or as links to where they already live (Google Drive…).

Storage (chosen by the super admin, Admin → Integrations → Document vault):
    LINKS       — only links are allowed; nothing is stored by us
    CLOUDINARY  — files go to Cloudinary as *private* assets; every open / share gets a short-lived signed URL
    DATABASE    — files are kept in our database (for testing or small installations)
Files are never public: they open only for signed-in staff with the Documents permission, or through a share
link that expires (default 7 days).

Settings: platform_settings["documents"].
"""

import datetime as dt
import secrets
import time

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Document, DocumentBlob, PlatformSetting

KEY = "documents"
STORAGES = ("LINKS", "CLOUDINARY", "DATABASE")
CATEGORIES = [
    "Income-tax return & computation", "Balance sheet / P&L", "Tax audit report", "GST registration & returns",
    "FSSAI licence", "Udyam / MSME", "PAN / TAN", "Shop & trade licence", "Company / LLP documents",
    "Bank statements", "Bills & invoices", "Agreements & deeds", "Insurance", "Other",
]
EXTENSIONS = {
    "pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp",
    "doc": "application/msword", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv", "txt": "text/plain", "zip": "application/zip",
}


def defaults() -> dict:
    return dict(enabled=True, allow_links=True, storage="CLOUDINARY" if get_settings().cloudinary_url else "DATABASE",
                max_file_mb=10, quota_mb=200, share_days=7)


def settings(db: Session) -> dict:
    row = db.get(PlatformSetting, KEY)
    return {**defaults(), **((row.value or {}) if row else {})}


def save_settings(db: Session, values: dict) -> dict:
    s = settings(db)
    s.update({k: v for k, v in values.items() if v is not None and k in defaults()})
    if s["storage"] not in STORAGES:
        raise HTTPException(422, "Unknown storage")
    if s["storage"] == "CLOUDINARY" and not get_settings().cloudinary_url:
        raise HTTPException(422, "Cloudinary is not configured on the server (CLOUDINARY_URL) — choose Database or Links only")
    row = db.get(PlatformSetting, KEY) or PlatformSetting(key=KEY)
    row.value = s
    db.add(row)
    db.commit()
    return s


def can_upload(s: dict) -> bool:
    return bool(s["enabled"]) and s["storage"] in ("CLOUDINARY", "DATABASE")


def used_bytes(db: Session, business_id: str) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
        Document.business_id == business_id, Document.kind == "FILE")) or 0)


# ================================================================ storing files
def _cloudinary():
    import cloudinary

    cloudinary.config(cloudinary_url=get_settings().cloudinary_url, secure=True)
    import cloudinary.uploader
    import cloudinary.utils

    return cloudinary


def store(db: Session, doc: Document, data: bytes, s: dict) -> None:
    if s["storage"] == "DATABASE":
        doc.storage = "DATABASE"
        db.add(DocumentBlob(document_id=doc.id, data=data))
        return
    cl = _cloudinary()
    res = cl.uploader.upload(data, resource_type="raw", type="private",
                             folder=f"{get_settings().cloudinary_folder}/{doc.business_id}/documents",
                             public_id=f"{doc.id}-{secrets.token_hex(4)}.{doc.file_ext}", use_filename=False)
    doc.storage, doc.storage_id = "CLOUDINARY", res["public_id"]


def _signed_url(doc: Document, minutes: int = 10) -> str:
    cl = _cloudinary()
    return cl.utils.private_download_url(doc.storage_id, "", resource_type="raw", type="private",
                                         expires_at=int(time.time()) + minutes * 60, attachment=False)


def read(db: Session, doc: Document) -> bytes:
    if doc.storage == "DATABASE":
        blob = db.get(DocumentBlob, doc.id)
        if not blob:
            raise HTTPException(404, "File not found")
        return blob.data
    import httpx

    r = httpx.get(_signed_url(doc), timeout=60)
    if r.status_code != 200:
        raise HTTPException(502, "Could not fetch the file from storage")
    return r.content


def open_url(doc: Document) -> str | None:
    """A short-lived direct URL (cloud storage); None when the file is served by us."""
    return _signed_url(doc) if doc.storage == "CLOUDINARY" else None


def remove(db: Session, doc: Document) -> None:
    if doc.storage == "CLOUDINARY" and doc.storage_id:
        try:
            _cloudinary().uploader.destroy(doc.storage_id, resource_type="raw", type="private")
        except Exception:  # noqa: BLE001 — the record goes anyway; an orphan file is harmless
            pass


def expiry_status(doc: Document, today: dt.date | None = None) -> str | None:
    if not doc.expiry_date:
        return None
    days = (doc.expiry_date - (today or dt.date.today())).days
    return "EXPIRED" if days < 0 else "EXPIRING" if days <= 30 else None
