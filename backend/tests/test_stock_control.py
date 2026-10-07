"""Billing more than is in stock: warn (confirm), block (manager approval / PIN), allow."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_rbac import staff


def bill(qty, item, **extra):
    return {"type": "SALE", "date": "2026-09-10", "fully_paid": True, "lines": [{"item_id": item["id"], "name": item["name"], "qty": qty, "rate": 100, "gst_rate": 0}], **extra}


def test_warn_block_allow(client):
    h = make_business(client, signup(client), stock_control="WARN")
    item = post(client, h, "/api/items", {"name": "Fan", "unit": "PCS", "sale_price": 100, "opening_stock": 5, "opening_stock_date": "2026-04-01"})
    svc = post(client, h, "/api/items", {"type": "SERVICE", "name": "Fitting", "hsn_sac": "998719", "sale_price": 100})

    assert client.post("/api/vouchers", headers=h, json=bill(5, item)).status_code == 201  # exactly the stock: fine
    r = client.post("/api/vouchers", headers=h, json=bill(2, item))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "STOCK_SHORT"
    s = r.json()["detail"]["shortages"][0]
    assert s["available"] == 0 and s["qty"] == 2 and s["after"] == -2 and "Fan: 0 in stock, billing 2 PCS" in r.json()["detail"]["message"]
    assert client.get(f"/api/items/{item['id']}", headers=h).json()["stock"] == 0  # nothing saved
    v = post(client, h, "/api/vouchers", bill(2, item, allow_negative=True))  # confirmed
    assert client.get(f"/api/items/{item['id']}", headers=h).json()["stock"] == -2
    # services are never checked; editing counts the bill's own quantity back
    assert client.post("/api/vouchers", headers=h, json={**bill(9, svc), "lines": [{"item_id": svc["id"], "name": "Fitting", "hsn_sac": "998719", "qty": 9, "rate": 100, "gst_rate": 0}]}).status_code == 201
    body = bill(1, item)
    assert client.put(f"/api/vouchers/{v['id']}", headers=h, json=body).status_code == 409  # still -1 after the edit
    assert client.put(f"/api/vouchers/{v['id']}", headers=h, json={**body, "allow_negative": True}).status_code == 200
    assert client.get("/api/reports/dashboard", headers=h).json()["inventory"]["negative"] == 1

    # BLOCK: the owner confirms; billing staff need a manager's PIN
    biz = client.get("/api/businesses/current", headers=h).json()
    keep = {k: x for k, x in biz.items() if k not in ("id", "plan", "einvoice_password_set", "ewb_password_set", "gst_portal", "modules")}
    assert client.put("/api/businesses/current", headers=h, json={**keep, "stock_control": "BLOCK"}).json()["stock_control"] == "BLOCK"
    assert client.post("/api/vouchers", headers=h, json=bill(1, item)).status_code == 409
    assert client.post("/api/vouchers", headers=h, json=bill(1, item, allow_negative=True)).status_code == 201
    op = staff(client, h, "op@x.in", "BILLING")
    r = client.post("/api/vouchers", headers=op, json=bill(1, item, allow_negative=True))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "APPROVAL_REQUIRED"
    client.put("/api/me/approval-pin", headers=h, json={"pin": "4321"})  # owner sets a manager PIN
    assert client.post("/api/vouchers", headers={**op, "X-Approval-Pin": "1111"}, json=bill(1, item)).status_code == 403
    assert client.post("/api/vouchers", headers={**op, "X-Approval-Pin": "4321"}, json=bill(1, item)).status_code == 201
    # a settings save that leaves the field out keeps it
    assert client.put("/api/businesses/current", headers=h, json={k: x for k, x in keep.items() if k != "stock_control"}).json()["stock_control"] == "BLOCK"

    # ALLOW: no check
    client.put("/api/businesses/current", headers=h, json={**keep, "stock_control": "ALLOW"})
    assert client.post("/api/vouchers", headers=op, json=bill(50, item)).status_code == 201

    # estimates / orders never take stock
    client.put("/api/businesses/current", headers=h, json={**keep, "stock_control": "BLOCK"})
    assert client.post("/api/vouchers", headers=h, json={**bill(500, item), "type": "ESTIMATE", "fully_paid": False}).status_code == 201
