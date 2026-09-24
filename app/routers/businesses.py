from fastapi import APIRouter

from ..deps import DB, MANAGERS, BCtx, CurrentUser
from ..gst.constants import Role
from ..models import Business, Membership
from ..schemas import BusinessIn, BusinessOut, MyBusinessOut
from ..services.accounts import cash_account
from .expenses import seed_categories

router = APIRouter(prefix="/businesses", tags=["business"])


@router.post("", response_model=MyBusinessOut, status_code=201)
def create_business(data: BusinessIn, db: DB, user: CurrentUser):
    biz = Business(**data.model_dump())
    db.add(biz)
    db.flush()
    db.add(Membership(user_id=user.id, business_id=biz.id, role=Role.OWNER))
    cash_account(db, biz.id)
    seed_categories(db, biz.id)
    db.commit()
    return MyBusinessOut(id=biz.id, name=biz.name, gstin=biz.gstin, gst_type=biz.gst_type, role=Role.OWNER)


@router.get("/current", response_model=BusinessOut)
def get_current(ctx: BCtx):
    return ctx.business


@router.put("/current", response_model=BusinessOut)
def update_current(data: BusinessIn, ctx: BCtx):
    ctx.require(*MANAGERS)
    for k, v in data.model_dump().items():
        setattr(ctx.business, k, v)
    ctx.db.commit()
    return ctx.business
