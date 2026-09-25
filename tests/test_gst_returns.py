"""Exports / SEZ under LUT, imports, blocked ITC, GSTR-1 & GSTR-3B JSON, composition CMP-08 / GSTR-4."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import gstin, post

Q = {"date_from": "2026-09-01", "date_to": "2026-09-30"}


def line(qty=1, rate=1000, gst=18, name="Widget", hsn="8471"):
    return {"name": name, "hsn_sac": hsn, "qty": qty, "rate": rate, "gst_rate": gst}


def party(client, h, name, gst_type, **extra):
    return post(client, h, "/api/parties", {"name": name, "gst_type": gst_type, **extra})


def test_exports_sez_and_imports(client):
    h = make_business(client, signup(client), address="12 MG Road", city="Pune", pincode="411001")
    foreign = party(client, h, "Acme Inc (USA)", "OVERSEAS", billing_address="1 Main St, Austin")
    sez = party(client, h, "SEZ Unit", "SEZ", gstin=gstin("29", "AAACZ1234K"), billing_address="EPIP Zone",
                city="Bengaluru", pincode="560066")
    supplier = party(client, h, "China Supplier", "OVERSEAS")

    # without a LUT the export must pay IGST
    r = client.post("/api/vouchers", headers=h, json={"type": "SALE", "date": "2026-09-05", "party_id": foreign["id"],
                                                       "export_with_payment": False, "lines": [line()]})
    assert r.status_code == 400 and "LUT" in r.text
    wp = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-05", "party_id": foreign["id"],
                                           "shipping_bill_no": "1234567", "shipping_bill_date": "2026-09-06",
                                           "port_code": "INNSA1", "currency_code": "usd", "exchange_rate": 83.5,
                                           "lines": [line()]})
    assert wp["export_type"] == "EXPWP" and wp["igst"] == 180 and wp["cgst"] == 0

    r = client.put("/api/businesses/current", headers=h, json={
        **{k: v for k, v in client.get("/api/businesses/current", headers=h).json().items()
           if k in ("name", "gst_type", "gstin", "state_code", "address", "city", "pincode")},
        "lut_number": "AD270926000001X", "lut_valid_till": "2027-03-31"})
    assert r.status_code == 200, r.text
    wop = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "party_id": foreign["id"],
                                            "lines": [line(2)]})
    assert wop["export_type"] == "EXPWOP" and wop["igst"] == 0 and wop["grand_total"] == 2000
    sez_inv = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-11", "party_id": sez["id"],
                                                "lines": [line(3)]})
    assert sez_inv["export_type"] == "SEZWOP" and sez_inv["igst"] == 0

    # import of goods: IGST paid at customs → ITC as IMPG
    imp = post(client, h, "/api/vouchers", {"type": "PURCHASE", "date": "2026-09-12", "party_id": supplier["id"],
                                            "supplier_invoice_no": "BOE-9", "lines": [line(1, 5000)]})
    assert imp["export_type"] == "IMPORT" and imp["igst"] == 900

    # blocked credit u/s 17(5)
    cats = {c["name"]: c for c in client.get("/api/expenses/categories", headers=h).json()}
    assert cats["Tea & Refreshments"]["itc_blocked"] is True
    vendor = party(client, h, "Cafe", "REGISTERED", gstin=gstin("27", "AABCC1111D"))
    post(client, h, "/api/vouchers", {"type": "EXPENSE", "date": "2026-09-15", "party_id": vendor["id"],
                                      "expense_category_id": cats["Tea & Refreshments"]["id"], "tax_applicable": True,
                                      "fully_paid": True, "lines": [line(1, 1000, 18, "Snacks", "9963")]})

    # ---- GSTR-1
    g1 = client.get("/api/reports/gstr1", headers=h, params=Q).json()
    assert {d["number"] for d in g1["exp"]} == {wp["number"], wop["number"]}
    assert g1["b2b"][0]["type"] == "SEWOP"
    j1 = client.get("/api/exports/gstr1-json", headers=h, params=Q).json()
    exp = {e["exp_typ"]: e["inv"] for e in j1["exp"]}
    assert exp["WPAY"][0]["sbnum"] == "1234567" and exp["WPAY"][0]["sbpcode"] == "INNSA1"
    assert exp["WPAY"][0]["itms"][0]["itm_det"] == {"txval": 1000.0, "rt": 18.0, "iamt": 180.0, "csamt": 0.0}
    assert exp["WOPAY"][0]["itms"][0]["itm_det"]["iamt"] == 0.0
    assert j1["b2b"][0]["inv"][0]["inv_typ"] == "SEWOP"

    # ---- GSTR-3B
    g3 = client.get("/api/reports/gstr3b", headers=h, params=Q).json()
    assert float(g3["zero_rated"]["taxable"]) == 6000 and float(g3["zero_rated"]["igst"]) == 180
    assert float(g3["itc_import_goods"]["igst"]) == 900
    assert float(g3["itc_blocked"]["cgst"]) == 90 and float(g3["itc_other"]["cgst"]) == 0
    j3 = client.get("/api/exports/gstr3b-json", headers=h, params=Q).json()
    assert j3["ret_period"] == "092026"
    assert j3["sup_details"]["osup_zero"] == {"txval": 6000.0, "iamt": 180.0, "csamt": 0.0}
    itc = {r["ty"]: r for r in j3["itc_elg"]["itc_avl"]}
    assert itc["IMPG"]["iamt"] == 900.0 and itc["OTH"]["camt"] == 0.0
    assert j3["itc_elg"]["itc_inelg"][0]["camt"] == 90.0

    # ---- e-invoice for an export
    e = client.get(f"/api/vouchers/{wp['id']}/einvoice/json", headers=h).json()[0]
    assert e["TranDtls"]["SupTyp"] == "EXPWP" and e["BuyerDtls"]["Gstin"] == "URP" and e["BuyerDtls"]["Pos"] == "96"
    assert e["ExpDtls"] == {"ShipBNo": "1234567", "Port": "INNSA1", "ForCur": "USD", "ShipBDt": "06/09/2026"}

    # books still balance
    bs = client.get("/api/reports/run/balance-sheet", headers=h, params={"as_of": "2026-09-30"}).json()
    assert not any("Difference" in x["label"] for s in bs["sections"] for x in s["rows"])


def test_composition_returns(client):
    h = make_business(client, signup(client), gst_type="COMPOSITION", composition_type="RESTAURANT")
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-07-10", "fully_paid": True,
                                      "lines": [line(10, 1000, 0, "Meals", "9963")]})
    supplier = party(client, h, "Veg Supplier", "REGISTERED", gstin=gstin("27", "AABCV2222E"))
    post(client, h, "/api/vouchers", {"type": "PURCHASE", "date": "2026-08-01", "party_id": supplier["id"],
                                      "tax_applicable": True, "lines": [line(1, 2000, 5, "Veg", "0702")]})
    c = client.get("/api/reports/run/cmp08", headers=h,
                   params={"date_from": "2026-07-01", "date_to": "2026-09-30"}).json()
    tax = c["sections"][0]["rows"][2]
    assert float(tax["cgst"]) == 250 and float(tax["sgst"]) == 250  # 5% of 10,000 split equally
    g4 = client.get("/api/reports/run/gstr4", headers=h,
                    params={"date_from": "2026-04-01", "date_to": "2027-03-31"}).json()
    quarters = g4["sections"][0]["rows"]
    assert len(quarters) == 4 and float(quarters[1]["tax"]) == 500
    assert g4["sections"][1]["rows"][0]["gstin"] == gstin("27", "AABCV2222E")
