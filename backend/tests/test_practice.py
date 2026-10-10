"""Practitioner workspace: entitlement, trial-balance import, final accounts maths, partnership, carry forward,
finalise / reopen, and importing from MyBillSync books."""

import io
from decimal import Decimal

from openpyxl import Workbook

from app.services import final_accounts as FA
from app.services import practice_io as IO
from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_security_admin import superadmin


def enable(client, root, user_email="owner@shop.in", clients=5):
    acc = next(a for a in client.get("/api/admin/accounts", headers=root).json() if a["email"] == user_email)
    r = client.put(f"/api/admin/accounts/{acc['account_id']}/subscription", headers=root, json={
        "plan": acc["plan"], "status": acc["status"], "valid_until": acc["valid_until"],
        "extra_businesses": acc["extra_businesses"], "feature_flags": {"practice_clients": clients}})
    assert r.status_code == 200, r.text


def xlsx(rows) -> bytes:
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def line(doc, section_title, key):
    sec = next(s for s in doc["sections"] if s["title"].startswith(section_title))
    return next(r for r in sec["rows"] if r.get("_key") == key)


def test_proprietorship_from_trial_balance(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    h = signup(client)
    make_business(client, h)
    assert client.get("/api/practice/status", headers=h).json()["enabled"] is False
    assert client.post("/api/practice/clients", headers=h, json={"name": "Ramesh Traders"}).status_code == 402
    enable(client, root, clients=1)

    c = post(client, h, "/api/practice/clients", {"name": "Ramesh Traders", "pan": "abcpr1234k"})
    assert c["pan"] == "ABCPR1234K"
    assert client.post("/api/practice/clients", headers=h, json={"name": "Second"}).status_code == 402  # limit 1
    f = post(client, h, f"/api/practice/clients/{c['id']}/files", {"fy": "2025-26"})

    tmpl = client.get("/api/practice/tb-template", headers=h)
    assert tmpl.status_code == 200
    r = client.post(f"/api/practice/files/{f['id']}/import-tb", headers=h,
                    files={"file": ("tb.xlsx", tmpl.content, "application/octet-stream")}).json()
    assert r["imported"] == 12 and r["unmapped"] == 0 and r["warnings"] == []
    heads = {l["name"]: l["head"] for l in r["file"]["data"]["ledgers"]}
    assert heads["Salary"] == "EMPLOYEE" and heads["Drawings - Ramesh"] == "DRAWINGS" and heads["HDFC Bank"] == "CASH_BANK"

    data = r["file"]["data"]
    data["closing_stock"] = {"cy": "200000", "py": "150000"}
    data["depreciation"] = {"method": "IT", "assets": [{"description": "Office furniture", "block": "Furniture & fittings", "opening": "50000"}],
                            "py_amount": "5500"}
    client.put(f"/api/practice/files/{f['id']}", headers=h, json={"data": data})
    st = client.get(f"/api/practice/files/{f['id']}/statements", headers=h).json()
    s = st["summary"]
    assert s["tb_difference"] == 0 and s["difference"] == 0
    assert float(s["total_dep"]) == 5000 and float(s["gross_profit"]) == 450000 and float(s["net_profit"]) == 265000
    assert float(s["capital_closing"]) == 365000 and float(s["total_assets"]) == 435000
    doc = st["doc"]
    assert float(line(doc, "Balance sheet", "FIXED_ASSETS")["cy"]) == 45000
    assert float(line(doc, "Balance sheet", "INVENTORY")["cy"]) == 200000
    assert float(line(doc, "Statement of profit", "CHANGE_IN_STOCK")["cy"]) == -50000
    assert any(sec["title"].startswith("Note 5") for sec in doc["sections"])
    assert "Furniture & fittings @ 10" in st["explain"]["DEPRECIATION"]["text"]
    assert st["checks"][0]["level"] == "ok"
    # PDF export of the statements works through the shared exporter
    pdf = client.post("/api/export/table", headers=h, params={"format": "pdf"}, json=doc)
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"

    # finalise → locked → reopen as version 2
    fin = post(client, h, f"/api/practice/files/{f['id']}/finalize", {}, 200)
    assert fin["status"] == "FINAL"
    assert client.put(f"/api/practice/files/{f['id']}", headers=h, json={"data": data}).status_code == 400
    assert post(client, h, f"/api/practice/files/{f['id']}/reopen", {}, 200)["version"] == 2

    # next year: comparatives and openings carried forward
    nxt = post(client, h, f"/api/practice/clients/{c['id']}/files", {"fy": "2026-27"})
    d2 = nxt["data"]
    sales = next(l for l in d2["ledgers"] if l["name"] == "Sales")
    assert Decimal(sales["py"]) == -1500000 and Decimal(sales["cy"]) == 0
    assert next(l for l in d2["ledgers"] if l["head"] == "OPENING_STOCK")["cy"] == "200000"
    assert Decimal(d2["depreciation"]["assets"][0]["opening"]) == 45000
    assert Decimal(d2["py"]["ppe"]) == 45000 and Decimal(d2["depreciation"]["py_amount"]) == 5000
    assert client.post(f"/api/practice/clients/{c['id']}/files", headers=h, json={"fy": "2026-27"}).status_code == 409


def test_partnership_and_tb_formats(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    h = signup(client)  # a practitioner without any business of their own
    assert client.get("/api/practice/status", headers=h).json() == {"enabled": False, "limit": 0, "used": 0}
    enable(client, root)
    c = post(client, h, "/api/practice/clients", {"name": "A & B Associates", "entity_type": "PARTNERSHIP"})
    f = post(client, h, f"/api/practice/clients/{c['id']}/files", {"fy": "2025-26"})
    # Tally-style export: Particulars / Debit / Credit with group rows above their ledgers
    tb = xlsx([["Trial Balance"], ["Particulars", "Debit", "Credit"],
               ["Capital Account", None, 500000], ["Capital - A", None, 300000], ["Capital - B", None, 200000],
               ["Drawings - A", 30000, None],
               ["Sales Accounts", None, 1000000], ["Sales", None, 1000000],
               ["Purchases", 600000, None], ["Office expenses", 100000, None],
               ["Bank of Baroda", 450000, None], ["Sundry Debtors", 320000, None], ["Grand Total", 1500000, 1500000]])
    r = client.post(f"/api/practice/files/{f['id']}/import-tb", headers=h, files={"file": ("tb.xlsx", tb, "application/octet-stream")}).json()
    names = [l["name"] for l in r["file"]["data"]["ledgers"]]
    assert "Capital Account" not in names and "Sales Accounts" not in names and "Sundry Debtors" in names
    data = r["file"]["data"]
    data["partners"] = [{"id": "A", "name": "A", "share": "60", "interest_rate": "10", "remuneration": "50000"},
                        {"id": "B", "name": "B", "share": "40", "interest_rate": "10", "remuneration": "0"}]
    for l in data["ledgers"]:
        if l["name"].endswith("- A"):
            l["partner"] = "A"
        elif l["name"].endswith("- B"):
            l["partner"] = "B"
    client.put(f"/api/practice/files/{f['id']}", headers=h, json={"data": data})
    st = client.get(f"/api/practice/files/{f['id']}/statements", headers=h).json()
    assert st["summary"]["difference"] == 0 and float(st["summary"]["net_profit"]) == 200000
    note = next(s for s in st["doc"]["sections"] if s["title"].startswith("Note 1"))
    closing = next(r for r in note["rows"] if r["label"] == "Closing balance")
    assert float(closing["p0"]) == 470000 and float(closing["p1"]) == 300000
    assert all(ch["level"] != "error" for ch in st["checks"])
    # mappings are remembered for the client
    c2 = client.get(f"/api/practice/clients/{c['id']}", headers=h).json()
    assert c2["files"][0]["fy"] == "2025-26"


def test_parser_and_depreciation_units():
    rows, warn = IO.parse_trial_balance("t.csv", b"Ledger,Amount\nSales,1000 Cr\nCash,1000 Dr\n")
    assert [(r["name"], Decimal(r["cy"])) for r in rows] == [("Sales", Decimal("-1000")), ("Cash", Decimal("1000"))] and not warn
    import datetime as dt
    d = FA.depreciation({"method": "IT", "assets": [
        {"block": "Computers & software", "opening": "10000", "addition": "20000", "addition_date": "2026-01-15"}]},
        dt.date(2025, 4, 1), dt.date(2026, 3, 31))
    assert d["total"]["depreciation"] == Decimal("8000.00")  # 10000×40% + 20000×20% (used < 180 days)
    d = FA.depreciation({"method": "CA", "assets": [
        {"description": "Machine", "cost": "100000", "opening_acc_dep": "0", "life": "10", "ca_method": "SLM", "put_to_use": "2020-04-01"}]},
        dt.date(2025, 4, 1), dt.date(2026, 3, 31))
    assert d["total"]["depreciation"] == Decimal("9500.00")  # (100000 − 5% residual) / 10


def test_import_from_mybillsync_books(client, monkeypatch):
    root = superadmin(client, monkeypatch)
    h = signup(client)
    b = make_business(client, h)
    enable(client, root)
    post(client, b, "/api/vouchers", {"type": "SALE", "date": "2025-06-10", "fully_paid": True,
                                      "lines": [{"name": "Widget", "qty": 10, "rate": 1000, "gst_rate": 18}]})
    sup = post(client, b, "/api/parties", {"name": "Supplier", "type": "SUPPLIER", "gst_type": "UNREGISTERED"})
    post(client, b, "/api/vouchers", {"type": "PURCHASE", "date": "2025-06-01", "fully_paid": True, "tax_applicable": False, "party_id": sup["id"],
                                      "lines": [{"name": "Widget", "qty": 10, "rate": 600, "gst_rate": 0}]})
    c = post(client, h, "/api/practice/clients", {"name": "Own shop"})
    f = post(client, h, f"/api/practice/clients/{c['id']}/files", {"fy": "2025-26"})
    biz = client.get("/api/practice/linkable-businesses", headers=h).json()
    assert biz and biz[0]["role"] == "OWNER"
    r = client.post(f"/api/practice/files/{f['id']}/import-books", headers=h, json={"business_id": biz[0]["id"]})
    assert r.status_code == 200, r.text
    st = client.get(f"/api/practice/files/{f['id']}/statements", headers=h).json()
    assert st["summary"]["tb_difference"] == 0 and st["summary"]["difference"] == 0
    assert float(st["summary"]["revenue"]) == 10000
    stranger = signup(client, email="other@x.in")
    assert client.post(f"/api/practice/files/{f['id']}/import-books", headers=stranger, json={"business_id": biz[0]["id"]}).status_code == 404
