"""Global search (Ctrl + K): parties, items, documents and payments of the current business.

Only what the user's role may view is searched. Pages and actions are matched in the browser.
"""

from fastapi import APIRouter
from sqlalchemy import or_, select

from ..deps import BCtx
from ..gst.constants import PaymentType, VoucherType
from ..models import Item, Party, Payment, Voucher
from ..permissions import voucher_module

router = APIRouter(tags=["search"])
LIMIT = 6


@router.get("/search")
def search(ctx: BCtx, q: str = ""):
    q = q.strip()
    out: dict[str, list] = {"parties": [], "items": [], "documents": [], "payments": []}
    if len(q) < 2:
        return out
    like = f"%{q}%"
    db = ctx.db

    if ctx.can("parties"):
        rows = db.scalars(select(Party).where(
            Party.business_id == ctx.bid,
            or_(Party.name.ilike(like), Party.gstin.ilike(like), Party.phone.ilike(like), Party.email.ilike(like)),
        ).order_by(Party.name).limit(LIMIT))
        out["parties"] = [dict(id=p.id, name=p.name, gstin=p.gstin, phone=p.phone, type=p.type.value) for p in rows]

    if ctx.can("items"):
        rows = db.scalars(select(Item).where(
            Item.business_id == ctx.bid,
            or_(Item.name.ilike(like), Item.code.ilike(like), Item.hsn_sac.ilike(f"{q}%")),
        ).order_by(Item.name).limit(LIMIT))
        out["items"] = [dict(id=i.id, name=i.name, code=i.code, hsn=i.hsn_sac, type=i.type.value) for i in rows]

    types = [t for t in VoucherType if ctx.can(voucher_module(t))]
    if types:
        rows = db.scalars(select(Voucher).where(
            Voucher.business_id == ctx.bid, Voucher.type.in_(types),
            or_(Voucher.number.ilike(like), Voucher.party_name.ilike(like), Voucher.supplier_invoice_no.ilike(like)),
        ).order_by(Voucher.date.desc(), Voucher.created_at.desc()).limit(LIMIT))
        out["documents"] = [dict(id=v.id, type=v.type.value, number=v.number, date=v.date, party_name=v.party_name,
                                 total=float(v.grand_total), cancelled=v.cancelled) for v in rows]

    ptypes = [t for t, m in ((PaymentType.IN, "payments_in"), (PaymentType.OUT, "payments_out")) if ctx.can(m)]
    if ptypes:
        rows = db.execute(select(Payment, Party.name).outerjoin(Party, Party.id == Payment.party_id).where(
            Payment.business_id == ctx.bid, Payment.type.in_(ptypes),
            or_(Payment.number.ilike(like), Payment.reference.ilike(like), Party.name.ilike(like)),
        ).order_by(Payment.date.desc()).limit(LIMIT)).all()
        out["payments"] = [dict(id=p.id, type=p.type.value, number=p.number, date=p.date, party_name=name,
                                amount=float(p.amount)) for p, name in rows]
    return out
