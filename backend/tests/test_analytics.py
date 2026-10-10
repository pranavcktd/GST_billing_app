"""First-party analytics (visits, plan interest, module use) and live-chat settings."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_payment_records import make_staff
from tests.test_security_admin import superadmin

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) Mobile Safari"}
DESK = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/130"}


def track(client, h, url, body):
    r = client.post(url, headers={**DESK, **h}, json=body)
    assert r.status_code == 204, r.text


def test_visits_plans_and_module_usage(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    sales = make_staff(client, "sales@platform.in", ["analytics"], "SALES")
    support = make_staff(client, "help@platform.in", ["helpdesk"], "SUPPORT")

    for vid, path, ref, h in (("visitor-aaaa1111", "/", "https://www.google.com/search?q=gst", UA),
                              ("visitor-aaaa1111", "/terms", None, UA),
                              ("visitor-bbbb2222", "/?utm_source=facebook&x=1", "https://facebook.com/", DESK)):
        assert client.post("/api/track/visit", headers=h, json={"visitor": vid, "path": path, "referrer": ref,
                                                                "utm_source": "facebook" if "utm" in path else None}).status_code == 204
    # bots and Do-Not-Track are skipped
    client.post("/api/track/visit", headers={"User-Agent": "Googlebot/2.1"}, json={"visitor": "visitor-bot00000", "path": "/"})
    client.post("/api/track/visit", headers={**DESK, "DNT": "1"}, json={"visitor": "visitor-dnt00000", "path": "/"})
    assert client.post("/api/track/visit", headers=DESK, json={"visitor": "x", "path": "/"}).status_code == 422

    track(client, {**UA}, "/api/track/event", {"visitor": "visitor-aaaa1111", "kind": "PRICING_VIEW", "page": "/"})
    track(client, {**UA}, "/api/track/event", {"visitor": "visitor-aaaa1111", "kind": "PLAN_CLICK", "plan": "PROFESSIONAL", "cycle": "YEARLY"})
    owner = signup(client)
    h = make_business(client, owner)
    track(client, {**owner, **DESK}, "/api/track/event", {"kind": "PLAN_CLICK", "plan": "PROFESSIONAL", "cycle": "YEARS_3"})
    for module in ("Sale Invoices", "Sale Invoices", "Items & Stock"):
        track(client, h, "/api/track/usage", {"module": module})
    track(client, owner, "/api/track/usage", {"module": "Dashboard"})  # no business on screen
    assert client.post("/api/track/usage", json={"module": "Sale Invoices"}).status_code == 401

    a = client.get("/api/admin/analytics", headers=sales, params={"days": 7}).json()
    t = a["totals"]
    assert t["visitors"] == 2 and t["views"] == 3 and t["signups"] >= 1 and t["dau"] == 1
    assert {p["key"] for p in a["pages"]} == {"/", "/terms"}
    assert {r["key"] for r in a["referrers"]} == {"www.google.com", "facebook.com", "(direct)"}
    assert {d["key"] for d in a["devices"]} == {"mobile", "desktop"}
    assert [c["key"] for c in a["campaigns"] if c["key"] == "facebook"]
    pro = a["plans"][0]
    assert pro["plan"] == "PROFESSIONAL" and pro["clicks"] == 2 and pro["visitors"] == 1 and pro["users"] == 1
    assert pro["cycles"] == {"YEARLY": 1, "YEARS_3": 1} and a["pricing_views"]["visitors"] == 1
    mods = {m["module"]: m for m in a["modules"]}
    assert mods["Sale Invoices"]["views"] == 2 and mods["Sale Invoices"]["users"] == 1 and "Dashboard" in mods

    people = client.get("/api/admin/analytics/users", headers=sales).json()
    assert people[0]["email"] == "owner@shop.in" and people[0]["views"] == 4 and people[0]["modules"][0]["module"] == "Sale Invoices"
    assert people[0]["businesses"] == ["Sharma Traders"]
    assert client.get("/api/admin/analytics/users", headers=sales, params={"module": "Items & Stock"}).json()[0]["views"] == 1
    d = client.get(f"/api/admin/analytics/users/{people[0]['user_id']}", headers=root).json()
    assert d["modules"][0] == {**d["modules"][0], "module": "Sale Invoices", "business": "Sharma Traders", "views": 2}
    assert d["plan_interest"][0]["cycle"] == "YEARS_3"

    assert client.get("/api/admin/analytics", headers=support).status_code == 403
    assert client.get("/api/admin/analytics", headers=owner).status_code == 403

    # switching analytics off stops collection (super admin only)
    assert client.put("/api/admin/analytics/settings", headers=sales, json={"enabled": False}).status_code == 403
    assert client.put("/api/admin/analytics/settings", headers=root, json={"enabled": False, "respect_dnt": True, "keep_days": 365}).status_code == 200
    client.post("/api/track/visit", headers=DESK, json={"visitor": "visitor-cccc3333", "path": "/"})
    track(client, h, "/api/track/usage", {"module": "Reports"})
    a = client.get("/api/admin/analytics", headers=root, params={"days": 7}).json()
    assert a["totals"]["visitors"] == 2 and "Reports" not in {m["module"] for m in a["modules"]}
    assert client.get("/api/meta").json()["analytics"]["enabled"] is False


def test_live_chat_settings(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    owner = signup(client)
    meta = client.get("/api/meta").json()
    assert meta["live_chat"]["enabled"] is False

    bad = client.put("/api/admin/live-chat", headers=root, json={"enabled": True, "property_id": ""})
    assert bad.status_code == 422
    assert client.put("/api/admin/live-chat", headers=root, json={"enabled": True, "property_id": "<script>"}).status_code == 422
    assert client.put("/api/admin/live-chat", headers=owner, json={"enabled": True, "property_id": "abc"}).status_code == 403
    out = client.put("/api/admin/live-chat", headers=root, json={"enabled": True, "property_id": "64fa1b2c3d4e5f6a7b8c9d0e",
                                                                 "widget_id": "1h9abcdef", "show_on": "WEBSITE", "secure_key": "tawk-api-key"}).json()
    assert out["enabled"] and out["secure_key_set"] and "secure_key_enc" not in out and "tawk-api-key" not in str(out)
    lc = client.get("/api/meta").json()["live_chat"]
    assert lc == {"enabled": True, "provider": "TAWK", "property_id": "64fa1b2c3d4e5f6a7b8c9d0e", "widget_id": "1h9abcdef",
                  "show_on": "WEBSITE", "pass_user": True, "secure": True}

    import hashlib
    import hmac
    ident = client.get("/api/track/chat-identity", headers=owner).json()
    assert ident["email"] == "owner@shop.in"
    assert ident["hash"] == hmac.new(b"tawk-api-key", b"owner@shop.in", hashlib.sha256).hexdigest()
    # saving without the key keeps it; empty string removes it
    client.put("/api/admin/live-chat", headers=root, json={"enabled": True, "property_id": "64fa1b2c3d4e5f6a7b8c9d0e"})
    assert client.get("/api/admin/live-chat", headers=root).json()["secure_key_set"]
    client.put("/api/admin/live-chat", headers=root, json={"enabled": False, "property_id": "64fa1b2c3d4e5f6a7b8c9d0e", "secure_key": ""})
    assert not client.get("/api/admin/live-chat", headers=root).json()["secure_key_set"]
    assert client.get("/api/meta").json()["live_chat"]["enabled"] is False
