"""WhatsApp Business API (fake Meta-compatible provider): sign-in codes, sign-up verification, sending invoices."""

import httpx

from app.services import plans as P
from app.services import whatsapp as W
from tests.test_api_flow import signup
from tests.test_phase2 import sale, setup
from tests.test_security_admin import superadmin

SENT: list[tuple[str, dict, dict]] = []


def fake(monkeypatch, fail: str | None = None):
    SENT.clear()

    def http_post(url, headers, body):
        SENT.append((url, headers, body))
        if fail:
            return httpx.Response(400, json={"error": {"message": fail, "code": 132001}})
        return httpx.Response(200, json={"messaging_product": "whatsapp", "contacts": [{"input": body["to"], "wa_id": body["to"]}],
                                         "messages": [{"id": f"wamid.TEST{len(SENT)}"}]})

    monkeypatch.setattr(W, "_http_post", http_post)


def last_code() -> str:
    return SENT[-1][2]["template"]["components"][0]["parameters"][0]["text"]


def enable(client, root, **extra):
    r = client.put("/api/admin/whatsapp", headers=root, json={"enabled": True, "provider": "SPRINGEDGE",
                                                              "base_url": "https://wa.springedge.test", "api_version": "v3",
                                                              "auth_header": "apikey", "phone_number_id": "1234567890",
                                                              "api_key": "se_test_key_abcdef", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_admin_settings_and_signin_with_whatsapp(client, monkeypatch):
    assert client.get("/api/meta").json()["whatsapp"] == {"login": False, "signup_verify": False, "send": False}
    root = superadmin(client, monkeypatch)
    v = enable(client, root)
    assert v["settings"]["ready"] and v["settings"]["api_key_set"] and "api_key_enc" not in v["settings"]
    assert "/api/whatsapp/webhook?key=" in v["webhook_url"]
    assert client.get("/api/meta").json()["whatsapp"]["login"] is True

    # test message: Spring Edge URL, apikey header, OTP template with copy-code button
    fake(monkeypatch)
    assert client.post("/api/admin/whatsapp/test", headers=root, json={"phone": "98765 43210"}).status_code == 200
    url, headers, body = SENT[-1]
    assert url == "https://wa.springedge.test/v3/1234567890/messages" and headers["apikey"] == "se_test_key_abcdef"
    assert body["to"] == "919876543210" and body["template"]["name"] == "login_otp"
    assert body["template"]["components"][1]["sub_type"] == "url"

    # link a number to an existing account
    h = signup(client, "shop@x.in")
    assert client.post("/api/auth/mobile", headers=h, json={"phone": "9123456780"}).status_code == 200
    code = last_code()
    assert client.post("/api/auth/mobile", headers=h, json={"phone": "9123456780", "code": "000000" if code != "000000" else "111111"}).status_code == 400
    assert client.post("/api/auth/mobile", headers=h, json={"phone": "9123456780", "code": code}).json()["mobile"] == "919123456780"
    assert client.get("/api/auth/me", headers=h).json()["user"]["mobile"] == "919123456780"

    # sign in with a WhatsApp code (the 60-second resend wait is per number, so skip it here)
    monkeypatch.setattr(W, "OTP_RESEND_SECONDS", 0)
    n = len(SENT)
    r = client.post("/api/auth/otp/send", json={"phone": "9123456780"})
    assert r.status_code == 200 and r.json()["to"].endswith("80") and len(SENT) == n + 1
    code = last_code()
    # resend is throttled
    monkeypatch.setattr(W, "OTP_RESEND_SECONDS", 60)
    assert client.post("/api/auth/otp/send", json={"phone": "9123456780"}).status_code == 429
    r = client.post("/api/auth/otp/login", json={"phone": "+91 91234 56780", "code": code})
    assert r.status_code == 200 and r.json()["user"]["email"] == "shop@x.in"
    # a code works once
    assert client.post("/api/auth/otp/login", json={"phone": "9123456780", "code": code}).status_code == 400

    # unknown number: same answer, nothing sent
    n = len(SENT)
    assert client.post("/api/auth/otp/send", json={"phone": "9000000001"}).status_code == 200 and len(SENT) == n
    assert client.post("/api/auth/otp/login", json={"phone": "9000000001", "code": "123456"}).status_code == 400
    assert client.post("/api/auth/otp/send", json={"phone": "12345"}).status_code == 422

    # sign-up needs a verified mobile when the admin asks for it
    monkeypatch.setattr(W, "OTP_RESEND_SECONDS", 0)
    enable(client, root, signup_verify=True)
    body = {"name": "New Shop", "email": "new@x.in", "password": "secret123", "phone": "9988776655"}
    assert client.post("/api/auth/register", json=body).status_code == 400
    assert client.post("/api/auth/otp/send", json={"phone": "9123456780", "purpose": "SIGNUP"}).status_code == 409  # taken
    assert client.post("/api/auth/otp/send", json={"phone": "9988776655", "purpose": "SIGNUP"}).status_code == 200
    r = client.post("/api/auth/register", json={**body, "phone_code": last_code()})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["mobile"] == "919988776655"


def test_send_invoice_quota_and_credits(client, monkeypatch):
    h, cust, item = setup(client)
    v = sale(client, h, cust, item)
    root = superadmin(client, monkeypatch)
    assert client.post(f"/api/vouchers/{v['id']}/whatsapp", headers=h, json={"phone": "9876543210"}).status_code == 503
    enable(client, root)
    fake(monkeypatch)
    monkeypatch.setitem(P.PLANS["ENTERPRISE"], "whatsapp_quota", 1)
    monkeypatch.setitem(P.PLANS["ENTERPRISE"], "api_quota", 0)

    assert client.post(f"/api/vouchers/{v['id']}/whatsapp", headers=h, json={}).status_code == 422  # party has no phone
    r = client.post(f"/api/vouchers/{v['id']}/whatsapp", headers=h, json={"phone": "9876543210"})
    assert r.status_code == 200, r.text
    assert r.json()["charged_credits"] is False
    _, _, body = SENT[-1]
    comps = body["template"]["components"]
    assert body["template"]["name"] == "invoice_document"
    assert comps[0]["parameters"][0]["document"]["link"].split("/api/public/invoice/")[1].endswith("/pdf")
    assert [p["text"] for p in comps[1]["parameters"]][1] == v["number"]
    st = client.get("/api/whatsapp/status", headers=h).json()
    assert st["used"] == 1 and st["left"] == 0

    # monthly messages used up and no credits → refused before sending
    n = len(SENT)
    r = client.post(f"/api/vouchers/{v['id']}/whatsapp", headers=h, json={"phone": "9876543210"})
    assert r.status_code == 402 and r.json()["detail"]["code"] == "CREDITS" and len(SENT) == n
    order = client.post("/api/billing/order", headers=h, json={"plan": "CREDITS_100"}).json()
    client.post("/api/billing/verify", headers=h, json={"order_id": order["order_id"], "simulate": True})
    r = client.post(f"/api/vouchers/{v['id']}/whatsapp", headers=h, json={"phone": "9876543210"})
    assert r.json()["charged_credits"] is True
    assert client.get("/api/billing/credits", headers=h).json()["balance"] == 99

    # provider refuses: error shown, nothing charged
    fake(monkeypatch, fail="Template name does not exist")
    r = client.post(f"/api/vouchers/{v['id']}/whatsapp", headers=h, json={"phone": "9876543210"})
    assert r.status_code == 502 and "Template name" in r.json()["detail"]
    assert client.get("/api/billing/credits", headers=h).json()["balance"] == 99

    # payment reminder with a link to the bill
    fake(monkeypatch)
    r = client.post(f"/api/reminders/whatsapp-send/{cust['id']}", headers=h, json={"phone": "9876543210"})
    assert r.status_code == 200, r.text
    params = [p["text"] for p in SENT[-1][2]["template"]["components"][0]["parameters"]]
    assert params[0] == cust["name"] and "/i/" in params[3]

    # delivery status webhook
    key = client.get("/api/admin/whatsapp", headers=root).json()["settings"]["webhook_key"]
    assert client.post("/api/whatsapp/webhook?key=wrong", json={}).status_code == 403
    hook = {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.TEST1", "status": "read", "recipient_id": "919876543210"}]}}]}]}
    assert client.post(f"/api/whatsapp/webhook?key={key}", json=hook).json()["updated"] == 1
    assert client.get(f"/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token={key}&hub.challenge=42").text == "42"
