import datetime as dt

from fastapi import APIRouter

from ..deps import BCtx
from ..gst.constants import VoucherType
from ..services import reports
from ..services.backup import maybe_auto_backup

router = APIRouter(prefix="/reports", tags=["reports"])

SALES = [VoucherType.SALE, VoucherType.SALE_RETURN]
PURCHASES = [VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN]


@router.get("/gstr1")
def gstr1(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    return reports.gstr1(ctx.db, ctx.business, date_from, date_to)


@router.get("/gstr3b")
def gstr3b(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    return reports.gstr3b(ctx.db, ctx.business, date_from, date_to)


@router.get("/sales-register")
def sales_register(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    return reports.register(ctx.db, ctx.business, SALES, date_from, date_to)


@router.get("/purchase-register")
def purchase_register(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    return reports.register(ctx.db, ctx.business, PURCHASES, date_from, date_to)


@router.get("/stock-summary")
def stock_summary(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    return reports.stock_summary(ctx.db, ctx.business, date_from, date_to)


@router.get("/outstanding")
def outstanding(ctx: BCtx):
    return reports.outstanding(ctx.db, ctx.business)


@router.get("/dashboard")
def dashboard(ctx: BCtx):
    try:
        maybe_auto_backup(ctx.db, ctx.business)
    except Exception:  # noqa: BLE001 — a failed backup must never block the dashboard
        ctx.db.rollback()
    return reports.dashboard(ctx.db, ctx.business, dt.date.today())


# ---------------------------------------------------------------- report catalogue
from fastapi import HTTPException  # noqa: E402

from ..reports.base import RCtx  # noqa: E402
from ..reports.registry import BY_SLUG, CATALOG  # noqa: E402


@router.get("/catalog")
def catalog(ctx: BCtx):
    return [{k: v for k, v in r.items() if k != "fn"} for r in CATALOG]


@router.get("/run/{slug}")
def run_report(
    slug: str,
    ctx: BCtx,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    as_of: dt.date | None = None,
    party_id: str | None = None,
    item_id: str | None = None,
    account_id: str | None = None,
    loan_id: str | None = None,
    category_id: str | None = None,
):
    rep = BY_SLUG.get(slug)
    if not rep or not rep["fn"]:
        raise HTTPException(404, "Report not found")
    today = dt.date.today()
    fy_start = dt.date(today.year if today.month >= 4 else today.year - 1, 4, 1)
    r = RCtx(db=ctx.db, biz=ctx.business, date_from=date_from or fy_start, date_to=date_to or today,
             as_of=as_of or today, party_id=party_id, item_id=item_id, account_id=account_id, loan_id=loan_id,
             category_id=category_id)
    return rep["fn"](r)
