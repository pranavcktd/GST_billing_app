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
