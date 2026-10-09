"""Demo company with about three months of realistic data, for showing the app to prospects.

    cd backend
    .venv/Scripts/python -m scripts.seed_demo            # creates the demo login + company (skips if it exists)
    .venv/Scripts/python -m scripts.seed_demo --fresh    # adds another, freshly filled demo company

Everything after the login is entered through the app's own API, so bills, stock, GST, ledgers and payroll are
worked out exactly as if staff had typed them in. The data is random but repeatable (fixed seed).
"""

import argparse
import datetime as dt
import random
import sys

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.gst.gstin import gstin_check_char
from app.main import app
from app.models import Business, User
from app.routers.auth import token_for
from app.security import hash_password
from app.services.plans import start_trial

EMAIL = "demo@example.com"
PASSWORD = "Demo@2026"
NAME = "Shree Ganesh Electricals"
TODAY = dt.date.today()
START = TODAY - dt.timedelta(days=95)
R = random.Random(2026)
CREATED: list[str] = []  # removed again if the run fails half-way


def gstin(state: str, pan: str) -> str:
    return f"{state}{pan}1Z" + gstin_check_char(f"{state}{pan}1Z")


class Api:
    def __init__(self, client: TestClient, token: str):
        self.c = client
        self.h = {"Authorization": f"Bearer {token}"}

    def __call__(self, method: str, path: str, body=None, ok=(200, 201)):
        r = self.c.request(method, f"/api{path}", headers=self.h, json=body)
        if r.status_code not in ok:
            raise SystemExit(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
        return r.json() if r.content else None


def login_user() -> tuple[str, bool]:
    with SessionLocal() as db:
        u = db.scalar(select(User).where(func.lower(User.email) == EMAIL))
        created = u is None
        if created:
            u = User(name="Demo Owner", email=EMAIL, phone="9822012345", password_hash=hash_password(PASSWORD))
            db.add(u)
            db.flush()
            start_trial(db, u.id)
            db.commit()
        return token_for(u), created


def days(n: int) -> list[dt.date]:
    return sorted(START + dt.timedelta(days=R.randint(0, (TODAY - START).days - 1)) for _ in range(n))


def main(fresh: bool) -> None:
    token, _ = login_user()
    client = TestClient(app)
    api = Api(client, token)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(func.lower(User.email) == EMAIL))
        have = db.scalars(select(Business.name).where(Business.owner_id == owner.id)).all()
    name = NAME if NAME not in have else (f"{NAME} ({len(have) + 1})" if fresh else None)
    if name is None:
        print(f"Demo company already exists. Sign in as {EMAIL} / {PASSWORD}  (use --fresh for another one)")
        return

    # ---------------------------------------------------------------- business
    biz = api("POST", "/businesses", {
        "name": name, "legal_name": "Shree Ganesh Electricals", "gst_type": "REGULAR", "gstin": gstin("27", "ABMPG4821K"),
        "pan": "ABMPG4821K", "state_code": "27", "address": "Shop 14, Laxmi Road, Budhwar Peth", "city": "Pune",
        "pincode": "411002", "phone": "9822012345", "email": EMAIL, "entity_type": "PROPRIETORSHIP",
        "bank_name": "HDFC Bank", "bank_account_no": "50200012345678", "bank_ifsc": "HDFC0000123", "bank_branch": "Laxmi Road, Pune",
        "upi_id": "shreeganesh@hdfcbank", "gst_registration_date": "2019-07-01",
        "invoice_terms": "Goods once sold will not be taken back.\nSubject to Pune jurisdiction.\nWarranty as per manufacturer."})
    CREATED.append(biz["id"])
    api.h["X-Business-Id"] = biz["id"]
    cur = api("GET", "/businesses/current")
    keep = {k: v for k, v in cur.items() if k not in ("id", "plan", "einvoice_password_set", "ewb_password_set", "gst_portal", "modules")}
    api("PUT", "/businesses/current", {**keep, "stock_control": "WARN"})
    accounts = api("GET", "/accounts")
    cash = next(a for a in accounts if a["is_default_cash"])
    api("PUT", f"/accounts/{cash['id']}", {"type": "CASH", "name": cash["name"], "opening_balance": 25000,
                                            "opening_date": START.isoformat()})
    bank = api("POST", "/accounts", {"type": "BANK", "name": "HDFC Current A/c", "bank_name": "HDFC Bank",
                                      "account_no": "50200012345678", "ifsc": "HDFC0000123", "opening_balance": 185000,
                                      "opening_date": START.isoformat()})
    print("company", name)

    # ---------------------------------------------------------------- parties
    def party(**k):
        return api("POST", "/parties", {"type": "CUSTOMER", "gst_type": "UNREGISTERED", "state_code": "27", **k})
    customers = [
        party(name="Kulkarni Builders Pvt Ltd", gst_type="REGISTERED", gstin=gstin("27", "AAECK7712M"), phone="9890011122",
              email="accounts@kulkarnibuilders.in", billing_address="Baner Road", city="Pune", pincode="411045", opening_balance=42000,
              credit_limit=300000),
        party(name="Patil Electrical Contractors", gst_type="REGISTERED", gstin=gstin("27", "AGJPP3345R"), phone="9823344556",
              billing_address="Kothrud", city="Pune", pincode="411038", opening_balance=15500),
        party(name="Sai Hardware & Paints", gst_type="REGISTERED", gstin=gstin("27", "BCQPS6621L"), phone="9765432109",
              billing_address="Hadapsar", city="Pune", pincode="411028"),
        party(name="Goa Interiors LLP", gst_type="REGISTERED", gstin=gstin("30", "AAKFG9091C"), state_code="30", phone="9822233344",
              billing_address="Panaji", city="Panaji", pincode="403001"),
        party(name="Karnataka Lighting House", gst_type="REGISTERED", gstin=gstin("29", "AAHFK5567B"), state_code="29",
              phone="9845098450", billing_address="SP Road", city="Bengaluru", pincode="560002"),
        party(name="Hotel Shreyas", gst_type="REGISTERED", gstin=gstin("27", "AABFH2234Q"), phone="9881234567",
              billing_address="Apte Road, Deccan", city="Pune", pincode="411004"),
        party(name="Rahul Deshmukh", gst_type="CONSUMER", phone="9970011223", city="Pune"),
        party(name="Sneha Joshi", gst_type="CONSUMER", phone="9922334455", city="Pune"),
        party(name="Amit Shinde", gst_type="CONSUMER", phone="9850066778", city="Pimpri"),
    ]
    suppliers = [
        party(type="SUPPLIER", name="Havells India Ltd (Distributor)", gst_type="REGISTERED", gstin=gstin("27", "AAACH0351E"),
              phone="02066112233", billing_address="Bhosari MIDC", city="Pune", pincode="411026", opening_balance=-68000),
        party(type="SUPPLIER", name="Polycab Wires Depot", gst_type="REGISTERED", gstin=gstin("27", "AAFCP2311M"),
              phone="9822098220", billing_address="Mundhwa", city="Pune", pincode="411036"),
        party(type="SUPPLIER", name="Anchor Switches Gujarat", gst_type="REGISTERED", gstin=gstin("24", "AACCA4455P"), state_code="24",
              phone="9898012345", billing_address="GIDC Vatva", city="Ahmedabad", pincode="382445"),
        party(type="SUPPLIER", name="Mehta Properties (Landlord)", gst_type="REGISTERED", gstin=gstin("27", "AGBPM7788D"),
              phone="9820098200", city="Pune"),
    ]
    print("parties", len(customers) + len(suppliers))

    # ---------------------------------------------------------------- items
    def item(name, code, hsn, unit, sale, buy, gst, stock, low, cat, mrp=None, typ="GOODS"):
        return api("POST", "/items", {"name": name, "code": code, "hsn_sac": hsn, "unit": unit, "sale_price": sale,
                                      "purchase_price": buy, "gst_rate": gst, "category": cat, "mrp": mrp, "type": typ,
                                      **({"opening_stock": stock, "opening_stock_date": START.isoformat(),
                                          "low_stock_level": low} if typ == "GOODS" else {})})
    goods = [
        item("LED Bulb 9W (Havells)", "LB9", "85395000", "PCS", 95, 62, 12, 400, 80, "Lighting", 140),
        item("LED Bulb 12W (Havells)", "LB12", "85395000", "PCS", 130, 88, 12, 250, 60, "Lighting", 190),
        item("LED Batten 20W", "BT20", "94054200", "PCS", 340, 236, 18, 120, 25, "Lighting", 499),
        item("LED Panel 15W Round", "PN15", "94054200", "PCS", 420, 290, 18, 80, 20, "Lighting", 650),
        item("Ceiling Fan 1200mm (Havells)", "CF1200", "84145110", "PCS", 2450, 1880, 18, 35, 8, "Fans", 3290),
        item("Exhaust Fan 9 inch", "EX9", "84145190", "PCS", 1150, 860, 18, 14, 12, "Fans", 1590),
        item("FR Wire 1.5 sq mm (90 m)", "W15", "85444999", "NOS", 1480, 1150, 18, 60, 15, "Wires", 2100),
        item("FR Wire 2.5 sq mm (90 m)", "W25", "85444999", "NOS", 2380, 1860, 18, 40, 10, "Wires", 3300),
        item("Modular Switch 6A (Anchor)", "SW6", "85365090", "PCS", 38, 24, 18, 900, 150, "Switches", 59),
        item("Modular Socket 16A", "SK16", "85366990", "PCS", 120, 80, 18, 300, 60, "Switches", 175),
        item("MCB 32A Single Pole", "MCB32", "85362090", "PCS", 260, 175, 18, 150, 30, "Protection", 380),
        item("Distribution Board 8 Way", "DB8", "85371000", "PCS", 1350, 980, 18, 16, 14, "Protection", 1890),
        item("PVC Conduit Pipe 25mm (3 m)", "CP25", "39172390", "PCS", 72, 48, 18, 500, 100, "Accessories", 95),
        item("Insulation Tape (pack of 10)", "TAPE", "39191000", "BOX", 150, 98, 18, 70, 15, "Accessories", 220),
    ]
    services = [
        item("Electrical Installation (per point)", "SVC-PT", "998719", "NOS", 350, 0, 18, 0, 0, "Services", typ="SERVICE"),
        item("Site Inspection Visit", "SVC-VIS", "998719", "NOS", 500, 0, 18, 0, 0, "Services", typ="SERVICE"),
    ]
    print("items", len(goods) + len(services))
    opening = {"LB9": 400, "LB12": 250, "BT20": 120, "PN15": 80, "CF1200": 35, "EX9": 14, "W15": 60, "W25": 40, "SW6": 900,
               "SK16": 300, "MCB32": 150, "DB8": 16, "CP25": 500, "TAPE": 70}
    stock = {g["id"]: opening[g["code"]] for g in goods}

    def line(it, qty, rate=None, disc=0):
        return {"item_id": it["id"], "name": it["name"], "qty": qty, "rate": rate if rate is not None else it["sale_price"],
                "gst_rate": it["gst_rate"], "discount_pct": disc}

    def buy_line(it):
        qty = R.choice([50, 100, 150]) if it["sale_price"] < 500 else R.choice([10, 15, 20])
        stock[it["id"]] += qty
        return line(it, qty, it["purchase_price"])

    def sell(it, qty, disc=0):
        """A sale line that never takes stock below 2 (goods); None when there is nothing to sell."""
        if it["id"] in stock:
            qty = min(qty, stock[it["id"]] - 2)
            if qty <= 0:
                return None
            stock[it["id"]] -= qty
        return line(it, qty, disc=disc)

    # ---------------------------------------------------------------- purchases (restock)
    for d in days(9):
        sup = R.choice(suppliers[:3])
        picks = R.sample([g for g in goods if g["code"] not in ("EX9", "DB8")], R.randint(2, 4))  # these two run low
        api("POST", "/vouchers", {"type": "PURCHASE", "date": d.isoformat(), "party_id": sup["id"],
                                  "supplier_invoice_no": f"{sup['name'][:3].upper()}/{R.randint(1000, 9999)}",
                                  "supplier_invoice_date": d.isoformat(),
                                  "lines": [buy_line(it) for it in picks],
                                  **({"fully_paid": True, "payment_mode": "BANK", "payment_account_id": bank["id"]} if R.random() < 0.5 else {})})
    print("purchases done")

    # ---------------------------------------------------------------- sales
    sales = []
    for d in days(85):
        cust = R.choice(customers + [None, None])
        picks = R.sample(goods, R.randint(1, 4))
        lines = [x for x in (sell(it, R.randint(1, 3) if it["sale_price"] > 1000 else R.randint(2, 25), R.choice([0, 0, 0, 5, 10]))
                             for it in picks) if x]
        if not lines:
            continue
        if cust and R.random() < 0.3:
            svc = R.choice(services)
            lines.append(line(svc, R.randint(1, 12)))
        body = {"type": "SALE", "date": d.isoformat(), "lines": lines, "allow_negative": True}
        if cust:
            body["party_id"] = cust["id"]
            body["due_date"] = (d + dt.timedelta(days=15)).isoformat()
            roll = R.random()
            if roll < 0.35:
                body.update(fully_paid=True, payment_mode=R.choice(["UPI", "CASH", "BANK"]),
                            payment_account_id=bank["id"] if R.random() < 0.6 else None)
        else:
            body.update(fully_paid=True, payment_mode=R.choice(["CASH", "UPI"]))
        sales.append(api("POST", "/vouchers", body))
    # one big inter-state order (needs an e-way bill) and one big local order
    sales.append(api("POST", "/vouchers", {"type": "SALE", "date": (TODAY - dt.timedelta(days=3)).isoformat(), "party_id": customers[4]["id"],
                                           "lines": [x for x in (sell(goods[4], 8), sell(goods[7], 6), sell(goods[2], 30)) if x], "allow_negative": True,
                                           "transport": {"vehicle_no": "MH12QW4521", "distance_km": 840}}))
    sales.append(api("POST", "/vouchers", {"type": "SALE", "date": (TODAY - dt.timedelta(days=1)).isoformat(), "party_id": customers[0]["id"],
                                           "lines": [x for x in (sell(goods[6], 10), sell(goods[10], 30), sell(goods[11], 3), line(services[0], 60)) if x],
                                           "due_date": (TODAY + dt.timedelta(days=30)).isoformat(), "allow_negative": True}))
    print("sales", len(sales))

    # ---------------------------------------------------------------- returns, quotations, orders, challan
    s = next(x for x in sales if x.get("party_id"))
    api("POST", "/vouchers", {"type": "SALE_RETURN", "date": min(TODAY, dt.date.fromisoformat(s["date"]) + dt.timedelta(days=4)).isoformat(),
                              "party_id": s["party_id"], "original_voucher_id": s["id"], "reason": "Damaged in transit",
                              "lines": [line(goods[0], 2)]})
    api("POST", "/vouchers", {"type": "PURCHASE_RETURN", "date": (TODAY - dt.timedelta(days=20)).isoformat(), "party_id": suppliers[0]["id"],
                              "reason": "Defective fans", "lines": [line(goods[4], 1, goods[4]["purchase_price"])]})
    api("POST", "/vouchers", {"type": "ESTIMATE", "date": (TODAY - dt.timedelta(days=2)).isoformat(), "party_id": customers[5]["id"],
                              "lines": [line(goods[3], 60), line(goods[9], 80), line(services[0], 140)], "notes": "Hotel renovation — 2nd floor"})
    api("POST", "/vouchers", {"type": "SALE_ORDER", "date": (TODAY - dt.timedelta(days=5)).isoformat(), "party_id": customers[1]["id"],
                              "lines": [line(goods[7], 20), line(goods[11], 4)]})
    api("POST", "/vouchers", {"type": "DELIVERY_CHALLAN", "date": TODAY.isoformat(), "party_id": customers[2]["id"],
                              "lines": [line(goods[12], 100), line(goods[8], 200)]})
    api("POST", "/vouchers", {"type": "PURCHASE_ORDER", "date": (TODAY - dt.timedelta(days=4)).isoformat(), "party_id": suppliers[1]["id"],
                              "lines": [line(goods[6], 30, goods[6]["purchase_price"]), line(goods[7], 20, goods[7]["purchase_price"])]})

    # ---------------------------------------------------------------- expenses
    cats = {c["name"]: c for c in api("GET", "/expenses/categories")}

    def expense(d, cat, name, amount, gst=0, party=None, account=None):
        it = api("POST", "/expenses/items", {"name": f"{name}", "category_id": cats[cat]["id"], "gst_rate": gst}) \
            if name not in exp_items else exp_items[name]
        exp_items[name] = it
        body = {"type": "EXPENSE", "date": d.isoformat(), "expense_category_id": cats[cat]["id"],
                "lines": [{"expense_item_id": it["id"], "name": name, "qty": 1, "rate": amount, "gst_rate": gst}]}
        if party:
            body.update(party_id=party["id"], tax_applicable=bool(gst))
        else:
            body.update(fully_paid=True, payment_account_id=account)
        api("POST", "/vouchers", body)
    exp_items: dict = {}
    month = START.replace(day=1)
    while month <= TODAY:
        d = max(month.replace(day=5), START)
        if d <= TODAY:
            expense(d, "Rent", "Shop rent", 18000, 18, party=suppliers[3])
            expense(min(month.replace(day=12), TODAY), "Electricity", "MSEDCL electricity bill", R.randint(3800, 5200), account=bank["id"])
            expense(min(month.replace(day=20), TODAY), "Telephone & Internet", "Jio Fiber + mobile", 1180, 18, account=bank["id"])
        month = (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    for d in days(10):
        expense(d, "Tea & Refreshments", "Tea and snacks", R.randint(120, 450))
    for d in days(5):
        expense(d, "Transport & Travel", "Tempo hire for delivery", R.randint(600, 1800))
    print("expenses done")

    # ---------------------------------------------------------------- payments
    for d in days(14):
        c = R.choice(customers[:6])
        api("POST", "/payments", {"type": "IN", "date": d.isoformat(), "party_id": c["id"], "amount": R.choice([5000, 10000, 15000, 25000]),
                                  "mode": R.choice(["UPI", "BANK", "CHEQUE"]), "account_id": bank["id"],
                                  "reference": f"UTR{R.randint(10**9, 10**10)}"})
    for d in days(5):
        api("POST", "/payments", {"type": "OUT", "date": d.isoformat(), "party_id": R.choice(suppliers[:3])["id"],
                                  "amount": R.choice([20000, 35000, 50000]), "mode": "BANK", "account_id": bank["id"]})
    api("POST", "/payments", {"type": "OUT", "date": (TODAY - dt.timedelta(days=30)).isoformat(), "party_id": suppliers[3]["id"],
                              "amount": 19440, "tds_amount": 1800, "mode": "BANK", "account_id": bank["id"], "notes": "Rent less TDS 194-I"})
    print("payments done")

    # ---------------------------------------------------------------- staff, attendance, payroll
    emps = [
        api("POST", "/employees", {"name": "Sunil Pawar", "code": "E001", "designation": "Store Manager", "salary_type": "MONTHLY",
                                   "salary": 32000, "pf": True, "pt_monthly": 200, "ot_rate": 150, "joined_on": "2021-04-01",
                                   "phone": "9822110011", "uan": "100988776655", "bank_name": "HDFC Bank", "bank_account": "50100998877",
                                   "bank_ifsc": "HDFC0000123"}),
        api("POST", "/employees", {"name": "Pooja More", "code": "E002", "designation": "Billing Executive", "salary_type": "MONTHLY",
                                   "salary": 18000, "pf": True, "esi": True, "pt_monthly": 200, "joined_on": "2023-06-15", "phone": "9822110022"}),
        api("POST", "/employees", {"name": "Ganesh Jadhav", "code": "E003", "designation": "Electrician", "salary_type": "DAILY",
                                   "salary": 850, "esi": True, "ot_rate": 120, "joined_on": "2024-01-10", "phone": "9822110033"}),
        api("POST", "/employees", {"name": "Imran Shaikh", "code": "E004", "designation": "Delivery & Helper", "salary_type": "DAILY",
                                   "salary": 600, "esi": True, "joined_on": "2025-02-01", "phone": "9822110044"}),
    ]
    last_month_end = TODAY.replace(day=1) - dt.timedelta(days=1)
    marks = []
    d = last_month_end.replace(day=1)
    while d < TODAY:
        if d.weekday() != 6:  # Sundays off
            for e in emps:
                st = R.choices(["P", "P", "P", "P", "P", "P", "P", "HD", "A", "L"], k=1)[0]
                m = {"employee_id": e["id"], "date": d.isoformat(), "status": st}
                if st == "P":
                    m.update(check_in=f"09:{R.randint(0, 40):02d}", check_out=f"{R.choice([19, 20, 21])}:{R.randint(0, 59):02d}",
                             ot_hours=R.choice([0, 0, 0, 1, 2]))
                marks.append(m)
        d += dt.timedelta(days=1)
    for i in range(0, len(marks), 200):
        api("PUT", "/attendance", {"marks": marks[i:i + 200]})
    api("POST", "/payroll/advances", {"employee_id": emps[2]["id"], "date": (TODAY - dt.timedelta(days=12)).isoformat(), "amount": 3000})
    run = api("POST", "/payroll/runs", {"month": last_month_end.strftime("%Y-%m")})
    api("POST", f"/payroll/runs/{run['id']}/finalize", {})
    api("POST", f"/payroll/runs/{run['id']}/pay", {"date": TODAY.replace(day=min(7, TODAY.day)).isoformat(), "account_id": bank["id"], "mode": "BANK"})
    api("POST", "/payroll/runs", {"month": TODAY.strftime("%Y-%m")})  # this month, in progress
    print("staff & payroll done")

    api("POST", "/backups", {})
    print(f"\nDone. Sign in as {EMAIL} / {PASSWORD} and pick '{name}'.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true", help="add another demo company even if one exists")
    try:
        main(ap.parse_args().fresh)
    except (SystemExit, KeyboardInterrupt, Exception):
        if CREATED:
            from sqlalchemy import delete

            with SessionLocal() as db:
                db.execute(delete(Business).where(Business.id.in_(CREATED)))
                db.commit()
            print("Stopped — the half-filled demo company was removed.")
        raise
