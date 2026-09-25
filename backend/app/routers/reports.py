import datetime as dt

from fastapi import APIRouter

from ..deps import BCtx
from ..gst.constants import VoucherType
from ..services import reports
from ..permissions import report_module, voucher_module
from ..services.backup import maybe_auto_backup
from ..services.plans import REPORT_MIN_PLAN, business_plan, check_report, rank

router = APIRouter(prefix="/reports", tags=["reports"])

SALES = [VoucherType.SALE, VoucherType.SALE_RETURN]
PURCHASES = [VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN]


def _gate(ctx: BCtx, slug: str, module: str) -> None:
    ctx.need(module, "view")
    check_report(ctx.db, ctx.bid, slug)


@router.get("/gstr1")
def gstr1(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    _gate(ctx, "gstr1", "reports_gst")
    return reports.gstr1(ctx.db, ctx.business, date_from, date_to)


@router.get("/gstr3b")
def gstr3b(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    _gate(ctx, "gstr3b", "reports_gst")
    return reports.gstr3b(ctx.db, ctx.business, date_from, date_to)


@router.get("/sales-register")
def sales_register(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    _gate(ctx, "sale", "reports_sales")
    return reports.register(ctx.db, ctx.business, SALES, date_from, date_to)


@router.get("/purchase-register")
def purchase_register(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    _gate(ctx, "purchase", "reports_financial")
    return reports.register(ctx.db, ctx.business, PURCHASES, date_from, date_to)


@router.get("/stock-summary")
def stock_summary(ctx: BCtx, date_from: dt.date, date_to: dt.date):
    _gate(ctx, "stock-summary", "reports_stock")
    return reports.stock_summary(ctx.db, ctx.business, date_from, date_to)


@router.get("/outstanding")
def outstanding(ctx: BCtx):
    _gate(ctx, "all-parties", "reports_financial")
    return reports.outstanding(ctx.db, ctx.business)


@router.get("/dashboard")
def dashboard(ctx: BCtx):
    try:
        maybe_auto_backup(ctx.db, ctx.business)
    except Exception:  # noqa: BLE001 — a failed backup must never block the dashboard
        ctx.db.rollback()
    data = reports.dashboard(ctx.db, ctx.business, dt.date.today())
    # only show what the role may see
    if not ctx.can("reports_financial"):
        for k in ("purchases_month", "payable", "receivable", "received_month"):
            data[k] = None
        data["trend"] = [{**t, "purchases": None, "expenses": None} for t in data["trend"]] if ctx.can("reports_sales") else []
    if not ctx.can("cashbank"):
        data["cash_bank"] = None
    if not ctx.can("expenses"):
        data["expenses"] = None
    if not ctx.flag("view_cost"):
        data["inventory"] = {**data["inventory"], "value": None}
    if not ctx.can("reports_sales"):
        data["sales_today"] = data["sales_month"] = None
    data["recent"] = [v for v in data["recent"] if ctx.can(voucher_module(v["type"]))]
    return data


# ---------------------------------------------------------------- report catalogue
from fastapi import HTTPException  # noqa: E402

from ..reports.base import RCtx  # noqa: E402
from ..reports.registry import BY_SLUG, CATALOG  # noqa: E402


@router.get("/catalog")
def catalog(ctx: BCtx):
    """Every report, flagged with whether this user's role and plan allow it."""
    plan = business_plan(ctx.db, ctx.bid)
    out = []
    for r in CATALOG:
        module = report_module(r["slug"], r["category"])
        need = REPORT_MIN_PLAN.get(r["slug"], "STARTER")
        if not ctx.can(module):
            continue  # hide reports the role may never open
        out.append({**{k: v for k, v in r.items() if k != "fn"}, "module": module, "min_plan": need,
                    "locked": rank(plan["code"]) < rank(need)})
    return out


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
    _gate(ctx, slug, report_module(slug, rep["category"]))
    today = dt.date.today()
    fy_start = dt.date(today.year if today.month >= 4 else today.year - 1, 4, 1)
    r = RCtx(db=ctx.db, biz=ctx.business, date_from=date_from or fy_start, date_to=date_to or today,
             as_of=as_of or today, party_id=party_id, item_id=item_id, account_id=account_id, loan_id=loan_id,
             category_id=category_id)
    return rep["fn"](r)
