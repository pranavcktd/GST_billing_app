"""E-way bills without API: validity, pending list, bulk JSON, import of generated numbers."""

import datetime as dt
import io

from openpyxl import Workbook

from app.services import ewaybill as E
from app.services.einvoice import IST
from tests.test_api_flow import make_business, signup
from tests.test_modules import gstin, post

Q = {"date_from": "2026-09-01", "date_to": "2026-09-30"}


def test_validity():
    t = dt.datetime(2026, 9, 10, 15, 0, tzinfo=IST)
    assert E.valid_till(t, 150) == dt.datetime(2026, 9, 11, 23, 59, 59, tzinfo=IST)      # up to 200 km: 1 day
    assert E.valid_till(t, 450) == dt.datetime(2026, 9, 13, 23, 59, 59, tzinfo=IST)      # 3 days
    assert E.valid_till(t, 30, odc=True) == dt.datetime(2026, 9, 12, 23, 59, 59, tzinfo=IST)
    assert E.valid_till(t, None) is None


def test_register_bulk_and_import(client):
    h = make_business(client, signup(client), address="12 MG Road", city="Pune", pincode="411001")
    buyer = post(client, h, "/api/parties", {"name": "Karnataka Retail", "gst_type": "REGISTERED", "gstin": gstin("29", "AAACK5678D"),
                                             "billing_address": "Brigade Road", "city": "Bengaluru", "pincode": "560001"})
    item = post(client, h, "/api/items", {"name": "Steel almirah", "hsn_sac": "9403", "unit": "PCS", "sale_price": 20000, "gst_rate": 18})
    ready = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "party_id": buyer["id"],
                                              "lines": [{"item_id": item["id"], "name": "Steel almirah", "hsn_sac": "9403", "qty": 3, "rate": 20000, "gst_rate": 18}],
                                              "transport": {"vehicle_no": "MH12AB1234", "distance_km": 850, "mode": "1"}})
    incomplete = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-11", "party_id": buyer["id"],
                                                   "lines": [{"item_id": item["id"], "name": "Steel almirah", "hsn_sac": "9403", "qty": 4, "rate": 20000, "gst_rate": 18}]})
    small = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-12", "party_id": buyer["id"],
                                              "lines": [{"item_id": item["id"], "name": "Steel almirah", "hsn_sac": "9403", "qty": 1, "rate": 20000, "gst_rate": 18}]})
    service = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-12", "party_id": buyer["id"],
                                                "lines": [{"name": "Installation", "hsn_sac": "998719", "qty": 1, "rate": 90000, "gst_rate": 18}]})

    rows = {r["number"]: r for r in client.get("/api/ewaybills", headers=h, params=Q).json()}
    assert set(rows) == {ready["number"], incomplete["number"]}             # small value & services need none
    assert rows[ready["number"]]["ready"] and rows[ready["number"]]["status"] == "PENDING"
    assert not rows[incomplete["number"]]["ready"] and any("distance" in p for p in rows[incomplete["number"]]["problems"])
    _ = small, service

    b = client.post("/api/ewaybills/bulk-json", headers=h, json={"voucher_ids": [ready["id"], incomplete["id"]]}).json()
    assert b["count"] == 1 and b["json"]["billLists"][0]["docNo"] == ready["number"]
    assert b["skipped"][0]["number"] == incomplete["number"]

    # the portal's list of generated e-way bills
    wb = Workbook()
    ws = wb.active
    ws.append(["Sl.No", "EWB No", "EWB Date", "Doc No", "Doc Date", "Valid Upto"])
    ws.append([1, "3412 5678 9012", "10/09/2026 04:15:00 PM", ready["number"], "10/09/2026", None])
    ws.append([2, "341256789099", "12/09/2026 10:00:00 AM", "UNKNOWN/1", "12/09/2026", "13/09/2026 11:59:00 PM"])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/api/ewaybills/import", headers=h, files={"file": ("ewb.xlsx", buf.getvalue(), "application/octet-stream")}).json()
    assert r["updated"] == [{"number": ready["number"], "ewb_no": "341256789012"}] and r["unmatched"] == ["UNKNOWN/1"]
    v = client.get(f"/api/vouchers/{ready['id']}", headers=h).json()
    assert v["ewb_no"] == "341256789012" and v["ewb_valid_till"].startswith("2026-09-15")   # 850 km → 5 days
    rows = {r["number"]: r for r in client.get("/api/ewaybills", headers=h, params=Q).json()}
    assert rows[ready["number"]]["status"] == "EXPIRED"                   # dates in the past
    bad = client.post("/api/ewaybills/import", headers=h, files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert bad.status_code == 422

    # manual record without validity → computed from the distance
    r = client.put(f"/api/vouchers/{incomplete['id']}/ewaybill", headers=h, json={"ewb_no": "341200000001", "ewb_date": "2026-09-11T10:00:00+05:30"})
    assert r.json()["ewb_valid_till"] is None                              # no distance on that bill
