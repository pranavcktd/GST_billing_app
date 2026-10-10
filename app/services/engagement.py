"""Website analytics and live chat settings (Admin → Analytics, Admin → Integrations → Live chat).

Analytics is first-party: the browser keeps a random id, we store the page, the referring site and the device type —
never the IP address — and nothing goes to a third party. Browsers that send "Do Not Track" are skipped when
respect_dnt is on.

Live chat uses tawk.to: the super admin pastes the property id and widget id (public values from tawk.to → Administration
→ Chat Widget). The optional secure-mode key (tawk.to → Administration → Property Settings → JavaScript API) lets the
chat know who a signed-in user is, so the agent sees their name and e-mail without asking.
"""

import hashlib
import hmac
import re

from sqlalchemy.orm import Session

from ..models import PlatformSetting
from ..security import decrypt_secret, encrypt_secret

KEY = "engagement"
DEFAULTS = {
    "analytics": {"enabled": True, "respect_dnt": True, "keep_days": 400},
    "live_chat": {"enabled": False, "provider": "TAWK", "property_id": "", "widget_id": "default", "show_on": "BOTH",
                  "pass_user": True, "secure_key_enc": None},
}
ID = re.compile(r"^[A-Za-z0-9]{1,40}$")


def get(db: Session) -> dict:
    row = db.get(PlatformSetting, KEY)
    saved = (row.value or {}) if row else {}
    return {k: {**v, **(saved.get(k) or {})} for k, v in DEFAULTS.items()}


def save(db: Session, analytics: dict | None = None, live_chat: dict | None = None) -> dict:
    cur = get(db)
    if analytics is not None:
        cur["analytics"].update({k: v for k, v in analytics.items() if k in DEFAULTS["analytics"]})
    if live_chat is not None:
        lc = {k: v for k, v in live_chat.items() if k in DEFAULTS["live_chat"] and k != "secure_key_enc"}
        for k in ("property_id", "widget_id"):
            if k in lc:
                lc[k] = (lc[k] or "").strip()
                if lc[k] and not ID.match(lc[k]):
                    raise ValueError(f"{k.replace('_', ' ')} should be letters and digits only, as shown in tawk.to")
        if "secure_key" in live_chat:
            key = (live_chat.get("secure_key") or "").strip()
            lc["secure_key_enc"] = encrypt_secret(key) if key else None
        cur["live_chat"].update(lc)
        if cur["live_chat"]["enabled"] and not cur["live_chat"]["property_id"]:
            raise ValueError("Enter the tawk.to property id before switching live chat on")
    row = db.get(PlatformSetting, KEY) or PlatformSetting(key=KEY)
    row.value = cur
    db.add(row)
    return cur


def public(db: Session) -> dict:
    """What every page needs (in /api/meta) — no secrets."""
    s = get(db)
    lc = s["live_chat"]
    return {"analytics": {"enabled": bool(s["analytics"]["enabled"]), "respect_dnt": bool(s["analytics"]["respect_dnt"])},
            "live_chat": {"enabled": bool(lc["enabled"] and lc["property_id"]), "provider": lc["provider"],
                          "property_id": lc["property_id"], "widget_id": lc["widget_id"] or "default",
                          "show_on": lc["show_on"], "pass_user": bool(lc["pass_user"]), "secure": bool(lc["secure_key_enc"])}}


def admin_view(db: Session) -> dict:
    s = get(db)
    lc = {k: v for k, v in s["live_chat"].items() if k != "secure_key_enc"}
    return {"analytics": s["analytics"], "live_chat": {**lc, "secure_key_set": bool(s["live_chat"]["secure_key_enc"])}}


def chat_hash(db: Session, email: str) -> str | None:
    """tawk.to secure mode: HMAC-SHA256 of the visitor's e-mail with the property's API key."""
    enc = get(db)["live_chat"].get("secure_key_enc")
    if not enc:
        return None
    return hmac.new(decrypt_secret(enc).encode(), email.encode(), hashlib.sha256).hexdigest()
