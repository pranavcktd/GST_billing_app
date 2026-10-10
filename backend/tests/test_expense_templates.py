"""Standard expense categories: the super admin's list, offered to a new business on first visit."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_security_admin import superadmin


def test_offer_import_skip_and_admin_list(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    h = make_business(client, signup(client))
    assert client.get("/api/expenses/categories", headers=h).json() == []  # nothing until the owner chooses
    t = client.get("/api/expenses/templates", headers=h).json()
    assert t["ask"] and t["choice"] is None and len(t["categories"]) == 16

    # import two of them; then the prompt is gone, rows are the business's own
    out = post(client, h, "/api/expenses/templates/import", {"names": ["Rent", "Tea & Refreshments"]}, 200)
    assert out == {"categories_added": 2, "items_added": 2}
    cats = {c["name"]: c for c in client.get("/api/expenses/categories", headers=h).json()}
    assert set(cats) == {"Rent", "Tea & Refreshments"} and cats["Tea & Refreshments"]["itc_blocked"]
    items = client.get("/api/expenses/items", headers=h).json()
    assert {i["name"] for i in items} == {"Shop / office rent", "Tea & snacks"}
    t = client.get("/api/expenses/templates", headers=h).json()
    assert not t["ask"] and t["choice"] == "IMPORTED" and [c for c in t["categories"] if c["name"] == "Rent"][0]["exists"]
    # importing everything later adds only what is missing
    assert post(client, h, "/api/expenses/templates/import", {}, 200)["categories_added"] == 14

    # the super admin edits the list; a new business gets the new list, existing ones keep theirs
    cur = client.get("/api/admin/expense-templates", headers=root).json()
    assert cur["built_in"] and 5 in cur["gst_rates"]
    bad = client.put("/api/admin/expense-templates", headers=root, json={"categories": [{"name": "Diesel", "items": [{"name": "Diesel", "gst_rate": 7}]}]})
    assert bad.status_code == 422
    assert client.put("/api/admin/expense-templates", headers=root, json={"categories": [{"name": "A"}, {"name": "a"}]}).status_code == 422
    new = client.put("/api/admin/expense-templates", headers=root, json={"categories": [
        {"name": "Generator Diesel", "kind": "DIRECT", "items": [{"name": "Diesel for DG set", "gst_rate": 18}]}]}).json()
    assert not new["built_in"] and new["categories"][0]["kind"] == "DIRECT"
    assert client.put("/api/admin/expense-templates", headers=h, json={"categories": []}).status_code == 403

    other = make_business(client, signup(client, "two@shop.in"))
    assert [c["name"] for c in client.get("/api/expenses/templates", headers=other).json()["categories"]] == ["Generator Diesel"]
    assert post(client, other, "/api/expenses/templates/skip", {}, 200)["choice"] == "SKIPPED"
    assert client.get("/api/expenses/templates", headers=other).json()["ask"] is False
    assert len(client.get("/api/expenses/categories", headers=h).json()) == 16  # untouched

    assert len(client.delete("/api/admin/expense-templates", headers=root).json()["categories"]) == 16
