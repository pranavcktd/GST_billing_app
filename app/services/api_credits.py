"""API credits — paid government-connected actions (e-invoice IRN, e-way bill, cancellations, filing-status sync).

Every plan includes a monthly allowance (`api_quota` on the plan: credits per calendar month, for the whole
subscriber account). Beyond it, prepaid credit packs bought from Plan & billing are used. The super admin sets:
    api_credit_costs  — credits per action   (Admin → GST config → API credits)
    api_credit_packs  — pack size → price ₹  (excl. GST)
Only real filings are charged: the provider's test mode and the local sandbox are free, and a rejected or failed
call is never charged (credits are recorded only after the action succeeds).
"""

import datetime as dt

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ApiCredit
from . import config_store as C

ACTIONS = {"EINVOICE": "e-Invoice (IRN)", "EWAYBILL": "e-Way bill", "CANCEL": "Cancellation (IRN / e-way bill)",
           "FILING_SYNC": "GST filing status (one year)",
           "WHATSAPP": "WhatsApp message (beyond the plan's monthly messages)"}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def cost(action: str) -> int:
    return int((C.get("api_credit_costs") or {}).get(action, 1))


def packs() -> dict[int, float]:
    return {int(k): float(v) for k, v in sorted((C.get("api_credit_packs") or {}).items(), key=lambda kv: int(kv[0]))}


def _month_start() -> dt.datetime:
    now = dt.datetime.now(IST)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def status(db: Session, account_id: str, allowance: int | None) -> dict:
    used = db.scalar(select(func.coalesce(func.sum(ApiCredit.units), 0)).where(
        ApiCredit.account_id == account_id, ApiCredit.kind == "USE", ApiCredit.created_at >= _month_start())) or 0
    added = db.scalar(select(func.coalesce(func.sum(ApiCredit.delta), 0)).where(
        ApiCredit.account_id == account_id, ApiCredit.kind.in_(["PACK", "ADMIN"]))) or 0
    spent = db.scalar(select(func.coalesce(func.sum(ApiCredit.from_pack), 0)).where(
        ApiCredit.account_id == account_id, ApiCredit.kind == "USE")) or 0
    allowance = int(allowance or 0)
    return {"allowance": allowance, "used_this_month": int(used), "free_left": max(allowance - int(used), 0),
            "balance": int(added) - int(spent)}


def ensure(db: Session, account_id: str, allowance: int | None, action: str, units: int = 1) -> None:
    """Refuse before calling the provider when the account cannot pay for the action."""
    need = cost(action) * units
    s = status(db, account_id, allowance)
    if need > s["free_left"] + s["balance"]:
        raise HTTPException(402, {"code": "CREDITS", "plan": "CREDITS",
                                  "message": f"Not enough API credits: {ACTIONS.get(action, action)} needs {need}, "
                                             f"you have {s['free_left']} left this month and {s['balance']} prepaid. "
                                             "Buy a credit pack in Plan & billing."})


def charge(db: Session, account_id: str, allowance: int | None, action: str, business_id: str | None, ref: str | None,
           user: str | None, units: int = 1) -> None:
    """Record a successful paid action: the month's allowance first, then the prepaid balance."""
    need = cost(action) * units
    if need <= 0:
        return
    s = status(db, account_id, allowance)
    from_pack = max(need - s["free_left"], 0)
    db.add(ApiCredit(account_id=account_id, business_id=business_id, kind="USE", action=action, units=need,
                     delta=-need, from_pack=from_pack, ref=ref, note=user))


def add(db: Session, account_id: str, credits: int, kind: str = "PACK", note: str | None = None) -> None:
    db.add(ApiCredit(account_id=account_id, kind=kind, delta=credits, units=0, from_pack=0, note=note))
