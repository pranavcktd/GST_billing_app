"""Staff, attendance and payroll (see services/payroll.py for the rules)."""

import datetime as dt
import re
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select

from ..deps import BCtx
from ..gst.constants import ExpenseKind, PaymentMode, TaxPaymentType
from ..models import (
    Attendance,
    Employee,
    ExpenseCategory,
    PayrollLine,
    PayrollRun,
    SalaryAdvance,
    TaxPayment,
    User,
)
from ..schemas import VoucherIn
from ..services import payroll as P
from ..services.accounts import resolve_account
from ..services.platform_audit import log
from ..services.vouchers import save_voucher

router = APIRouter(tags=["payroll"])
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
HM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _emp(ctx: BCtx, emp_id: str) -> Employee:
    e = ctx.db.get(Employee, emp_id)
    if not e or e.business_id != ctx.bid:
        raise HTTPException(404, "Employee not found")
    return e


def _month(m: str) -> str:
    if not MONTH.match(m or ""):
        raise HTTPException(422, "Month like 2026-10")
    return m


# ================================================================ employees
class EmployeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=200)
    designation: str | None = Field(None, max_length=80)
    department: str | None = Field(None, max_length=80)
    joined_on: dt.date | None = None
    left_on: dt.date | None = None
    is_active: bool = True
    salary_type: Literal["MONTHLY", "DAILY"] = "MONTHLY"
    salary: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    basic_pct: Decimal = Field(Decimal("50"), ge=0, le=100)
    ot_rate: Decimal = Field(Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    pf: bool = False
    esi: bool = False
    pt_monthly: Decimal = Field(Decimal("0"), ge=0, max_digits=8, decimal_places=2)
    tds_monthly: Decimal = Field(Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    uan: str | None = Field(None, max_length=20)
    esic_no: str | None = Field(None, max_length=20)
    pan: str | None = Field(None, max_length=10)
    bank_name: str | None = Field(None, max_length=120)
    bank_account: str | None = Field(None, max_length=40)
    bank_ifsc: str | None = Field(None, max_length=11)
    user_id: str | None = None
    notes: str | None = Field(None, max_length=1000)

    @field_validator("*", mode="before")
    @classmethod
    def _blank(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


def _emp_out(ctx: BCtx, e: Employee, full: bool) -> dict:
    out = {k: getattr(e, k) for k in ("id", "code", "name", "phone", "email", "designation", "department", "joined_on",
                                      "left_on", "is_active", "user_id")}
    if full:  # salary details only for people who may see payroll
        out.update({k: getattr(e, k) for k in ("salary_type", "salary", "basic_pct", "ot_rate", "pf", "esi", "pt_monthly",
                                               "tds_monthly", "uan", "esic_no", "pan", "bank_name", "bank_account", "bank_ifsc",
                                               "notes")})
        out["advance_due"] = float(P.outstanding_advance(ctx.db, e.id))
    return out


@router.get("/employees")
def list_employees(ctx: BCtx, include_inactive: bool = False):
    ctx.need("attendance", "view")
    q = select(Employee).where(Employee.business_id == ctx.bid).order_by(Employee.name)
    if not include_inactive:
        q = q.where(Employee.is_active.is_(True))
    full = ctx.can("payroll", "view")
    return [_emp_out(ctx, e, full) for e in ctx.db.scalars(q)]


def _check_user(ctx: BCtx, user_id: str | None, emp_id: str | None = None) -> None:
    if not user_id:
        return
    from ..models import Membership

    if not ctx.db.scalar(select(Membership.id).where(Membership.user_id == user_id, Membership.business_id == ctx.bid)):
        raise HTTPException(422, "That login does not belong to this business")
    clash = ctx.db.scalar(select(Employee.id).where(Employee.business_id == ctx.bid, Employee.user_id == user_id,
                                                    Employee.id != (emp_id or "")))
    if clash:
        raise HTTPException(409, "That login is already linked to another employee")


@router.post("/employees", status_code=201)
def create_employee(data: EmployeeIn, ctx: BCtx):
    ctx.need("payroll", "create")
    _check_user(ctx, data.user_id)
    e = Employee(business_id=ctx.bid, **data.model_dump())
    ctx.db.add(e)
    ctx.db.commit()
    return _emp_out(ctx, e, True)


@router.put("/employees/{emp_id}")
def update_employee(emp_id: str, data: EmployeeIn, ctx: BCtx):
    ctx.need("payroll", "edit")
    e = _emp(ctx, emp_id)
    _check_user(ctx, data.user_id, e.id)
    for k, v in data.model_dump().items():
        setattr(e, k, v)
    ctx.db.commit()
    return _emp_out(ctx, e, True)


@router.delete("/employees/{emp_id}", status_code=204)
def delete_employee(emp_id: str, ctx: BCtx):
    """Removes an employee who has no payroll history; otherwise mark them as left instead."""
    ctx.need("payroll", "delete")
    e = _emp(ctx, emp_id)
    if ctx.db.scalar(select(PayrollLine.id).where(PayrollLine.employee_id == e.id).limit(1)) or \
            ctx.db.scalar(select(SalaryAdvance.id).where(SalaryAdvance.employee_id == e.id).limit(1)):
        raise HTTPException(400, "This employee has salary records — set a leaving date and untick 'Active' instead")
    ctx.db.delete(e)
    ctx.db.commit()


# ================================================================ settings
class SettingsIn(BaseModel):
    weekly_off: list[int] = Field(default_factory=lambda: [6], max_length=7)
    holidays: list[dict] = Field(default_factory=list, max_length=100)
    unmarked: Literal["PRESENT", "ABSENT"] = "PRESENT"
    basis: Literal["CALENDAR", "FIXED_30", "WORKING"] = "CALENDAR"


@router.get("/payroll/settings")
def get_settings(ctx: BCtx):
    ctx.need("attendance", "view")
    return P.settings(ctx.business)


@router.put("/payroll/settings")
def put_settings(data: SettingsIn, ctx: BCtx):
    ctx.need("payroll", "edit")
    if any(d not in range(7) for d in data.weekly_off):
        raise HTTPException(422, "Weekly off days are 0 (Monday) to 6 (Sunday)")
    holidays = []
    for h in data.holidays:
        try:
            d = dt.date.fromisoformat(str(h.get("date")))
        except ValueError:
            raise HTTPException(422, f"Holiday date '{h.get('date')}' is not valid") from None
        holidays.append({"date": d.isoformat(), "name": str(h.get("name") or "Holiday")[:60]})
    ctx.business.payroll_settings = {**data.model_dump(), "holidays": sorted(holidays, key=lambda x: x["date"])}
    ctx.db.commit()
    return P.settings(ctx.business)


# ================================================================ attendance
@router.get("/attendance")
def month_attendance(ctx: BCtx, month: str):
    """Grid for the month: every active employee × every day, marked or default (week off / holiday / default)."""
    ctx.need("attendance", "view")
    month = _month(month)
    days = P.month_days(month)
    s = P.settings(ctx.business)
    marks = P.attendance_map(ctx.db, ctx.bid, month)
    emps = [e for e in ctx.db.scalars(select(Employee).where(Employee.business_id == ctx.bid).order_by(Employee.name))
            if (e.is_active or (e.left_on and e.left_on >= days[0])) and not (e.joined_on and e.joined_on > days[-1])]
    rows = []
    for e in emps:
        m = marks.get(e.id, {})
        cells = {}
        for d in days:
            if (e.joined_on and d < e.joined_on) or (e.left_on and d > e.left_on):
                cells[d.isoformat()] = None
                continue
            a = m.get(d)
            cells[d.isoformat()] = (dict(status=a.status, marked=True, check_in=a.check_in, check_out=a.check_out,
                                         ot_hours=float(a.ot_hours or 0), note=a.note, source=a.source)
                                    if a else dict(status=P.default_status(d, s), marked=False))
        counts = P.day_counts(e, month, m, s)
        rows.append(dict(id=e.id, name=e.name, designation=e.designation, code=e.code, days=cells, counts=counts))
    return {"month": month, "days": [d.isoformat() for d in days], "employees": rows, "settings": s, "statuses": P.STATUSES,
            "today": dt.datetime.now(IST).date().isoformat()}


class Mark(BaseModel):
    employee_id: str
    date: dt.date
    status: Literal["P", "A", "HD", "L", "WO", "H"] | None = None  # None = clear (back to the default)
    check_in: str | None = None
    check_out: str | None = None
    ot_hours: Decimal = Field(Decimal("0"), ge=0, le=24)
    note: str | None = Field(None, max_length=200)


class MarksIn(BaseModel):
    marks: list[Mark] = Field(min_length=1, max_length=2000)


def _locked(ctx: BCtx, d: dt.date) -> None:
    run = ctx.db.scalar(select(PayrollRun).where(PayrollRun.business_id == ctx.bid, PayrollRun.month == d.strftime("%Y-%m")))
    if run and run.status != "DRAFT":
        raise HTTPException(400, f"Payroll for {d:%b %Y} is finalised — reopen it to change attendance")


@router.put("/attendance")
def save_marks(data: MarksIn, ctx: BCtx):
    ctx.need("attendance", "edit")
    for m in data.marks:
        _emp(ctx, m.employee_id)
        _locked(ctx, m.date)
        for t in (m.check_in, m.check_out):
            if t and not HM.match(t):
                raise HTTPException(422, "Times like 09:30")
        row = ctx.db.scalar(select(Attendance).where(Attendance.employee_id == m.employee_id, Attendance.date == m.date))
        if m.status is None:
            if row:
                ctx.db.delete(row)
            continue
        if row is None:
            row = Attendance(business_id=ctx.bid, employee_id=m.employee_id, date=m.date)
            ctx.db.add(row)
        row.status, row.check_in, row.check_out = m.status, m.check_in, m.check_out
        row.ot_hours, row.note, row.source, row.marked_by = m.ot_hours, m.note, "MANUAL", ctx.user.name
    ctx.db.commit()
    return {"saved": len(data.marks)}


# ---- staff mark their own attendance (linked login)
def _me(ctx: BCtx) -> Employee:
    e = ctx.db.scalar(select(Employee).where(Employee.business_id == ctx.bid, Employee.user_id == ctx.user.id,
                                             Employee.is_active.is_(True)))
    if not e:
        raise HTTPException(404, "Your login is not linked to an employee of this business")
    return e


@router.get("/attendance/me")
def my_day(ctx: BCtx):
    e = ctx.db.scalar(select(Employee).where(Employee.business_id == ctx.bid, Employee.user_id == ctx.user.id,
                                             Employee.is_active.is_(True)))
    if not e:
        return {"linked": False}
    today = dt.datetime.now(IST).date()
    a = ctx.db.scalar(select(Attendance).where(Attendance.employee_id == e.id, Attendance.date == today))
    return {"linked": True, "name": e.name, "date": today, "status": a.status if a else None,
            "check_in": a.check_in if a else None, "check_out": a.check_out if a else None}


@router.post("/attendance/me/{action}")
def my_check(action: Literal["check-in", "check-out"], ctx: BCtx, request: Request):
    e = _me(ctx)
    now = dt.datetime.now(IST)
    _locked(ctx, now.date())
    a = ctx.db.scalar(select(Attendance).where(Attendance.employee_id == e.id, Attendance.date == now.date()))
    if action == "check-in":
        if a and a.check_in:
            raise HTTPException(400, f"Already checked in at {a.check_in}")
        if a is None:
            a = Attendance(business_id=ctx.bid, employee_id=e.id, date=now.date())
            ctx.db.add(a)
        a.status, a.check_in, a.source, a.marked_by = "P", now.strftime("%H:%M"), "SELF", ctx.user.name
    else:
        if not a or not a.check_in:
            raise HTTPException(400, "Check in first")
        a.check_out = now.strftime("%H:%M")
    from ..services.platform_audit import client_ip
    a.note = (a.note or f"from {client_ip(request) or 'unknown'}")[:200]
    ctx.db.commit()
    return {"status": a.status, "check_in": a.check_in, "check_out": a.check_out}


# ================================================================ payroll runs
def _run(ctx: BCtx, run_id: str) -> PayrollRun:
    r = ctx.db.get(PayrollRun, run_id)
    if not r or r.business_id != ctx.bid:
        raise HTTPException(404, "Payroll not found")
    return r


def _run_out(r: PayrollRun) -> dict:
    return dict(id=r.id, month=r.month, status=r.status, paid_on=r.paid_on, voucher_id=r.voucher_id,
                statutory_paid=r.statutory_paid or {}, totals=P.totals(r), employees=len(r.lines),
                lines=[dict(id=l.id, employee_id=l.employee_id, name=l.name, data=l.data, bonus=float(l.bonus),
                            other_additions=float(l.other_additions), advance_recovery=float(l.advance_recovery),
                            other_deductions=float(l.other_deductions), gross=float(l.gross), deductions=float(l.deductions),
                            net=float(l.net), note=l.note) for l in r.lines])


@router.get("/payroll/runs")
def list_runs(ctx: BCtx):
    ctx.need("payroll", "view")
    runs = ctx.db.scalars(select(PayrollRun).where(PayrollRun.business_id == ctx.bid).order_by(PayrollRun.month.desc())).all()
    return [dict(id=r.id, month=r.month, status=r.status, paid_on=r.paid_on, employees=len(r.lines), totals=P.totals(r)) for r in runs]


class RunIn(BaseModel):
    month: str


@router.post("/payroll/runs", status_code=201)
def make_run(data: RunIn, ctx: BCtx):
    """Prepare (or rebuild) a month's payroll from attendance."""
    ctx.need("payroll", "create")
    try:
        run = P.generate(ctx.db, ctx.business, _month(data.month), ctx.user.name)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    ctx.db.commit()
    return _run_out(run)


@router.get("/payroll/runs/{run_id}")
def get_run(run_id: str, ctx: BCtx):
    ctx.need("payroll", "view")
    return _run_out(_run(ctx, run_id))


class LineIn(BaseModel):
    bonus: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    other_additions: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    advance_recovery: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    other_deductions: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    note: str | None = Field(None, max_length=200)


@router.put("/payroll/runs/{run_id}/lines/{line_id}")
def edit_line(run_id: str, line_id: str, data: LineIn, ctx: BCtx):
    ctx.need("payroll", "edit")
    run = _run(ctx, run_id)
    if run.status != "DRAFT":
        raise HTTPException(400, "Finalised payroll cannot be changed — reopen it first")
    line = next((l for l in run.lines if l.id == line_id), None)
    if line is None:
        raise HTTPException(404, "Line not found")
    due = P.outstanding_advance(ctx.db, line.employee_id, exclude_run=run.id)
    if data.advance_recovery > due:
        raise HTTPException(400, f"Only ₹{due:,.2f} of advance is outstanding for {line.name}")
    for k, v in data.model_dump().items():
        setattr(line, k, v)
    P.recompute(ctx.db, ctx.business, run, line)
    if line.net < 0:
        ctx.db.rollback()
        raise HTTPException(400, "Deductions are more than the pay for this month")
    ctx.db.commit()
    return _run_out(run)


@router.post("/payroll/runs/{run_id}/finalize")
def finalize_run(run_id: str, ctx: BCtx, request: Request):
    return _run_action(run_id, "finalize", ctx, request)


@router.post("/payroll/runs/{run_id}/reopen")
def reopen_run(run_id: str, ctx: BCtx, request: Request):
    return _run_action(run_id, "reopen", ctx, request)


def _run_action(run_id: str, action: str, ctx: BCtx, request: Request):
    ctx.need("payroll", "edit")
    run = _run(ctx, run_id)
    if action == "finalize":
        if run.status != "DRAFT":
            raise HTTPException(400, "Already finalised")
        P.generate(ctx.db, ctx.business, run.month, ctx.user.name)  # latest attendance
        run.status = "FINAL"
    else:
        if run.status == "PAID":
            raise HTTPException(400, "Salaries are already paid — delete the salary expense entry first to reopen")
        run.status = "DRAFT"
    log(ctx.db, ctx.user, "PAYROLL", "payroll", f"{action.capitalize()}d payroll {run.month}", entity_id=run.id,
        business_id=ctx.bid, request=request)
    ctx.db.commit()
    return _run_out(run)


@router.delete("/payroll/runs/{run_id}", status_code=204)
def delete_run(run_id: str, ctx: BCtx):
    ctx.need("payroll", "delete")
    run = _run(ctx, run_id)
    if run.status != "DRAFT":
        raise HTTPException(400, "Only a draft payroll can be deleted")
    ctx.db.delete(run)
    ctx.db.commit()


# ---- paying: posts expense entries so Cash & Bank and the P&L include salaries
def _category(ctx: BCtx, name: str) -> str:
    c = ctx.db.scalar(select(ExpenseCategory).where(ExpenseCategory.business_id == ctx.bid, ExpenseCategory.name == name))
    if c is None:
        c = ExpenseCategory(business_id=ctx.bid, name=name, kind=ExpenseKind.INDIRECT)
        ctx.db.add(c)
        ctx.db.flush()
    return c.id


def _post_expense(ctx: BCtx, category: str, date: dt.date, lines: list[tuple[str, Decimal]], account_id: str | None,
                  mode: PaymentMode, notes: str) -> str:
    resolve_account(ctx.db, ctx.bid, account_id)
    v = save_voucher(ctx, VoucherIn.model_validate({
        "type": "EXPENSE", "date": date, "expense_category_id": _category(ctx, category), "tax_applicable": False,
        "notes": notes, "fully_paid": True, "payment_mode": mode, "payment_account_id": account_id,
        "lines": [{"name": n[:200], "qty": 1, "rate": a, "gst_rate": 0} for n, a in lines if a > 0]}))
    return v.id


class PayIn(BaseModel):
    date: dt.date
    account_id: str | None = None
    mode: PaymentMode = PaymentMode.BANK


@router.post("/payroll/runs/{run_id}/pay")
def pay_run(run_id: str, data: PayIn, ctx: BCtx, request: Request):
    """Pay net salaries: one 'Salary' expense entry (a line per employee) paid from the chosen cash / bank account."""
    ctx.need("payroll", "edit")
    run = _run(ctx, run_id)
    if run.status != "FINAL":
        raise HTTPException(400, "Finalise the payroll before paying it" if run.status == "DRAFT" else "Already paid")
    month = dt.date(int(run.month[:4]), int(run.month[5:7]), 1).strftime("%b %Y")
    lines = [(f"Salary — {l.name} ({month})", l.net) for l in run.lines]
    if not any(a > 0 for _, a in lines):
        raise HTTPException(400, "Nothing to pay")
    run.voucher_id = _post_expense(ctx, "Salary", data.date, lines, data.account_id, data.mode, f"Payroll {run.month}")
    run.status, run.paid_on = "PAID", data.date
    log(ctx.db, ctx.user, "PAYROLL", "payroll", f"Paid salaries {run.month}: ₹{sum(a for _, a in lines):,.2f}",
        entity_id=run.id, business_id=ctx.bid, request=request)
    ctx.db.commit()
    return _run_out(run)


class StatutoryIn(BaseModel):
    kind: Literal["PF", "ESI", "PT", "TDS"]
    date: dt.date
    account_id: str | None = None
    mode: PaymentMode = PaymentMode.BANK
    reference: str | None = Field(None, max_length=100)


@router.post("/payroll/runs/{run_id}/statutory")
def pay_statutory(run_id: str, data: StatutoryIn, ctx: BCtx):
    """Record depositing the month's EPF / ESI / professional tax / TDS (employee + employer share)."""
    ctx.need("payroll", "edit")
    run = _run(ctx, run_id)
    if run.status == "DRAFT":
        raise HTTPException(400, "Finalise the payroll first")
    done = dict(run.statutory_paid or {})
    if data.kind in done:
        raise HTTPException(400, f"{data.kind} for {run.month} is already recorded")
    t = P.totals(run)
    amount = Decimal(str({"PF": t["pf_employee"] + t["pf_employer"], "ESI": t["esi_employee"] + t["esi_employer"],
                          "PT": t["pt"], "TDS": t["tds"]}[data.kind]))
    if amount <= 0:
        raise HTTPException(400, f"No {data.kind} for {run.month}")
    note = f"{data.kind} for {run.month}" + (f" · {data.reference}" if data.reference else "")
    if data.kind == "TDS":
        acc = resolve_account(ctx.db, ctx.bid, data.account_id)
        tp = TaxPayment(business_id=ctx.bid, date=data.date, type=TaxPaymentType.TDS, amount=amount, account_id=acc.id,
                        reference=data.reference, period=run.month, note=f"TDS on salaries {run.month}")
        ctx.db.add(tp)
        ctx.db.flush()
        ref_id = tp.id
    else:
        cat = {"PF": "EPF / ESI contributions", "ESI": "EPF / ESI contributions", "PT": "Professional tax"}[data.kind]
        ref_id = _post_expense(ctx, cat, data.date, [(note, amount)], data.account_id, data.mode, note)
    done[data.kind] = {"date": data.date.isoformat(), "amount": float(amount), "reference": data.reference, "ref_id": ref_id}
    run.statutory_paid = done
    ctx.db.commit()
    return _run_out(run)


# ================================================================ advances
class AdvanceIn(BaseModel):
    employee_id: str
    date: dt.date
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    account_id: str | None = None
    mode: PaymentMode = PaymentMode.CASH
    note: str | None = Field(None, max_length=200)


@router.get("/payroll/advances")
def list_advances(ctx: BCtx):
    ctx.need("payroll", "view")
    rows = ctx.db.execute(select(SalaryAdvance, Employee.name).join(Employee, Employee.id == SalaryAdvance.employee_id)
                          .where(SalaryAdvance.business_id == ctx.bid).order_by(SalaryAdvance.date.desc())).all()
    return [dict(id=a.id, employee_id=a.employee_id, name=n, date=a.date, amount=float(a.amount), note=a.note,
                 voucher_id=a.voucher_id) for a, n in rows]


@router.post("/payroll/advances", status_code=201)
def give_advance(data: AdvanceIn, ctx: BCtx):
    """Money given ahead of salary: paid from cash / bank now (Salary expense), recovered in a later payroll."""
    ctx.need("payroll", "create")
    e = _emp(ctx, data.employee_id)
    vid = _post_expense(ctx, "Salary", data.date, [(f"Salary advance — {e.name}", data.amount)], data.account_id, data.mode,
                        data.note or f"Advance to {e.name}")
    a = SalaryAdvance(business_id=ctx.bid, employee_id=e.id, date=data.date, amount=data.amount, note=data.note,
                      voucher_id=vid, created_by=ctx.user.name)
    ctx.db.add(a)
    ctx.db.commit()
    return {"id": a.id, "advance_due": float(P.outstanding_advance(ctx.db, e.id))}


@router.delete("/payroll/advances/{adv_id}", status_code=204)
def delete_advance(adv_id: str, ctx: BCtx):
    ctx.need("payroll", "delete")
    a = ctx.db.get(SalaryAdvance, adv_id)
    if not a or a.business_id != ctx.bid:
        raise HTTPException(404, "Advance not found")
    if P.outstanding_advance(ctx.db, a.employee_id) < a.amount:
        raise HTTPException(400, "Part of this advance is already recovered in a payroll")
    if a.voucher_id:
        from ..models import Voucher
        from ..services.vouchers import cancel_voucher

        v = ctx.db.get(Voucher, a.voucher_id)
        if v and not v.cancelled:
            cancel_voucher(ctx, v)
    ctx.db.delete(a)
    ctx.db.commit()


# helper for the staff linking dropdown
@router.get("/employees/logins")
def linkable_logins(ctx: BCtx):
    ctx.need("payroll", "edit")
    from ..models import Membership

    rows = ctx.db.execute(select(User.id, User.name, User.email).join(Membership, Membership.user_id == User.id)
                          .where(Membership.business_id == ctx.bid, Membership.status == "ACTIVE")).all()
    return [dict(id=i, name=n, email=e) for i, n, e in rows]
