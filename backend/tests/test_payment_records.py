"""Subscription transactions: every attempt recorded, receipts, failures, leads, and alerts (bell + e-mail) to the
owner and the platform team."""

import hashlib
import hmac
import json

from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_razorpay import HOOK, configure, fake, sign
from tests.test_security_admin import SENT, fake_mail, platform_mail, superadmin  # noqa: F401 — fake_mail: e-mail stub


def db_session():
    from app.db import get_db
    from app.main import app

    gen = app.dependency_overrides.get(get_db, get_db)()
    return gen, next(gen)


def make_staff(client, email, areas, team="FINANCE"):
    h = signup(client, email)
    from app.models import User

    gen, db = db_session()
    try:
        u = db.query(User).filter(User.email == email).one()
        u.platform_role, u.platform_areas, u.platform_team = "TEAM", areas, team
        db.commit()
    finally:
        gen.close()
    return h


def bell(client, h):
    return client.get("/api/notifications", headers=h).json()


def test_paid_payment_receipt_and_alerts(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    platform_mail(client)
    fin = make_staff(client, "fin@platform.in", ["payments"])
    helpdesk = make_staff(client, "help@platform.in", ["helpdesk"], "SUPPORT")
    owner = signup(client)
    h = make_business(client, owner)

    order = post(client, h, "/api/billing/order", {"plan": "STARTER", "cycle": "YEARLY"}, 200)
    SENT.clear()
    post(client, h, "/api/billing/verify", {"order_id": order["order_id"], "simulate": True}, 200)

    mine = client.get("/api/billing/payments", headers=owner).json()
    assert len(mine) == 1 and mine[0]["status"] == "PAID" and mine[0]["receipt_no"].startswith("SR")
    assert mine[0]["business_name"] and mine[0]["item"] == "Starter plan — 1 year"
    assert abs(mine[0]["taxable"] + mine[0]["gst"] - mine[0]["amount"]) < 0.01 and mine[0]["gst_rate"] == 18

    rec = client.get(f"/api/billing/payments/{mine[0]['id']}", headers=owner).json()
    assert rec["seller"]["phone"] == "+91 96032 43575" and rec["buyer"]["name"] and rec["tax_split"] in ("IGST", "CGST_SGST")
    assert client.get(f"/api/billing/payments/{mine[0]['id']}", headers=root).status_code == 200
    assert client.get(f"/api/billing/payments/{mine[0]['id']}", headers=fin).status_code == 200
    assert client.get(f"/api/billing/payments/{mine[0]['id']}", headers=helpdesk).status_code == 404  # no payments area
    assert client.get(f"/api/billing/payments/{mine[0]['id']}", headers=signup(client, "other@x.in")).status_code == 404

    # alerts: owner, super admin and the finance team member — not the helpdesk member
    for name, who in (("owner", owner), ("root", root), ("fin", fin)):
        n = bell(client, who)
        assert n["unread"] == 1 and n["items"][0]["kind"] == "PAYMENT_OK", (name, n)
    assert bell(client, helpdesk)["unread"] == 0
    assert bell(client, owner)["items"][0]["link"] == f"/receipt/{mine[0]['id']}"
    to = {m["To"] for m in SENT}
    assert {"owner@shop.in", "root@platform.in", "fin@platform.in"} <= to and "help@platform.in" not in to
    assert any("Payment received" in m["Subject"] for m in SENT)

    # mark read
    post(client, owner, "/api/notifications/read", {"ids": None}, 200)
    assert client.get("/api/notifications/unread", headers=owner).json()["unread"] == 0

    # admin list, filters and access
    out = client.get("/api/admin/payments", headers=fin, params={"mode": "DEV"}).json()
    assert out["summary"]["PAID"]["count"] == 1 and out["rows"][0]["owner_email"] == "owner@shop.in"
    assert client.get("/api/admin/payments", headers=root, params={"mode": "DEV", "q": "shop.in"}).json()["total"] == 1
    assert client.get("/api/admin/payments", headers=root, params={"mode": "DEV", "q": "nobody"}).json()["total"] == 0
    assert client.get("/api/admin/payments", headers=helpdesk).status_code == 403
    assert client.get("/api/admin/payments", headers=owner).status_code == 403
    assert len(client.get(f"/api/admin/payments/{mine[0]['id']}", headers=root).json()["account_history"]) == 1


def test_failed_cancelled_webhook_and_leads(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    platform_mail(client)
    configure(client, root)
    owner = signup(client)
    h = make_business(client, owner)
    fake(monkeypatch)

    # checkout reports a failure
    o1 = post(client, h, "/api/billing/order", {"plan": "PROFESSIONAL", "cycle": "YEARLY"}, 200)["order_id"]
    SENT.clear()
    r = post(client, h, "/api/billing/failed", {"order_id": o1, "payment_id": "pay_f1", "code": "BAD_REQUEST_ERROR",
                                                "reason": "Your bank declined the payment"}, 200)
    assert r["status"] == "FAILED"
    n = bell(client, owner)["items"][0]
    assert n["kind"] == "PAYMENT_FAILED" and "declined" in n["body"]
    assert bell(client, root)["items"][0]["kind"] == "PAYMENT_FAILED"
    assert {"owner@shop.in", "root@platform.in"} <= {m["To"] for m in SENT}
    # closing the window afterwards keeps the failure; the same failure twice alerts once
    post(client, h, "/api/billing/failed", {"order_id": o1, "cancelled": True}, 200)
    post(client, h, "/api/billing/failed", {"order_id": o1, "payment_id": "pay_f1", "reason": "again"}, 200)
    assert len([i for i in bell(client, owner)["items"] if i["kind"] == "PAYMENT_FAILED"]) == 1

    # closed without paying: team sees it in the bell (no e-mail), owner gets nothing
    o2 = post(client, h, "/api/billing/order", {"plan": "STARTER", "cycle": "MONTHLY"}, 200)["order_id"]
    SENT.clear()
    assert post(client, h, "/api/billing/failed", {"order_id": o2, "cancelled": True}, 200)["status"] == "CANCELLED"
    assert bell(client, root)["items"][0]["kind"] == "PAYMENT_CANCELLED" and not SENT
    assert bell(client, owner)["items"][0]["kind"] == "PAYMENT_FAILED"

    # Razorpay webhook: payment.failed
    o3 = post(client, h, "/api/billing/order", {"plan": "ENTERPRISE", "cycle": "YEARLY"}, 200)["order_id"]
    body = json.dumps({"event": "payment.failed", "payload": {"payment": {"entity": {
        "order_id": o3, "id": "pay_w3", "method": "upi", "error_code": "BAD_REQUEST_ERROR",
        "error_description": "UPI request expired"}}}}).encode()
    sig = hmac.new(HOOK.encode(), body, hashlib.sha256).hexdigest()
    assert client.post("/api/billing/webhook", content=body, headers={"x-razorpay-signature": sig}).status_code == 200
    rows = {p["order_id"]: p for p in client.get("/api/billing/payments", headers=owner).json()}
    assert rows[o3]["status"] == "FAILED" and rows[o3]["error_reason"] == "UPI request expired" and rows[o3]["method"] == "upi"

    # wrong signature from the browser is recorded as failed
    o4 = post(client, h, "/api/billing/order", {"plan": "STARTER", "cycle": "YEARLY"}, 200)["order_id"]
    client.post("/api/billing/verify", headers=h, json={"order_id": o4, "payment_id": "pay_x", "signature": "bad"})
    assert {p["order_id"]: p for p in client.get("/api/billing/payments", headers=owner).json()}[o4]["status"] == "FAILED"

    # summary and leads
    out = client.get("/api/admin/payments", headers=root, params={"mode": "TEST"}).json()
    assert out["summary"]["FAILED"]["count"] == 3 and out["summary"]["CANCELLED"]["count"] == 1
    leads = client.get("/api/admin/payments/leads", headers=root).json()
    assert len(leads) == 1 and leads[0]["owner_email"] == "owner@shop.in" and leads[0]["attempts"] == 4

    # paying afterwards closes the lead, and a failed order that later succeeds becomes PAID
    pid = "pay_" + o1.split("_")[1]
    post(client, h, "/api/billing/verify", {"order_id": o1, "payment_id": pid, "signature": sign(o1, pid)}, 200)
    rows = {p["order_id"]: p for p in client.get("/api/billing/payments", headers=owner).json()}
    assert rows[o1]["status"] == "PAID" and rows[o1]["error_reason"] is None and rows[o1]["receipt_no"]
    assert client.get("/api/admin/payments/leads", headers=root).json() == []
    # another account's order cannot be touched
    other = make_business(client, signup(client, "other@x.in"))
    assert client.post("/api/billing/failed", headers=other, json={"order_id": o2, "cancelled": True}).status_code == 404
