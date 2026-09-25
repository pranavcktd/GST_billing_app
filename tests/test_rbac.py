"""Staff roles & permissions, approval PIN, custom roles, super admin and reseller levels."""

from app.config import get_settings
from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_phase2 import setup


def staff(client, owner_h, email, role):
    member = signup(client, email)
    post(client, owner_h, "/api/members", {"email": email, "role": role})
    return {**member, "X-Business-Id": owner_h["X-Business-Id"]}


def line(item):
    return {"item_id": item["id"], "name": "Bottle", "qty": 1, "rate": 500, "gst_rate": 18}


def test_billing_operator(client):
    h, cust, item = setup(client)
    op = staff(client, h, "cashier@x.in", "BILLING")
    # can bill and receive money
    today = __import__("datetime").date.today().isoformat()
    inv = post(client, op, "/api/vouchers", {"type": "SALE", "date": today, "party_id": cust["id"], "lines": [line(item)]})
    post(client, op, "/api/payments", {"type": "IN", "date": today, "party_id": cust["id"], "amount": 100})
    # sees stock but not purchase rates
    it = client.get(f"/api/items/{item['id']}", headers=op).json()
    assert it["stock"] == 19 and it["purchase_price"] == 0
    # cannot touch purchases, P&L, deletion, settings or staff
    assert client.post("/api/vouchers", headers=op, json={"type": "PURCHASE", "date": today, "party_id": cust["id"],
                                                          "lines": [line(item)]}).status_code == 403
    assert client.get("/api/vouchers?type=PURCHASE", headers=op).status_code == 403
    assert all(v["type"] == "SALE" for v in client.get("/api/vouchers", headers=op).json())
    assert client.get("/api/reports/run/profit-loss", headers=op).status_code == 403
    assert client.post(f"/api/vouchers/{inv['id']}/cancel", headers=op).status_code == 403
    assert client.put("/api/businesses/current", headers=op, json={}).status_code in (403, 422)
    assert client.get("/api/members", headers=op).status_code == 403
    dash = client.get("/api/reports/dashboard", headers=op).json()
    assert dash["payable"] is None and dash["cash_bank"] is None and dash["sales_month"] is not None
    slugs = {r["slug"] for r in client.get("/api/reports/catalog", headers=op).json()}
    assert "sale" in slugs and "profit-loss" not in slugs and "gstr1" not in slugs


def test_inventory_clerk_and_accountant(client):
    h, cust, item = setup(client)
    clerk = staff(client, h, "store@x.in", "INVENTORY")
    today = __import__("datetime").date.today().isoformat()
    sup = post(client, clerk, "/api/parties", {"name": "Supplier", "type": "SUPPLIER"})
    post(client, clerk, "/api/vouchers", {"type": "PURCHASE", "date": today, "party_id": sup["id"],
                                          "tax_applicable": False, "lines": [line(item)]})
    assert client.get(f"/api/items/{item['id']}", headers=clerk).json()["purchase_price"] == 300
    assert client.get("/api/reports/run/stock-summary", headers=clerk).status_code == 200
    assert client.get(f"/api/parties/{cust['id']}/ledger", headers=clerk).status_code == 403
    assert client.get("/api/reports/run/profit-loss", headers=clerk).status_code == 403
    assert client.get("/api/reports/gstr3b", headers=clerk, params={"date_from": today, "date_to": today}).status_code == 403

    ca = staff(client, h, "ca@x.in", "ACCOUNTANT")
    assert client.get("/api/reports/run/balance-sheet", headers=ca).status_code == 200
    assert client.get("/api/audit", headers=ca).status_code == 200
    assert client.get("/api/reports/gstr3b", headers=ca, params={"date_from": today, "date_to": today}).status_code == 200
    assert client.post("/api/vouchers", headers=ca, json={"type": "SALE", "date": today, "party_id": cust["id"],
                                                          "lines": [line(item)]}).status_code == 403
    assert client.post("/api/parties", headers=ca, json={"name": "x"}).status_code == 403


def test_approval_pin_for_old_entries(client):
    h, cust, item = setup(client)
    mgr = staff(client, h, "mgr@x.in", "MANAGER")
    op = staff(client, h, "op@x.in", "BILLING")
    # give the operator edit rights on sales (custom role) but not edit_past
    members = {m["email"]: m for m in client.get("/api/members", headers=h).json()}
    r = client.put(f"/api/members/{members['op@x.in']['id']}/permissions", headers=h,
                   json={"modules": {"sales": ["view", "create", "edit"], "items": ["view"], "parties": ["view"]}, "flags": []})
    assert r.status_code == 200, r.text
    old = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-01-10", "party_id": cust["id"], "lines": [line(item)]})
    body = {"type": "SALE", "date": "2026-01-10", "party_id": cust["id"], "lines": [{**line(item), "qty": 2}]}
    r = client.put(f"/api/vouchers/{old['id']}", headers=op, json=body)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "APPROVAL_REQUIRED"
    client.put("/api/me/approval-pin", headers=mgr, json={"pin": "4321"})
    assert client.put(f"/api/vouchers/{old['id']}", headers={**op, "X-Approval-Pin": "1111"}, json=body).status_code == 403
    r = client.put(f"/api/vouchers/{old['id']}", headers={**op, "X-Approval-Pin": "4321"}, json=body)
    assert r.status_code == 200 and r.json()["lines"][0]["qty"] == 2
    # the operator cannot set approval PINs
    assert client.put("/api/me/approval-pin", headers=op, json={"pin": "9999"}).status_code == 403


def test_account_level_limits(client):
    owner = signup(client, "chain@x.in")
    a = make_business(client, owner)  # trial: Enterprise
    b = make_business(client, owner, name="Branch 2", gstin=None, gst_type="UNREGISTERED")
    for i in range(3):
        staff(client, a, f"s{i}@x.in", "BILLING")
    # users are counted across the whole account, and plans apply to every business
    st = client.get("/api/billing/status", headers=b).json()
    assert st["usage"]["businesses"] == 2 and st["usage"]["users"] == 4


def test_superadmin_and_reseller(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "superadmin_emails", "boss@platform.in")
    boss = signup(client, "boss@platform.in")
    assert client.get("/api/auth/me", headers=boss).json()["platform_role"] == "SUPERADMIN"
    shop = make_business(client, signup(client, "shopkeeper@x.in"))
    assert client.get("/api/admin/stats", headers=boss).json()["accounts"] >= 1
    assert client.get("/api/admin/stats", headers={"Authorization": shop["Authorization"]}).status_code == 403
    health = client.get("/api/admin/health", headers=boss).json()
    assert health["database"] is True and health["einvoice_provider"] == "sandbox"

    partner = signup(client, "partner@x.in")
    post(client, boss, "/api/admin/resellers", {"email": "partner@x.in", "commission_pct": 25})
    acc = post(client, partner, "/api/reseller/accounts", {"name": "New Trader", "email": "trader@x.in"})
    assert len(acc["temporary_password"]) >= 8
    sale = post(client, partner, "/api/reseller/licenses", {"account_id": acc["account_id"], "plan": "PROFESSIONAL", "months": 12})
    assert sale["amount"] == 5898.82 and sale["commission"] == 1249.75  # 4999 + 18% GST ; 25% of 4999
    mine = client.get("/api/reseller/accounts", headers=partner).json()
    assert mine[0]["plan"] == "PROFESSIONAL" and "feature_flags" not in mine[0]
    # the reseller cannot license accounts outside their portfolio, nor see business data
    shop_owner = client.get("/api/auth/me", headers=shop).json()["user"]["id"]
    assert client.post("/api/reseller/licenses", headers=partner,
                       json={"account_id": shop_owner, "plan": "STARTER", "months": 1}).status_code == 404
    assert client.get("/api/parties", headers={**partner, "X-Business-Id": shop["X-Business-Id"]}).status_code == 403
    # new owner signs in with the temporary password and changes it
    tok = client.post("/api/auth/login", json={"email": "trader@x.in", "password": acc["temporary_password"]}).json()["token"]
    th = {"Authorization": f"Bearer {tok}"}
    assert client.put("/api/auth/password", headers=th, json={"current_password": acc["temporary_password"],
                                                              "new_password": "brandnew123"}).status_code == 200
    # super admin overrides + payouts
    r = client.put(f"/api/admin/accounts/{shop_owner}/subscription", headers=boss,
                   json={"plan": "STARTER", "status": "ACTIVE", "feature_flags": {"tally": True}})
    assert r.json()["plan"] == "STARTER"
    assert client.get("/api/exports/tally", headers=shop, params={"date_from": "2026-09-01", "date_to": "2026-09-30"}).status_code == 200
    lic = client.get("/api/admin/licenses", headers=boss).json()[0]
    assert post(client, boss, f"/api/admin/licenses/{lic['id']}/paid", {}, 200)["payout_status"] == "PAID"
    assert client.get("/api/reseller/licenses", headers=partner).json()["commission_pending"] == 0
