"""Razorpay settings managed by the super admin (Admin → Integrations), with Test and Live key sets.

platform_settings["razorpay"] = {
    "mode": "TEST" | "LIVE",
    "TEST": {"key_id", "key_secret_enc", "webhook_secret_enc"},
    "LIVE": {...},
}
Keys in backend/.env (RAZORPAY_KEY_ID / _KEY_SECRET / _WEBHOOK_SECRET) are used when nothing is
saved in the admin panel. Test-mode payments are marked TEST and never count as revenue.
"""

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import PlatformSetting
from ..security import decrypt_secret, encrypt_secret

KEY = "razorpay"
API = "https://api.razorpay.com/v1"


def _raw(db: Session) -> dict:
    row = db.get(PlatformSetting, KEY)
    return dict(row.value or {}) if row else {}


def _dec(v: str | None) -> str | None:
    try:
        return decrypt_secret(v) if v else None
    except Exception:  # noqa: BLE001 — encrypted with an old secret
        return None


def creds(db: Session) -> dict | None:
    """{mode, key_id, key_secret, webhook_secret} for the active mode, or None when not configured."""
    raw = _raw(db)
    mode = raw.get("mode") or "TEST"
    k = raw.get(mode) or {}
    if k.get("key_id") and k.get("key_secret_enc"):
        secret = _dec(k["key_secret_enc"])
        if secret:
            return dict(mode=mode, key_id=k["key_id"], key_secret=secret, webhook_secret=_dec(k.get("webhook_secret_enc")),
                        source="admin")
    s = get_settings()
    if s.razorpay_key_id and s.razorpay_key_secret:
        return dict(mode="TEST" if s.razorpay_key_id.startswith("rzp_test_") else "LIVE", key_id=s.razorpay_key_id,
                    key_secret=s.razorpay_key_secret, webhook_secret=s.razorpay_webhook_secret, source="env")
    return None


def webhook_secrets(db: Session) -> list[str]:
    """Every configured webhook secret (Test and Live), so events from either mode are accepted."""
    raw = _raw(db)
    out = [_dec((raw.get(m) or {}).get("webhook_secret_enc")) for m in ("TEST", "LIVE")]
    out.append(get_settings().razorpay_webhook_secret)
    return [x for x in out if x]


def public(db: Session) -> dict:
    raw = _raw(db)
    active = creds(db)

    def side(m: str) -> dict:
        k = raw.get(m) or {}
        return dict(key_id=k.get("key_id"), key_secret_set=bool(k.get("key_secret_enc")),
                    webhook_secret_set=bool(k.get("webhook_secret_enc")))
    return dict(mode=raw.get("mode") or "TEST", TEST=side("TEST"), LIVE=side("LIVE"),
                active=dict(mode=active["mode"], key_id=active["key_id"], source=active["source"],
                            webhook=bool(active["webhook_secret"])) if active else None)


def save(db: Session, values: dict) -> dict:
    raw = _raw(db)
    if values.get("mode") in ("TEST", "LIVE"):
        raw["mode"] = values["mode"]
    for m in ("TEST", "LIVE"):
        v = values.get(m) or {}
        k = dict(raw.get(m) or {})
        if v.get("key_id") is not None:
            kid = v["key_id"].strip()
            want = "rzp_test_" if m == "TEST" else "rzp_live_"
            if kid and not kid.startswith(want):
                raise ValueError(f"{m.title()} key id must start with {want}")
            k["key_id"] = kid or None
        if v.get("key_secret"):
            k["key_secret_enc"] = encrypt_secret(v["key_secret"].strip())
        if v.get("webhook_secret"):
            k["webhook_secret_enc"] = encrypt_secret(v["webhook_secret"].strip())
        if v.get("clear"):
            k = {}
        raw[m] = k
    row = db.get(PlatformSetting, KEY) or PlatformSetting(key=KEY)
    row.value = raw
    db.add(row)
    db.commit()
    return public(db)


# ---------------------------------------------------------------- API calls (single seam for tests)
def request(method: str, path: str, c: dict, **kw) -> httpx.Response:
    return httpx.request(method, f"{API}{path}", auth=(c["key_id"], c["key_secret"]), timeout=20, **kw)


def test_connection(db: Session) -> dict:
    c = creds(db)
    if not c:
        return {"ok": False, "error": "No Razorpay keys saved for the selected mode"}
    try:
        r = request("GET", "/orders?count=1", c)
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"Could not reach Razorpay: {e}"}
    if r.status_code == 200:
        return {"ok": True, "mode": c["mode"], "key_id": c["key_id"]}
    try:
        msg = r.json().get("error", {}).get("description") or r.text
    except ValueError:
        msg = r.text
    return {"ok": False, "status": r.status_code, "error": msg[:200]}
