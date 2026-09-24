"""End-to-end flow: signup -> business -> masters -> sale/purchase/returns -> payments -> reports."""

from app.gst.gstin import gstin_check_char


def gstin(state: str, pan: str = "AAPFU0939F") -> str:
    first14 = f"{state}{pan}1Z"
    return first14 + gstin_check_char(first14)


def signup(client, email="owner@shop.in"):
    r = client.post("/api/auth/register", json={"name": "Owner", "email": email, "password": "secret123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def make_business(client, auth, **over):
    body = {"name": "Sharma Traders", "gst_type": "REGULAR", "gstin": gstin("27", "AABCS1429B"), "state_code": "27"}
    body.update(over)
    r = client.post("/api/businesses", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return {**auth, "X-Business-Id": r.json()["id"]}


def test_full_billing_flow(client):
    h = make_business(client, signup(client))

    # masters
    local = client.post("/api/parties", headers=h, json={
        "name": "Local Retail", "type": "CUSTOMER", "gst_type": "REGISTERED", "gstin": gstin("27", "AAACL1234C")}).json()
    assert local["state_code"] == "27"
    outstation = client.post("/api/parties", headers=h, json={
        "name": "Karnataka Buyer", "type": "CUSTOMER", "gst_type": "REGISTERED", "gstin": gstin("29", "AAACK5678D")}).json()
    supplier = client.post("/api/parties", headers=h, json={
        "name": "Wholesale Supplier", "type": "SUPPLIER", "gst_type": "REGISTERED", "gstin": gstin("27", "AAACW9999E"),
        "opening_balance": -500}).json()
    item = client.post("/api/items", headers=h, json={
        "name": "Steel Bottle", "hsn_sac": "7323", "unit": "PCS", "sale_price": 500, "purchase_price": 300,
        "gst_rate": 18, "opening_stock": 10}).json()
    assert item["stock"] == 10

    # bad GSTIN is rejected
    r = client.post("/api/parties", headers=h, json={"name": "X", "gst_type": "REGISTERED", "gstin": "27AAPFU0939F1ZA"})
    assert r.status_code == 422

    line = {"item_id": item["id"], "name": "Steel Bottle", "qty": 2, "rate": 500, "gst_rate": 18}

    # intra-state sale -> CGST+SGST, partially paid
    r = client.post("/api/vouchers", headers=h, json={
        "type": "SALE", "date": "2026-09-10", "party_id": local["id"], "lines": [line], "amount_paid": 180})
    assert r.status_code == 201, r.text
    s1 = r.json()
    assert s1["number"] == "INV/26-27/0001"
    assert (s1["cgst"], s1["sgst"], s1["igst"], s1["grand_total"]) == (90, 90, 0, 1180)
    assert s1["status"] == "PARTIAL" and s1["balance"] == 1000
    assert s1["title"] == "Tax Invoice"

    # inter-state sale -> IGST
    s2 = client.post("/api/vouchers", headers=h, json={
        "type": "SALE", "date": "2026-09-11", "party_id": outstation["id"], "lines": [line]}).json()
    assert s2["inter_state"] and s2["igst"] == 180 and s2["number"] == "INV/26-27/0002"

    # walk-in sale must be fully paid
    r = client.post("/api/vouchers", headers=h, json={"type": "SALE", "date": "2026-09-12", "lines": [line]})
    assert r.status_code == 400
    r = client.post("/api/vouchers", headers=h, json={
        "type": "SALE", "date": "2026-09-12", "lines": [line], "amount_paid": 1180, "payment_mode": "UPI"})
    assert r.status_code == 201 and r.json()["status"] == "PAID"

    # purchase adds stock and ITC
    p1 = client.post("/api/vouchers", headers=h, json={
        "type": "PURCHASE", "date": "2026-09-05", "party_id": supplier["id"], "supplier_invoice_no": "W-77",
        "lines": [{**line, "qty": 20, "rate": 300}]}).json()
    assert p1["tax_applicable"] and p1["grand_total"] == 7080

    # credit note against first invoice returns 1 unit to stock
    cn = client.post("/api/vouchers", headers=h, json={
        "type": "SALE_RETURN", "date": "2026-09-15", "party_id": local["id"], "original_voucher_id": s1["id"],
        "lines": [{**line, "qty": 1}]}).json()
    assert cn["title"] == "Credit Note" and cn["grand_total"] == 590

    stock = client.get(f"/api/items/{item['id']}", headers=h).json()["stock"]
    assert stock == 10 - 2 - 2 - 2 + 20 + 1

    # payment in settles the open invoice (FIFO)
    pay = client.post("/api/payments", headers=h, json={
        "type": "IN", "date": "2026-09-20", "party_id": local["id"], "amount": 410, "mode": "BANK"}).json()
    assert pay["allocated"] == 410 and pay["number"].startswith("RCT/26-27/")

    # balances: local = 1180 - 180 - 590 - 410 = 0 ; supplier = -500 - 7080
    parties = {p["id"]: p for p in client.get("/api/parties", headers=h).json()}
    assert parties[local["id"]]["balance"] == 0
    assert parties[supplier["id"]]["balance"] == -7580

    ledger = client.get(f"/api/parties/{local['id']}/ledger", headers=h).json()
    assert ledger["closing"] == 0 and len(ledger["entries"]) == 4

    # cancel the inter-state invoice: stock restored, excluded from GST
    client.post(f"/api/vouchers/{s2['id']}/cancel", headers=h)
    assert client.get(f"/api/items/{item['id']}", headers=h).json()["stock"] == stock + 2

    g1 = client.get("/api/reports/gstr1?date_from=2026-09-01&date_to=2026-09-30", headers=h).json()
    assert len(g1["b2b"]) == 1 and len(g1["cdnr"]) == 1
    assert g1["b2cs_total"]["taxable"] == 1000
    sales_doc = next(d for d in g1["docs"] if d["nature"].startswith("Invoices"))
    assert sales_doc["total"] == 3 and sales_doc["cancelled"] == 1

    g3 = client.get("/api/reports/gstr3b?date_from=2026-09-01&date_to=2026-09-30", headers=h).json()
    # output: (1000 + 1000 - 500) taxable -> CGST 135 ; ITC CGST 540
    assert g3["outward_taxable"]["taxable"] == 1500
    assert g3["outward_taxable"]["cgst"] == 135
    assert g3["itc_other"]["cgst"] == 540
    assert g3["net_payable"]["cgst"] == -405

    dash = client.get("/api/reports/dashboard", headers=h).json()
    assert "trend" in dash and len(dash["trend"]) == 6

    stock_rep = client.get("/api/reports/stock-summary?date_from=2026-09-01&date_to=2026-09-30", headers=h).json()
    assert stock_rep["rows"][0]["closing"] == stock + 2


def test_composition_business_issues_bill_of_supply(client):
    h = make_business(client, signup(client), gst_type="COMPOSITION")
    r = client.post("/api/vouchers", headers=h, json={
        "type": "SALE", "date": "2026-09-10", "amount_paid": 100,
        "lines": [{"name": "Service", "qty": 1, "rate": 100, "gst_rate": 18}]})
    v = r.json()
    assert v["title"] == "Bill of Supply" and v["grand_total"] == 100 and v["cgst"] == 0


def test_unregistered_business_needs_no_gstin(client):
    h = make_business(client, signup(client), gst_type="UNREGISTERED", gstin=None)
    r = client.get("/api/businesses/current", headers=h)
    assert r.json()["gstin"] is None


def test_tenant_isolation(client):
    a = make_business(client, signup(client, "a@x.in"))
    b = make_business(client, signup(client, "b@x.in"))
    party = client.post("/api/parties", headers=a, json={"name": "A's customer"}).json()
    assert client.get(f"/api/parties/{party['id']}", headers=b).status_code == 404
    assert client.get("/api/parties", headers=b).json() == []
    # b cannot act on a's business even with a's business id
    spoof = {**b, "X-Business-Id": a["X-Business-Id"]}
    assert client.get("/api/parties", headers=spoof).status_code == 403


def test_reverse_charge_purchase(client):
    h = make_business(client, signup(client))
    sup = client.post("/api/parties", headers=h, json={
        "name": "GTA Transport", "type": "SUPPLIER", "gst_type": "REGISTERED", "gstin": gstin("27", "AAACG1111F")}).json()
    v = client.post("/api/vouchers", headers=h, json={
        "type": "PURCHASE", "date": "2026-09-10", "party_id": sup["id"], "reverse_charge": True,
        "lines": [{"name": "Freight", "hsn_sac": "9965", "qty": 1, "rate": 1000, "gst_rate": 5}]}).json()
    assert v["grand_total"] == 1000 and v["cgst"] == 25
    g3 = client.get("/api/reports/gstr3b?date_from=2026-09-01&date_to=2026-09-30", headers=h).json()
    assert g3["inward_rcm"]["cgst"] == 25 and g3["itc_rcm"]["cgst"] == 25
