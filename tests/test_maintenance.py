"""Planned downtime: schedule, countdown in /meta, everyone but super admins signed out and kept out, notices, go live."""

import datetime as dt

from app.routers import maintenance as maint_router
from app.services import maintenance as MT
from tests.test_api_flow import make_business, signup
from tests.test_payment_records import make_staff
from tests.test_security_admin import SENT, fake_mail, platform_mail, superadmin  # noqa: F401


def test_maintenance_window(client, monkeypatch):
    monkeypatch.setattr(maint_router, "SYNC", True)
    MT.clear_cache()
    root = superadmin(client, monkeypatch)
    platform_mail(client)
    owner = signup(client)
    h = make_business(client, owner)
    team = make_staff(client, "help@platform.in", ["helpdesk"], "SUPPORT")
    client.get("/api/auth/me", headers=root)

    # scheduled for later: countdown visible, nobody blocked yet
    later = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=2)).isoformat()
    SENT.clear()
    r = client.put("/api/admin/maintenance", headers=root, json={"starts_at": later, "message": "Upgrading to v2 — back soon.",
                                                                 "notify_email": True})
    assert r.status_code == 200, r.text
    assert r.json()["scheduled"] and not r.json()["active"] and r.json()["owners"] == 1
    assert client.get("/api/meta").json()["maintenance"]["scheduled"]
    assert client.get("/api/businesses/current", headers=h).status_code == 200
    assert [m["To"] for m in SENT] == ["owner@shop.in"] and "maintenance" in SENT[0]["Subject"]
    assert client.put("/api/admin/maintenance", headers=owner, json={"message": "hello there"}).status_code == 403

    # start now: owner and team member are out, super admin carries on
    end = (dt.datetime.now(dt.UTC) + dt.timedelta(minutes=30)).isoformat()
    client.put("/api/admin/maintenance", headers=root, json={"ends_at": end, "message": "Upgrading to v2 — back soon.", "notify_email": False})
    meta = client.get("/api/meta").json()["maintenance"]
    assert meta["active"] and meta["ends_at"] and meta["message"].startswith("Upgrading")
    r = client.get("/api/businesses/current", headers=h)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "MAINTENANCE"
    assert client.get("/api/admin/helpdesk", headers=team).status_code == 503
    assert client.get("/api/admin/maintenance", headers=root).status_code == 200
    login = client.post("/api/auth/login", json={"email": "owner@shop.in", "password": "secret123"})
    assert login.status_code == 503 and login.json()["detail"]["code"] == "MAINTENANCE"
    assert client.post("/api/auth/login", json={"email": "root@platform.in", "password": "secret123"}).status_code == 200
    assert client.get("/api/meta").status_code == 200  # public pages keep working

    # end must be after start
    bad = client.put("/api/admin/maintenance", headers=root, json={"starts_at": later, "ends_at": end, "message": "Upgrading again"})
    assert bad.status_code == 422

    # mark live, tell owners
    SENT.clear()
    r = client.post("/api/admin/maintenance/end", headers=root, json={"notify_email": True})
    assert not r.json()["active"] and r.json()["notified"]["kind"] == "end"
    assert "back online" in SENT[0]["Subject"]
    assert client.get("/api/businesses/current", headers=h).status_code == 200
    assert client.post("/api/auth/login", json={"email": "owner@shop.in", "password": "secret123"}).status_code == 200

    # auto-end: a window whose end has passed is over by itself
    past_start = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)).isoformat()
    past_end = (dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)).isoformat()
    from app.db import get_db
    from app.main import app
    gen = app.dependency_overrides.get(get_db, get_db)()
    db = next(gen)
    try:
        MT.save(db, {"active": True, "starts_at": past_start, "ends_at": past_end, "auto_end": True}, "test")
        db.commit()
    finally:
        gen.close()
    assert client.get("/api/businesses/current", headers=h).status_code == 200
    MT.clear_cache()
