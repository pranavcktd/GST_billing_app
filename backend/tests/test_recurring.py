"""Recurring invoices: schedule maths, catch-up, end date, pause, auto e-mail, invoices like a user's."""

import datetime as dt

from app.db import get_db
from app.main import app
from app.models import RecurringInvoice
from app.services import recurring as RC
from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_security_admin import SENT, fake_mail  # noqa: F401


def run(day):
    db = next(app.dependency_overrides[get_db]())
    try:
        return RC.run_all(db, dt.date.fromisoformat(day))
    finally:
        db.close()


def test_add_period_keeps_month_end():
    d = dt.date(2026, 1, 31)
    d2 = RC.add_period(d, "MONTHLY", 1, 31)
    d3 = RC.add_period(d2, "MONTHLY", 1, 31)
    assert (d2, d3) == (dt.date(2026, 2, 28), dt.date(2026, 3, 31))
    assert RC.add_period(dt.date(2026, 4, 30), "QUARTERLY", 1, 30) == dt.date(2026, 7, 30)
    assert RC.add_period(dt.date(2026, 4, 1), "WEEKLY", 2, 1) == dt.date(2026, 4, 15)


def test_recurring_flow(client):
    h = make_business(client, signup(client))
    client.put("/api/smtp", headers=h, json={"host": "smtp.shop.in", "from_email": "billing@shop.in", "password": "x"})
    tenant = post(client, h, "/api/parties", {"name": "Tenant Pvt Ltd", "gst_type": "UNREGISTERED", "email": "accounts@tenant.in"})
    inv = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-04-01", "party_id": tenant["id"], "notes": "Office rent",
                                            "lines": [{"name": "Office rent", "hsn_sac": "997212", "qty": 1, "rate": 25000, "gst_rate": 18}]})
    bad = client.post("/api/recurring", headers=h, json={"voucher_id": inv["id"], "start_date": "2026-05-01", "end_date": "2026-04-01"})
    assert bad.status_code == 422
    r = post(client, h, "/api/recurring", {"voucher_id": inv["id"], "name": "Office rent", "frequency": "MONTHLY",
                                           "start_date": "2026-05-01", "end_date": "2026-08-31", "due_days": 7, "auto_email": True})
    assert [str(d) for d in r["upcoming"]] == ["2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01"]

    SENT.clear()
    assert run("2026-04-30") == 0
    assert run("2026-06-15") == 2                       # May and June caught up
    assert run("2026-06-15") == 0                       # never twice
    lst = client.get(f"/api/recurring/{r['id']}/invoices", headers=h).json()
    assert [x["date"] for x in lst] == ["2026-06-01", "2026-05-01"]
    v = client.get(f"/api/vouchers/{lst[0]['id']}", headers=h).json()
    assert v["grand_total"] == 29500 and v["due_date"] == "2026-06-08" and v["notes"] == "Office rent" and v["lines"][0]["hsn_sac"] == "997212"
    assert len(SENT) == 2 and SENT[-1]["To"] == "accounts@tenant.in"
    assert any(a.get_content_type() == "application/pdf" for a in SENT[-1].iter_attachments())

    # pause → nothing; resume → continues
    client.put(f"/api/recurring/{r['id']}", headers=h, json={"status": "PAUSED"})
    assert run("2026-07-05") == 0
    client.put(f"/api/recurring/{r['id']}", headers=h, json={"status": "ACTIVE"})
    assert run("2026-07-05") == 1
    # ends after the end date
    assert run("2026-12-31") == 1
    st = client.get("/api/recurring", headers=h).json()[0]
    assert st["status"] == "ENDED" and st["generated_count"] == 4 and st["next_date"] is None


def test_failure_is_recorded_and_retried(client, monkeypatch):
    h = make_business(client, signup(client))
    c = post(client, h, "/api/parties", {"name": "AMC Client", "gst_type": "UNREGISTERED"})
    inv = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-04-01", "party_id": c["id"],
                                            "lines": [{"name": "AMC", "qty": 1, "rate": 1000, "gst_rate": 18}]})
    r = post(client, h, "/api/recurring", {"voucher_id": inv["id"], "frequency": "YEARLY", "start_date": "2026-05-01"})
    # break the template (as if a GST slab were withdrawn) → the error is kept, nothing created
    db = next(app.dependency_overrides[get_db]())
    row = db.get(RecurringInvoice, r["id"])
    row.template = {**row.template, "lines": [{**row.template["lines"][0], "gst_rate": "13"}]}
    db.commit()
    db.close()
    assert run("2026-05-02") == 0
    st = client.get("/api/recurring", headers=h).json()[0]
    assert st["last_error"] and st["next_date"] == "2026-05-01" and st["generated_count"] == 0
    # fixed by re-basing on a correct invoice → next run succeeds
    client.put(f"/api/recurring/{r['id']}", headers=h, json={"template_from_voucher_id": inv["id"]})
    assert run("2026-05-02") == 1
    assert client.get("/api/recurring", headers=h).json()[0]["next_date"] == "2027-05-01"
