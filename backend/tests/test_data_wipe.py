"""Clearing a business's data group by group, with a backup first; owner and super admin."""

from tests.test_modules import build_books, post


def _wipe(client, h, groups, name=None, path="/api/data-wipe"):
    biz = client.get("/api/businesses/current", headers=h).json() if "X-Business-Id" in h else None
    return client.post(path, headers=h, json={"groups": groups, "confirm_name": name or biz["name"]})


def test_clear_sales_only_then_everything(client):
    h, ctx = build_books(client)
    opts = client.get("/api/data-wipe", headers=h).json()
    assert opts["counts"]["sales"] > 0 and {g["key"] for g in opts["groups"]} >= {"sales", "parties", "items", "accounts"}
    assert next(g for g in opts["groups"] if g["key"] == "parties")["requires"] == ["sales", "purchases", "expenses", "payments"]

    assert _wipe(client, h, ["sales"], name="wrong name").status_code == 400
    r = _wipe(client, h, ["sales"])
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["cleared"] == ["sales"] and out["removed"]["sales"] > 0 and out["backup_file"].endswith(".gstbak")
    types = {v["type"] for v in client.get("/api/vouchers", headers=h).json()}
    assert not types & {"SALE", "SALE_RETURN", "DELIVERY_CHALLAN", "SALE_ORDER", "ESTIMATE"}
    assert {"PURCHASE", "EXPENSE"} <= types
    pays = client.get("/api/payments", headers=h).json()
    assert pays and all(p["type"] == "OUT" for p in pays)  # receipts went with the sales, payments made stay
    assert len(client.get("/api/parties", headers=h).json()) == 4  # masters untouched
    backups = client.get("/api/backups", headers=h).json()
    assert backups[0]["kind"] == "WIPE"

    # the safety backup brings the sales back (as a new company)
    blob = client.get(f"/api/backups/{backups[0]['id']}/download", headers=h).content
    auth = {"Authorization": h["Authorization"]}
    new = client.post("/api/backups/restore", headers=auth, files={"file": ("x.gstbak", blob)}).json()
    assert any(v["type"] == "SALE" for v in client.get("/api/vouchers", headers={**auth, "X-Business-Id": new["id"]}).json())

    # parties pull in everything that uses them; numbering restarts
    r = _wipe(client, h, ["parties", "items", "accounts", "staff", "stock", "banking", "expense_items", "documents", "compliance"])
    assert r.status_code == 200, r.text
    assert set(r.json()["cleared"]) >= {"sales", "purchases", "expenses", "payments", "parties", "items", "accounts"}
    left = client.get("/api/data-wipe", headers=h).json()["counts"]
    assert all(v == 0 for v in left.values()), left
    accounts = client.get("/api/accounts", headers=h).json()
    assert len(accounts) == 1 and accounts[0]["is_default_cash"] and accounts[0]["opening_balance"] == 0
    assert client.get("/api/businesses/current", headers=h).json()["gstin"]  # profile kept
    item = post(client, h, "/api/items", {"name": "Fresh item", "sale_price": 10, "gst_rate": 18, "unit": "PCS"})
    v = post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-10-09", "lines": [{"item_id": item["id"], "name": "Fresh item", "qty": 1, "rate": 10, "gst_rate": 18}],
                                          "fully_paid": True, "allow_negative": True})
    assert v["number"].endswith("0001")


def test_only_owner_and_super_admin(client, monkeypatch):
    from tests.test_rbac import accept_invites
    from tests.test_security_admin import superadmin
    from tests.test_api_flow import signup

    h, _ = build_books(client)
    staff = signup(client, "manager@x.in")
    post(client, h, "/api/members", {"email": "manager@x.in", "role": "ADMIN"})
    accept_invites(client, staff)
    hs = {**staff, "X-Business-Id": h["X-Business-Id"]}
    assert client.get("/api/data-wipe", headers=hs).status_code == 403
    assert _wipe(client, hs, ["sales"], name="x").status_code == 403

    root = superadmin(client, monkeypatch)
    bid = h["X-Business-Id"]
    opts = client.get(f"/api/admin/businesses/{bid}/data-wipe", headers=root).json()
    r = client.post(f"/api/admin/businesses/{bid}/data-wipe", headers=root,
                    json={"groups": ["purchases"], "confirm_name": opts["business_name"]})
    assert r.status_code == 200, r.text
    assert not any(v["type"] == "PURCHASE" for v in client.get("/api/vouchers", headers=h).json())
    assert client.get("/api/backups", headers=h).json()[0]["kind"] == "WIPE"


def test_super_admin_sql_export(client, monkeypatch):
    from tests.test_security_admin import superadmin

    h, _ = build_books(client)
    post(client, h, "/api/backups", {})
    root = superadmin(client, monkeypatch)
    assert client.get("/api/admin/backups/sql", headers=h).status_code == 403
    r = client.get("/api/admin/backups/sql", headers=root)
    assert r.status_code == 200 and r.headers["content-disposition"].endswith('.sql"')
    sql = r.text
    assert sql.count("BEGIN;") == 1 and sql.count("COMMIT;") == 1
    assert 'INSERT INTO "vouchers"' in sql and 'INSERT INTO "businesses"' in sql
    assert 'INSERT INTO "backups"' not in sql  # stored backups are left out
    assert 'UPDATE "vouchers" SET "original_voucher_id"' in sql  # credit note → invoice link set after both exist
