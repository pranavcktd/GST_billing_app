"""Image uploads (logo, signature, item photos).

Where they are kept is chosen by the super admin (Admin → Integrations → File storage), like the document vault:
    CLOUDINARY — Cloudinary (resized there); the image URL is Cloudinary's
    DATABASE   — our database (resized here to at most 1200 px); served from /api/files/img/<id>.<ext>
Logos and signatures appear on invoices that customers open without signing in, so image links are public
(but unguessable); private papers belong in the document vault instead.
"""

import io
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from ..config import get_settings
from ..deps import DB, BCtx
from ..models import ImageFile
from ..services import documents as D

router = APIRouter(tags=["uploads"])

ALLOWED = {"image/png", "image/jpeg", "image/webp"}
MAX_SIDE = 1200

_configured = False


def _configure() -> None:
    global _configured
    url = get_settings().cloudinary_url
    if not url:
        raise HTTPException(503, "Cloud storage is not configured on the server — the platform administrator can "
                                 "switch image storage to 'Our database' in Admin > Integrations > File storage")
    if not _configured:
        import cloudinary

        cloudinary.config(cloudinary_url=url, secure=True)
        _configured = True


def _shrink(data: bytes) -> tuple[bytes, str, str]:
    """At most 1200 px on the longer side; PNG when the image has transparency (logos, signatures), else JPEG."""
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    img.load()
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P"):
        img.save(out, "PNG", optimize=True)
        return out.getvalue(), "image/png", "png"
    img.convert("RGB").save(out, "JPEG", quality=85, optimize=True)
    return out.getvalue(), "image/jpeg", "jpg"


@router.post("/uploads")
async def upload_image(
    ctx: BCtx,
    file: UploadFile = File(...),
    kind: Literal["logo", "signature", "item"] = Form(...),
):
    ctx.need("items" if kind == "item" else "settings", "edit")
    if file.content_type not in ALLOWED:
        raise HTTPException(400, "Only PNG, JPEG or WEBP images are allowed")
    data = await file.read()
    s = D.settings(ctx.db)
    limit = int(s.get("image_max_mb") or 2)
    if len(data) > limit * 1024 * 1024:
        raise HTTPException(400, f"Image must be {limit} MB or smaller")
    storage = s.get("images_storage") or "CLOUDINARY"
    if storage == "DATABASE":
        try:
            blob, ctype, ext = _shrink(data)
        except Exception:  # noqa: BLE001 — not a readable image
            raise HTTPException(400, "This file is not a readable image") from None
        row = ImageFile(business_id=ctx.bid, kind=kind, content_type=ctype, ext=ext, data=blob)
        ctx.db.add(row)
        ctx.db.commit()
        return {"url": f"/api/files/img/{row.id}.{ext}", "public_id": row.id}
    _configure()
    import cloudinary.uploader

    result = cloudinary.uploader.upload(
        data,
        folder=f"{get_settings().cloudinary_folder}/{ctx.bid}/{kind}",
        resource_type="image",
        transformation=[{"width": MAX_SIDE, "height": MAX_SIDE, "crop": "limit", "quality": "auto"}],
    )
    return {"url": result["secure_url"], "public_id": result["public_id"]}


@router.get("/files/img/{name}")
def serve_image(name: str, db: DB):
    """Images kept in our database (logos, signatures, item photos)."""
    image_id = name.split(".", 1)[0]
    row = db.get(ImageFile, image_id) if len(image_id) == 32 else None
    if row is None:
        raise HTTPException(404, "Image not found")
    return Response(row.data, media_type=row.content_type,
                    headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"})


def load_local(url: str, db=None) -> bytes | None:
    """Bytes of an image kept in our database, from its /api/files/img/... URL (used by the PDF renderer)."""
    if "/api/files/img/" not in url:
        return None
    image_id = url.rsplit("/", 1)[1].split(".", 1)[0]
    if db is not None:
        row = db.get(ImageFile, image_id)
        return bytes(row.data) if row else None
    from ..db import SessionLocal

    with SessionLocal() as own:
        row = own.get(ImageFile, image_id)
        return bytes(row.data) if row else None
