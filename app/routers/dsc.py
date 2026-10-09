"""Digital signature certificate of the business (Settings → Digital signature). See services/dsc.py."""

from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from ..deps import MANAGERS, BCtx
from ..models import BusinessCertificate
from ..services import dsc
from ..services.platform_audit import log

router = APIRouter(prefix="/dsc", tags=["digital signature"])


@router.get("")
def get_dsc(ctx: BCtx):
    return dsc.status(ctx.db.get(BusinessCertificate, ctx.bid))


@router.post("")
async def upload_dsc(ctx: BCtx, request: Request, file: UploadFile = File(...), password: str = Form(""),
                     mode: Literal["AUTO", "ON_REQUEST"] = Form("AUTO")):
    ctx.require(*MANAGERS)
    ctx.need("settings", "edit")
    row = dsc.save(ctx.db, ctx.bid, await file.read(), password, mode, ctx.user.name)
    log(ctx.db, ctx.user, "CONFIG", "dsc", f"Digital signature certificate added: {row.subject} (valid till {row.not_after:%d %b %Y})",
        business_id=ctx.bid, request=request)
    ctx.db.commit()
    return dsc.status(row)


class ModeIn(BaseModel):
    mode: Literal["AUTO", "ON_REQUEST"]


@router.put("/mode")
def set_mode(data: ModeIn, ctx: BCtx):
    ctx.require(*MANAGERS)
    row = ctx.db.get(BusinessCertificate, ctx.bid)
    if not row:
        raise HTTPException(404, "No certificate added")
    row.mode = data.mode
    ctx.db.commit()
    return dsc.status(row)


@router.delete("", status_code=204)
def remove_dsc(ctx: BCtx, request: Request):
    ctx.require(*MANAGERS)
    row = ctx.db.get(BusinessCertificate, ctx.bid)
    if row:
        log(ctx.db, ctx.user, "DELETE", "dsc", f"Digital signature certificate removed: {row.subject}", business_id=ctx.bid, request=request)
        ctx.db.delete(row)
        ctx.db.commit()
