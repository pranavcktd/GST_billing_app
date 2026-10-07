"""Live e-invoice / e-way bill generation through gstinapi.in (fake provider), alerts and the setup info."""

import json

import httpx

from app.services import einvoice as ei
from tests.test_gstin_verify import enable
from tests.test_modules import post
from tests.test_phase2 import sale, setup
from tests.test_security_admin import superadmin

SENT: list[tuple[str, dict]] = []
NOW = __import__("datetime").datetime.now(ei.IST).strftime("%d/%m/%Y %H:%M:%S")  # cancellable: within 24 hours


def fake(monkeypatch, fail: dict | None = None):
    SENT.clear()

    def http_post(url, key, body):
        path = url.split("/v1/", 1)[1]
        SENT.append((path, body))
        assert key == "gak_test_key_123456"
        if fail and path in fail:
            return httpx.Response(fail[path][0], json={"success": False, "error": fail[path][1], "error_code": "2150"})
        if path == "einvoice":
            return httpx.Response(200, json={"success": True, "irn": "a" * 64, "ack_no": "112010012345678",
                                             "ack_date": "10/09/2026 10:00:00", "qr_code_image": "eyJhbGciOiJSUzI1NiJ9.e30.sig",
                                             "already_existed": False})
        if path == "ewaybill":
            return httpx.Response(200, json={"success": True, "ewaybill_no": "TEST-351000000123", "ewaybill_date": NOW,
                                             "valid_upto": "15/09/2026", "already_existed": False})
        return httpx.Response(200, json={"success": True, "cancel_date": "10/09/2026"})

    monkeypatch.setattr(ei, "_http_post", http_post)


def test_live_generation_and_alerts(client, monkeypatch):
    h, cust, item = setup(client)
    biz = client.get("/api/businesses/current", headers=h).json()
    body = {k: v for k, v in biz.items() if k not in ("id", "plan", "einvoice_password_set", "ewb_password_set", "gst_portal", "modules")}
    client.put("/api/businesses/current", headers=h, json={**body, "einvoice_applicable": True,
                                                           "ewb_username": "ewb_user", "ewb_password": "ewb_pass"})

    # big goods invoice to a registered buyer: needs an IRN and an e-way bill
    v = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "party_id": cust["id"],
                                          "lines": [{"item_id": item["id"], "name": "Bottle", "qty": 120, "rate": 500, "gst_rate": 18}],
                                          "transport": {"vehicle_no": "MH12AB1234", "distance_km": 840}})
    d = client.get(f"/api/vouchers/{v['id']}", headers=h).json()
    assert d["irn_required"] and d["ewb_required"]
    small = sale(client, h, cust, item)  # ₹1,180: IRN yes, e-way bill no
    s = client.get(f"/api/vouchers/{small['id']}", headers=h).json()
    assert s["irn_required"] and not s["ewb_required"]
    pend = client.get("/api/einvoice/pending", headers=h).json()
    assert pend["ewb"] == 1 and pend["irn"] == 2

    # switched on by the super admin, in the provider's test mode; GSP name shown to businesses
    root = superadmin(client, monkeypatch)
    enable(client, root, einv_live=True, einv_test_mode=True, gsp_name="Chartered Information Systems Private Limited")
    setup_info = client.get("/api/einvoice/setup", headers=h).json()
    assert setup_info["live"] and setup_info["test_mode"] and setup_info["gsp_name"].startswith("Chartered")
    assert setup_info["ewb_user_set"] and not setup_info["einvoice_user_set"]

    fake(monkeypatch)
    g = post(client, h, f"/api/vouchers/{v['id']}/einvoice", {}, 200)
    path, sent = SENT[-1]
    assert path == "einvoice" and sent["test_mode"] is True and sent["gstin"] == biz["gstin"]
    assert sent["einv_username"] == "test-user"  # test mode works without a real portal user
    assert sent["payload"]["DocDtls"]["No"] == v["number"]
    assert g["irn"] == "a" * 64 and g["ack_no"] == "112010012345678" and g["signed_qr"].startswith("eyJ") and g["einvoice_sandbox"]
    assert not g["irn_required"]

    e = post(client, h, f"/api/vouchers/{v['id']}/ewaybill", {}, 200)
    path, sent = SENT[-1]
    assert path == "ewaybill" and sent["gstin_username"] == "ewb_user" and sent["password"] == "ewb_pass"
    p = sent["payload"]
    assert "userGstin" not in p and p["transMode"] == "1" and "cessNonadvol" in p["itemList"][0] and "itemNo" not in p["itemList"][0]
    assert e["ewb_no"] == "TEST-351000000123" and e["ewb_valid_till"].startswith("2026-09-15T23:59") and not e["ewb_required"]
    assert client.get("/api/einvoice/pending", headers=h).json()["ewb"] == 0

    # the portal's rejection reaches the user as a clear message, nothing is saved
    fake(monkeypatch, fail={"einvoice": (400, "Duplicate IRN")})
    r = client.post(f"/api/vouchers/{small['id']}/einvoice", headers=h)
    assert r.status_code == 400 and "Duplicate IRN" in r.json()["detail"]
    assert client.get(f"/api/vouchers/{small['id']}", headers=h).json()["irn"] is None
    fake(monkeypatch, fail={"einvoice": (402, "no credits")})
    assert "run out of credits" in client.post(f"/api/vouchers/{small['id']}/einvoice", headers=h).json()["detail"]

    # live mode needs the business's own API user
    enable(client, root, einv_live=True, einv_test_mode=False)
    fake(monkeypatch)
    r = client.post(f"/api/vouchers/{small['id']}/einvoice", headers=h)
    assert r.status_code == 400 and "Chartered Information Systems" in r.json()["detail"]

    # cancel the e-way bill (within 24 hours)
    c = post(client, h, f"/api/vouchers/{v['id']}/ewaybill/cancel", {"reason": "2", "remark": "wrong vehicle"}, 200)
    assert SENT[-1][0] == "ewaybill/cancel" and SENT[-1][1]["ewaybill_no"] == "TEST-351000000123" and SENT[-1][1]["cancel_reason_code"] == "2"
    assert c["ewb_no"] is None and c["ewb_required"]


def test_helpers():
    assert ei.qr_text("eyJx.y.z") == "eyJx.y.z"
    import base64
    assert ei.qr_text(base64.b64encode(b"eyJhbGc.payload.sig").decode()) == "eyJhbGc.payload.sig"
    assert ei.parse_dt("10/09/2026 10:00:00").hour == 10 and ei.parse_dt("15/09/2026", end_of_day=True).hour == 23
    assert ei.parse_dt("") is None and json.dumps(ei.api_ewb_payload({"billLists": [{"userGstin": "x", "transMode": 1, "itemList": [{"itemNo": 1, "cessNonAdvol": 0}]}]}))
