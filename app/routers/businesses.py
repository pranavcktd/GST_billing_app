from fastapi import APIRouter

from ..deps import DB, BCtx, CurrentUser
from ..gst.constants import Role
from ..models import Business, Membership
from ..schemas import BusinessIn, BusinessOut, ModulesIn, MyBusinessOut
from ..security import encrypt_secret
from ..services.accounts import cash_account
from ..services.godowns import default_godown
from ..services.plans import business_plan, check_business_limit, require_feature, start_trial
from .expenses import seed_categories

router = APIRouter(prefix="/businesses", tags=["business"])


def apply_business(biz: Business, data: BusinessIn) -> None:
    values = data.model_dump(exclude={"einvoice_password", "ewb_password"})
    if values.get("einvoice_applicable") is None:
        values.pop("einvoice_applicable", None)  # not sent: keep what the business chose
    for k, v in values.items():
        setattr(biz, k, v)
    if data.einvoice_password:
        biz.einvoice_password_enc = encrypt_secret(data.einvoice_password)
    if data.ewb_password:
        biz.ewb_password_enc = encrypt_secret(data.ewb_password)


def _check_theme(db, business_id: str | None, data: BusinessIn) -> None:
    """Custom themes / accent colours need a plan with custom_themes; the classic look is always free."""
    ps = data.print_settings
    if ps.theme != "classic" or ps.accent.lower() != "#1f65bb":
        if business_id:
            require_feature(db, business_id, "custom_themes")
        else:
            ps.theme, ps.accent = "classic", "#1f65bb"


def _fill_registration_date(db, biz: Business) -> dict | None:
    """Portal details of the business's GSTIN; also remembers the registration date when it is not known yet."""
    from ..services import gstin_verify as G

    d = G.portal_details(db, biz.gstin) if biz.gstin else None
    if d and not biz.gst_registration_date:
        biz.gst_registration_date = G.parse_date(d.get("registration_date"))
        if biz.gst_registration_date:
            db.commit()
    return d


def business_out(db, biz: Business) -> BusinessOut:
    portal = _fill_registration_date(db, biz)
    out = BusinessOut.model_validate(biz)
    out.gst_portal = portal
    out.einvoice_password_set = bool(biz.einvoice_password_enc)
    out.ewb_password_set = bool(biz.ewb_password_enc)
    p = business_plan(db, biz.id)
    out.plan = {"code": p["code"], "name": p["name"], "watermark": p["watermark"],
                "custom_themes": p["custom_themes"], "barcode": p["barcode"], "einvoice": p["einvoice"],
                "gst_json": p["gst_json"], "gstr2b": p["gstr2b"], "audit_view": p["audit_view"],
                "custom_roles": p["custom_roles"], "tally": p["tally"]}
    return out


@router.post("", response_model=MyBusinessOut, status_code=201)
def create_business(data: BusinessIn, db: DB, user: CurrentUser):
    start_trial(db, user.id)  # first business of a new account starts its trial
    check_business_limit(db, user.id)
    biz = Business(owner_id=user.id)
    apply_business(biz, data)
    _check_theme(db, None, data)
    db.add(biz)
    db.flush()
    db.add(Membership(user_id=user.id, business_id=biz.id, role=Role.OWNER))
    cash_account(db, biz.id)
    seed_categories(db, biz.id)
    default_godown(db, biz.id)
    db.commit()
    return MyBusinessOut(id=biz.id, name=biz.name, gstin=biz.gstin, gst_type=biz.gst_type, role=Role.OWNER,
                         modules=biz.modules, entity_type=biz.entity_type or "PROPRIETORSHIP")


@router.get("/current", response_model=BusinessOut)
def get_current(ctx: BCtx):
    return business_out(ctx.db, ctx.business)


@router.put("/current", response_model=BusinessOut)
def update_current(data: BusinessIn, ctx: BCtx):
    ctx.need("settings", "edit")
    _check_theme(ctx.db, ctx.bid, data)
    apply_business(ctx.business, data)
    ctx.db.commit()
    return business_out(ctx.db, ctx.business)


@router.put("/current/modules", response_model=BusinessOut)
def update_modules(data: ModulesIn, ctx: BCtx):
    """Hide menus the business does not use (e.g. stock and godowns for a services business). Data is never removed."""
    ctx.need("settings", "edit")
    ctx.business.modules = {"mode": data.mode, "hidden": sorted(set(data.hidden))}
    ctx.db.commit()
    return business_out(ctx.db, ctx.business)
