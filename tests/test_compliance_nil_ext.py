"""Nil-return alerts from the business's own data, one-off due-date extensions, per-business filing-status switch."""

import datetime as dt

from tests.test_api_flow import make_business, signup
from tests.test_gstin_verify import enable
from tests.test_modules import post
from tests.test_security_admin import superadmin


def _cal(client, h):
    return client.get("/api/compliance/calendar", headers=h, params={"ahead_days": 400}).json()


def test_nil_return_alert_and_extension(client, monkeypatch):
    h = make_business(client, signup(client, "nil@x.in"))
    client.put("/api/compliance/settings", headers=h, json={"gst_filing": "MONTHLY", "tax_audit": False, "tds": True,
                                                             "pf": True, "esi": False, "employees": 25, "track_from": "2026-04-01"})
    items = _cal(client, h)["items"]
    g = [i for i in items if i["code"] == "GSTR3B_M" and i["status"] != "DONE"]
    ended = [i for i in g if dt.date.fromisoformat(i["period_end"]) < dt.date.today()]
    assert ended and all(i["nil"] is True for i in ended)  # no sales or purchases yet → nil return
    assert "nil return must still be filed" in ended[0]["nil_note"]
    assert any(i["code"] == "PF" and i["nil"] for i in items) and any(i["code"] == "TDS_RET" and i["nil_note"] for i in items)

    # a sale in that month → not nil any more
    month = ended[0]["period_start"]
    item = post(client, h, "/api/items", {"name": "Thing", "sale_price": 100, "gst_rate": 18, "unit": "PCS"})
    post(client, h, "/api/vouchers", {"type": "SALE", "date": month, "fully_paid": True, "allow_negative": True,
                                      "lines": [{"item_id": item["id"], "name": "Thing", "qty": 1, "rate": 100, "gst_rate": 18}]})
    again = next(i for i in _cal(client, h)["items"] if i["code"] == "GSTR3B_M" and i["period_key"] == ended[0]["period_key"])
    assert again["nil"] is False
    reg = client.get("/api/compliance/register", headers=h, params={"law": "GST"}).json()
    assert reg["rows"] and all("nil" in r and "nil_note" in r for r in reg["rows"])  # rows carry the flag

    # super admin extends one period's due date
    root = superadmin(client, monkeypatch)
    target = next(i for i in _cal(client, h)["items"] if i["code"] == "GSTR1_M" and i["status"] != "DONE")
    new_due = (dt.date.fromisoformat(target["due_date"]) + dt.timedelta(days=10)).isoformat()
    bad = client.post("/api/admin/config/versions", headers=root, json={"effective_from": "2026-01-01",
                      "values": {"compliance_extensions": [{"code": "GSTR1_M", "period_key": target["period_key"], "due_date": "31/02/2026"}]}})
    assert bad.status_code == 422
    r = client.post("/api/admin/config/versions", headers=root, json={"effective_from": "2026-01-01", "values": {"compliance_extensions": [
        {"code": "GSTR1_M", "period_key": target["period_key"], "due_date": new_due, "note": "Notification 99/2026-CT"}]}})
    assert r.status_code == 201, r.text
    ext = next(i for i in _cal(client, h)["items"] if i["code"] == "GSTR1_M" and i["period_key"] == target["period_key"])
    assert ext["due_date"] == new_due and ext["extended_from"] == target["due_date"] and "99/2026" in ext["extension_note"]
    assert "compliance_extensions" not in client.get("/api/meta").json()["config"]


def test_filing_sync_switch_per_business(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    enable(client, root, filing_sync=False)
    h = make_business(client, signup(client, "sync@x.in"))
    bid = h["X-Business-Id"]
    assert client.get("/api/compliance/sync/available", headers=h).json()["available"] is False
    r = client.put(f"/api/admin/businesses/{bid}/filing-sync", headers=root, json={"enabled": True})
    assert r.json() == {"filing_sync": True, "filing_sync_on": True}
    assert client.get("/api/compliance/sync/available", headers=h).json()["available"] is True
    other = make_business(client, signup(client, "other@x.in"))
    assert client.get("/api/compliance/sync/available", headers=other).json()["available"] is False  # only that business
    # platform default on, this business switched off
    enable(client, root, filing_sync=True)
    client.put(f"/api/admin/businesses/{bid}/filing-sync", headers=root, json={"enabled": False})
    assert client.get("/api/compliance/sync/available", headers=h).json()["available"] is False
    assert client.get("/api/compliance/sync/available", headers=other).json()["available"] is True
    row = next(x for x in client.get("/api/admin/businesses", headers=root).json() if x["id"] == bid)
    assert row["filing_sync"] is False and row["filing_sync_on"] is False
