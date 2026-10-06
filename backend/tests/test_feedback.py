"""User feedback round: service units, PDF file names, portal links."""

from tests.test_api_flow import gstin, make_business, signup
from tests.test_modules import post
from tests.test_security_admin import superadmin

Q = {"date_from": "2026-09-01", "date_to": "2026-09-30"}


def test_service_has_no_unit_and_reports_na(client):
    h = make_business(client, signup(client))
    svc = post(client, h, "/api/items", {"type": "SERVICE", "name": "Consulting", "unit": "HRS", "hsn_sac": "998311", "sale_price": 1000, "gst_rate": 18})
    assert svc["unit"] == "NA"  # whatever the client sends, a service has no unit
    goods = post(client, h, "/api/items", {"name": "Chair", "unit": "PCS", "sale_price": 500, "gst_rate": 18})
    assert goods["unit"] == "PCS"
    assert client.post("/api/items", headers=h, json={"name": "Desk", "unit": "NA"}).status_code == 422
    # switching a service to a product needs a real unit
    r = client.put(f"/api/items/{svc['id']}", headers=h, json={**svc, "type": "GOODS", "unit": "NOS", "hsn_sac": "9403"})
    assert r.status_code == 200 and r.json()["unit"] == "NOS"
    client.put(f"/api/items/{svc['id']}", headers=h, json={**svc, "type": "SERVICE"})

    buyer = post(client, h, "/api/parties", {"name": "M/s. Karan Stores Pvt Ltd", "gst_type": "REGISTERED", "gstin": gstin("27", "AAACK1234A")})
    v = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "party_id": buyer["id"], "lines": [
        {"item_id": svc["id"], "name": "Consulting", "hsn_sac": "998311", "unit": "NA", "qty": 3, "rate": 1000, "gst_rate": 18},
        {"item_id": goods["id"], "name": "Chair", "unit": "PCS", "qty": 2, "rate": 500, "gst_rate": 18, "hsn_sac": "9401"}]})

    g = client.get("/api/exports/gstr1-json", headers=h, params=Q).json()
    rows = {r["hsn_sc"]: r for r in g["hsn"]["hsn_b2b"]}
    assert rows["998311"]["uqc"] == "NA" and rows["998311"]["qty"] == 0
    assert rows["9401"]["uqc"] == "PCS" and rows["9401"]["qty"] == 2

    # PDF file name: type, number, short party name, date
    r = client.get(f"/api/vouchers/{v['id']}/pdf", headers=h)
    assert r.status_code == 200
    num = "".join(c if c.isalnum() else "-" for c in v["number"]).strip("-")
    assert f'filename="Tax-Invoice_{num}_Karan-Stores_10-09-2026.pdf"' in r.headers["content-disposition"]


def test_portal_links_are_configurable(client, monkeypatch):
    from app.services import config_store as C
    root = superadmin(client, monkeypatch)
    assert C.link("ewaybill_portal").startswith("https://")
    r = client.post("/api/admin/config/versions", headers=root, json={
        "effective_from": "2026-01-01", "values": {"links": {**C.LINKS, "ewaybill_portal": "https://new-ewb.example.in"}}})
    assert r.status_code == 201, r.text
    assert client.get("/api/meta").json()["config"]["links"]["ewaybill_portal"] == "https://new-ewb.example.in"
    bad = client.post("/api/admin/config/versions", headers=root, json={
        "effective_from": "2026-01-01", "values": {"links": {"gst_portal": "javascript:alert(1)"}}})
    assert bad.status_code == 422


def test_money_entries_can_be_corrected(client):
    import datetime as dt
    h = make_business(client, signup(client))
    today = dt.date.today().isoformat()  # today's entries need no manager approval
    accounts = client.get("/api/accounts", headers=h).json()
    cash = next(a for a in accounts if a["is_default_cash"])
    bank = post(client, h, "/api/accounts", {"type": "BANK", "name": "HDFC", "opening_balance": 0})
    bal = lambda acc: next(a for a in client.get("/api/accounts", headers=h).json() if a["id"] == acc["id"])["balance"]  # noqa: E731

    t = post(client, h, "/api/transfers", {"date": today, "from_account_id": cash["id"], "to_account_id": bank["id"], "amount": 500})
    r = client.put(f"/api/transfers/{t['id']}", headers=h, json={**t, "amount": 300})
    assert r.status_code == 200 and bal(bank) == 300
    assert client.put(f"/api/transfers/{t['id']}", headers=h, json={**t, "to_account_id": cash["id"]}).status_code == 400

    c = post(client, h, "/api/capital", {"date": today, "type": "INTRODUCED", "amount": 1000, "account_id": bank["id"]})
    assert client.put(f"/api/capital/{c['id']}", headers=h, json={**c, "amount": 1500}).json()["amount"] == 1500
    assert bal(bank) == 1800

    tp = post(client, h, "/api/tax-payments", {"date": today, "type": "GST", "amount": 100, "account_id": bank["id"]})
    assert client.put(f"/api/tax-payments/{tp['id']}", headers=h, json={**tp, "type": "TDS", "reference": "CIN1"}).json()["type"] == "TDS"

    loan = post(client, h, "/api/loans", {"name": "Term loan", "opening_balance": 10000})
    e = post(client, h, f"/api/loans/{loan['id']}/txns", {"date": today, "type": "EMI", "principal": 1000, "interest": 100})
    r = client.put(f"/api/loans/{loan['id']}/txns/{e['id']}", headers=h, json={**e, "principal": 2000})
    assert r.status_code == 200 and client.get(f"/api/loans/{loan['id']}", headers=h).json()["loan"]["outstanding"] == 8000
    assert client.put(f"/api/loans/{loan['id']}/txns/{e['id']}", headers=h, json={**e, "principal": 20000}).status_code == 400

    # a payment re-settles its bills when corrected
    p = post(client, h, "/api/parties", {"name": "Ravi", "gst_type": "UNREGISTERED"})
    bills = [post(client, h, "/api/vouchers", {"type": "SALE", "date": today, "party_id": p["id"],
              "lines": [{"name": "Work", "qty": 1, "rate": amt, "gst_rate": 0}]}) for amt in (1000, 1000)]
    pay = post(client, h, "/api/payments", {"type": "IN", "date": today, "party_id": p["id"], "amount": 1000, "voucher_id": bills[1]["id"]})
    assert [a["voucher_id"] for a in pay["allocations"]] == [bills[1]["id"]]
    r = client.put(f"/api/payments/{pay['id']}", headers=h, json={"type": "IN", "date": today, "party_id": p["id"], "amount": 1500, "mode": "UPI"})
    assert r.status_code == 200, r.text
    alloc = {a["voucher_id"]: a["amount"] for a in r.json()["allocations"]}
    assert alloc == {bills[1]["id"]: 1000, bills[0]["id"]: 500} and r.json()["number"] == pay["number"]
    assert client.put(f"/api/payments/{pay['id']}", headers=h, json={"type": "OUT", "date": today, "party_id": p["id"], "amount": 1}).status_code == 400

    # older entries need a manager's approval (or the edit-past right) — the owner has it
    old = post(client, h, "/api/capital", {"date": "2026-04-01", "type": "DRAWINGS", "amount": 10})
    assert client.delete(f"/api/capital/{old['id']}", headers=h).status_code == 204

    # manual stock adjustment can be deleted; other movements can't
    item = post(client, h, "/api/items", {"name": "Box", "unit": "PCS", "opening_stock": 5})
    client.post(f"/api/items/{item['id']}/adjust", headers=h, json={"qty": 2, "direction": "ADD", "date": today})
    moves = client.get(f"/api/items/{item['id']}/movements", headers=h).json()
    adj = next(m for m in moves if m["type"] == "ADJUSTMENT")
    opening = next(m for m in moves if m["type"] == "OPENING")
    assert client.delete(f"/api/items/{item['id']}/movements/{opening['id']}", headers=h).status_code == 400
    assert client.delete(f"/api/items/{item['id']}/movements/{adj['id']}", headers=h).status_code == 204
    assert client.get(f"/api/items/{item['id']}", headers=h).json()["stock"] == 5
