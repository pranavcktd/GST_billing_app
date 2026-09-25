"""Cash & bank accounts, transfers, cheques, capital and tax (challan) payments."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import selectinload

from ..deps import BCtx
from ..gst.constants import PaymentMode
from ..models import (
    Account,
    AccountTransfer,
    CapitalEntry,
    LoanTxn,
    Payment,
    PaymentAllocation,
    TaxPayment,
)
from ..schemas import (
    AccountIn,
    AccountOut,
    CapitalIn,
    CapitalOut,
    PaymentOut,
    TaxPaymentIn,
    TaxPaymentOut,
    TransferIn,
    TransferOut,
)
from ..services.accounts import account_balances, cash_account, resolve_account, statement
from ..services.payments import payment_out

router = APIRouter(tags=["cash & bank"])


def _owned(ctx: BCtx, model, obj_id: str, label: str):
    obj = ctx.db.get(model, obj_id)
    if not obj or obj.business_id != ctx.bid:
        raise HTTPException(404, f"{label} not found")
    return obj


# ---------------------------------------------------------------- accounts
@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(ctx: BCtx):
    """Everyone who records money needs the account list; balances only for cash & bank viewers."""
    if not any(ctx.can(m, a) for m, a in (("cashbank", "view"), ("payments_in", "create"), ("payments_out", "create"),
                                           ("sales", "create"), ("purchases", "create"), ("expenses", "create"))):
        ctx.need("cashbank", "view")
    cash_account(ctx.db, ctx.bid)
    ctx.db.commit()
    balances = account_balances(ctx.db, ctx.bid) if ctx.can("cashbank") else {}
    out = []
    for a in ctx.db.scalars(select(Account).where(Account.business_id == ctx.bid)
                            .order_by(Account.is_default_cash.desc(), Account.name)):
        o = AccountOut.model_validate(a)
        o.balance = balances.get(a.id, Decimal("0"))
        out.append(o)
    return out


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(data: AccountIn, ctx: BCtx):
    ctx.need("cashbank", "create")
    a = Account(business_id=ctx.bid, **data.model_dump())
    ctx.db.add(a)
    ctx.db.commit()
    o = AccountOut.model_validate(a)
    o.balance = a.opening_balance
    return o


@router.put("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: str, data: AccountIn, ctx: BCtx):
    ctx.need("cashbank", "edit")
    a = _owned(ctx, Account, account_id, "Account")
    for k, v in data.model_dump().items():
        if k == "type" and a.is_default_cash:
            continue
        setattr(a, k, v)
    ctx.db.commit()
    o = AccountOut.model_validate(a)
    o.balance = account_balances(ctx.db, ctx.bid).get(a.id, Decimal("0"))
    return o


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: str, ctx: BCtx):
    ctx.need("cashbank", "delete")
    a = _owned(ctx, Account, account_id, "Account")
    if a.is_default_cash:
        raise HTTPException(400, "Cash in hand cannot be deleted")
    used = any(ctx.db.scalar(select(m.id).where(col == a.id).limit(1)) for m, col in (
        (Payment, Payment.account_id), (CapitalEntry, CapitalEntry.account_id), (LoanTxn, LoanTxn.account_id),
        (TaxPayment, TaxPayment.account_id)))
    used = used or ctx.db.scalar(select(AccountTransfer.id).where(
        or_(AccountTransfer.from_account_id == a.id, AccountTransfer.to_account_id == a.id)).limit(1))
    if used:
        a.is_active = False
    else:
        ctx.db.delete(a)
    ctx.db.commit()


@router.get("/accounts/{account_id}/statement")
def account_statement(account_id: str, ctx: BCtx, date_from: dt.date | None = None, date_to: dt.date | None = None):
    ctx.need("cashbank", "view")
    a = _owned(ctx, Account, account_id, "Account")
    return {"account": AccountOut.model_validate(a).model_dump(mode="json"), **statement(ctx.db, a, date_from, date_to)}


# ---------------------------------------------------------------- transfers
@router.get("/transfers", response_model=list[TransferOut])
def list_transfers(ctx: BCtx):
    ctx.need("cashbank", "view")
    return ctx.db.scalars(select(AccountTransfer).where(AccountTransfer.business_id == ctx.bid)
                          .order_by(AccountTransfer.date.desc())).all()


@router.post("/transfers", response_model=TransferOut, status_code=201)
def create_transfer(data: TransferIn, ctx: BCtx):
    ctx.need("cashbank", "create")
    if data.from_account_id == data.to_account_id:
        raise HTTPException(400, "Choose two different accounts")
    _owned(ctx, Account, data.from_account_id, "Account")
    _owned(ctx, Account, data.to_account_id, "Account")
    t = AccountTransfer(business_id=ctx.bid, **data.model_dump())
    ctx.db.add(t)
    ctx.db.commit()
    return t


@router.delete("/transfers/{transfer_id}", status_code=204)
def delete_transfer(transfer_id: str, ctx: BCtx):
    ctx.need("cashbank", "delete")
    ctx.db.delete(_owned(ctx, AccountTransfer, transfer_id, "Transfer"))
    ctx.db.commit()


# ---------------------------------------------------------------- cheques
@router.get("/cheques", response_model=list[PaymentOut])
def list_cheques(ctx: BCtx, status: str | None = None):
    ctx.need("cashbank", "view")
    q = (select(Payment)
         .options(selectinload(Payment.allocations).selectinload(PaymentAllocation.voucher),
                  selectinload(Payment.party), selectinload(Payment.account))
         .where(Payment.business_id == ctx.bid, Payment.mode == PaymentMode.CHEQUE)
         .order_by(Payment.date.desc()))
    if status:
        q = q.where(Payment.cheque_status == status)
    return [payment_out(p) for p in ctx.db.scalars(q)]


class ChequeAction(BaseModel):
    action: Literal["clear", "bounce", "reopen"]
    date: dt.date | None = None
    account_id: str | None = None


@router.post("/cheques/{payment_id}", response_model=PaymentOut)
def cheque_action(payment_id: str, data: ChequeAction, ctx: BCtx):
    ctx.need("cashbank", "edit")
    p = _owned(ctx, Payment, payment_id, "Cheque")
    if p.mode != PaymentMode.CHEQUE:
        raise HTTPException(400, "This payment is not a cheque")
    if data.action == "clear":
        p.cheque_status = "CLEARED"
        p.cleared_on = data.date or dt.date.today()
        if data.account_id:
            p.account_id = resolve_account(ctx.db, ctx.bid, data.account_id).id
    elif data.action == "bounce":
        # the payment no longer settles anything; the bills are due again
        p.cheque_status = "BOUNCED"
        p.cleared_on = None
        ctx.db.execute(delete(PaymentAllocation).where(PaymentAllocation.payment_id == p.id))
    else:
        if p.cheque_status == "BOUNCED":
            raise HTTPException(400, "A bounced cheque cannot be reopened — record a new payment")
        p.cheque_status, p.cleared_on = "OPEN", None
    ctx.db.commit()
    ctx.db.refresh(p)
    return payment_out(p)


# ---------------------------------------------------------------- capital
@router.get("/capital", response_model=list[CapitalOut])
def list_capital(ctx: BCtx):
    ctx.need("cashbank", "view")
    return ctx.db.scalars(select(CapitalEntry).where(CapitalEntry.business_id == ctx.bid)
                          .order_by(CapitalEntry.date.desc())).all()


@router.post("/capital", response_model=CapitalOut, status_code=201)
def create_capital(data: CapitalIn, ctx: BCtx):
    ctx.need("cashbank", "create")
    acc = resolve_account(ctx.db, ctx.bid, data.account_id)
    c = CapitalEntry(business_id=ctx.bid, **{**data.model_dump(), "account_id": acc.id})
    ctx.db.add(c)
    ctx.db.commit()
    return c


@router.delete("/capital/{entry_id}", status_code=204)
def delete_capital(entry_id: str, ctx: BCtx):
    ctx.need("cashbank", "delete")
    ctx.db.delete(_owned(ctx, CapitalEntry, entry_id, "Entry"))
    ctx.db.commit()


# ---------------------------------------------------------------- tax payments
@router.get("/tax-payments", response_model=list[TaxPaymentOut])
def list_tax_payments(ctx: BCtx):
    ctx.need("cashbank", "view")
    return ctx.db.scalars(select(TaxPayment).where(TaxPayment.business_id == ctx.bid)
                          .order_by(TaxPayment.date.desc())).all()


@router.post("/tax-payments", response_model=TaxPaymentOut, status_code=201)
def create_tax_payment(data: TaxPaymentIn, ctx: BCtx):
    ctx.need("cashbank", "create")
    acc = resolve_account(ctx.db, ctx.bid, data.account_id)
    t = TaxPayment(business_id=ctx.bid, **{**data.model_dump(), "account_id": acc.id})
    ctx.db.add(t)
    ctx.db.commit()
    return t


@router.delete("/tax-payments/{payment_id}", status_code=204)
def delete_tax_payment(payment_id: str, ctx: BCtx):
    ctx.need("cashbank", "delete")
    ctx.db.delete(_owned(ctx, TaxPayment, payment_id, "Tax payment"))
    ctx.db.commit()
