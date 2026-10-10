"""Login security, super-admin user management, hierarchy, audit, backups (full/account), SMTP and sharing."""

import pyotp
import pytest

from app.config import get_settings
from app.services import mailer
from tests.test_api_flow import make_business, signup
from tests.test_modules import build_books, post
from tests.test_phase2 import setup

SENT: list = []


class FakeSMTP:
    def __init__(self, host, port, timeout=30, **kw):
        self.host = host

    def starttls(self, context=None):
        pass

    def login(self, u, p):
        pass

    def send_message(self, msg):
        SENT.append(msg)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture(autouse=True)
def fake_mail(monkeypatch):
    SENT.clear()
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTP)


def platform_mail(client, from_email="noreply@platform.in"):
    """A platform default e-mail sender (SMTP, so FakeSMTP captures the messages) — e-mail is platform-managed."""
    from app.db import get_db
    from app.main import app
    from app.models import MailSender
    from app.security import encrypt_secret

    gen = app.dependency_overrides.get(get_db, get_db)()
    db = next(gen)
    try:
        db.add(MailSender(label="Platform", provider="SMTP", host="smtp.platform.in", port=587, security="STARTTLS",
                          username="u", secret_enc=encrypt_secret("p"), from_email=from_email, is_default=True))
        db.commit()
    finally:
        gen.close()


def superadmin(client, monkeypatch, email="root@platform.in"):
    monkeypatch.setattr(get_settings(), "superadmin_emails", email)
    return signup(client, email)


def login(client, email, password="secret123", otp=None):
    return client.post("/api/auth/login", json={"email": email, "password": password, **({"otp": otp} if otp else {})})


def test_lockout_and_session_revocation(client):
    h = signup(client, "user@x.in")
    for _ in range(5):
        assert login(client, "user@x.in", "wrong-pass").status_code == 401
    assert login(client, "user@x.in").status_code == 423  # locked even with the right password
    # change password signs out other sessions
    h2 = signup(client, "user2@x.in")
    r = client.put("/api/auth/password", headers=h2, json={"current_password": "secret123", "new_password": "newsecret1"})
    new_token = r.json()["token"]
    assert client.get("/api/auth/me", headers=h2).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200
    assert client.post("/api/auth/logout-all", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 401
    _ = h


def test_forgot_password_temporary_password(client):
    signup(client, "forgot@x.in")
    r = client.post("/api/auth/forgot", json={"email": "forgot@x.in"}).json()
    temp = r["dev_temp_password"]  # no SMTP configured in dev → returned for testing
    assert len(temp) == 14 and "temporary password" in r["message"]
    miss = client.post("/api/auth/forgot", json={"email": "nobody@x.in"}).json()
    assert miss["ok"] and miss["message"] == r["message"] and "dev_temp_password" not in miss  # same answer, no leak
    # the old password still works until the temporary one is used (no lock-out by strangers)
    first = login(client, "forgot@x.in")
    assert first.status_code == 200 and not first.json()["must_change_password"]
    # sign in with the temporary password → must set a new one
    r2 = login(client, "forgot@x.in", temp)
    assert r2.status_code == 200 and r2.json()["must_change_password"]
    assert r2.json()["previous_login_at"] is not None  # the earlier sign-in above
    assert login(client, "forgot@x.in").status_code == 401  # old password replaced
    assert login(client, "forgot@x.in", temp).status_code == 200  # (now the current password until changed)
    h = {"Authorization": f"Bearer {login(client, 'forgot@x.in', temp).json()['token']}"}
    ok = client.put("/api/auth/password", headers=h, json={"current_password": temp, "new_password": "brandnew99"})
    assert ok.status_code == 200
    me = login(client, "forgot@x.in", "brandnew99").json()
    assert not me["must_change_password"]
    # rate limit: at most 3 e-mails an hour, same answer
    for _ in range(3):
        client.post("/api/auth/forgot", json={"email": "forgot@x.in"})
    assert "dev_temp_password" not in client.post("/api/auth/forgot", json={"email": "forgot@x.in"}).json()


def test_two_factor_login(client):
    h = signup(client, "2fa@x.in")
    secret = client.post("/api/auth/2fa/setup", headers=h).json()["secret"]
    assert client.post("/api/auth/2fa/enable", headers=h, json={"code": "000000"}).status_code == 400
    assert client.post("/api/auth/2fa/enable", headers=h, json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    r = login(client, "2fa@x.in")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "OTP_REQUIRED"
    assert login(client, "2fa@x.in", otp=pyotp.TOTP(secret).now()).status_code == 200


def test_superadmin_user_management(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    shop = make_business(client, signup(client, "owner@x.in"))
    # create users at every level
    res = post(client, root, "/api/admin/users", {"name": "Partner", "email": "p@x.in", "level": "RESELLER", "commission_pct": 15})
    assert res["temporary_password"]
    own = post(client, root, "/api/admin/users", {"name": "New Owner", "email": "o2@x.in", "level": "OWNER", "plan": "STARTER",
                                                  "valid_days": 30, "reseller_id": res["id"]})
    staff = post(client, root, "/api/admin/users", {"name": "Clerk", "email": "clerk@x.in", "level": "STAFF",
                                                    "business_id": shop["X-Business-Id"], "role": "INVENTORY", "password": "clerkpass1"})
    assert login(client, "clerk@x.in", "clerkpass1").json()["businesses"][0]["role"] == "INVENTORY"
    # temporary password must be changed after sign-in
    assert login(client, "o2@x.in", own["temporary_password"]).json()["must_change_password"] is True
    levels = {u["email"]: u["level"] for u in client.get("/api/admin/users", headers=root).json()}
    assert levels["p@x.in"] == "RESELLER" and levels["o2@x.in"] == "OWNER" and levels["clerk@x.in"] == "STAFF"
    tree = client.get("/api/admin/hierarchy", headers=root).json()
    assert tree["resellers"][0]["accounts"][0]["email"] == "o2@x.in"
    shop_node = next(a for a in tree["direct_accounts"] if a["email"] == "owner@x.in")
    assert shop_node["businesses"][0]["staff"][0]["email"] == "clerk@x.in"

    # deactivate → signed out immediately and cannot sign in
    clerk_token = login(client, "clerk@x.in", "clerkpass1").json()["token"]
    client.put(f"/api/admin/users/{staff['id']}/active", headers=root, json={"active": False})
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {clerk_token}"}).status_code == 401
    assert login(client, "clerk@x.in", "clerkpass1").status_code == 403
    client.put(f"/api/admin/users/{staff['id']}/active", headers=root, json={"active": True})
    # reset password to a temporary one
    temp = post(client, root, f"/api/admin/users/{staff['id']}/reset-password", {"mode": "temp"}, 200)["temporary_password"]
    assert login(client, "clerk@x.in", temp).status_code == 200
    # safety rules
    root_id = client.get("/api/auth/me", headers=root).json()["user"]["id"]
    assert client.delete(f"/api/admin/users/{root_id}", headers=root).status_code == 400
    assert client.put(f"/api/admin/users/{root_id}/platform-role", headers=root, json={"role": None}).status_code == 400
    owner_id = client.get("/api/auth/me", headers=shop).json()["user"]["id"]
    assert client.delete(f"/api/admin/users/{owner_id}", headers=root).status_code == 409  # owns a business
    # transfer the business, then the old owner can be deleted
    post(client, root, f"/api/admin/businesses/{shop['X-Business-Id']}/transfer", {"new_owner_email": "o2@x.in"}, 200)
    assert client.delete(f"/api/admin/users/{owner_id}", headers=root).status_code == 200
    me_o2 = login(client, "o2@x.in", temp_pw := post(client, root, f"/api/admin/users/{own['id']}/reset-password", {"mode": "temp"}, 200)["temporary_password"]).json()
    assert any(b["owned"] for b in me_o2["businesses"]) and temp_pw
    # non-admins are refused
    assert client.get("/api/admin/users", headers=shop).status_code in (401, 403)

    audit = client.get("/api/admin/audit", headers=root).json()["rows"]
    summaries = " | ".join(r["summary"] for r in audit)
    for text in ("Created reseller p@x.in", "Deactivated clerk@x.in", "Transferred", "Deleted user owner@x.in", "Signed in"):
        assert text in summaries, text


def test_full_and_account_backups(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    h, _ = build_books(client)
    owner_id = client.get("/api/auth/me", headers=h).json()["user"]["id"]
    before = client.get("/api/reports/run/balance-sheet", headers=h, params={"as_of": "2026-06-30"}).json()["summary"]

    acc = post(client, root, "/api/admin/backups", {"scope": "ACCOUNT", "ref_id": owner_id})
    full = post(client, root, "/api/admin/backups", {"scope": "FULL"})
    biz = post(client, root, "/api/admin/backups", {"scope": "BUSINESS", "ref_id": h["X-Business-Id"]})
    listing = client.get("/api/admin/backups", headers=root).json()
    assert len(listing["platform"]) == 2 and len(listing["business"]) >= 1
    blob = client.get(f"/api/admin/backups/{acc['id']}/download", headers=root).content

    # account backup → imported into another owner as new businesses
    signup(client, "target@x.in")
    r = client.post("/api/admin/backups/import", headers=root, files={"file": ("acc.gstbak", blob)}, data={"owner_email": "target@x.in"})
    assert r.status_code == 200 and r.json()["restored"] == "ACCOUNT", r.text

    # full restore needs the confirmation phrase
    full_blob = client.get(f"/api/admin/backups/{full['id']}/download", headers=root).content
    r = client.post("/api/admin/backups/import", headers=root, files={"file": ("full.gstbak", full_blob)})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "CONFIRM_FULL"
    # wreck some data, then restore everything
    v = client.get("/api/vouchers?type=SALE", headers=h).json()[0]
    post(client, h, f"/api/vouchers/{v['id']}/cancel", {}, 200)
    r = client.post("/api/admin/backups/import", headers=root, files={"file": ("full.gstbak", full_blob)},
                    data={"confirm": "RESTORE ALL DATA"})
    assert r.status_code == 200 and r.json()["safety_backup_id"], r.text
    # the super admin still works, the owner too, and the books match the moment of the backup
    assert client.get("/api/admin/stats", headers=root).status_code == 200
    after = client.get("/api/reports/run/balance-sheet", headers=h, params={"as_of": "2026-06-30"}).json()["summary"]
    assert after == before
    assert not client.get(f"/api/vouchers/{v['id']}", headers=h).json()["cancelled"]
    assert biz["business"]


def test_smtp_levels_and_invoice_email(client, monkeypatch):
    """E-mail is platform-managed: a default sender for everyone, an own sender for one business, API providers."""
    from app.services import mailer

    root = superadmin(client, monkeypatch)
    h, cust, item = setup(client)
    assert client.put("/api/smtp", headers=h, json={"host": "smtp.shop.in", "from_email": "billing@shop.in", "password": "x"}).status_code == 403
    sm = post(client, root, "/api/admin/mail/senders", {"label": "Platform SMTP", "provider": "SMTP", "host": "smtp.platform.in",
                                                         "port": 587, "security": "STARTTLS", "username": "u", "secret": "p",
                                                         "from_email": "noreply@platform.in"})
    assert sm["is_default"] and sm["secret_set"] and "secret" not in sm
    st = client.get("/api/smtp", headers=h).json()
    biz = client.get("/api/businesses/current", headers=h).json()
    assert st["effective_source"] == "PLATFORM" and st["from_email"] == "noreply@platform.in" and st["from_name"] == biz["name"]
    v0 = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "party_id": cust["id"],
                                           "lines": [{"item_id": item["id"], "name": "Bottle", "qty": 1, "rate": 500, "gst_rate": 18}]})
    post(client, h, f"/api/vouchers/{v0['id']}/email", {"to": ["buyer@client.in"]}, 200)
    assert biz["name"] in SENT[-1]["From"] and "noreply@platform.in" in SENT[-1]["From"]

    # an own sender (Brevo API) for this business
    calls = []
    monkeypatch.setattr(mailer, "_http_post", lambda url, headers, body: calls.append((url, headers, body)) or __import__("httpx").Response(201, json={"messageId": "x"}))
    br = post(client, root, "/api/admin/mail/senders", {"label": "Shop domain", "provider": "BREVO", "secret": "xkeysib-123",
                                                         "from_email": "billing@shop.in", "from_name": "Sharma Traders"})
    assert not br["is_default"]
    assert client.put(f"/api/admin/mail/businesses/{h['X-Business-Id']}", headers=root, json={"sender_id": br["id"]}).status_code == 200
    assert client.get("/api/smtp", headers=h).json()["effective_source"] == "BUSINESS"
    v = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "party_id": cust["id"],
                                          "lines": [{"item_id": item["id"], "name": "Bottle", "qty": 2, "rate": 500, "gst_rate": 18}]})
    r = post(client, h, f"/api/vouchers/{v['id']}/email", {"to": ["buyer@client.in"], "message": "Thanks!"}, 200)
    assert r["via"] == "BUSINESS" and "/i/" in r["link"]
    url, headers, body = calls[-1]
    assert url == "https://api.brevo.com/v3/smtp/email" and headers["api-key"] == "xkeysib-123"
    assert body["sender"]["email"] == "billing@shop.in" and body["to"] == [{"email": "buyer@client.in"}]
    import base64
    assert len(body["attachment"]) == 1 and base64.b64decode(body["attachment"][0]["content"])[:5] == b"%PDF-"
    post(client, h, f"/api/vouchers/{v['id']}/email", {"to": ["buyer@client.in"], "attach_pdf": False}, 200)
    assert "attachment" not in calls[-1][2]
    # ZeptoMail (India data centre) request format, and a provider refusal shows its message
    zp = post(client, root, "/api/admin/mail/senders", {"label": "Zepto", "provider": "ZEPTOMAIL", "region": "IN", "secret": "abc",
                                                         "from_email": "bills@shop.in"})
    assert post(client, root, f"/api/admin/mail/senders/{zp['id']}/test", {"to": "me@shop.in"}, 200)["sent"]
    url, headers, body = calls[-1]
    assert url == "https://api.zeptomail.in/v1.1/email" and headers["Authorization"] == "Zoho-enczapikey abc"
    assert body["to"] == [{"email_address": {"address": "me@shop.in"}}]
    monkeypatch.setattr(mailer, "_http_post", lambda *a: __import__("httpx").Response(401, json={"error": {"message": "Invalid API Token"}}))
    refused = client.post(f"/api/admin/mail/senders/{zp['id']}/test", headers=root, json={"to": "me@shop.in"})
    assert refused.status_code == 502 and "Invalid API Token" in refused.json()["detail"]
    assert client.get("/api/admin/mail/senders", headers=root).json()["senders"][-1]["last_error"]
    token = r["link"].rsplit("/", 1)[1]
    pub = client.get(f"/api/public/invoice/{token}")  # no login
    assert pub.status_code == 200 and pub.json()["voucher"]["number"] == v["number"]
    assert "bank_account_no" in pub.json()["business"] and "einvoice_password_enc" not in pub.json()["business"]
    client.delete(f"/api/vouchers/{v['id']}/share-link", headers=h)
    assert client.get(f"/api/public/invoice/{token}").status_code == 404

    # forgot password now goes out through the platform SMTP
    signup(client, "someone@x.in")
    out = client.post("/api/auth/forgot", json={"email": "someone@x.in"}).json()
    assert "dev_temp_password" not in out and "noreply@platform.in" in SENT[-1]["From"]
    assert "temporary password" in SENT[-1]["Subject"]


def test_hierarchy_resets(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    partner = signup(client, "partner@x.in")
    post(client, root, "/api/admin/resellers", {"email": "partner@x.in", "commission_pct": 20})
    acc = post(client, partner, "/api/reseller/accounts", {"name": "Trader", "email": "trader@x.in"})
    temp = post(client, partner, f"/api/reseller/accounts/{acc['account_id']}/user", {"action": "reset_temp"}, 200)["temporary_password"]
    assert login(client, "trader@x.in", temp).status_code == 200
    post(client, partner, f"/api/reseller/accounts/{acc['account_id']}/user", {"action": "deactivate"}, 200)
    assert login(client, "trader@x.in", temp).status_code == 403
    # owner e-mails a reset link to their staff
    h, _, _ = setup(client)
    s9 = signup(client, "staff9@x.in")
    post(client, h, "/api/members", {"email": "staff9@x.in", "role": "BILLING"})
    from tests.test_rbac import accept_invites
    accept_invites(client, s9)
    m = next(x for x in client.get("/api/members", headers=h).json() if x["email"] == "staff9@x.in")
    assert post(client, h, f"/api/members/{m['id']}/reset-password", {}, 200)["sent"]


def test_server_listed_super_admin_cannot_be_demoted_in_ui(client, monkeypatch):
    """E-mails in SUPERADMIN_EMAILS are made super admin on every request, so the panel refuses to demote them."""
    monkeypatch.setattr(get_settings(), "superadmin_emails", "root@platform.in,boss@platform.in")
    root = signup(client, "root@platform.in")
    signup(client, "boss@platform.in")
    client.get("/api/auth/me", headers=root)
    users = client.get("/api/admin/users", headers=root).json()
    boss = next(u for u in (users if isinstance(users, list) else users["users"]) if u["email"] == "boss@platform.in")
    assert boss["superadmin_by_server"] is True
    r = client.put(f"/api/admin/users/{boss['id']}/platform-role", headers=root, json={"role": None})
    assert r.status_code == 400 and "SUPERADMIN_EMAILS" in r.json()["detail"]
