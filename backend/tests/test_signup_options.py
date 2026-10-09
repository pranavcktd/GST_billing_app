"""Sign-up verification by e-mail code or WhatsApp code (user's choice), and Continue with Google."""

from app.services import signup as SU
from app.services import whatsapp as W
from tests.test_security_admin import superadmin
from tests.test_whatsapp import enable as wa_enable
from tests.test_whatsapp import fake as wa_fake


def _signup(client, **extra):
    return client.post("/api/auth/register", json={"name": "New Shop", "email": "new@shop.in", "password": "secret123", **extra})


def test_email_code_and_either_choice(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    assert client.get("/api/meta").json()["signup"] == {"verify": [], "google_client_id": None}
    client.put("/api/admin/signup", headers=root, json={"verify": "EMAIL"})
    assert client.get("/api/meta").json()["signup"]["verify"] == ["EMAIL"]
    assert _signup(client).status_code == 422  # code needed
    code = client.post("/api/auth/email-code", json={"email": "new@shop.in"}).json()["sandbox_code"]  # dev server, no SMTP
    assert _signup(client, email_code="000000" if code != "000000" else "111111").status_code == 400
    r = _signup(client, email_code=code)
    assert r.status_code == 201, r.text
    assert client.post("/api/auth/email-code", json={"email": "new@shop.in"}).status_code == 409  # taken now

    # user's choice: WhatsApp or e-mail
    wa_enable(client, root)
    wa_fake(monkeypatch)
    monkeypatch.setattr(W, "OTP_RESEND_SECONDS", 0)
    client.put("/api/admin/signup", headers=root, json={"verify": "EITHER"})
    assert client.get("/api/meta").json()["signup"]["verify"] == ["WHATSAPP", "EMAIL"]
    client.post("/api/auth/otp/send", json={"phone": "9811100011", "purpose": "SIGNUP"})
    from tests.test_whatsapp import last_code
    r = client.post("/api/auth/register", json={"name": "WA Shop", "email": "wa@shop.in", "password": "secret123",
                                                "phone": "9811100011", "phone_code": last_code()})
    assert r.status_code == 201 and r.json()["user"]["mobile"] == "919811100011"
    code = client.post("/api/auth/email-code", json={"email": "mail@shop.in"}).json()["sandbox_code"]
    assert client.post("/api/auth/register", json={"name": "Mail Shop", "email": "mail@shop.in", "password": "secret123",
                                                   "email_code": code}).status_code == 201


def test_continue_with_google(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    assert client.post("/api/auth/google", json={"credential": "x" * 40}).status_code == 503  # switched off
    assert client.put("/api/admin/signup", headers=root, json={"google_enabled": True, "google_client_id": "not-a-client-id"}).status_code == 422
    cid = "1234567890-abc.apps.googleusercontent.com"
    client.put("/api/admin/signup", headers=root, json={"google_enabled": True, "google_client_id": cid})
    assert client.get("/api/meta").json()["signup"]["google_client_id"] == cid

    def verify(credential, client_id):
        assert client_id == cid
        if credential.startswith("bad"):
            raise ValueError("wrong signature")
        return {"email": "Owner@Gmail.com", "email_verified": True, "name": "Asha Rao", "sub": "g-123"}

    monkeypatch.setattr(SU, "_verify_google", verify)
    assert client.post("/api/auth/google", json={"credential": "bad" + "x" * 40}).status_code == 401
    r = client.post("/api/auth/google", json={"credential": "ok" + "x" * 40})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["user"]["email"] == "owner@gmail.com" and me["user"]["name"] == "Asha Rao" and me["businesses"] == []  # → business details next
    again = client.post("/api/auth/google", json={"credential": "ok" + "x" * 40}).json()
    assert again["user"]["id"] == me["user"]["id"]  # same account, signed in
    # an existing e-mail / password account is signed in (and linked), not duplicated
    client.post("/api/auth/register", json={"name": "Old", "email": "old@gmail.com", "password": "secret123"})
    monkeypatch.setattr(SU, "_verify_google", lambda c, i: {"email": "old@gmail.com", "email_verified": True, "name": "Old", "sub": "g-9"})
    assert client.post("/api/auth/google", json={"credential": "ok" + "x" * 40}).json()["user"]["name"] == "Old"
