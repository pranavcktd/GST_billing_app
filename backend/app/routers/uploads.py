"""Image uploads (logo, signature, item photos) to Cloudinary."""

from typing import Literal

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import get_settings
from ..deps import BCtx

router = APIRouter(prefix="/uploads", tags=["uploads"])

MAX_BYTES = 2 * 1024 * 1024
ALLOWED = {"image/png", "image/jpeg", "image/webp"}

_configured = False


def _configure() -> None:
    global _configured
    url = get_settings().cloudinary_url
    if not url:
        raise HTTPException(503, "File storage is not configured (set CLOUDINARY_URL)")
    if not _configured:
        cloudinary.config(cloudinary_url=url, secure=True)
        _configured = True


@router.post("")
async def upload_image(
    ctx: BCtx,
    file: UploadFile = File(...),
    kind: Literal["logo", "signature", "item"] = Form(...),
):
    ctx.need("items" if kind == "item" else "settings", "edit")
    _configure()
    if file.content_type not in ALLOWED:
        raise HTTPException(400, "Only PNG, JPEG or WEBP images are allowed")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(400, "Image must be 2 MB or smaller")
    result = cloudinary.uploader.upload(
        data,
        folder=f"{get_settings().cloudinary_folder}/{ctx.bid}/{kind}",
        resource_type="image",
        transformation=[{"width": 1200, "height": 1200, "crop": "limit", "quality": "auto"}],
    )
    return {"url": result["secure_url"], "public_id": result["public_id"]}
