"""API credits: monthly allowance, prepaid packs bought through billing, charged only for successful real filings."""

from decimal import Decimal

from app.services import plans as P
from tests.test_einvoice_live import SENT, fake
from tests.test_gstin_verify import enable
from tests.test_modules import post
from tests.test_phase2 import sale, setup
from tests.test_security_admin import superadmin


def test_credits_allowance_packs_and_charging(client, monkeypatch):
    h, cust, item = setup(client)  # trial = Business plan
    biz = client.get("/api/businesses/current", headers=h).json()
    body = {k: v for k, v in biz.items() if k not in ("id", "plan", "einvoice_password_set", "ewb_password_set", "gst_portal", "modules")}
    client.put("/api/businesses/current", headers=h, json={**body, "einvoice_applicable": True,
                                                           "einvoice_username": "einv_user", "einvoice_password": "einv_pass"})
    monkeypatch.setitem(P.PLANS["ENTERPRISE"], "api_quota", 1)
    v1, v2, v3 = (sale(client, h, cust, item) for _ in range(3))

    root = superadmin(client, monkeypatch)
    enable(client, root, einv_live=True, einv_test_mode=False)
    c = client.get("/api/billing/credits", headers=h).json()
    assert c["allowance"] == 1 and c["free_left"] == 1 and c["balance"] == 0 and c["api_enabled"]
    assert [p["credits"] for p in c["packs"]] == [100, 500, 2000] and c["costs"]["EINVOICE"] == 1

    # the month's allowance is used first
    fake(monkeypatch)
    post(client, h, f"/api/vouchers/{v1['id']}/einvoice", {}, 200)
    c = client.get("/api/billing/credits", headers=h).json()
    assert c["used_this_month"] == 1 and c["free_left"] == 0 and c["history"][0]["action"] == "EINVOICE"

    # nothing left: refused before calling the provider
    n = len(SENT)
    r = client.post(f"/api/vouchers/{v2['id']}/einvoice", headers=h, json={})
    assert r.status_code == 402 and r.json()["detail"]["code"] == "CREDITS" and len(SENT) == n

    # buy a pack (local development: simulated payment)
    assert client.post("/api/billing/order", headers=h, json={"plan": "CREDITS_7"}).status_code == 400
    order = post(client, h, "/api/billing/order", {"plan": "CREDITS_100"}, 200)
    assert order["amount"] == float(P.with_gst(Decimal("299")))
    post(client, h, "/api/billing/verify", {"order_id": order["order_id"], "simulate": True}, 200)
    assert client.get("/api/billing/credits", headers=h).json()["balance"] == 100
    assert client.get("/api/billing/status", headers=h).json()["plan"]["code"] == "ENTERPRISE"  # plan unchanged

    # a failed call is not charged; a successful one comes from the pack
    fake(monkeypatch, fail={"einvoice": (400, "Invalid buyer GSTIN")})
    assert client.post(f"/api/vouchers/{v2['id']}/einvoice", headers=h, json={}).status_code >= 400
    assert client.get("/api/billing/credits", headers=h).json()["balance"] == 100
    fake(monkeypatch)
    post(client, h, f"/api/vouchers/{v2['id']}/einvoice", {}, 200)
    c = client.get("/api/billing/credits", headers=h).json()
    assert c["balance"] == 99 and c["used_this_month"] == 2

    # admin-set cost per action
    r = client.post("/api/admin/config/versions", headers=root, json={"effective_from": __import__("datetime").date.today().isoformat(), "values": {"api_credit_costs": {"EINVOICE": 5, "EWAYBILL": 1, "CANCEL": 1, "FILING_SYNC": 1}}})
    assert r.status_code == 201, r.text
    monkeypatch.setitem(P.PLANS["ENTERPRISE"], "api_quota", 1)  # saving config reloads the plans
    post(client, h, f"/api/vouchers/{v3['id']}/einvoice", {}, 200)
    assert client.get("/api/billing/credits", headers=h).json()["balance"] == 94

    # the provider's test mode is free
    enable(client, root, einv_live=True, einv_test_mode=True)
    v4 = sale(client, h, cust, item)
    post(client, h, f"/api/vouchers/{v4['id']}/einvoice", {}, 200)
    assert client.get("/api/billing/credits", headers=h).json()["balance"] == 94
