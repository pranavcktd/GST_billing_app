"""Bank branch details from an IFSC code (bank, branch, address, city, state) — fills bank forms, user can still edit.

Default source: Razorpay's free public IFSC API  GET {base_url}/{IFSC}  → JSON, 404 "Not Found" for unknown codes.
The super admin can switch it off or point it at another compatible service (Admin → Integrations).
The format is checked locally first; answers are cached (branch data hardly changes) and each user has an hourly limit.
"""

import re
import time

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import PlatformSetting

KEY = "ifsc_api"
DEFAULTS = dict(enabled=True, base_url="https://ifsc.razorpay.com", hourly_limit_user=100)
PATTERN = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
CACHE_SECONDS = 30 * 86400
_cache: dict[str, tuple[float, dict | None]] = {}
_calls: dict[str, list[float]] = {}


def settings(db: Session) -> dict:
    row = db.get(PlatformSetting, KEY)
    return {**DEFAULTS, **((row.value or {}) if row else {})}


def save_settings(db: Session, values: dict) -> dict:
    s = settings(db)
    for k in DEFAULTS:
        if values.get(k) is not None:
            s[k] = values[k]
    s["base_url"] = str(s["base_url"]).rstrip("/")
    row = db.get(PlatformSetting, KEY) or PlatformSetting(key=KEY)
    row.value = s
    db.add(row)
    db.commit()
    _cache.clear()
    return s


def valid(code: str) -> bool:
    return bool(PATTERN.match(code))


def _http_get(url: str) -> httpx.Response:
    """Single seam for tests."""
    return httpx.get(url, headers={"Accept": "application/json"}, timeout=10)


def lookup(db: Session, code: str, user_id: str) -> dict:
    code = (code or "").strip().upper()
    if not valid(code):
        raise HTTPException(422, "IFSC is 11 characters: 4 letters, a zero, then 6 letters or digits (e.g. HDFC0001234)")
    s = settings(db)
    if not s["enabled"]:
        raise HTTPException(503, "IFSC lookup is switched off — type the bank details yourself.")
    now = time.time()
    hit = _cache.get(code)
    if hit and now - hit[0] < CACHE_SECONDS:
        return _answer(code, hit[1])
    recent = [t for t in _calls.get(user_id, []) if now - t < 3600]
    if len(recent) >= int(s["hourly_limit_user"] or 100):
        raise HTTPException(429, "Too many IFSC lookups — try again in a while, or type the bank details yourself.")
    _calls[user_id] = recent + [now]
    try:
        r = _http_get(f"{s['base_url']}/{code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, "The IFSC service did not answer — type the bank details yourself.") from e
    if r.status_code == 404:
        data = None
    elif r.status_code >= 400:
        raise HTTPException(502, "The IFSC service did not answer — type the bank details yourself.")
    else:
        try:
            data = r.json()
        except ValueError:
            raise HTTPException(502, "The IFSC service gave an unreadable answer.") from None
        if not isinstance(data, dict):
            data = None
    if len(_cache) > 20000:
        _cache.clear()
    _cache[code] = (now, data)
    return _answer(code, data)


def _answer(code: str, d: dict | None) -> dict:
    if not d:
        raise HTTPException(404, f"No bank branch found for IFSC {code} — check the code")
    g = lambda *ks: next((str(d[k]).strip() for k in ks if d.get(k) not in (None, "")), None)  # noqa: E731
    return {"ifsc": code, "bank": g("BANK", "bank"), "branch": g("BRANCH", "branch"), "address": g("ADDRESS", "address"),
            "city": g("CITY", "city"), "district": g("DISTRICT", "district"), "state": g("STATE", "state"),
            "micr": g("MICR", "micr"), "swift": g("SWIFT", "swift"),
            "upi": bool(d.get("UPI")), "neft": bool(d.get("NEFT")), "rtgs": bool(d.get("RTGS")), "imps": bool(d.get("IMPS"))}
