"""Global search respects permissions and finds parties, items, documents and payments."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import gstin, post


def test_global_search(client):
    h = make_business(client, signup(client))
    cust = post(client, h, "/api/parties", {"name": "Karnataka Retail", "gst_type": "REGISTERED",
                                            "gstin": gstin("29", "AAACK5678D"), "phone": "9876500000"})
    post(client, h, "/api/items", {"name": "Steel Bottle", "code": "SB-1", "hsn_sac": "7323", "gst_rate": 18})
    inv = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-10", "party_id": cust["id"],
                                            "lines": [{"name": "Steel Bottle", "qty": 1, "rate": 100, "gst_rate": 18}]})
    post(client, h, "/api/payments", {"type": "IN", "date": "2026-09-11", "party_id": cust["id"], "amount": 50, "mode": "CASH"})

    r = client.get("/api/search", headers=h, params={"q": "karnat"}).json()
    assert r["parties"][0]["name"] == "Karnataka Retail"
    assert r["documents"][0]["number"] == inv["number"]            # by party name
    assert r["payments"] and r["payments"][0]["party_name"] == "Karnataka Retail"
    assert client.get("/api/search", headers=h, params={"q": "9876500"}).json()["parties"]   # phone
    assert client.get("/api/search", headers=h, params={"q": "29AAACK"}).json()["parties"]   # GSTIN
    assert client.get("/api/search", headers=h, params={"q": "SB-1"}).json()["items"][0]["name"] == "Steel Bottle"
    assert client.get("/api/search", headers=h, params={"q": inv["number"][-6:]}).json()["documents"]
    assert client.get("/api/search", headers=h, params={"q": "k"}).json() == {"parties": [], "items": [], "documents": [], "payments": []}
