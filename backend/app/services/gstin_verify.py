"""GSTIN verification & autofill through gstinapi.in (settings managed by the super admin).

Cost control
  * The API is called only when a user clicks "Verify & autofill" — typing a GSTIN never calls it.
  * Format + checksum are checked locally first (a wrong GSTIN never reaches the paid API).
  * Answers are cached: the same GSTIN within `cache_days` is served from our database for free.
  * Daily limits per business and per user; an optional minimum plan.
  * Failed calls (not found, provider down) are not charged by gstinapi.in.

Settings: platform_settings["gstin_api"] = {enabled, base_url, api_key_enc, cache_days,
daily_limit_business, daily_limit_user, min_plan}
"""

import datetime as dt
import re
import time

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..gst.gstin import validate_gstin
from ..gst.states import STATES
from ..models import GstinLookup, PlatformSetting, User
from ..security import decrypt_secret, encrypt_secret

KEY = "gstin_api"
DEFAULTS = dict(enabled=False, base_url="https://gstinapi.in", api_key_enc=None, cache_days=30,
                daily_limit_business=50, daily_limit_user=100, min_plan="FREE")


# ================================================================ settings
def settings(db: Session) -> dict:
    row = db.get(PlatformSetting, KEY)
    return {**DEFAULTS, **((row.value or {}) if row else {})}


def public_settings(db: Session) -> dict:
    s = settings(db)
    key = _key(s)
    return {k: v for k, v in s.items() if k != "api_key_enc"} | {
        "api_key_set": bool(key), "api_key_hint": f"{key[:6]}…{key[-4:]}" if key and len(key) > 12 else None}


def save_settings(db: Session, values: dict) -> dict:
    s = settings(db)
    for k in ("enabled", "base_url", "cache_days", "daily_limit_business", "daily_limit_user", "min_plan"):
        if k in values and values[k] is not None:
            s[k] = values[k]
    if values.get("api_key"):
        s["api_key_enc"] = encrypt_secret(values["api_key"].strip())
    if values.get("clear_api_key"):
        s["api_key_enc"] = None
    s["base_url"] = str(s["base_url"]).rstrip("/")
    row = db.get(PlatformSetting, KEY) or PlatformSetting(key=KEY)
    row.value = s
    db.add(row)
    db.commit()
    return public_settings(db)


def _key(s: dict) -> str | None:
    try:
        return decrypt_secret(s["api_key_enc"]) if s.get("api_key_enc") else None
    except Exception:  # noqa: BLE001 — key encrypted with an old secret
        return None


# ================================================================ provider call
def _http_get(url: str, key: str) -> httpx.Response:
    """Single seam for tests."""
    return httpx.get(url, headers={"x-api-key": key, "Accept": "application/json"}, timeout=15)


class ProviderError(Exception):
    def __init__(self, status: int | None, message: str):
        super().__init__(message)
        self.status = status


FRIENDLY = {
    400: "The GST portal did not accept this GSTIN format.",
    401: "GSTIN verification is not set up correctly (API key). Please fill the details manually.",
    402: "GSTIN verification is temporarily unavailable. Please fill the details manually.",
    403: "GSTIN verification is temporarily unavailable. Please fill the details manually.",
    404: "This GSTIN is not registered on the GST portal. Please check the number.",
    429: "Too many verifications right now — please try again in a minute.",
    502: "The GST portal is not responding right now — please try again shortly, or fill the details manually.",
}


def _call(s: dict, path: str) -> tuple[dict, int]:
    key = _key(s)
    if not key:
        raise ProviderError(None, "no API key")
    url = f"{s['base_url']}/v1/{path.lstrip('/')}"
    last = None
    for attempt in range(3):
        try:
            r = _http_get(url, key)
        except httpx.HTTPError as e:
            last = ProviderError(502, f"network: {e}")
        else:
            try:
                body = r.json()
            except ValueError:
                body = {}
            if r.status_code == 200:
                return body, 200
            msg = (body.get("error") or body.get("message") or r.text or "")[:200] if isinstance(body, dict) else str(body)[:200]
            last = ProviderError(r.status_code, msg)
            if r.status_code not in (429, 502, 503, 504):
                break  # never retry 400/401/402/403/404 (provider's guidance)
        if attempt < 2:
            time.sleep(0.5 * 2 ** attempt)
    raise last


# ================================================================ normalising
PARTY_TYPE = [("sez", "SEZ"), ("composition", "COMPOSITION")]


def _city_from(address: str | None, state: str | None) -> str | None:
    if not address:
        return None
    parts = [p.strip() for p in re.split(r",", address) if p.strip()]
    for p in reversed(parts):
        p2 = re.sub(r"\b\d{6}\b", "", p).strip(" -")
        if p2 and (not state or p2.lower() != state.lower()) and not p2.isdigit() and len(p2) <= 40:
            return p2.title() if p2.isupper() else p2
    return None


def normalise(raw: dict, gstin: str) -> dict:
    d = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    state_code = str(d.get("state_code") or gstin[:2]).zfill(2)
    address = d.get("address")
    pincode = d.get("pincode")
    if not pincode and address:
        m = re.search(r"\b(\d{6})\b", address)
        pincode = m.group(1) if m else None
    taxpayer = (d.get("taxpayer_type") or "").strip()
    party_type = next((v for k, v in PARTY_TYPE if k in taxpayer.lower()), "REGISTERED")
    status = (d.get("status") or "").strip()
    return dict(
        gstin=(d.get("gstin") or gstin).upper(), legal_name=d.get("legal_name"), trade_name=d.get("trade_name"),
        status=status, active=status.lower() == "active", taxpayer_type=taxpayer or None,
        constitution=d.get("business_constitution"), registration_date=d.get("registration_date"),
        cancellation_date=d.get("cancellation_date"), state_code=state_code, state=STATES.get(state_code),
        jurisdiction=d.get("state_jurisdiction"), address=address, pincode=pincode,
        city=_city_from(address, STATES.get(state_code)), nature_of_business=d.get("nature_of_business") or [],
        block_status=d.get("block_status"), pan=gstin[2:12],
        party_gst_type=party_type, business_gst_type="COMPOSITION" if party_type == "COMPOSITION" else "REGULAR",
    )


# ================================================================ verify
def _count_today(db: Session, **where) -> int:
    start = dt.datetime.combine(dt.date.today(), dt.time.min, tzinfo=dt.UTC)
    q = select(func.count()).select_from(GstinLookup).where(GstinLookup.source == "LIVE", GstinLookup.created_at >= start)
    for k, v in where.items():
        q = q.where(getattr(GstinLookup, k) == v)
    return db.scalar(q) or 0


def verify(db: Session, user: User, business_id: str | None, gstin: str, refresh: bool = False) -> dict:
    gstin = (gstin or "").strip().upper()
    err = validate_gstin(gstin)
    if err:
        raise HTTPException(422, err)  # checked locally: no API cost
    s = settings(db)
    if not s["enabled"] or not _key(s):
        raise HTTPException(503, "GSTIN verification is not available yet — please fill the details manually.")
    if business_id and s.get("min_plan") and s["min_plan"] != "FREE":
        from . import plans as P
        plan = P.business_plan(db, business_id)
        if P.rank(plan["code"]) < P.rank(s["min_plan"]):
            raise P.UpgradeRequired(f"GSTIN verification is available from the {P.PLANS[s['min_plan']]['name']} plan",
                                    s["min_plan"])

    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=int(s["cache_days"]))
    cached = None if refresh else db.scalar(
        select(GstinLookup).where(GstinLookup.gstin == gstin, GstinLookup.ok.is_(True), GstinLookup.source == "LIVE",
                                  GstinLookup.created_at >= since).order_by(GstinLookup.created_at.desc()).limit(1))
    if cached is not None:
        db.add(GstinLookup(gstin=gstin, user_id=user.id, business_id=business_id, source="CACHE", ok=True, data=cached.data))
        db.commit()
        return {**cached.data, "source": "cache", "fetched_at": cached.created_at}

    if business_id and _count_today(db, business_id=business_id) >= int(s["daily_limit_business"]):
        raise HTTPException(429, "Today's GSTIN verification limit for this business is reached — please fill the details manually.")
    if _count_today(db, user_id=user.id) >= int(s["daily_limit_user"]):
        raise HTTPException(429, "Today's GSTIN verification limit is reached — please fill the details manually.")

    log = GstinLookup(gstin=gstin, user_id=user.id, business_id=business_id, source="LIVE")
    try:
        raw, status = _call(s, f"gstin/{gstin}")
    except ProviderError as e:
        log.ok, log.http_status, log.error = False, e.status, str(e)[:300]
        db.add(log)
        db.commit()
        raise HTTPException(404 if e.status == 404 else 502 if e.status not in (429,) else 429,
                            FRIENDLY.get(e.status or 0, "GSTIN verification failed — please fill the details manually.")) from None
    data = normalise(raw, gstin)
    credits = raw.get("credits_remaining") if isinstance(raw, dict) else None
    log.ok, log.http_status, log.data = True, status, data
    log.credits_remaining = int(credits) if isinstance(credits, (int, float)) else None
    db.add(log)
    db.commit()
    return {**data, "source": "live", "fetched_at": log.created_at}


# ================================================================ admin
def provider_stats(db: Session) -> dict:
    """gstinapi.in usage endpoint (free) — used by 'Test connection'."""
    s = settings(db)
    try:
        body, _ = _call(s, "gstin/stats/me")
        return {"ok": True, "stats": body}
    except ProviderError as e:
        return {"ok": False, "status": e.status, "error": FRIENDLY.get(e.status or 0, str(e)), "detail": str(e)}


def usage(db: Session, days: int = 30) -> dict:
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    rows = db.execute(select(GstinLookup.source, GstinLookup.ok, func.count()).where(GstinLookup.created_at >= since)
                      .group_by(GstinLookup.source, GstinLookup.ok)).all()
    agg = {"live_ok": 0, "live_failed": 0, "cache": 0}
    for source, ok, n in rows:
        key = "cache" if source == "CACHE" else "live_ok" if ok else "live_failed"
        agg[key] += n
    last_credits = db.scalar(select(GstinLookup.credits_remaining).where(GstinLookup.credits_remaining.is_not(None))
                             .order_by(GstinLookup.created_at.desc()).limit(1))
    recent = db.scalars(select(GstinLookup).order_by(GstinLookup.created_at.desc()).limit(50)).all()
    return {**agg, "days": days, "credits_remaining": last_credits,
            "saved_by_cache_pct": round(100 * agg["cache"] / max(1, agg["cache"] + agg["live_ok"])),
            "recent": [dict(gstin=r.gstin, source=r.source, ok=r.ok, http_status=r.http_status, error=r.error,
                            name=(r.data or {}).get("legal_name"), business_id=r.business_id, at=r.created_at) for r in recent]}
