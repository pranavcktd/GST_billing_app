"""Compliance calendar: rules by registration and constitution, due dates, mark as filed, admin-editable rules."""

import datetime as dt
from types import SimpleNamespace as N

from app.gst.constants import BusinessGstType
from app.services import compliance_calendar as CC
from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_security_admin import superadmin

TODAY = dt.date(2026, 10, 6)


def biz(gst="REGULAR", entity="PROPRIETORSHIP", state="27", **settings):
    return N(gst_type=BusinessGstType(gst), entity_type=entity, state_code=state, created_at=None,
             compliance_settings={"track_from": "2026-04-01", **settings})


def codes(b, ahead=120):
    return {i["code"] for i in CC.calendar_for(b, CC.DEFAULT_RULES, {}, today=TODAY, ahead_days=ahead)["items"]}


def due(b, code, period_key):
    items = CC.calendar_for(b, CC.DEFAULT_RULES, {}, today=TODAY, ahead_days=400)["items"]
    return next(i["due_date"] for i in items if i["code"] == code and i["period_key"] == period_key)


def test_rules_follow_registration_and_constitution():
    monthly = codes(biz())
    assert {"GSTR1_M", "GSTR3B_M", "ADV_TAX", "ITR"} <= monthly
    assert not monthly & {"GSTR1_Q", "CMP08", "AOC4", "LLP11", "TDS_PAY", "PF", "ITR_AUDIT"}
    assert {"GSTR1_Q", "GSTR3B_Q", "PMT06"} <= codes(biz(gst_filing="QUARTERLY"))
    assert {"CMP08"} <= codes(biz("COMPOSITION")) and not codes(biz("COMPOSITION")) & {"GSTR1_M", "GSTR3B_M"}
    assert not codes(biz("UNREGISTERED")) & {"GSTR1_M", "GSTR3B_M", "CMP08"}
    company = codes(biz(entity="PRIVATE_LIMITED", tds=True, payroll=True))
    assert {"AGM", "AOC4", "MGT7", "ITR_CO", "TDS_PAY", "TDS_RET", "PF", "ESI"} <= company and "ITR" not in company
    assert {"LLP11", "LLP8"} <= codes(biz(entity="LLP"), 400) and "AOC4" not in codes(biz(entity="LLP"), 400)
    audited = codes(biz(tax_audit=True))
    assert "ITR_AUDIT" in audited and "TAX_AUDIT" in audited and "ITR" not in audited


def test_due_dates():
    assert due(biz(), "GSTR3B_M", "2026-09") == dt.date(2026, 10, 20)
    assert due(biz(), "GSTR1_M", "2026-09") == dt.date(2026, 10, 11)
    # QRMP GSTR-3B: 22nd in Maharashtra, 24th in Delhi; PMT-06 only for the first two months of a quarter
    assert due(biz(gst_filing="QUARTERLY"), "GSTR3B_Q", "FY2026-Q2") == dt.date(2026, 10, 22)
    assert due(biz(gst_filing="QUARTERLY", state="07"), "GSTR3B_Q", "FY2026-Q2") == dt.date(2026, 10, 24)
    pmt = {i["period_key"] for i in CC.calendar_for(biz(gst_filing="QUARTERLY"), CC.DEFAULT_RULES, {}, today=TODAY)["items"] if i["code"] == "PMT06"}
    assert "2026-07" in pmt and "2026-08" in pmt and "2026-09" not in pmt
    # TDS: March deposit by 30 April, Q4 return by 31 May
    t = biz(tds=True)
    assert due(t, "TDS_PAY", "2026-03") == dt.date(2026, 4, 30) and due(t, "TDS_PAY", "2026-04") == dt.date(2026, 5, 7)
    assert due(t, "TDS_RET", "FY2025-Q4") == dt.date(2026, 5, 31) and due(t, "TDS_RET", "FY2026-Q2") == dt.date(2026, 10, 31)
    # advance tax falls inside the year; the return in the year after it
    assert due(biz(), "ADV_TAX", "FY2026#4") == dt.date(2027, 3, 15)
    assert due(biz(), "ITR", "FY2025") == dt.date(2026, 7, 31)


def test_status_and_late_fee():
    items = CC.calendar_for(biz(), CC.DEFAULT_RULES, {("GSTR3B_M", "2026-08"): {"id": "x"}}, today=TODAY)["items"]
    by = {(i["code"], i["period_key"]): i for i in items}
    assert by[("GSTR3B_M", "2026-08")]["status"] == "DONE"
    late = by[("GSTR1_M", "2026-08")]  # due 11 Sep
    assert late["status"] == "OVERDUE" and late["days_overdue"] == 25 and late["late_fee_so_far"] == 1250
    assert by[("GSTR1_M", "2026-04")]["late_fee_so_far"] == 7400  # due 11 May: 148 days x ₹50
    old = CC.calendar_for(biz(track_from="2025-07-01"), CC.DEFAULT_RULES, {}, today=TODAY)["items"]
    assert next(i for i in old if i["code"] == "GSTR1_M" and i["period_key"] == "2025-07")["late_fee_so_far"] == 10000  # capped
    assert by[("GSTR1_M", "2026-09")]["status"] == "DUE_SOON"
    assert "₹50" in late["penalty"] and "{" not in late["penalty"]


def test_calendar_api(client, monkeypatch):
    h = make_business(client, signup(client), entity_type="LLP")
    cal = client.get("/api/compliance/calendar", headers=h).json()
    assert cal["entity_type"] == "LLP" and cal["settings"]["gst_filing"] == "MONTHLY" and cal["disclaimer"]
    # tracking starts on the day the business joined: no old overdue items
    assert cal["summary"]["OVERDUE"] == 0
    s = client.put("/api/compliance/settings", headers=h, json={"gst_filing": "MONTHLY", "tds": True, "track_from": "2026-04-01"}).json()
    assert s["tds"] is True and s["track_from"] == "2026-04-01"
    cal = client.get("/api/compliance/calendar", headers=h).json()
    item = next(i for i in cal["items"] if i["code"] == "GSTR3B_M" and i["status"] == "OVERDUE")
    r = post(client, h, "/api/compliance/tasks", {"rule_code": "GSTR3B_M", "period_key": item["period_key"], "done_on": "2026-05-19", "reference": "AA2705260012345"})
    after = client.get("/api/compliance/calendar", headers=h).json()
    done = next(i for i in after["items"] if i["code"] == "GSTR3B_M" and i["period_key"] == item["period_key"])
    assert done["status"] == "DONE" and done["done"]["reference"] == "AA2705260012345"
    assert after["summary"]["OVERDUE"] == cal["summary"]["OVERDUE"] - 1
    assert client.get("/api/compliance/summary", headers=h).json()["summary"]["OVERDUE"] >= 1
    assert client.post("/api/compliance/tasks", headers=h, json={"rule_code": "NOPE", "period_key": "2026-01", "done_on": "2026-01-01"}).status_code == 404
    assert client.delete(f"/api/compliance/tasks/{r['id']}", headers=h).status_code == 204

    # the rules are not sent to every browser, and the super admin can change them
    assert "compliance_rules" not in client.get("/api/meta").json()["config"]
    root = superadmin(client, monkeypatch)
    rules = client.get("/api/admin/config", headers=root).json()["effective"]["compliance_rules"]
    bad = client.post("/api/admin/config/versions", headers=root, json={"effective_from": "2026-01-01", "values": {"compliance_rules": [{"code": "X"}]}})
    assert bad.status_code == 422
    changed = [{**r, "due": {**r["due"], "day": 25}} if r["code"] == "GSTR3B_M" else r for r in rules]
    assert client.post("/api/admin/config/versions", headers=root, json={"effective_from": "2026-01-01", "values": {"compliance_rules": changed}}).status_code == 201
    cal = client.get("/api/compliance/calendar", headers=h).json()
    assert all(i["due_date"].endswith("-25") for i in cal["items"] if i["code"] == "GSTR3B_M")


def test_switched_off_rule_is_hidden():
    rules = [{**r, "disabled": True} if r["code"] == "GSTR1_M" else r for r in CC.DEFAULT_RULES]
    got = {i["code"] for i in CC.calendar_for(biz(), rules, {}, today=TODAY)["items"]}
    assert "GSTR1_M" not in got and "GSTR3B_M" in got


def test_nothing_before_gst_registration():
    b = biz(track_from="2025-07-01")
    b.gst_registration_date = dt.date(2026, 6, 15)
    s = CC.settings(b)
    assert s["track_from"] == "2026-06-15" and s["registration_date"] == "2026-06-15"
    items = CC.calendar_for(b, CC.DEFAULT_RULES, {}, today=TODAY)["items"]
    keys = {(i["code"], i["period_key"]) for i in items}
    assert ("GSTR3B_M", "2026-05") not in keys and ("GSTR3B_M", "2026-06") in keys  # June: registered mid-month
    reg = CC.register(b, CC.DEFAULT_RULES, {}, 2026, "GST", today=TODAY)
    assert all(r["period_key"] >= "2026-06" for r in reg["rows"] if r["code"] == "GSTR1_M")
    assert CC.register(b, CC.DEFAULT_RULES, {}, 2025, "GST", today=TODAY)["rows"] == []


def test_filed_items_listed_even_before_track_from():
    b = biz(track_from="2026-09-01")
    done = {("GSTR1_M", "2026-05"): {"id": "x", "source": "SYNC"}}
    items = CC.calendar_for(b, CC.DEFAULT_RULES, done, today=TODAY)["items"]
    assert any(i["code"] == "GSTR1_M" and i["period_key"] == "2026-05" and i["status"] == "DONE" for i in items)
    assert not any(i["code"] == "GSTR3B_M" and i["period_key"] == "2026-05" for i in items)  # pending + before tracking: hidden
