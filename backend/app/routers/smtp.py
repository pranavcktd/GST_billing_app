"""Business view of its e-mail: which address its e-mails go from, and a test. Senders are managed by the super admin
(routers/mail.py); businesses cannot set up e-mail themselves."""

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from ..deps import BCtx
from ..services import config_store, mailer

router = APIRouter(tags=["email"])


class TestIn(BaseModel):
    to: EmailStr


@router.get("/smtp")
def business_get(ctx: BCtx):
    """Which address this business's e-mails go from. E-mail is managed by the platform (Admin → Email)."""
    cfg = mailer.business_smtp(ctx.db, ctx.bid)
    return {"managed": True, "effective_source": cfg.source if cfg else None, "from_email": cfg.from_email if cfg else None,
            "from_name": cfg.from_name if cfg else None, "reply_to": cfg.reply_to if cfg else None,
            "own_sender": cfg is not None and cfg.source == "BUSINESS"}


@router.post("/smtp/test")
def business_test(data: TestIn, ctx: BCtx):
    ctx.need("settings", "view")
    cfg = mailer.business_smtp(ctx.db, ctx.bid)
    mailer.send(cfg, [str(data.to)], f"Test e-mail from {config_store.app_name()}",
                mailer.layout("It works!", f"<p>This test e-mail was sent for {ctx.business.name}.</p>"))
    return {"sent": True, "via": cfg.source if cfg else None}
