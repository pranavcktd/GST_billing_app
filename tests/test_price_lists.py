"""Price lists: rule-based and special rates, assigned to customers; last rate charged."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import post


def test_price_lists_and_last_rate(client):
    h = make_business(client, signup(client))
    tv = post(client, h, "/api/items", {"name": "LED TV", "unit": "PCS", "sale_price": 30000, "mrp": 35000, "gst_rate": 18})
    fan = post(client, h, "/api/items", {"name": "Ceiling fan", "unit": "PCS", "sale_price": 2000, "gst_rate": 18})
    pl = post(client, h, "/api/price-lists", {"name": "Dealer", "adjust_pct": -10})
    assert pl["special_rates"] == 0

    rows = {r["name"]: r for r in client.get(f"/api/price-lists/{pl['id']}/items", headers=h).json()}
    assert rows["LED TV"]["default_rate"] == 27000 and rows["Ceiling fan"]["default_rate"] == 1800
    r = client.put(f"/api/price-lists/{pl['id']}/items", headers=h, json={"rates": {tv["id"]: 26500, "bogus": 1}})
    assert r.status_code == 200 and r.json()["special_rates"] == 1
    assert client.put(f"/api/price-lists/{pl['id']}/items", headers=h, json={"rates": {fan["id"]: -1}}).status_code == 422

    dealer = post(client, h, "/api/parties", {"name": "City Electricals", "gst_type": "UNREGISTERED", "price_list_id": pl["id"]})
    assert dealer["price_list_id"] == pl["id"]
    walk = post(client, h, "/api/parties", {"name": "Retail buyer", "gst_type": "UNREGISTERED"})
    rates = client.get(f"/api/parties/{dealer['id']}/rates", headers=h).json()
    assert rates["price_list"]["name"] == "Dealer" and rates["rates"][tv["id"]] == 26500 and rates["rates"][fan["id"]] == 1800
    assert client.get(f"/api/parties/{walk['id']}/rates", headers=h).json() == {"price_list": None, "rates": {}}

    # MRP-based list
    mrp = post(client, h, "/api/price-lists", {"name": "MRP less 5%", "based_on": "MRP", "adjust_pct": -5})
    rows = {r["name"]: r for r in client.get(f"/api/price-lists/{mrp['id']}/items", headers=h).json()}
    assert rows["LED TV"]["default_rate"] == 33250 and rows["Ceiling fan"]["default_rate"] == 1900  # no MRP → sale price

    # a price list from another business cannot be assigned
    other = make_business(client, signup(client, "other@x.in"))
    foreign = post(client, other, "/api/price-lists", {"name": "Theirs"})
    assert client.post("/api/parties", headers=h, json={"name": "X", "price_list_id": foreign["id"]}).status_code == 404

    # last rate charged to the customer
    assert client.get(f"/api/items/{tv['id']}/last-rate", headers=h, params={"party_id": dealer["id"]}).json() is None
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-05", "party_id": dealer["id"],
                                      "lines": [{"item_id": tv["id"], "name": "LED TV", "qty": 1, "rate": 26000, "gst_rate": 18}]})
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-20", "party_id": dealer["id"],
                                      "lines": [{"item_id": tv["id"], "name": "LED TV", "qty": 1, "rate": 26400, "discount_pct": 2, "gst_rate": 18}]})
    last = client.get(f"/api/items/{tv['id']}/last-rate", headers=h, params={"party_id": dealer["id"]}).json()
    assert last["rate"] == 26400 and last["discount_pct"] == 2 and last["date"] == "2026-09-20"

    # deleting a list detaches its customers
    assert client.delete(f"/api/price-lists/{pl['id']}", headers=h).status_code == 204
    assert client.get(f"/api/parties/{dealer['id']}", headers=h).json()["price_list_id"] is None
