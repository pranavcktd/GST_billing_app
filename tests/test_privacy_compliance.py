"""Legal compliance: consent records, DPDP rights requests, incidents, edit log (audit trail), lawful Clear data, HSN."""

import datetime as dt

import pytest
from sqlalchemy import text

from app.db import get_db
from app.main import app
from tests.test_api_flow import make_business, signup
from tests.test_modules import build_books, gstin, post
from tests.test_security_admin import superadmin


def _db():
    gen = app.dependency_overrides.get(get_db, get_db)()
    return next(gen), gen


def test_consent_rights_requests_and_incidents(client, monkeypatch):
    r = client.post("/api/auth/register", json={"name": "No Consent", "email": "nc@x.in", "password": "secret123"})
    assert r.status_code == 422 and "Terms" in r.json()["detail"]
    h = signup(client, "consent@x.in")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["legal_ok"] is True and me["legal_version"]

    root = superadmin(client, monkeypatch)
    legal = client.get("/api/admin/config", headers=root).json()["effective"]["legal"]
    r = client.post("/api/admin/config/versions", headers=root, json={"effective_from": "2026-01-01",
                    "values": {"legal": {**legal, "version": "2027-01-01"}}})
    assert r.status_code == 201, r.text
    assert client.get("/api/auth/me", headers=h).json()["legal_ok"] is False  # asked to accept the new terms
    assert client.post("/api/auth/legal/accept", headers=h).json()["legal_ok"] is True
    assert client.get("/api/auth/me", headers=h).json()["legal_ok"] is True

    mine = client.get("/api/privacy/my-data", headers=h)
    assert mine.status_code == 200 and "attachment" in mine.headers["content-disposition"]
    assert [c["version"] for c in mine.json()["consents"]] == [legal["version"], "2027-01-01"]

    req = post(client, h, "/api/privacy/requests", {"kind": "ERASURE", "details": "Please delete my account"})
    assert req["status"] == "OPEN" and req["due_on"] and len(req["ref"]) == 8
    assert [x["id"] for x in client.get("/api/admin/privacy-requests", headers=root).json()] == [req["id"]]
    done = client.put(f"/api/admin/privacy-requests/{req['id']}", headers=root, json={"status": "CLOSED", "response": "Done", "erase": True})
    assert done.status_code == 200 and "erased" in done.json()["response"]
    assert client.post("/api/auth/login", json={"email": "consent@x.in", "password": "secret123"}).status_code == 401

    inc = post(client, root, "/api/admin/incidents", {"title": "Leaked test key", "description": "A test API key was exposed",
                                                     "severity": "LOW"})
    assert inc["status"] == "OPEN" and inc["notified_count"] == 0
    assert client.post(f"/api/admin/incidents/{inc['id']}/notify", headers=root, json={}).status_code == 503  # no e-mail set up
    assert client.get("/api/admin/incidents", headers=root).json()[0]["title"] == "Leaked test key"


def test_edit_log_and_lawful_clear_data(client, monkeypatch):
    h, ctx = build_books(client)
    party = ctx["cust"]
    client.put(f"/api/parties/{party['id']}", headers=h, json={**{k: v for k, v in party.items() if k in (
        "name", "type", "gst_type", "gstin", "state_code", "opening_balance")}, "phone": "9811112222"})
    ch = client.get("/api/audit/changes", headers=h, params={"row_id": party["id"]}).json()["rows"]
    upd = next(c for c in ch if c["op"] == "UPDATE")
    assert upd["after"]["phone"] == "9811112222" and "phone" in upd["before"] and upd["user"]
    pay = client.get("/api/payments", headers=h).json()[0]
    assert client.delete(f"/api/payments/{pay['id']}", headers=h).status_code == 204
    gone = client.get("/api/audit/changes", headers=h, params={"row_id": pay["id"]}).json()["rows"]
    assert any(c["op"] == "DELETE" and c["before"]["amount"] for c in gone)

    db, gen = _db()
    try:
        if db.get_bind().dialect.name == "postgresql":
            with pytest.raises(Exception):
                db.execute(text("DELETE FROM audit_changes"))
                db.commit()
            db.rollback()
    finally:
        gen.close()

    # Clear data: bills need the "test data" declaration, and reported documents block it
    biz = client.get("/api/businesses/current", headers=h).json()
    r = client.post("/api/data-wipe", headers=h, json={"groups": ["sales"], "confirm_name": biz["name"]})
    assert r.status_code == 400 and "test" in r.json()["detail"]
    post(client, h, "/api/compliance/tasks", {"rule_code": "GSTR3B_M", "period_key": "2026-04", "done_on": "2026-05-20"})
    r = client.post("/api/data-wipe", headers=h, json={"groups": ["sales"], "confirm_name": biz["name"], "test_data": True})
    assert r.status_code == 409 and "72 months" in r.json()["detail"]
    # masters-free groups that are not books can still be cleared
    assert client.post("/api/data-wipe", headers=h, json={"groups": ["documents"], "confirm_name": biz["name"]}).status_code == 200
    wipe_backup = next(b for b in client.get("/api/backups", headers=h).json() if b["kind"] == "WIPE")
    assert client.delete(f"/api/backups/{wipe_backup['id']}", headers=h).status_code == 403


def test_hsn_required_on_b2b_invoices(client):
    h = make_business(client, signup(client, "hsn@x.in"))
    cust = post(client, h, "/api/parties", {"name": "B2B Buyer", "gst_type": "REGISTERED", "gstin": gstin("27", "AAACB1234C")})
    line = {"name": "Widget", "qty": 1, "rate": 100, "gst_rate": 18}
    r = client.post("/api/vouchers", headers=h, json={"type": "SALE", "date": "2026-09-10", "party_id": cust["id"], "lines": [line]})
    assert r.status_code == 400 and "HSN" in r.json()["detail"]
    r = client.post("/api/vouchers", headers=h, json={"type": "SALE", "date": "2026-09-10", "party_id": cust["id"],
                                                      "lines": [{**line, "hsn_sac": "84"}]})
    assert r.status_code == 400  # fewer than 4 digits
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "party_id": cust["id"], "lines": [{**line, "hsn_sac": "8471"}]})
    # B2C (no GSTIN) of a business up to Rs 5 crore: not required
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "fully_paid": True, "lines": [line]})
    assert dt.date.today()
