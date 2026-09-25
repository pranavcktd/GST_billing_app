"""GSTIN verification & autofill (user) and its settings (super admin)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import DB, CurrentUser, SuperAdmin
from ..models import Membership
from ..services import gstin_verify as G
from ..services.platform_audit import log

router = APIRouter(tags=["gstin"])


class VerifyIn(BaseModel):
    gstin: str = Field(min_length=15, max_length=15)
    refresh: bool = False  # bypass the cache (costs a credit)


@router.post("/gstin/verify")
def verify(data: VerifyIn, db: DB, user: CurrentUser, x_business_id: Annotated[str | None, Header()] = None):
    """Works during onboarding too (no business yet); inside a business the business's limits apply."""
    bid = None
    if x_business_id:
        m = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.business_id == x_business_id))
        if m is None:
            raise HTTPException(403, "You do not have access to this business")
        bid = x_business_id
    return G.verify(db, user, bid, data.gstin, data.refresh)


@router.get("/gstin/available")
def available(db: DB, user: CurrentUser):
    s = G.settings(db)
    return {"enabled": bool(s["enabled"] and G._key(s))}


# ---------------------------------------------------------------- super admin
class SettingsIn(BaseModel):
    enabled: bool | None = None
    base_url: str | None = Field(None, pattern=r"^https://[\w.-]+(:\d+)?(/[\w./-]*)?$")
    api_key: str | None = Field(None, max_length=300)
    clear_api_key: bool = False
    cache_days: int | None = Field(None, ge=0, le=365)
    daily_limit_business: int | None = Field(None, ge=0, le=100000)
    daily_limit_user: int | None = Field(None, ge=0, le=100000)
    min_plan: Literal["FREE", "STARTER", "PROFESSIONAL", "ENTERPRISE"] | None = None
    trial_live_limit: int | None = Field(None, ge=0, le=1000)  # paid lookups per trial / free account (lifetime)


@router.get("/admin/gstin-api")
def get_settings(db: DB, admin: SuperAdmin):
    return {"settings": G.public_settings(db), "usage": G.usage(db)}


@router.put("/admin/gstin-api")
def put_settings(data: SettingsIn, db: DB, admin: SuperAdmin, request: Request):
    out = G.save_settings(db, data.model_dump())
    changed = [k for k, v in data.model_dump().items() if v not in (None, False)]
    log(db, admin, "CONFIG", "gstin-api", "GSTIN API settings: " + ", ".join("api_key" if k == "api_key" else k for k in changed),
        request=request)
    db.commit()
    return {"settings": out, "usage": G.usage(db)}


@router.post("/admin/gstin-api/test")
def test_connection(db: DB, admin: SuperAdmin):
    return G.provider_stats(db)


class StatusIn(BaseModel):
    gstins: list[str] = Field(default_factory=list, max_length=500)


@router.post("/gstin/status")
def status(data: StatusIn, db: DB, user: CurrentUser):
    """Free: has this GSTIN been verified on this platform before, and what was the result?"""
    found = G.last_status(db, data.gstins)
    return {g.strip().upper(): found.get(g.strip().upper(), {"verified": False}) for g in data.gstins if g}
