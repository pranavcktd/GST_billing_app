"""Multi-year plans paid upfront: discounted price, validity of N years, offers set by the super admin."""

import datetime as dt
from decimal import Decimal

from app.services import plans as P
from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_security_admin import superadmin


def test_three_year_plan_and_admin_offers(client, monkeypatch):
    h = make_business(client, signup(client, "multi@x.in"))
    plans = client.get("/api/billing/plans").json()
    assert [c["code"] for c in plans["cycles"]] == ["MONTHLY", "YEARLY", "YEARS_2", "YEARS_3"]
    growth = next(p for p in plans["plans"] if p["code"] == "PROFESSIONAL")
    three = growth["multi_year"]["YEARS_3"]
    assert three["price"] == float((Decimal(growth["yearly"]) * 3 * Decimal("0.75")).quantize(Decimal("1"))) and three["saving"] > 0

    order = post(client, h, "/api/billing/order", {"plan": "PROFESSIONAL", "cycle": "YEARS_3"}, 200)
    assert order["amount"] == three["price_with_gst"]
    post(client, h, "/api/billing/verify", {"order_id": order["order_id"], "simulate": True}, 200)
    st = client.get("/api/billing/status", headers=h).json()
    assert st["plan"]["code"] == "PROFESSIONAL" and st["valid_until"] == (dt.date.today() + dt.timedelta(days=3 * 365)).isoformat()

    assert client.post("/api/billing/order", headers=h, json={"plan": "PROFESSIONAL", "cycle": "YEARS_4"}).status_code == 400  # not offered
    assert client.post("/api/billing/order", headers=h, json={"plan": "PROFESSIONAL", "cycle": "YEARS_9"}).status_code == 422

    root = superadmin(client, monkeypatch)
    bad = client.post("/api/admin/config/versions", headers=root, json={"effective_from": "2026-01-01", "values": {"multi_year_offers": {"7": 50}}})
    assert bad.status_code == 422
    ok = client.post("/api/admin/config/versions", headers=root, json={"effective_from": "2026-01-01",
                     "values": {"multi_year_offers": {"2": 10, "3": 20, "5": 35}}})
    assert ok.status_code == 201, ok.text
    assert [c["code"] for c in client.get("/api/billing/plans").json()["cycles"]][-1] == "YEARS_5"
    assert P.multi_year_price("STARTER", 5) == (Decimal(P.PLANS["STARTER"]["yearly"]) * 5 * Decimal("0.65")).quantize(Decimal("1"))
