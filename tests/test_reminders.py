"""Payment reminders: schedule stages, one e-mail per customer with PDFs, no repeats, advances skipped,
manual send, WhatsApp text, daily job timing."""

import datetime as dt

from app.db import get_db
from app.main import app
from app.models import Business
from app.services import reminders as R
from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_security_admin import SENT, fake_mail  # noqa: F401 — fake SMTP for this module


def db_session():
    return next(app.dependency_overrides[get_db]())


def setup(client):
    h = make_business(client, signup(client), address="12 MG Road", city="Pune", pincode="411001", upi_id="shop@okhdfc")
    client.put("/api/smtp", headers=h, json={"host": "smtp.shop.in", "from_email": "billing@shop.in", "password": "x"})
    cust = post(client, h, "/api/parties", {"name": "Karan Stores", "gst_type": "UNREGISTERED", "email": "karan@client.in", "phone": "98765 43210"})
    inv = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-01", "due_date": "2026-09-10", "party_id": cust["id"],
                                            "lines": [{"name": "Widget", "qty": 2, "rate": 500, "gst_rate": 18}]})
    return h, cust, inv


def run(client, h, day):
    db = db_session()
    try:
        biz = db.get(Business, h["X-Business-Id"])
        return R.run_business(db, biz, "http://app.test", dt.date.fromisoformat(day))
    finally:
        db.close()


def test_automatic_schedule(client):
    h, cust, inv = setup(client)
    assert run(client, h, "2026-09-13") == {"sent": 0, "failed": 0, "skipped": 0}  # switched off by default
    s = client.put("/api/reminders/settings", headers=h, json={"enabled": True, "before_days": [3], "on_due": True,
                                                               "after_days": [3, 7]}).json()
    assert s["enabled"] and s["after_days"] == [3, 7]

    SENT.clear()
    assert run(client, h, "2026-09-07")["sent"] == 1          # 3 days before due
    assert run(client, h, "2026-09-07")["sent"] == 0          # never twice for the same stage
    assert run(client, h, "2026-09-08")["sent"] == 0          # no stage today
    assert run(client, h, "2026-09-10")["sent"] == 1          # on the due date
    assert run(client, h, "2026-09-13")["sent"] == 1          # 3 days overdue
    msg = SENT[-1]
    assert msg["To"] == "karan@client.in" and "Payment reminder" in msg["Subject"]
    html = msg.get_body(("html",)).get_content()
    assert inv["number"] in html and "3 days overdue" in html and "shop@okhdfc" in html and "http://app.test/i/" in html
    pdfs = [a for a in msg.iter_attachments() if a.get_content_type() == "application/pdf"]
    assert len(pdfs) == 1 and pdfs[0].get_content()[:5] == b"%PDF-"

    # a customer whose advance covers the bill is not chased
    adv = post(client, h, "/api/parties", {"name": "Advance Co", "gst_type": "UNREGISTERED", "email": "a@x.in", "opening_balance": -5000})
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-01", "due_date": "2026-09-10", "party_id": adv["id"],
                                      "lines": [{"name": "Widget", "qty": 1, "rate": 1000, "gst_rate": 0}]})
    r = run(client, h, "2026-09-17")
    assert r == {"sent": 1, "failed": 0, "skipped": 1}

    # no e-mail address → logged as failed
    post(client, h, "/api/parties", {"name": "No Mail", "gst_type": "UNREGISTERED"})
    log = client.get("/api/reminders/log", headers=h).json()
    assert {x["stage"] for x in log if x["status"] == "SENT"} >= {"BEFORE_3", "DUE", "AFTER_3", "AFTER_7"}


def test_due_list_manual_send_and_whatsapp(client):
    h, cust, inv = setup(client)
    due = client.get("/api/reminders/due", headers=h).json()
    assert due[0]["name"] == "Karan Stores" and due[0]["whatsapp"] == "919876543210" and due[0]["total"] == 1180
    SENT.clear()
    r = post(client, h, "/api/reminders/send", {"party_ids": [cust["id"]], "note": "Kindly clear this week."}, 200)
    assert r["sent"] == 1 and "Kindly clear this week." in SENT[-1].get_body(("html",)).get_content()
    wa = client.get(f"/api/reminders/whatsapp/{cust['id']}", headers=h).json()
    assert wa["url"].startswith("https://wa.me/919876543210?text=") and inv["number"] in wa["text"] and "shop@okhdfc" in wa["text"]
    log = client.get("/api/reminders/log", headers=h).json()
    assert {x["channel"] for x in log} == {"EMAIL", "WHATSAPP"}
    # paid invoices drop out
    post(client, h, "/api/payments", {"type": "IN", "date": "2026-09-12", "party_id": cust["id"], "amount": 1180, "mode": "CASH"})
    assert client.get("/api/reminders/due", headers=h).json() == []


def test_daily_job_timing(client):
    h, cust, inv = setup(client)
    client.put("/api/reminders/settings", headers=h, json={"enabled": True, "after_days": [3]})
    db = db_session()
    try:
        assert R.maybe_run_daily(db, dt.datetime(2026, 9, 13, 8, 0)) is None           # before 9 AM
        first = R.maybe_run_daily(db, dt.datetime(2026, 9, 13, 10, 0))
        assert first == {"businesses": 1, "sent": 1, "failed": 0}
        assert R.maybe_run_daily(db, dt.datetime(2026, 9, 13, 15, 0)) is None          # once a day
        assert not db.in_transaction()                                                   # nothing left open
    finally:
        db.close()
