import datetime as dt

from fastapi import APIRouter, HTTPException
from sqlalchemy import or_, select

from ..deps import WRITERS, BCtx
from ..gst.constants import PartyType
from ..models import Party, Payment, Voucher
from ..schemas import PartyIn, PartyOut
from ..services.ledger import party_balances, party_ledger

router = APIRouter(prefix="/parties", tags=["parties"])


def _get(ctx: BCtx, party_id: str) -> Party:
    p = ctx.db.get(Party, party_id)
    if not p or p.business_id != ctx.bid:
        raise HTTPException(404, "Party not found")
    return p


def _out(p: Party, balance) -> PartyOut:
    o = PartyOut.model_validate(p)
    o.balance = balance
    return o


@router.get("", response_model=list[PartyOut])
def list_parties(ctx: BCtx, search: str | None = None, type: PartyType | None = None, include_inactive: bool = False):
    q = select(Party).where(Party.business_id == ctx.bid).order_by(Party.name)
    if not include_inactive:
        q = q.where(Party.is_active.is_(True))
    if type in (PartyType.CUSTOMER, PartyType.SUPPLIER):
        q = q.where(Party.type.in_([type, PartyType.BOTH]))
    if search:
        like = f"%{search}%"
        q = q.where(or_(Party.name.ilike(like), Party.phone.ilike(like), Party.gstin.ilike(like)))
    parties = ctx.db.scalars(q).all()
    balances = party_balances(ctx.db, ctx.bid)
    return [_out(p, balances.get(p.id, 0)) for p in parties]


@router.post("", response_model=PartyOut, status_code=201)
def create_party(data: PartyIn, ctx: BCtx):
    ctx.require(*WRITERS)
    p = Party(business_id=ctx.bid, **data.model_dump())
    ctx.db.add(p)
    ctx.db.commit()
    return _out(p, p.opening_balance)


@router.get("/{party_id}", response_model=PartyOut)
def get_party(party_id: str, ctx: BCtx):
    p = _get(ctx, party_id)
    return _out(p, party_balances(ctx.db, ctx.bid, [p.id]).get(p.id, 0))


@router.put("/{party_id}", response_model=PartyOut)
def update_party(party_id: str, data: PartyIn, ctx: BCtx):
    ctx.require(*WRITERS)
    p = _get(ctx, party_id)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    ctx.db.commit()
    return _out(p, party_balances(ctx.db, ctx.bid, [p.id]).get(p.id, 0))


@router.delete("/{party_id}", status_code=204)
def delete_party(party_id: str, ctx: BCtx):
    """Parties with transactions are deactivated instead of deleted, to keep records intact."""
    ctx.require(*WRITERS)
    p = _get(ctx, party_id)
    used = ctx.db.scalar(select(Voucher.id).where(Voucher.party_id == p.id).limit(1)) or ctx.db.scalar(
        select(Payment.id).where(Payment.party_id == p.id).limit(1)
    )
    if used:
        p.is_active = False
    else:
        ctx.db.delete(p)
    ctx.db.commit()


@router.get("/{party_id}/ledger")
def get_ledger(party_id: str, ctx: BCtx, date_from: dt.date | None = None, date_to: dt.date | None = None):
    p = _get(ctx, party_id)
    return {"party": _out(p, 0).model_dump(mode="json"), **party_ledger(ctx.db, p, date_from, date_to)}
