"""Staff, attendance and payroll: calculation, advances, paying (expense entries), statutory deposits, self check-in."""

from tests.test_api_flow import make_business, signup
from tests.test_modules import post
from tests.test_rbac import staff

M = "2026-10"  # 31 days; Sundays 4, 11, 18, 25


def cash(client, h):
    return next(a for a in client.get("/api/accounts", headers=h).json() if a["is_default_cash"])["balance"]


def test_payroll_month(client):
    h = make_business(client, signup(client))
    ravi = post(client, h, "/api/employees", {"name": "Ravi", "designation": "Sales", "salary_type": "MONTHLY", "salary": 31000,
                                              "basic_pct": 50, "pf": True, "esi": True, "pt_monthly": 200, "ot_rate": 150,
                                              "joined_on": "2025-01-01", "uan": "100200300400"})
    sita = post(client, h, "/api/employees", {"name": "Sita", "salary_type": "DAILY", "salary": 600, "esi": True})
    assert ravi["advance_due"] == 0

    # Ravi: absent 6th & 7th, half day 8th, paid leave 9th, 3 hours overtime on the 10th; Sita: nothing marked
    marks = [{"employee_id": ravi["id"], "date": d, "status": s} for d, s in
             (("2026-10-06", "A"), ("2026-10-07", "A"), ("2026-10-08", "HD"), ("2026-10-09", "L"))]
    marks.append({"employee_id": ravi["id"], "date": "2026-10-10", "status": "P", "check_in": "09:30", "check_out": "21:00", "ot_hours": 3})
    assert client.put("/api/attendance", headers=h, json={"marks": marks}).status_code == 200
    grid = client.get("/api/attendance", headers=h, params={"month": M}).json()
    r = next(e for e in grid["employees"] if e["id"] == ravi["id"])
    assert r["days"]["2026-10-04"] == {"status": "WO", "marked": False} and r["days"]["2026-10-06"]["status"] == "A"
    assert r["counts"]["P"] == 23 and r["counts"]["WO"] == 4

    # advance of ₹5,000 (paid from cash now, recovered in payroll)
    before = cash(client, h)
    post(client, h, "/api/payroll/advances", {"employee_id": ravi["id"], "date": "2026-10-05", "amount": 5000})
    assert cash(client, h) == before - 5000

    run = post(client, h, "/api/payroll/runs", {"month": M})
    L = {l["name"]: l for l in run["lines"]}
    rv, st = L["Ravi"], L["Sita"]
    assert rv["data"]["paid_days"] == 28.5 and rv["data"]["earned"] == 28500 and rv["data"]["ot_pay"] == 450
    assert rv["data"]["pf_employee"] == 1710 and rv["data"]["pf_employer"] == 1710 and rv["data"]["esi_employee"] == 0  # gross above ESI limit
    assert rv["advance_recovery"] == 5000 and rv["gross"] == 28950 and rv["net"] == 28950 - 1710 - 200 - 5000
    assert st["data"]["present"] == 27 and st["gross"] == 16200 and st["data"]["esi_employee"] == 122 and st["data"]["esi_employer"] == 527

    # bonus; recovering more advance than given is refused
    run = client.put(f"/api/payroll/runs/{run['id']}/lines/{rv['id']}", headers=h,
                     json={"bonus": 1000, "advance_recovery": 5000}).json()
    assert next(l for l in run["lines"] if l["name"] == "Ravi")["net"] == 29950 - 1710 - 200 - 5000
    assert client.put(f"/api/payroll/runs/{run['id']}/lines/{rv['id']}", headers=h, json={"advance_recovery": 6000}).status_code == 400
    assert client.post(f"/api/payroll/runs/{run['id']}/pay", headers=h, json={"date": "2026-11-01"}).status_code == 400  # draft

    # finalise: attendance of the month is locked
    post(client, h, f"/api/payroll/runs/{run['id']}/finalize", {}, 200)
    assert client.put("/api/attendance", headers=h, json={"marks": [{"employee_id": sita["id"], "date": "2026-10-15", "status": "A"}]}).status_code == 400

    # pay: one Salary expense entry from cash
    before = cash(client, h)
    paid = post(client, h, f"/api/payroll/runs/{run['id']}/pay", {"date": "2026-11-01", "mode": "CASH"}, 200)
    net = paid["totals"]["net"]
    assert paid["status"] == "PAID" and net == (29950 - 1710 - 200 - 5000) + 16200 - 122
    assert cash(client, h) == before - net
    v = client.get(f"/api/vouchers/{paid['voucher_id']}", headers=h).json()
    assert v["type"] == "EXPENSE" and v["grand_total"] == net and len(v["lines"]) == 2
    assert client.post(f"/api/payroll/runs/{run['id']}/reopen", headers=h).status_code == 400
    # the advance is now recovered
    assert next(e for e in client.get("/api/employees", headers=h).json() if e["id"] == ravi["id"])["advance_due"] == 0

    # statutory deposits: EPF (employee + employer), ESI, PT; TDS none
    s = post(client, h, f"/api/payroll/runs/{run['id']}/statutory", {"kind": "PF", "date": "2026-11-14", "reference": "TRRN1"}, 200)
    assert s["statutory_paid"]["PF"]["amount"] == 3420
    assert post(client, h, f"/api/payroll/runs/{run['id']}/statutory", {"kind": "ESI", "date": "2026-11-14"}, 200)["statutory_paid"]["ESI"]["amount"] == 649
    assert client.post(f"/api/payroll/runs/{run['id']}/statutory", headers=h, json={"kind": "PF", "date": "2026-11-14"}).status_code == 400
    assert client.post(f"/api/payroll/runs/{run['id']}/statutory", headers=h, json={"kind": "TDS", "date": "2026-11-14"}).status_code == 400

    # the month is unique; an employee with salary records can't be deleted
    assert client.delete(f"/api/employees/{ravi['id']}", headers=h).status_code == 400


def test_self_check_in_and_permissions(client):
    h = make_business(client, signup(client))
    op = staff(client, h, "op@x.in", "BILLING")
    mgr = staff(client, h, "mgr@x.in", "MANAGER")
    op_user = client.get("/api/auth/me", headers=op).json()["user"]["id"]
    e = post(client, h, "/api/employees", {"name": "Operator", "salary": 15000, "user_id": op_user})
    assert client.post("/api/employees", headers=h, json={"name": "X", "user_id": op_user}).status_code == 409  # one login, one employee

    assert client.get("/api/attendance/me", headers=op).json()["linked"]
    r = post(client, op, "/api/attendance/me/check-in", {}, 200)
    assert r["status"] == "P" and r["check_in"]
    assert client.post("/api/attendance/me/check-in", headers=op).status_code == 400
    assert post(client, op, "/api/attendance/me/check-out", {}, 200)["check_out"]

    # billing staff: no staff register or payroll; the manager sees attendance but not salaries
    assert client.get("/api/payroll/runs", headers=op).status_code == 403
    assert client.get("/api/attendance", headers=op, params={"month": M}).status_code == 403
    emps = client.get("/api/employees", headers=mgr).json()
    assert emps[0]["name"] == "Operator" and "salary" not in emps[0]
    assert client.get("/api/payroll/runs", headers=mgr).status_code == 403
    assert client.get("/api/employees", headers=h).json()[0]["salary"] == 15000
    assert client.get("/api/attendance/me", headers=mgr).json() == {"linked": False}

    # settings: weekly offs and holidays decide the default for unmarked days
    s = client.put("/api/payroll/settings", headers=h, json={"weekly_off": [6, 5], "holidays": [{"date": "2026-10-20", "name": "Diwali"}],
                                                             "unmarked": "PRESENT", "basis": "FIXED_30"}).json()
    assert s["holidays"][0]["name"] == "Diwali"
    grid = client.get("/api/attendance", headers=h, params={"month": M}).json()
    days = grid["employees"][0]["days"]
    assert days["2026-10-20"]["status"] == "H" and days["2026-10-03"]["status"] == "WO"  # Saturday
    assert client.put("/api/payroll/settings", headers=mgr, json=s).status_code == 403
