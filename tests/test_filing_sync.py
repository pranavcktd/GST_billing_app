"""Compliance calendar: fetch GST return filing status from the provider without spending credit twice."""

import httpx

from app.services import filing_sync as FS
from app.services import gstin_verify as G
from tests.test_api_flow import make_business, signup
from tests.test_gstin_verify import enable
from tests.test_modules import post
from tests.test_security_admin import superadmin

CALLS: list[str] = []


def provider(monkeypatch, returns):
    CALLS.clear()

    def get(url, key):
        CALLS.append(url)
        fy = url.split("fy=")[1]
        return httpx.Response(200, json={"success": True, "fy": fy, "returns": returns.get(fy, [])})

    monkeypatch.setattr(G, "_http_get", get)
    monkeypatch.setattr(G.time, "sleep", lambda s: None)


def test_parse_shapes():
    ours = FS.parse({"returns": [{"return_type": "GSTR-3B", "return_period": "2025-06", "filing_status": "Filed",
                                  "filing_date": "2025-07-20", "arn": "AA33"}, {"return_type": "GSTR1", "return_period": "2025-07",
                                  "filing_status": "Not Filed"}]})
    assert len(ours) == 1 and {k: ours[0][k] for k in ("type", "year", "month", "arn")} == {"type": "GSTR3B", "year": 2025, "month": 6, "arn": "AA33"}
    assert str(ours[0]["filed_on"]) == "2025-07-20"
    portal = FS.parse({"EFiledlist": [{"rtntype": "GSTR1", "ret_prd": "042025", "dof": "11-05-2025", "arn": "AB1", "status": "Filed", "valid": "Y"}]})
    assert portal[0]["type"] == "GSTR1" and (portal[0]["year"], portal[0]["month"]) == (2025, 4)
    assert ("GSTR1_Q", "FY2025-Q1") in FS.keys_for(portal[0]) and ("GSTR1_M", "2025-04") in FS.keys_for(portal[0])
    assert FS.keys_for({"type": "GSTR9", "year": 2026, "month": 3})[0] == ("GSTR9", "FY2025")


def test_sync_marks_filed_and_saves_credit(client, monkeypatch):
    h = make_business(client, signup(client))
    # not available until the super admin switches the GST data service on
    assert client.post("/api/compliance/sync", headers=h).status_code == 503
    root = superadmin(client, monkeypatch)
    enable(client, root, filing_sync_hours=24)
    assert client.get("/api/compliance/sync/available", headers=h).json()["available"]

    client.put("/api/compliance/settings", headers=h, json={"gst_filing": "MONTHLY", "track_from": "2026-04-01"})
    provider(monkeypatch, {"2026-27": [
        {"return_type": "GSTR-1", "return_period": "2026-04", "filing_status": "Filed", "filing_date": "2026-05-10", "arn": "AA270426001"},
        {"return_type": "GSTR-3B", "return_period": "2026-04", "filing_status": "Filed", "filing_date": "2026-05-19", "arn": "AA270426002"},
    ]})
    # a return marked by hand stays as it is
    post(client, h, "/api/compliance/tasks", {"rule_code": "GSTR3B_M", "period_key": "2026-04", "done_on": "2026-05-18", "reference": "MANUAL1"})
    r = client.post("/api/compliance/sync", headers=h).json()
    # FY 2025-26 too: the March 2026 returns fall due in April 2026
    assert r["calls"] == 2 and r["added"] == 1 and r["fetched_years"] == ["2025-26", "2026-27"]
    assert all("/v1/gstin/27AABCS1429B" in u and "/returns?fy=" in u for u in CALLS)
    items = {(i["code"], i["period_key"]): i for i in client.get("/api/compliance/calendar", headers=h).json()["items"]}
    assert items[("GSTR1_M", "2026-04")]["done"]["reference"] == "AA270426001" and items[("GSTR1_M", "2026-04")]["done"]["source"] == "SYNC"
    assert items[("GSTR3B_M", "2026-04")]["done"]["reference"] == "MANUAL1"

    # the same year is not fetched again within 24 hours
    r = client.post("/api/compliance/sync", headers=h).json()
    assert r["calls"] == 0 and r["skipped_years"] == ["2025-26", "2026-27"] and len(CALLS) == 2

    # a business without unfiled GST returns makes no call at all
    other = make_business(client, signup(client, "u2@x.in"), gst_type="UNREGISTERED", gstin=None)
    assert client.post("/api/compliance/sync", headers=other).status_code == 400


def test_gst_register_shows_portal_data(client, monkeypatch):
    h = make_business(client, signup(client))
    root = superadmin(client, monkeypatch)
    enable(client, root)
    client.put("/api/compliance/settings", headers=h, json={"gst_filing": "MONTHLY", "track_from": "2026-04-01"})
    provider(monkeypatch, {"2026-27": [
        {"return_type": "GSTR-1", "return_period": "2026-04", "filing_status": "Filed", "filing_date": "2026-05-10", "arn": "AA1"},
        {"return_type": "GSTR-3B", "return_period": "2026-04", "filing_status": "Not Filed"},
        {"return_type": "IFF", "return_period": "2026-05", "filing_status": "Filed", "filing_date": "2026-06-12", "arn": "AA9"},
    ]})
    post(client, h, "/api/compliance/tasks", {"rule_code": "GSTR1_M", "period_key": "2026-05", "done_on": "2026-06-10", "reference": "MAN"})
    r = client.post("/api/compliance/sync", headers=h, params={"fy": 2026}).json()
    assert r["fetched_years"] == ["2026-27"] and len(CALLS) == 1  # only the chosen year

    reg = client.get("/api/compliance/register", headers=h, params={"law": "GST", "fy": 2026}).json()
    assert [c["code"] for c in reg["columns"]][:2] == ["GSTR1_M", "GSTR3B_M"] and reg["fy_label"] == "2026-27"
    cell = {(x["code"], x["period_key"]): x for x in reg["rows"]}
    assert cell[("GSTR1_M", "2026-04")]["done"]["source"] == "SYNC" and cell[("GSTR1_M", "2026-04")]["done"]["reference"] == "AA1"
    assert cell[("GSTR1_M", "2026-05")]["done"]["source"] == "MANUAL"
    assert cell[("GSTR3B_M", "2026-04")]["status"] == "OVERDUE"
    portal = {(p["return_type"], p["return_period"]): p for p in reg["portal"]}
    assert portal[("GSTR3B", "2026-04")]["filed"] is False and portal[("IFF", "2026-05")]["arn"] == "AA9"  # everything the portal said
    assert reg["portal_fetched_at"]
    assert "TDS" not in reg["laws"] and client.get("/api/compliance/register", headers=h, params={"law": "INCOME_TAX", "fy": 2025}).json()["rows"]
