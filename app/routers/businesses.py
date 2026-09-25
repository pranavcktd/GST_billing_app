from fastapi import APIRouter

from ..deps import DB, MANAGERS, BCtx, CurrentUser
from ..gst.constants import Role
from ..models import Business, Membership
from ..schemas import BusinessIn, BusinessOut, MyBusinessOut
from ..security import encrypt_secret
from ..services.accounts import cash_account
from ..services.godowns import default_godown
from ..services.plans import start_trial
from .expenses import seed_categories

router = APIRouter(prefix="/businesses", tags=["business"])


def apply_business(biz: Business, data: BusinessIn) -> None:
    values = data.model_dump(exclude={"einvoice_password"})
    for k, v in values.items():
        setattr(biz, k, v)
    if data.einvoice_password:
        biz.einvoice_password_enc = encrypt_secret(data.einvoice_password)


def business_out(biz: Business) -> BusinessOut:
    out = BusinessOut.model_validate(biz)
    out.einvoice_password_set = bool(biz.einvoice_password_enc)
    return out


@router.post("", response_model=MyBusinessOut, status_code=201)
def create_business(data: BusinessIn, db: DB, user: CurrentUser):
    biz = Business()
    apply_business(biz, data)
    db.add(biz)
    db.flush()
    db.add(Membership(user_id=user.id, business_id=biz.id, role=Role.OWNER))
    cash_account(db, biz.id)
    seed_categories(db, biz.id)
    default_godown(db, biz.id)
    start_trial(db, biz.id)
    db.commit()
    return MyBusinessOut(id=biz.id, name=biz.name, gstin=biz.gstin, gst_type=biz.gst_type, role=Role.OWNER)


@router.get("/current", response_model=BusinessOut)
def get_current(ctx: BCtx):
    return business_out(ctx.business)


@router.put("/current", response_model=BusinessOut)
def update_current(data: BusinessIn, ctx: BCtx):
    ctx.require(*MANAGERS)
    apply_business(ctx.business, data)
    ctx.db.commit()
    return business_out(ctx.business)
