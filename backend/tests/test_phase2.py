"""Godowns, e-invoice / e-way bill, GSTR-1 JSON, Tally XML, audit log, print settings, subscriptions."""

import hashlib
import hmac
import json
import xml.etree.ElementTree as ET
from decimal import Decimal

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import Subscription
from app.services import plans as P
from app.services.einvoice import compute_irn
from tests.test_api_flow import make_business, signup
from tests.test_modules import gstin, post


def db_session():
    return next(app.dependency_overrides[get_db]())


def setup(client):
    h = make_business(client, signup(client), address="12 MG Road", city="Pune", pincode="411001", phone="9876543210")
    cust = post(client, h, "/api/parties", {"name": "Karnataka Retail", "gst_type": "REGISTERED",
                                            "gstin": gstin("29", "AAACK5678D"), "billing_address": "Brigade Road",
                                            "city": "Bengaluru", "pincode": "560001"})
    item = post(client, h, "/api/items", {"name": "Bottle", "hsn_sac": "7323", "unit": "PCS", "sale_price": 500,
                                          "purchase_price": 300, "gst_rate": 18, "opening_stock": 20,
                                          "opening_stock_date": "2026-04-01"})
    return h, cust, item


def sale(client, h, cust, item, **extra):
    return post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "party_id": cust["id"],
                                             "lines": [{"item_id": item["id"], "name": "Bottle", "qty": 2, "rate": 500,
                                                        "gst_rate": 18}], **extra})


def test_godowns_and_transfers(client):
    h, cust, item = setup(client)
    gds = client.get("/api/godowns", headers=h).json()
    main = gds[0]
    assert main["is_default"] and main["name"] == "Main Godown"
    shop = post(client, h, "/api/godowns", {"name": "City Shop"})
    t = post(client, h, "/api/stock-transfers", {"date": "2026-09-05", "from_godown_id": main["id"], "to_godown_id": shop["id"],
                                                 "lines": [{"item_id": item["id"], "qty": 8}]})
    assert t["number"].startswith("ST/")
    r = client.post("/api/stock-transfers", headers=h, json={"date": "2026-09-05", "from_godown_id": main["id"],
                                                              "to_godown_id": shop["id"], "lines": [{"item_id": item["id"], "qty": 50}]})
    assert r.status_code == 400
    sale(client, h, cust, item, godown_id=shop["id"])
    per = {g["godown"]: g["qty"] for g in client.get(f"/api/items/{item['id']}/godowns", headers=h).json()}
    assert per == {"Main Godown": 12, "City Shop": 6}
    assert client.get(f"/api/items/{item['id']}", headers=h).json()["stock"] == 18  # transfers net to zero
    rep = client.get("/api/reports/run/godown-stock", headers=h, params={"as_of": "2026-09-30"}).json()
    assert rep["sections"][0]["rows"][0]["total"] == 18
    # balance sheet still balances with transfers
    bs = client.get("/api/reports/run/balance-sheet", headers=h, params={"as_of": "2026-09-30"}).json()
    assert not any("Difference" in x["label"] for s in bs["sections"] for x in s["rows"])
    assert client.delete(f"/api/godowns/{main['id']}", headers=h).status_code == 400


def test_einvoice_and_ewaybill(client):
    h, cust, item = setup(client)
    walkin = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "fully_paid": True,
                                               "lines": [{"item_id": item["id"], "name": "Bottle", "qty": 1, "rate": 500, "gst_rate": 18}]})
    r = client.get(f"/api/vouchers/{walkin['id']}/einvoice/json", headers=h)
    assert r.status_code == 422 and "GSTIN" in r.json()["detail"]

    v = sale(client, h, cust, item)
    payload = client.get(f"/api/vouchers/{v['id']}/einvoice/json", headers=h).json()[0]
    assert payload["Version"] == "1.1" and payload["DocDtls"] == {"Typ": "INV", "No": v["number"], "Dt": "10/09/2026"}
    assert payload["SellerDtls"]["Pin"] == 411001 and payload["BuyerDtls"]["Pos"] == "29"
    assert payload["ValDtls"]["IgstVal"] == 180 and payload["ValDtls"]["TotInvVal"] == 1180
    assert payload["ItemList"][0]["HsnCd"] == "7323" and payload["ItemList"][0]["IsServc"] == "N"

    done = post(client, h, f"/api/vouchers/{v['id']}/einvoice", {}, 200)
    biz = client.get("/api/businesses/current", headers=h).json()
    assert done["irn"] == compute_irn(biz["gstin"], __import__("datetime").date(2026, 9, 10), "INV", v["number"])
    assert done["einvoice_status"] == "GENERATED" and done["einvoice_sandbox"] and done["signed_qr"].startswith("SANDBOX.")
    # locked for editing until the IRN is cancelled
    edit = client.put(f"/api/vouchers/{v['id']}", headers=h, json={"type": "SALE", "date": "2026-09-10", "party_id": cust["id"],
                                                                   "lines": [{"name": "x", "qty": 1, "rate": 1}]})
    assert edit.status_code == 400
    assert post(client, h, f"/api/vouchers/{v['id']}/einvoice/cancel", {"reason": "2", "remark": "typo"}, 200)["einvoice_status"] == "CANCELLED"

    # e-way bill needs transport details
    assert client.get(f"/api/vouchers/{v['id']}/ewaybill/json", headers=h).status_code == 422
    r = client.put(f"/api/vouchers/{v['id']}/transport", headers=h,
                   json={"vehicle_no": "mh 12 ab 1234", "distance_km": 840, "transporter_name": "VRL"})
    assert r.json()["transport"]["vehicle_no"] == "MH12AB1234"
    ewb = client.get(f"/api/vouchers/{v['id']}/ewaybill/json", headers=h).json()["billLists"][0]
    assert ewb["supplyType"] == "O" and ewb["toPincode"] == 560001 and ewb["itemList"][0]["igstRate"] == 18
    gen = post(client, h, f"/api/vouchers/{v['id']}/ewaybill", {}, 200)
    assert len(gen["ewb_no"]) == 12 and gen["ewb_valid_till"]

    bulk = client.get("/api/einvoice/bulk-json", headers=h, params={"date_from": "2026-09-01", "date_to": "2026-09-30"})
    assert bulk.status_code == 400  # the only B2B invoice already has an IRN (cancelled one still has irn)


def test_gstr1_json_and_tally(client):
    h, cust, item = setup(client)
    local = post(client, h, "/api/parties", {"name": "Local", "gst_type": "REGISTERED", "gstin": gstin("27", "AAACL1234C")})
    s1 = sale(client, h, cust, item)
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-11", "fully_paid": True,
                                      "lines": [{"item_id": item["id"], "name": "Bottle", "qty": 1, "rate": 500, "gst_rate": 18}]})
    post(client, h, "/api/vouchers", {"type": "SALE_RETURN", "date": "2026-09-12", "party_id": cust["id"],
                                      "original_voucher_id": s1["id"],
                                      "lines": [{"item_id": item["id"], "name": "Bottle", "qty": 1, "rate": 500, "gst_rate": 18}]})
    post(client, h, "/api/vouchers", {"type": "PURCHASE", "date": "2026-09-01", "party_id": local["id"],
                                      "lines": [{"item_id": item["id"], "name": "Bottle", "qty": 10, "rate": 300, "gst_rate": 18}]})
    post(client, h, "/api/payments", {"type": "IN", "date": "2026-09-15", "party_id": cust["id"], "amount": 500, "tds_amount": 10})

    g = client.get("/api/exports/gstr1-json", headers=h, params={"date_from": "2026-09-01", "date_to": "2026-09-30"}).json()
    assert g["fp"] == "092026"
    assert g["b2b"][0]["ctin"] == cust["gstin"] if "gstin" in cust else g["b2b"][0]["inv"][0]["itms"][0]["itm_det"]["iamt"] == 180
    assert g["b2cs"][0]["sply_ty"] == "INTRA" and g["b2cs"][0]["camt"] == 45
    assert g["cdnr"][0]["nt"][0]["ntty"] == "C"
    assert g["hsn"]["hsn_b2b"][0]["txval"] == 500 and g["hsn"]["hsn_b2c"][0]["txval"] == 500
    assert g["doc_issue"]["doc_det"][0]["docs"][0]["totnum"] == 2

    xml = client.get("/api/exports/tally", headers=h, params={"date_from": "2026-09-01", "date_to": "2026-09-30"}).text
    root = ET.fromstring(xml)
    vouchers = root.findall(".//VOUCHER")
    assert {v.get("VCHTYPE") for v in vouchers} >= {"Sales", "Credit Note", "Purchase", "Receipt"}
    for v in vouchers:  # every voucher balances
        assert sum(Decimal(a.text) for a in v.findall(".//AMOUNT")) == 0, ET.tostring(v)
    ledgers = {l.get("NAME") for l in root.findall(".//LEDGER")}
    assert {"Sales", "Output IGST", "Input CGST", "TDS Receivable", "Karnataka Retail"} <= ledgers


def test_audit_log(client):
    h, cust, item = setup(client)
    v = sale(client, h, cust, item)
    post(client, h, f"/api/vouchers/{v['id']}/cancel", {}, 200)
    log = client.get("/api/audit", headers=h).json()
    summaries = [r["summary"] for r in log["rows"]]
    assert any(v["number"] in s and s.startswith("Created Tax Invoice") for s in summaries), summaries
    assert any(s.startswith("Cancelled") for s in summaries)
    assert any("Created party Karnataka Retail" in s for s in summaries)
    assert log["rows"][0]["user"] == "Owner"


def test_print_settings_and_custom_fields(client):
    h, cust, item = setup(client)
    biz = client.get("/api/businesses/current", headers=h).json()
    biz["print_settings"] = {**(biz["print_settings"] or {}), "theme": "modern", "paper": "A5",
                             "custom_fields": [{"key": "po_no", "label": "PO No."}, {"key": "vehicle", "label": "Vehicle"}]}
    biz["einvoice_username"], biz["einvoice_password"] = "api_user", "s3cret"
    r = client.put("/api/businesses/current", headers=h, json=biz)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["print_settings"]["theme"] == "modern" and out["einvoice_password_set"] and "einvoice_password" not in out
    v = sale(client, h, cust, item, extra_fields={"po_no": "PO-77", "junk": "dropped"})
    assert v["extra_fields"] == {"po_no": "PO-77"}


def test_items_assign_codes(client):
    h, _, item = setup(client)
    post(client, h, "/api/items/assign-codes", {}, 200)
    code = client.get(f"/api/items/{item['id']}", headers=h).json()["code"]
    digits = [int(c) for c in code]
    assert len(code) == 13 and (sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:12])) + digits[12]) % 10 == 0


def test_subscription_trial_limits_and_payments(client, monkeypatch):
    h, cust, item = setup(client)
    st = client.get("/api/billing/status", headers=h).json()
    assert st["status"] == "TRIAL" and st["plan"]["code"] == "BUSINESS" and st["dev_mode"]
    plans = client.get("/api/billing/plans").json()  # public, no auth
    assert [p["code"] for p in plans["plans"]] == ["FREE", "GROWTH", "BUSINESS"]

    # drop to the free plan with a tiny limit
    db = db_session()
    db.get(Subscription, h["X-Business-Id"]).plan = "FREE"
    db.commit()
    monkeypatch.setitem(P.PLANS["FREE"], "invoices_per_month", 1)
    sale(client, h, cust, item)
    r = client.post("/api/vouchers", headers=h, json={"type": "SALE", "date": "2026-09-10", "party_id": cust["id"],
                                                      "lines": [{"name": "x", "qty": 1, "rate": 1}]})
    assert r.status_code == 402 and "upgrade" in r.json()["detail"].lower()
    assert client.get("/api/exports/tally", headers=h, params={"date_from": "2026-09-01", "date_to": "2026-09-30"}).status_code == 402
    assert client.post("/api/godowns", headers=h, json={"name": "Second"}).status_code == 402

    # local development: simulated payment upgrades the plan
    order = post(client, h, "/api/billing/order", {"plan": "GROWTH", "cycle": "YEARLY"}, 200)
    assert order["amount"] == float(P.with_gst(Decimal("3999"))) and not order["live"]
    res = post(client, h, "/api/billing/verify", {"order_id": order["order_id"], "simulate": True}, 200)
    assert res["plan"] == "GROWTH" and res["status"] == "ACTIVE"
    assert client.post("/api/vouchers", headers=h, json={"type": "SALE", "date": "2026-09-10", "party_id": cust["id"],
                                                         "lines": [{"name": "x", "qty": 1, "rate": 1}]}).status_code == 201

    # real Razorpay signature checks
    monkeypatch.setattr(get_settings(), "razorpay_key_secret", "rzp_secret")
    monkeypatch.setattr(get_settings(), "razorpay_webhook_secret", "wh_secret")
    good = hmac.new(b"rzp_secret", b"order_1|pay_1", hashlib.sha256).hexdigest()
    assert P.signature_ok("order_1", "pay_1", good) and not P.signature_ok("order_1", "pay_1", "bad")
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"order_id": "nope", "id": "p"}}}}).encode()
    sig = hmac.new(b"wh_secret", body, hashlib.sha256).hexdigest()
    assert client.post("/api/billing/webhook", content=body, headers={"x-razorpay-signature": sig}).status_code == 200
    assert client.post("/api/billing/webhook", content=body, headers={"x-razorpay-signature": "x"}).status_code == 400
