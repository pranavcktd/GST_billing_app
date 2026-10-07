"""Recurring invoices: make one from an existing invoice, generate on schedule, optionally e-mail.

Invoices are created through save_voucher (the same rules as a user's invoice) on behalf of the
business owner. Missed dates are caught up (at most 12 per run); errors are kept on the profile.
"""

import calendar
import datetime as dt
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import Ctx
from ..gst.constants import Role, VoucherType
from ..models import Business, Membership, Party, RecurringInvoice, Voucher
from ..permissions import effective
from ..schemas import VoucherIn
from . import invoice_pdf, mailer
from .plans import account_of, business_plan

MONTHS = {"MONTHLY": 1, "QUARTERLY": 3, "HALF_YEARLY": 6, "YEARLY": 12}
LINE_FIELDS = ("item_id", "name", "description", "hsn_sac", "unit", "qty", "rate", "discount_pct", "gst_rate", "cess_rate",
               "tax_inclusive")


def add_period(d: dt.date, frequency: str, interval: int, anchor_day: int) -> dt.date:
    if frequency == "WEEKLY":
        return d + dt.timedelta(weeks=interval)
    months = MONTHS[frequency] * interval
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return dt.date(year, month, min(anchor_day, calendar.monthrange(year, month)[1]))


def upcoming(r: RecurringInvoice, n: int = 5) -> list[dt.date]:
    out, d = [], r.next_date
    while d and len(out) < n and (not r.end_date or d <= r.end_date):
        out.append(d)
        d = add_period(d, r.frequency, r.interval, r.start_date.day)
    return out


def template_from(v: Voucher) -> dict:
    def j(x):
        return str(x) if isinstance(x, Decimal) else x
    return dict(
        party_id=v.party_id, place_of_supply=v.place_of_supply, notes=v.notes, terms=v.terms, tcs_rate=j(v.tcs_rate),
        godown_id=v.godown_id, extra_fields=v.extra_fields,
        lines=[{k: j(getattr(l, k)) for k in LINE_FIELDS} for l in sorted(v.lines, key=lambda l: l.sort_order)],
    )


def owner_ctx(db: Session, biz: Business) -> Ctx:
    m = db.scalar(select(Membership).where(Membership.business_id == biz.id, Membership.user_id == biz.owner_id)) or \
        db.scalar(select(Membership).where(Membership.business_id == biz.id, Membership.role == Role.OWNER))
    return Ctx(db=db, user=m.user, business=biz, role=m.role, membership=m, perms=effective(m.role, m.permissions))


def _email(db: Session, biz: Business, v: Voucher, base_url: str) -> None:
    party = db.get(Party, v.party_id) if v.party_id else None
    if not party or not party.email:
        return
    import html as h
    import secrets
    if not v.share_token:
        v.share_token = secrets.token_urlsafe(24)
    link = f"{base_url}/i/{v.share_token}"
    body = mailer.layout(f"{h.escape(biz.name)} — {h.escape(v.number)}", f"""
        <p>Dear {h.escape(party.name)},</p>
        <p>Please find attached invoice <b>{h.escape(v.number)}</b> dated {v.date:%d %b %Y} for <b>₹{float(v.grand_total):,.2f}</b>
        {f'due by {v.due_date:%d %b %Y}' if v.due_date else ''}.</p>
        {f'<p>Pay by UPI to <b>{h.escape(biz.upi_id)}</b>.</p>' if biz.upi_id else ''}
        <p style="text-align:center;margin:24px 0"><a href="{link}" style="background:#1f65bb;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none">View the invoice</a></p>""",
        footer=f"{h.escape(biz.name)}{' · GSTIN ' + h.escape(biz.gstin) if biz.gstin else ''}")
    pdf = invoice_pdf.render(v, biz, watermark=bool(business_plan(db, biz.id)["watermark"]), copies=["ORIGINAL"], images=False)
    cfg = mailer.business_smtp(db, biz.id, account_of(db, biz.id))
    mailer.send(cfg, [party.email], f"Invoice {v.number} from {biz.name}", body,
                attachments=[(invoice_pdf.filename(v), pdf, "application/pdf")], reply_to=biz.email)


def generate_due(db: Session, r: RecurringInvoice, today: dt.date, base_url: str, limit: int = 12) -> list[Voucher]:
    """Create every invoice whose date has arrived. Commits after each one."""
    biz = db.get(Business, r.business_id)
    made: list[Voucher] = []
    while r.status == "ACTIVE" and r.next_date and r.next_date <= today and len(made) < limit:
        if r.end_date and r.next_date > r.end_date:
            r.status, r.next_date = "ENDED", None
            break
        body = {**r.template, "type": VoucherType.SALE.value, "date": r.next_date.isoformat(),
                "due_date": (r.next_date + dt.timedelta(days=r.due_days)).isoformat() if r.due_days else None}
        try:
            ctx = owner_ctx(db, biz)
            from .vouchers import save_voucher
            v = save_voucher(ctx, VoucherIn.model_validate(body))
            from .stock_control import enforce
            enforce(ctx, v, allow=True)
            v.recurring_id = r.id
            db.flush()
            r.generated_count += 1
            r.last_generated_at, r.last_error = dt.datetime.now(dt.UTC), None
            r.next_date = add_period(r.next_date, r.frequency, r.interval, r.start_date.day)
            if r.end_date and r.next_date > r.end_date:
                r.status, r.next_date = "ENDED", None
            db.commit()
            made.append(v)
        except Exception as e:  # noqa: BLE001 — keep the reason on the profile, try again next run
            db.rollback()
            r = db.get(RecurringInvoice, r.id)
            r.last_error = str(getattr(e, "detail", e))[:300]
            db.commit()
            break
        if r.auto_email:
            try:
                _email(db, biz, v, base_url)
                db.commit()
            except Exception as e:  # noqa: BLE001
                db.rollback()
                r = db.get(RecurringInvoice, r.id)
                r.last_error = f"Invoice {v.number} created, e-mail not sent: {str(getattr(e, 'detail', e))[:200]}"
                db.commit()
    return made


def run_all(db: Session, today: dt.date | None = None) -> int:
    from ..config import get_settings
    today = today or dt.date.today()
    base = (get_settings().app_url or "http://localhost:3000").rstrip("/")
    total = 0
    for rid in db.scalars(select(RecurringInvoice.id).where(RecurringInvoice.status == "ACTIVE",
                                                            RecurringInvoice.next_date <= today)).all():
        r = db.get(RecurringInvoice, rid)
        total += len(generate_due(db, r, today, base))
    db.commit()
    return total
