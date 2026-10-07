"""Staff attendance and monthly payroll.

Attendance status per employee per day: P present, A absent, HD half day, L paid leave, WO weekly off, H holiday.
Days that were not marked follow the business's payroll settings:
    weekly_off      weekdays off (0 = Monday … 6 = Sunday); default Sunday
    holidays        [{"date": "2026-10-20", "name": "Diwali"}]
    unmarked        "PRESENT" (only mark absences — the usual way in small businesses) or "ABSENT"
    basis           how a monthly salary is divided:
                    CALENDAR (days in the month, default) · FIXED_30 (always 30) · WORKING (days minus weekly offs
                    and holidays)

Monthly salary: weekly offs, holidays and paid leave are paid; absence and half of a half day are deducted.
Daily wage: paid for days worked (present + half of half days) only.
Overtime: hours × the employee's overtime rate.

Statutory deductions (rates from the platform configuration, effective-dated):
    EPF  — employee and employer share of the EPF wage (basic pay = salary × basic %, up to the wage ceiling)
    ESI  — employee and employer share of gross pay, while gross pay is within the ESI limit
    PT / TDS — the fixed monthly amounts set on the employee
"""

import calendar
import datetime as dt
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Attendance, Business, Employee, PayrollLine, PayrollRun, SalaryAdvance
from . import config_store as C

ZERO = Decimal("0")
STATUSES = {"P": "Present", "A": "Absent", "HD": "Half day", "L": "Paid leave", "WO": "Weekly off", "H": "Holiday"}
DEFAULT_SETTINGS = {"weekly_off": [6], "holidays": [], "unmarked": "PRESENT", "basis": "CALENDAR"}


def r2(x: Decimal) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rupee(x: Decimal) -> Decimal:
    """Statutory amounts are paid in whole rupees."""
    return Decimal(x).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def settings(biz: Business) -> dict:
    return {**DEFAULT_SETTINGS, **(biz.payroll_settings or {})}


def month_days(month: str) -> list[dt.date]:
    y, m = int(month[:4]), int(month[5:7])
    return [dt.date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]


def default_status(d: dt.date, s: dict) -> str:
    holidays = {h["date"] for h in s.get("holidays") or []}
    if d.isoformat() in holidays:
        return "H"
    if d.weekday() in (s.get("weekly_off") or []):
        return "WO"
    return "P" if s.get("unmarked", "PRESENT") == "PRESENT" else "A"


def attendance_map(db: Session, business_id: str, month: str) -> dict[str, dict[dt.date, Attendance]]:
    days = month_days(month)
    rows = db.scalars(select(Attendance).where(Attendance.business_id == business_id, Attendance.date >= days[0],
                                               Attendance.date <= days[-1])).all()
    out: dict[str, dict[dt.date, Attendance]] = {}
    for a in rows:
        out.setdefault(a.employee_id, {})[a.date] = a
    return out


def day_counts(emp: Employee, month: str, marks: dict[dt.date, Attendance], s: dict) -> dict:
    """Days of the month by status, only while the employee was employed."""
    counts = {k: 0 for k in STATUSES}
    ot = ZERO
    employed = 0
    for d in month_days(month):
        if (emp.joined_on and d < emp.joined_on) or (emp.left_on and d > emp.left_on):
            continue
        employed += 1
        a = marks.get(d)
        counts[a.status if a else default_status(d, s)] += 1
        if a:
            ot += a.ot_hours or ZERO
    return {**counts, "employed_days": employed, "ot_hours": float(ot)}


def outstanding_advance(db: Session, employee_id: str, exclude_run: str | None = None) -> Decimal:
    given = db.scalar(select(func.coalesce(func.sum(SalaryAdvance.amount), 0)).where(SalaryAdvance.employee_id == employee_id)) or ZERO
    q = (select(func.coalesce(func.sum(PayrollLine.advance_recovery), 0)).join(PayrollRun, PayrollRun.id == PayrollLine.run_id)
         .where(PayrollLine.employee_id == employee_id))
    if exclude_run:
        q = q.where(PayrollRun.id != exclude_run)
    recovered = db.scalar(q) or ZERO
    return max(Decimal(given) - Decimal(recovered), ZERO)


def compute(emp: Employee, month: str, counts: dict, s: dict, line: PayrollLine | None = None) -> dict:
    """Earnings and deductions of one employee for the month (manual additions/deductions come from `line`)."""
    on = dt.date(int(month[:4]), int(month[5:7]), 1)
    days_in_month = len(month_days(month))
    salary = Decimal(emp.salary or 0)
    worked = Decimal(counts["P"]) + Decimal(counts["HD"]) / 2
    if emp.salary_type == "DAILY":
        per_day = salary
        earned = per_day * worked
        paid_days = worked
    else:
        paid_days = worked + counts["L"] + counts["WO"] + counts["H"]
        basis = s.get("basis", "CALENDAR")
        if basis == "FIXED_30":
            per_day = salary / 30
            earned = min(salary, per_day * paid_days)
        elif basis == "WORKING":
            working = max(days_in_month - counts["WO"] - counts["H"], 1)  # working days of the month
            per_day = salary / working
            earned = min(salary, per_day * (worked + counts["L"]))
        else:
            per_day = salary / days_in_month
            earned = per_day * paid_days
    earned = r2(earned)
    ot_pay = r2(Decimal(str(counts["ot_hours"])) * Decimal(emp.ot_rate or 0))
    bonus = Decimal((line.bonus if line else 0) or 0)
    other_add = Decimal((line.other_additions if line else 0) or 0)
    gross = earned + ot_pay + bonus + other_add

    pf_emp = pf_er = esi_emp = esi_er = ZERO
    pf_wage = ZERO
    if emp.pf:
        pf_wage = r2(earned * Decimal(emp.basic_pct or 0) / 100)
        pf_wage = min(pf_wage, C.get("pf_wage_ceiling", on))
        pf_emp = rupee(pf_wage * C.get("pf_employee_rate", on) / 100)
        pf_er = rupee(pf_wage * C.get("pf_employer_rate", on) / 100)
    if emp.esi and gross > 0 and gross <= C.get("esi_wage_limit", on):
        esi_emp = (gross * C.get("esi_employee_rate", on) / 100).quantize(Decimal("1"), rounding=ROUND_CEILING)
        esi_er = (gross * C.get("esi_employer_rate", on) / 100).quantize(Decimal("1"), rounding=ROUND_CEILING)
    pt = Decimal(emp.pt_monthly or 0) if gross > 0 else ZERO
    tds = Decimal(emp.tds_monthly or 0) if gross > 0 else ZERO
    adv = Decimal((line.advance_recovery if line else 0) or 0)
    other_ded = Decimal((line.other_deductions if line else 0) or 0)
    deductions = pf_emp + esi_emp + pt + tds + adv + other_ded
    return dict(
        days_in_month=days_in_month, employed_days=counts["employed_days"], present=counts["P"], absent=counts["A"],
        half_days=counts["HD"], leave=counts["L"], weekly_off=counts["WO"], holidays=counts["H"], ot_hours=counts["ot_hours"],
        salary_type=emp.salary_type, rate=float(salary), per_day=float(r2(per_day)), paid_days=float(paid_days),
        earned=float(earned), ot_pay=float(ot_pay), pf_wage=float(pf_wage),
        pf_employee=float(pf_emp), pf_employer=float(pf_er), esi_employee=float(esi_emp), esi_employer=float(esi_er),
        pt=float(pt), tds=float(tds), designation=emp.designation, code=emp.code, uan=emp.uan, esic_no=emp.esic_no,
        bank=" ".join(x for x in (emp.bank_name, emp.bank_account, emp.bank_ifsc) if x) or None,
        _gross=gross, _deductions=deductions,
    )


def apply(line: PayrollLine, data: dict) -> None:
    gross, ded = data.pop("_gross"), data.pop("_deductions")
    line.data = data
    line.gross, line.deductions = r2(gross), r2(ded)
    line.net = r2(gross - ded)


def generate(db: Session, biz: Business, month: str, by: str) -> PayrollRun:
    """Create (or rebuild) the month's draft from attendance; manual additions/deductions are kept."""
    run = db.scalar(select(PayrollRun).where(PayrollRun.business_id == biz.id, PayrollRun.month == month))
    if run is not None and run.status != "DRAFT":
        raise ValueError("This month's payroll is already finalised — reopen it to make changes")
    days = month_days(month)
    if run is None:
        run = PayrollRun(business_id=biz.id, month=month, created_by=by)
        db.add(run)
        db.flush()
    s = settings(biz)
    marks = attendance_map(db, biz.id, month)
    emps = db.scalars(select(Employee).where(Employee.business_id == biz.id)).all()
    keep = {l.employee_id: l for l in run.lines}
    for emp in emps:
        if (emp.joined_on and emp.joined_on > days[-1]) or (emp.left_on and emp.left_on < days[0]):
            continue
        if not emp.is_active and not (emp.left_on and emp.left_on >= days[0]):
            continue
        line = keep.pop(emp.id, None)
        if line is None:
            line = PayrollLine(employee_id=emp.id, name=emp.name)
            run.lines.append(line)
            out = outstanding_advance(db, emp.id, exclude_run=run.id)
            line.advance_recovery = out  # suggested: recover the whole outstanding advance (editable)
        line.name = emp.name
        apply(line, compute(emp, month, day_counts(emp, month, marks.get(emp.id, {}), s), s, line))
        if line.net < 0 and line.advance_recovery > 0:  # never recover more than the pay
            line.advance_recovery = max(r2(line.advance_recovery + line.net), ZERO)
            apply(line, compute(emp, month, day_counts(emp, month, marks.get(emp.id, {}), s), s, line))
    for gone in keep.values():
        run.lines.remove(gone)
    db.flush()
    return run


def recompute(db: Session, biz: Business, run: PayrollRun, line: PayrollLine) -> None:
    emp = db.get(Employee, line.employee_id)
    s = settings(biz)
    marks = attendance_map(db, biz.id, run.month)
    apply(line, compute(emp, run.month, day_counts(emp, run.month, marks.get(emp.id, {}), s), s, line))


def totals(run: PayrollRun) -> dict:
    t = {k: ZERO for k in ("gross", "deductions", "net", "pf_employee", "pf_employer", "esi_employee", "esi_employer",
                           "pt", "tds", "advance_recovery")}
    for l in run.lines:
        t["gross"] += l.gross
        t["deductions"] += l.deductions
        t["net"] += l.net
        t["advance_recovery"] += l.advance_recovery
        for k in ("pf_employee", "pf_employer", "esi_employee", "esi_employer", "pt", "tds"):
            t[k] += Decimal(str(l.data.get(k, 0)))
    return {k: float(v) for k, v in t.items()}
