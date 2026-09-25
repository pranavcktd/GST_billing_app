import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import BCtx
from ..gst.constants import LoanTxnType
from ..models import Loan, LoanTxn
from ..schemas import LoanIn, LoanOut, LoanTxnIn, LoanTxnOut
from ..services.accounts import resolve_account

router = APIRouter(prefix="/loans", tags=["loans"])
ZERO = Decimal("0")


def outstanding(loan: Loan, as_of: dt.date | None = None) -> Decimal:
    bal = loan.opening_balance or ZERO
    for t in loan.txns:
        if as_of and t.date > as_of:
            continue
        if t.type == LoanTxnType.DISBURSEMENT:
            bal += t.principal
        elif t.type == LoanTxnType.EMI:
            bal -= t.principal
    return bal


def _get(ctx: BCtx, loan_id: str) -> Loan:
    loan = ctx.db.get(Loan, loan_id)
    if not loan or loan.business_id != ctx.bid:
        raise HTTPException(404, "Loan not found")
    return loan


def _out(loan: Loan) -> LoanOut:
    o = LoanOut.model_validate(loan)
    o.outstanding = outstanding(loan)
    return o


def statement(loan: Loan, date_from: dt.date | None = None, date_to: dt.date | None = None) -> dict:
    opening = loan.opening_balance or ZERO
    rows, running = [], None
    for t in sorted(loan.txns, key=lambda t: (t.date, t.created_at)):
        change = t.principal if t.type == LoanTxnType.DISBURSEMENT else -t.principal if t.type == LoanTxnType.EMI else ZERO
        if date_from and t.date < date_from:
            opening += change
            continue
        if date_to and t.date > date_to:
            continue
        running = (running if running is not None else opening) + change
        rows.append(dict(id=t.id, date=t.date, type=t.type.value, principal=t.principal, interest=t.interest,
                         paid=t.principal + t.interest if t.type != LoanTxnType.DISBURSEMENT else ZERO,
                         received=t.principal if t.type == LoanTxnType.DISBURSEMENT else ZERO,
                         balance=running, note=t.note))
    return dict(opening=opening, closing=running if running is not None else opening, entries=rows)


@router.get("", response_model=list[LoanOut])
def list_loans(ctx: BCtx):
    ctx.need("cashbank", "view")
    loans = ctx.db.scalars(select(Loan).options(selectinload(Loan.txns))
                           .where(Loan.business_id == ctx.bid).order_by(Loan.name)).all()
    return [_out(l) for l in loans]


@router.post("", response_model=LoanOut, status_code=201)
def create_loan(data: LoanIn, ctx: BCtx):
    ctx.need("cashbank", "create")
    loan = Loan(business_id=ctx.bid, **data.model_dump())
    ctx.db.add(loan)
    ctx.db.commit()
    return _out(loan)


@router.put("/{loan_id}", response_model=LoanOut)
def update_loan(loan_id: str, data: LoanIn, ctx: BCtx):
    ctx.need("cashbank", "edit")
    loan = _get(ctx, loan_id)
    for k, v in data.model_dump().items():
        setattr(loan, k, v)
    ctx.db.commit()
    return _out(loan)


@router.delete("/{loan_id}", status_code=204)
def delete_loan(loan_id: str, ctx: BCtx):
    ctx.need("cashbank", "delete")
    loan = _get(ctx, loan_id)
    if loan.txns:
        loan.is_active = False
    else:
        ctx.db.delete(loan)
    ctx.db.commit()


@router.get("/{loan_id}")
def get_loan(loan_id: str, ctx: BCtx, date_from: dt.date | None = None, date_to: dt.date | None = None):
    ctx.need("cashbank", "view")
    loan = _get(ctx, loan_id)
    return {"loan": _out(loan).model_dump(mode="json"), **statement(loan, date_from, date_to)}


@router.post("/{loan_id}/txns", response_model=LoanTxnOut, status_code=201)
def add_txn(loan_id: str, data: LoanTxnIn, ctx: BCtx):
    ctx.need("cashbank", "create")
    loan = _get(ctx, loan_id)
    acc = resolve_account(ctx.db, ctx.bid, data.account_id)
    if data.type == LoanTxnType.EMI and data.principal > outstanding(loan):
        raise HTTPException(400, "Principal repaid is more than the loan outstanding")
    t = LoanTxn(loan_id=loan.id, business_id=ctx.bid, **{**data.model_dump(), "account_id": acc.id})
    ctx.db.add(t)
    ctx.db.commit()
    return t


@router.delete("/{loan_id}/txns/{txn_id}", status_code=204)
def delete_txn(loan_id: str, txn_id: str, ctx: BCtx):
    ctx.need("cashbank", "delete")
    loan = _get(ctx, loan_id)
    t = ctx.db.get(LoanTxn, txn_id)
    if not t or t.loan_id != loan.id:
        raise HTTPException(404, "Entry not found")
    ctx.db.delete(t)
    ctx.db.commit()
