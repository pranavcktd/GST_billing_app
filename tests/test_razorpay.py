"""Razorpay subscriptions with keys from the admin panel (fake Razorpay server — no network)."""

import hashlib
import hmac
import json
from decimal import Decimal

import httpx

from app.services import plans as P
from app.services import razorpay_cfg as rz
from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_security_admin import superadmin

SECRET, HOOK = "test_secret_abc", "hook_secret_xyz"
CALLS: list[tuple] = []
ORDERS: dict[str, int] = {}


def fake(monkeypatch, payment_status="captured", amount_delta=0, method="upi"):
    CALLS.clear()
    orders = ORDERS

    def request(method_, path, c, **kw):
        CALLS.append((method_, path))
        assert c["key_id"] == "rzp_test_ABC123" and c["key_secret"] == SECRET
        if method_ == "POST" and path == "/orders":
            oid = f"order_{len(orders) + 1}"  # unique across the whole test session
            orders[oid] = kw["json"]["amount"]
            return httpx.Response(200, json={"id": oid, "amount": kw["json"]["amount"], "status": "created"})
        if method_ == "GET" and path.startswith("/payments/"):
            oid = "order_" + path.rsplit("_", 1)[1]
            return httpx.Response(200, json={"id": path.rsplit("/", 1)[1], "order_id": oid, "status": payment_status,
                                             "amount": orders.get(oid, 0) + amount_delta, "method": method})
        if method_ == "POST" and path.endswith("/capture"):
            return httpx.Response(200, json={"status": "captured"})
        if path.startswith("/orders?count"):
            return httpx.Response(200, json={"items": []})
        return httpx.Response(404, json={"error": {"description": "not found"}})

    monkeypatch.setattr(rz, "request", request)


def sign(order_id, payment_id):
    return hmac.new(SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def configure(client, root):
    r = client.put("/api/admin/razorpay", headers=root, json={"mode": "TEST", "TEST": {
        "key_id": "rzp_test_ABC123", "key_secret": SECRET, "webhook_secret": HOOK}})
    assert r.status_code == 200, r.text
    return r.json()


def test_admin_keys_checkout_and_revenue(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    h = make_business(client, signup(client))
    fake(monkeypatch)

    # without keys: local simulation
    assert client.get("/api/billing/status", headers=h).json()["dev_mode"] is True
    bad = client.put("/api/admin/razorpay", headers=root, json={"TEST": {"key_id": "rzp_live_X", "key_secret": "s"}})
    assert bad.status_code == 422 and "rzp_test_" in bad.text
    assert client.put("/api/admin/razorpay", headers=h, json={"mode": "TEST"}).status_code == 403

    out = configure(client, root)
    assert out["settings"]["active"] == {"mode": "TEST", "key_id": "rzp_test_ABC123", "source": "admin", "webhook": True}
    assert out["settings"]["TEST"]["key_secret_set"] and "key_secret" not in json.dumps(out["settings"]["TEST"]).replace("key_secret_set", "")
    assert out["webhook_url"].endswith("/api/billing/webhook")
    assert client.post("/api/admin/razorpay/test", headers=root).json() == {"ok": True, "mode": "TEST", "key_id": "rzp_test_ABC123"}

    st = client.get("/api/billing/status", headers=h).json()
    assert st["payments_live"] and st["test_mode"] and not st["dev_mode"]

    order = post(client, h, "/api/billing/order", {"plan": "STARTER", "cycle": "YEARLY"}, 200)
    assert order["live"] and order["test_mode"] and order["key_id"] == "rzp_test_ABC123" and order["order_id"].startswith("order_")
    assert order["amount_paise"] == int(P.with_gst(Decimal("1999")) * 100)
    # simulation is refused once keys exist
    assert client.post("/api/billing/verify", headers=h, json={"order_id": order["order_id"], "simulate": True}).status_code == 400
    # wrong signature
    r = client.post("/api/billing/verify", headers=h, json={"order_id": order["order_id"], "payment_id": "pay_x", "signature": "x"})
    assert r.status_code == 400

    o = post(client, h, "/api/billing/order", {"plan": "STARTER", "cycle": "YEARLY"}, 200)["order_id"]
    pid = "pay_" + o.split("_")[1]
    res = post(client, h, "/api/billing/verify", {"order_id": o, "payment_id": pid, "signature": sign(o, pid)}, 200)
    assert res["plan"] == "STARTER" and res["status"] == "ACTIVE"
    assert ("GET", f"/payments/{pid}") in CALLS
    hist = client.get("/api/billing/status", headers=h).json()["payments"]
    paid = [p for p in hist if p["status"] == "PAID"][0]
    assert paid["mode"] == "TEST" and paid["method"] == "upi"
    # test payments are not revenue
    assert client.get("/api/admin/stats", headers=root).json()["revenue_30d"] == 0
    listed = client.get("/api/admin/razorpay", headers=root).json()["payments"]
    assert listed[0]["mode"] == "TEST" and listed[0]["account"] == "owner@shop.in"


def test_capture_amount_check_and_webhook(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    h = make_business(client, signup(client))
    configure(client, root)

    # manual-capture account: authorised payment gets captured
    fake(monkeypatch, payment_status="authorized")
    o = post(client, h, "/api/billing/order", {"plan": "PROFESSIONAL", "cycle": "MONTHLY"}, 200)["order_id"]
    pid = "pay_" + o.split("_")[1]
    post(client, h, "/api/billing/verify", {"order_id": o, "payment_id": pid, "signature": sign(o, pid)}, 200)
    assert ("POST", f"/payments/{pid}/capture") in CALLS

    # amount tampering is rejected even with a valid signature
    fake(monkeypatch, amount_delta=-100)
    o = post(client, h, "/api/billing/order", {"plan": "ENTERPRISE", "cycle": "YEARLY"}, 200)["order_id"]
    pid = "pay_" + o.split("_")[1]
    r = client.post("/api/billing/verify", headers=h, json={"order_id": o, "payment_id": pid, "signature": sign(o, pid)})
    assert r.status_code == 400 and "does not match" in r.text

    # failed payment
    fake(monkeypatch, payment_status="failed")
    o = post(client, h, "/api/billing/order", {"plan": "ENTERPRISE", "cycle": "YEARLY"}, 200)["order_id"]
    pid = "pay_" + o.split("_")[1]
    r = client.post("/api/billing/verify", headers=h, json={"order_id": o, "payment_id": pid, "signature": sign(o, pid)})
    assert r.status_code == 400

    # webhook (browser closed before the handler ran) activates with the admin-saved webhook secret
    fake(monkeypatch)
    order = post(client, h, "/api/billing/order", {"plan": "ENTERPRISE", "cycle": "YEARLY"}, 200)
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
        "order_id": order["order_id"], "id": "pay_w", "method": "card"}}}}).encode()
    assert client.post("/api/billing/webhook", content=body, headers={"x-razorpay-signature": "bad"}).status_code == 400
    sig = hmac.new(HOOK.encode(), body, hashlib.sha256).hexdigest()
    assert client.post("/api/billing/webhook", content=body, headers={"x-razorpay-signature": sig}).status_code == 200
    assert client.get("/api/billing/status", headers=h).json()["plan"]["code"] == "ENTERPRISE"
