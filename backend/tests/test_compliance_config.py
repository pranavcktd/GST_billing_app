"""Super admin configuration: effective-dated GST rules, plans, HSN master, rate-change notices."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_security_admin import superadmin


def line(rate=1000, gst=18, hsn="8471", **extra):
    return {"name": "Laptop", "hsn_sac": hsn, "qty": 1, "rate": rate, "gst_rate": gst, **extra}


def test_effective_dated_config(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    h = make_business(client, signup(client))
    cfg = client.get("/api/admin/config", headers=root).json()
    assert {f["key"] for f in cfg["fields"]} >= {"gst_rates", "b2cl_limit", "uqc", "states", "company"}
    assert cfg["effective"]["b2cl_limit"] == 100000

    # validation
    r = client.post("/api/admin/config/versions", headers=root, json={"effective_from": "2026-10-01", "values": {"b2cl_limit": "abc"}})
    assert r.status_code == 422
    r = client.post("/api/admin/config/versions", headers=root, json={"effective_from": "2026-10-01", "values": {"nope": 1}})
    assert r.status_code == 422
    assert client.post("/api/admin/config/versions", headers=h, json={"effective_from": "2026-10-01", "values": {}}).status_code == 403

    # from 1-Oct-2026: B2CL limit ₹50,000, the 12% slab withdrawn, a new 7% slab, invoice numbers up to 20 chars
    v = post(client, root, "/api/admin/config/versions", {"effective_from": "2026-10-01", "note": "Test notification",
             "values": {"b2cl_limit": 50000, "gst_rates": [0, 0.25, 3, 5, 7, 18, 28, 40], "invoice_number_max_len": 20}})
    old = client.get("/api/admin/config", headers=root, params={"on": "2026-09-30"}).json()["effective"]
    new = client.get("/api/admin/config", headers=root, params={"on": "2026-10-01"}).json()["effective"]
    assert old["b2cl_limit"] == 100000 and new["b2cl_limit"] == 50000 and 7 in new["gst_rates"] and 12 not in new["gst_rates"]

    # 12% still allowed on a September bill, refused on an October bill; 7% the other way round
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-09-30", "fully_paid": True, "lines": [line(gst=12)]})
    r = client.post("/api/vouchers", headers=h, json={"type": "SALE", "date": "2026-10-02", "fully_paid": True, "lines": [line(gst=12)]})
    assert r.status_code == 400 and "not valid" in r.text
    r = client.post("/api/vouchers", headers=h, json={"type": "SALE", "date": "2026-09-30", "fully_paid": True, "lines": [line(gst=7)]})
    assert r.status_code == 400
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-10-02", "fully_paid": True, "lines": [line(gst=7)]})
    # number length follows the date too
    r = client.post("/api/vouchers", headers=h, json={"type": "SALE", "date": "2026-09-30", "number": "A" * 18,
                                                       "fully_paid": True, "lines": [line()]})
    assert r.status_code == 400 and "16" in r.text
    post(client, h, "/api/vouchers", {"type": "SALE", "date": "2026-10-03", "number": "A" * 18, "fully_paid": True, "lines": [line()]})

    # B2CL uses the limit in force on the invoice date
    far = post(client, h, "/api/parties", {"name": "Delhi buyer", "gst_type": "UNREGISTERED", "state_code": "07"})
    for d in ("2026-09-20", "2026-10-20"):
        post(client, h, "/api/vouchers", {"type": "SALE", "date": d, "party_id": far["id"], "fully_paid": True,
                                          "lines": [line(70000)]})
    g1 = client.get("/api/reports/gstr1", headers=h, params={"date_from": "2026-09-01", "date_to": "2026-10-31"}).json()
    assert [d["date"] for d in g1["b2cl"]] == ["2026-10-20"]

    meta = client.get("/api/meta").json()
    assert "config" in meta and meta["config"]["company"]["name"]

    # deleting the version restores the defaults
    assert client.delete(f"/api/admin/config/versions/{v['id']}", headers=root).status_code == 204
    assert client.get("/api/admin/config", headers=root, params={"on": "2026-10-01"}).json()["effective"]["b2cl_limit"] == 100000
    audit = client.get("/api/admin/audit", headers=root).json()
    rows = audit["rows"] if isinstance(audit, dict) else audit
    assert any(a["entity"] == "config" for a in rows)


def test_plan_overrides(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    r = client.put("/api/admin/plans-config/STARTER", headers=root, json={"monthly": 249, "invoices_per_month": 300,
                                                                          "highlights": ["300 invoices / month"]})
    assert r.status_code == 200, r.text
    assert r.json()["plans"]["STARTER"]["monthly"] == 249
    plans = {p["code"]: p for p in client.get("/api/billing/plans").json()["plans"]}
    assert plans["STARTER"]["monthly"] == 249
    assert client.put("/api/admin/plans-config/STARTER", headers=root, json={"hack": 1}).status_code == 422
    # back to defaults
    back = client.put("/api/admin/plans-config/STARTER", headers=root, json={"monthly": 199, "invoices_per_month": 250,
                      "highlights": r.json()["defaults"]["STARTER"]["highlights"]}).json()
    assert "STARTER" not in back["overrides"]


def test_hsn_master_and_rate_notice(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    h = make_business(client, signup(client))
    post(client, root, "/api/admin/hsn", {"code": "84713010", "description": "Laptops", "gst_rate": 18})
    post(client, root, "/api/admin/hsn", {"code": "6109", "description": "T-shirts", "gst_rate": 12})
    assert client.get("/api/hsn-master", headers=h, params={"search": "lapt"}).json()[0]["code"] == "84713010"

    shirt = post(client, h, "/api/items", {"name": "T-shirt", "hsn_sac": "6109", "unit": "PCS", "sale_price": 500, "gst_rate": 12})
    laptop = post(client, h, "/api/items", {"name": "Laptop", "hsn_sac": "84713010", "unit": "PCS", "sale_price": 50000, "gst_rate": 18})
    copied = post(client, h, "/api/hsn-master/copy", {}, 200)
    assert copied["copied"] == 2

    n = post(client, root, "/api/admin/rate-notices", {"title": "Apparel to 5%", "reference": "9/2025-CT(Rate)",
             "effective_from": "2025-09-22", "changes": [{"hsn_prefix": "61", "new_rate": 5}]})
    assert client.get("/api/rate-notices", headers=h).json() == []  # drafts are not visible
    pub = post(client, root, f"/api/admin/rate-notices/{n['id']}/publish", {}, 200)
    assert pub["master_updated"] == 1
    assert client.put(f"/api/admin/rate-notices/{n['id']}", headers=root, json={
        "title": "Edited", "effective_from": "2025-09-22", "changes": [{"hsn_prefix": "61", "new_rate": 5}]}).status_code == 400

    pending = client.get("/api/rate-notices", headers=h).json()
    assert len(pending) == 1 and pending[0]["affected"] == 1
    prev = client.get(f"/api/rate-notices/{n['id']}/preview", headers=h).json()
    assert prev["items"] == [dict(id=shirt["id"], name="T-shirt", hsn="6109", old_rate=12.0, new_rate=5.0, old_cess=0.0, new_cess=0.0)]
    assert post(client, h, f"/api/rate-notices/{n['id']}/apply", {}, 200)["items_changed"] == 1
    assert client.get(f"/api/items/{shirt['id']}", headers=h).json()["gst_rate"] == 5
    assert client.get(f"/api/items/{laptop['id']}", headers=h).json()["gst_rate"] == 18
    hsn = {x["code"]: x for x in client.get("/api/hsn", headers=h).json()}
    assert hsn["6109"]["gst_rate"] == 5
    assert client.get("/api/rate-notices", headers=h).json() == []
    assert client.get("/api/rate-notices", headers=h, params={"include_done": True}).json()[0]["status"] == "APPLIED"
    assert client.get("/api/admin/rate-notices", headers=root).json()[0]["businesses_applied"] == 1

    # bulk import / export of the master
    x = client.get("/api/admin/hsn/export", headers=root)
    assert x.status_code == 200 and x.content[:2] == b"PK"
    csv = "HSN/SAC Code,Description,GST %,Cess %,Effective From\n1006,Rice,5,0,2025-09-22\n12,bad,5,,\n9999,Bad rate,13,,\n"
    res = client.post("/api/admin/hsn/import", headers=root, files={"file": ("hsn.csv", csv.encode(), "text/csv")}).json()
    assert res["created"] == 1 and len(res["errors"]) == 2
