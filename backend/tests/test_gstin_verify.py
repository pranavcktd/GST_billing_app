"""GSTIN verification & autofill: settings, local checks, cache, limits, provider errors (fake provider)."""

import httpx

from app.services import gstin_verify as G
from tests.test_api_flow import make_business, signup
from tests.test_modules import gstin, post
from tests.test_security_admin import superadmin

GOOD = gstin("24", "AAKPV8888P")
CALLS: list[str] = []


def fake_provider(monkeypatch, status=200, body=None):
    CALLS.clear()

    def get(url, key):
        CALLS.append(url)
        assert key == "gak_test_key_123456"
        if url.endswith("/stats/me"):
            return httpx.Response(200, json={"credits_remaining": 97, "used": 3})
        return httpx.Response(status, json=body if body is not None else {
            "gstin": url.rsplit("/", 1)[1], "legal_name": "HARILAL SAVAJIBHAI VAGHASIA", "trade_name": "CHANDNI SOFT SERVICES",
            "status": "Active", "taxpayer_type": "Regular", "business_constitution": "Proprietorship", "state_code": "24",
            "registration_date": "2020-10-01", "cancellation_date": None,
            "address": "Shop No.204, 2nd Floor, Citadell, SURAT, Gujarat, 395007", "pincode": None,
            "nature_of_business": ["Retail Business"], "block_status": "U", "credits_remaining": 99})

    monkeypatch.setattr(G, "_http_get", get)
    monkeypatch.setattr(G.time, "sleep", lambda s: None)


def enable(client, root, **extra):
    extra.setdefault("trial_live_limit", 100)  # tests below use trial accounts; the trial cap has its own test
    r = client.put("/api/admin/gstin-api", headers=root, json={"enabled": True, "api_key": "gak_test_key_123456", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_verify_autofill_cache_and_limits(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    user = signup(client)
    fake_provider(monkeypatch)

    # not configured yet → friendly 503, no call
    assert client.post("/api/gstin/verify", headers=user, json={"gstin": GOOD}).status_code == 503
    assert client.get("/api/gstin/available", headers=user).json() == {"enabled": False}

    s = enable(client, root)["settings"]
    assert s["api_key_set"] and s["api_key_hint"] == "gak_te…3456" and "api_key_enc" not in s
    assert client.get("/api/gstin/available", headers=user).json() == {"enabled": True}
    assert client.put("/api/admin/gstin-api", headers=user, json={"enabled": False}).status_code == 403

    # a wrong checksum is rejected locally — no paid call
    bad = GOOD[:14] + ("A" if GOOD[14] != "A" else "B")
    r = client.post("/api/gstin/verify", headers=user, json={"gstin": bad})
    assert r.status_code == 422 and CALLS == []

    # onboarding (no business yet)
    d = post(client, user, "/api/gstin/verify", {"gstin": GOOD.lower()}, 200)
    assert d["source"] == "live" and d["legal_name"] == "HARILAL SAVAJIBHAI VAGHASIA" and d["active"]
    assert d["pincode"] == "395007" and d["city"] == "Surat" and d["state"] == "Gujarat"
    assert d["party_gst_type"] == "REGISTERED" and d["business_gst_type"] == "REGULAR" and d["pan"] == "AAKPV8888P"
    assert CALLS == [f"https://gstinapi.in/v1/gstin/{GOOD}"]

    # second time: served from the cache, free
    h = make_business(client, user, gstin=GOOD, state_code="24")
    assert post(client, h, "/api/gstin/verify", {"gstin": GOOD}, 200)["source"] == "cache"
    assert len(CALLS) == 1
    # forced refresh calls again
    assert post(client, h, "/api/gstin/verify", {"gstin": GOOD, "refresh": True}, 200)["source"] == "live"
    assert len(CALLS) == 2

    # daily limit per business
    enable(client, root, daily_limit_business=1)
    other = gstin("27", "AABCS1429B")
    r = client.post("/api/gstin/verify", headers=h, json={"gstin": other})
    assert r.status_code == 429 and len(CALLS) == 2

    # someone else's business id is refused
    stranger = signup(client, email="x@y.in")
    assert client.post("/api/gstin/verify", headers={**stranger, "X-Business-Id": h["X-Business-Id"]},
                       json={"gstin": GOOD}).status_code == 403

    usage = client.get("/api/admin/gstin-api", headers=root).json()["usage"]
    assert usage["live_ok"] == 2 and usage["cache"] == 1 and usage["credits_remaining"] == 99
    assert client.post("/api/admin/gstin-api/test", headers=root).json() == {"ok": True, "stats": {"credits_remaining": 97, "used": 3}}


def test_provider_errors_and_types(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    user = signup(client)
    enable(client, root)

    fake_provider(monkeypatch, 404, {"success": False, "error": "GSTIN not found"})
    r = client.post("/api/gstin/verify", headers=user, json={"gstin": GOOD})
    assert r.status_code == 404 and "not registered" in r.text and len(CALLS) == 1  # 404 never retried

    fake_provider(monkeypatch, 502, {"success": False, "error": "upstream"})
    r = client.post("/api/gstin/verify", headers=user, json={"gstin": GOOD})
    assert r.status_code == 502 and len(CALLS) == 3  # retried with back-off

    fake_provider(monkeypatch, 402, {"success": False, "error": "Insufficient credits"})
    r = client.post("/api/gstin/verify", headers=user, json={"gstin": GOOD})
    assert r.status_code == 502 and "manually" in r.text and len(CALLS) == 1
    # failures are not cached
    usage = client.get("/api/admin/gstin-api", headers=root).json()["usage"]
    assert usage["live_failed"] == 3 and usage["live_ok"] == 0

    # wrapped response, composition / SEZ / cancelled
    fake_provider(monkeypatch, 200, {"success": True, "credits_remaining": 5, "data": {
        "gstin": GOOD, "legal_name": "ABC", "status": "Cancelled", "taxpayer_type": "Composition", "state_code": "24",
        "cancellation_date": "2024-03-31", "address": None}})
    d = post(client, user, "/api/gstin/verify", {"gstin": GOOD}, 200)
    assert d["party_gst_type"] == "COMPOSITION" and d["business_gst_type"] == "COMPOSITION" and not d["active"]
    assert d["cancellation_date"] == "2024-03-31"
    assert G.normalise({"taxpayer_type": "SEZ Unit"}, GOOD)["party_gst_type"] == "SEZ"


def test_last_status_is_free_and_platform_wide(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    enable(client, root, cache_days=30)
    fake_provider(monkeypatch)
    a, b = signup(client), signup(client, email="b@shop.in")
    st = client.post("/api/gstin/status", headers=a, json={"gstins": [GOOD]}).json()
    assert st == {GOOD: {"verified": False}}
    post(client, a, "/api/gstin/verify", {"gstin": GOOD}, 200)
    # another user of another account sees it was verified, without any API call
    CALLS.clear()
    st = client.post("/api/gstin/status", headers=b, json={"gstins": [GOOD.lower(), "27AABCS1429B1Z1"]}).json()
    assert st[GOOD]["verified"] and st[GOOD]["fresh"] and st[GOOD]["status"] == "Active" and st[GOOD]["days_ago"] == 0
    assert st["27AABCS1429B1Z1"] == {"verified": False} and CALLS == []
    # and autofill for them comes from the cache (free)
    assert post(client, b, "/api/gstin/verify", {"gstin": GOOD}, 200)["source"] == "cache" and CALLS == []


def test_trial_accounts_get_one_paid_lookup(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    enable(client, root, trial_live_limit=1)
    fake_provider(monkeypatch)
    user = signup(client)                                   # self sign-up → trial
    h = make_business(client, user)
    post(client, h, "/api/gstin/verify", {"gstin": GOOD}, 200)
    r = client.post("/api/gstin/verify", headers=h, json={"gstin": gstin("27", "AABCS1429B")})
    assert r.status_code == 402 and r.json()["detail"]["code"] == "UPGRADE" and len(CALLS) == 1
    # staff / onboarding of the same account share the allowance; answers already on the platform stay free
    assert post(client, h, "/api/gstin/verify", {"gstin": GOOD}, 200)["source"] == "cache"
    # a paid plan lifts the cap
    from app.db import get_db
    from app.main import app
    from app.models import Subscription
    db = next(app.dependency_overrides[get_db]())
    acc = db.scalar(__import__("sqlalchemy").select(Subscription))
    acc.plan, acc.status = "STARTER", "ACTIVE"
    db.commit()
    assert post(client, h, "/api/gstin/verify", {"gstin": gstin("27", "AABCS1429B")}, 200)["source"] == "live"
    # super admins are never capped
    assert post(client, root, "/api/gstin/verify", {"gstin": gstin("29", "AAACK5678D")}, 200)["source"] == "live"
