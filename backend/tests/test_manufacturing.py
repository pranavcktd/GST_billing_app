"""Manufacturing: BOM, production plan, stock & cost, shortages, books stay balanced, undo."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import gstin, post


def test_bom_and_production(client):
    h = make_business(client, signup(client))
    sup = post(client, h, "/api/parties", {"name": "Raw supplier", "type": "SUPPLIER", "gst_type": "REGISTERED", "gstin": gstin("27", "AABCR1111A")})
    a = post(client, h, "/api/items", {"name": "Steel sheet", "unit": "KGS", "purchase_price": 100, "gst_rate": 18})
    b = post(client, h, "/api/items", {"name": "Paint", "unit": "LTR", "purchase_price": 50, "gst_rate": 18, "opening_stock": 20,
                                        "opening_stock_date": "2026-04-01"})
    f = post(client, h, "/api/items", {"name": "Steel almirah", "unit": "PCS", "sale_price": 1200, "gst_rate": 18})
    post(client, h, "/api/vouchers", {"type": "PURCHASE", "date": "2026-09-01", "party_id": sup["id"], "fully_paid": True,
                                      "lines": [{"item_id": a["id"], "name": "Steel sheet", "qty": 10, "rate": 100, "gst_rate": 18}]})

    assert client.post("/api/boms", headers=h, json={"item_id": f["id"], "lines": [{"item_id": f["id"], "qty": 1}]}).status_code == 422
    bom = post(client, h, "/api/boms", {"item_id": f["id"], "output_qty": 1, "other_cost": 20,
                                        "lines": [{"item_id": a["id"], "qty": 2}, {"item_id": b["id"], "qty": 3}]})
    assert bom["name"] == "Steel almirah — standard" and len(bom["lines"]) == 2

    plan = client.get(f"/api/boms/{bom['id']}/plan", headers=h, params={"qty": 4, "date": "2026-09-10"}).json()
    assert float(plan["material_cost"]) == 1400 and float(plan["other_cost"]) == 80 and float(plan["unit_cost"]) == 370
    p = post(client, h, "/api/productions", {"bom_id": bom["id"], "qty": 4, "date": "2026-09-10", "batch_no": "B-01"})
    assert p["number"].startswith("PRD/") and p["unit_cost"] == 370 and p["shortages"] == []
    stock = {i["name"]: i["stock"] for i in client.get("/api/items", headers=h).json()}
    assert stock == {"Steel sheet": 2, "Paint": 8, "Steel almirah": 4}

    # not enough steel for 2 more → refused unless allowed
    r = client.post("/api/productions", headers=h, json={"bom_id": bom["id"], "qty": 2, "date": "2026-09-11"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "SHORTAGE" and "Steel sheet" in r.json()["detail"]["message"]

    # sell two, books still balance; closing stock carries the produced cost
    buyer = post(client, h, "/api/parties", {"name": "Buyer", "gst_type": "UNREGISTERED"})
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-15", "party_id": buyer["id"], "fully_paid": True,
                                      "lines": [{"item_id": f["id"], "name": "Steel almirah", "qty": 2, "rate": 1200, "gst_rate": 18}]})
    bs = client.get("/api/reports/run/balance-sheet", headers=h, params={"as_of": "2026-09-30"}).json()
    assert not any("Difference" in x["label"] for s in bs["sections"] for x in s["rows"])
    assert len(client.get("/api/productions", headers=h).json()) == 1

    # undo the production → stock returns
    assert client.delete(f"/api/productions/{p['id']}", headers=h).status_code == 204
    stock = {i["name"]: i["stock"] for i in client.get("/api/items", headers=h).json()}
    assert stock == {"Steel sheet": 10, "Paint": 20, "Steel almirah": -2}
