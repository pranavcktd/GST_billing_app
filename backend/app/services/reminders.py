"""Payment reminders: automatic (daily schedule) and on demand, by e-mail, plus a WhatsApp message text.

Settings (Business.reminder_settings):
  enabled           automatic reminders on / off
  before_days       [3]            days before the due date
  on_due            true           on the due date
  after_days        [3, 7, 15, 30] days after the due date (overdue)
  default_credit_days 0           due date for invoices that have none (invoice date + N days)
  cc_me             true           copy the business e-mail
  attach_pdf        true           attach the invoice PDFs (up to 5)

One e-mail per customer per day lists every unpaid invoice; each (invoice, stage) is sent once.
Customers whose overall balance is not receivable (advances cover the bills) are skipped.
"""

import datetime as dt
import html
import secrets
from collections import defaultdict
from decimal import Decimal
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..gst.constants import VoucherType
from ..models import Business, Party, ReminderLog, User, Voucher
from . import invoice_pdf, mailer
from .ledger import party_balances
from .plans import account_of, business_plan

DEFAULTS = dict(enabled=False, before_days=[3], on_due=True, after_days=[3, 7, 15, 30], default_credit_days=0,
                cc_me=True, attach_pdf=True)
ZERO = Decimal("0")


def settings(biz: Business) -> dict:
    return {**DEFAULTS, **(biz.reminder_settings or {})}


def _due(v: Voucher, s: dict) -> dt.date:
    return v.due_date or (v.date + dt.timedelta(days=int(s.get("default_credit_days") or 0)))


def _balance(v: Voucher) -> Decimal:
    return max(v.grand_total - sum((a.amount for a in v.allocations), ZERO), ZERO)


def open_invoices(db: Session, biz: Business, party_ids: list[str] | None = None) -> list[Voucher]:
    q = (select(Voucher).options(selectinload(Voucher.allocations))
         .where(Voucher.business_id == biz.id, Voucher.type == VoucherType.SALE, Voucher.cancelled.is_(False),
                Voucher.party_id.is_not(None)))
    if party_ids:
        q = q.where(Voucher.party_id.in_(party_ids))
    return [v for v in db.scalars(q.order_by(Voucher.date)) if _balance(v) > 0]


def stage_for(due: dt.date, today: dt.date, s: dict) -> str | None:
    d = (today - due).days
    if d < 0 and -d in [int(x) for x in s.get("before_days") or []]:
        return f"BEFORE_{-d}"
    if d == 0 and s.get("on_due"):
        return "DUE"
    if d > 0 and d in [int(x) for x in s.get("after_days") or []]:
        return f"AFTER_{d}"
    return None


def due_today(db: Session, biz: Business, today: dt.date) -> dict[str, list[tuple[Voucher, str]]]:
    """Invoices that reach a reminder stage today and were not reminded for it yet, by party."""
    s = settings(biz)
    sent = {(r.voucher_id, r.stage) for r in db.scalars(select(ReminderLog).where(
        ReminderLog.business_id == biz.id, ReminderLog.status == "SENT", ReminderLog.voucher_id.is_not(None)))}
    out: dict[str, list] = defaultdict(list)
    for v in open_invoices(db, biz):
        st = stage_for(_due(v, s), today, s)
        if st and (v.id, st) not in sent:
            out[v.party_id].append((v, st))
    return out


# ---------------------------------------------------------------- messages
def _ensure_token(v: Voucher) -> str:
    if not v.share_token:
        v.share_token = secrets.token_urlsafe(24)
    return v.share_token


def _rows(vs: list[Voucher], s: dict, today: dt.date) -> list[dict]:
    out = []
    for v in vs:
        due = _due(v, s)
        out.append(dict(v=v, number=v.number, date=v.date, due=due, balance=_balance(v), overdue=max((today - due).days, 0)))
    return out


def email_body(biz: Business, party: Party, rows: list[dict], base_url: str, note: str | None = None) -> tuple[str, str]:
    e = html.escape
    total = sum((r["balance"] for r in rows), ZERO)
    overdue = [r for r in rows if r["overdue"] > 0]
    subject = (f"Payment reminder: {'₹' + format(total, ',.2f')} {'overdue' if overdue else 'due'} — {biz.name}")
    lines = "".join(
        f"<tr><td style='padding:4px 6px'>{e(r['number'])}</td><td style='padding:4px 6px'>{r['date']:%d %b %Y}</td>"
        f"<td style='padding:4px 6px'>{r['due']:%d %b %Y}{' — <b style=\"color:#b91c1c\">' + str(r['overdue']) + ' days overdue</b>' if r['overdue'] else ''}</td>"
        f"<td style='padding:4px 6px;text-align:right'>₹{float(r['balance']):,.2f}</td>"
        f"<td style='padding:4px 6px'><a href='{base_url}/i/{_ensure_token(r['v'])}'>View</a></td></tr>" for r in rows)
    upi = ""
    if biz.upi_id:
        link = f"upi://pay?pa={quote(biz.upi_id)}&pn={quote(biz.name)}&am={total:.2f}&cu=INR"
        upi = f"<p>Pay instantly by UPI to <b>{e(biz.upi_id)}</b> (<a href='{link}'>pay ₹{float(total):,.2f}</a> from a phone).</p>"
    bank = ""
    if biz.bank_account_no:
        bank = (f"<p style='color:#4b5563;font-size:13px'>Bank: {e(biz.bank_name or '')} · A/c {e(biz.bank_account_no)}"
                f"{' · IFSC ' + e(biz.bank_ifsc) if biz.bank_ifsc else ''}</p>")
    msg = f"<p>{e(note).replace(chr(10), '<br>')}</p>" if note else ""
    body = mailer.layout("Payment reminder", f"""
        <p>Dear {e(party.name)},</p>{msg}
        <p>This is a friendly reminder that the following {'invoice is' if len(rows) == 1 else 'invoices are'} pending with
        <b>{e(biz.name)}</b>. Total due: <b>₹{float(total):,.2f}</b>.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          <tr style="background:#f3f4f6;text-align:left"><th style="padding:4px 6px">Invoice</th><th style="padding:4px 6px">Date</th>
          <th style="padding:4px 6px">Due</th><th style="padding:4px 6px;text-align:right">Balance</th><th></th></tr>{lines}
        </table>{upi}{bank}
        <p>If you have already paid, please ignore this e-mail — thank you.</p>""",
        footer=f"{e(biz.name)}{' · GSTIN ' + e(biz.gstin) if biz.gstin else ''}{' · ' + e(biz.phone) if biz.phone else ''}")
    return subject, body


def whatsapp_text(biz: Business, party: Party, rows: list[dict], base_url: str) -> str:
    total = sum((r["balance"] for r in rows), ZERO)
    lines = [f"Dear {party.name},", "", f"Friendly reminder from {biz.name}: ₹{total:,.2f} is pending."]
    for r in rows[:10]:
        lines.append(f"• {r['number']} ({r['date']:%d-%m-%Y}) ₹{r['balance']:,.2f}"
                     + (f" — {r['overdue']} days overdue" if r["overdue"] else f" — due {r['due']:%d-%m-%Y}")
                     + f"\n  {base_url}/i/{_ensure_token(r['v'])}")
    if biz.upi_id:
        lines += ["", f"UPI: {biz.upi_id}"]
    lines += ["", "Please ignore if already paid. Thank you!"]
    return "\n".join(lines)


def wa_phone(p: str | None) -> str | None:
    digits = "".join(ch for ch in (p or "") if ch.isdigit())
    if len(digits) == 10:
        return "91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    return None


# ---------------------------------------------------------------- sending
def send_party(db: Session, biz: Business, party: Party, invoices: list[tuple[Voucher, str]], base_url: str, *,
               automatic: bool, actor: User | None = None, note: str | None = None, today: dt.date | None = None) -> tuple[bool, str | None]:
    """E-mail one customer about the given invoices. Returns (sent, error). Every invoice gets a log row."""
    s = settings(biz)
    rows = _rows([v for v, _ in invoices], s, today or dt.date.today())

    def log(status: str, error: str | None = None, to: str | None = None) -> None:
        for v, st in invoices:
            db.add(ReminderLog(business_id=biz.id, party_id=party.id, voucher_id=v.id, stage=st, channel="EMAIL", sent_to=to,
                               status=status, error=error, automatic=automatic, amount=_balance(v),
                               by_name=actor.name if actor else None))

    if not party.email:
        log("FAILED", "Customer has no e-mail address")
        return False, "Customer has no e-mail address"
    subject, body = email_body(biz, party, rows, base_url, note)
    attachments = None
    if s.get("attach_pdf"):
        watermark = bool(business_plan(db, biz.id)["watermark"])
        attachments = [(invoice_pdf.filename(r["v"]), invoice_pdf.render(r["v"], biz, watermark=watermark, copies=["ORIGINAL"], images=False),
                        "application/pdf") for r in rows[:5]]
    cfg = mailer.business_smtp(db, biz.id, account_of(db, biz.id))
    try:
        mailer.send(cfg, [party.email], subject, body, attachments=attachments,
                    cc=[biz.email] if s.get("cc_me") and biz.email else None, reply_to=biz.email)
    except Exception as e:  # noqa: BLE001 — recorded in the log, never breaks the daily run
        err = str(getattr(e, "detail", e))[:300]
        log("FAILED", err, party.email)
        return False, err
    log("SENT", None, party.email)
    return True, None


def run_business(db: Session, biz: Business, base_url: str, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    if not settings(biz)["enabled"]:
        return {"sent": 0, "failed": 0, "skipped": 0}
    groups = due_today(db, biz, today)
    balances = party_balances(db, biz.id, list(groups)) if groups else {}
    sent = failed = skipped = 0
    for pid, invoices in groups.items():
        if balances.get(pid, ZERO) <= 0:
            skipped += 1  # advances / credit notes already cover the bills
            continue
        ok, _ = send_party(db, biz, db.get(Party, pid), invoices, base_url, automatic=True, today=today)
        sent += ok
        failed += not ok
    db.commit()
    return {"sent": sent, "failed": failed, "skipped": skipped}


def run_all(db: Session, today: dt.date | None = None) -> dict:
    """Daily job: every business with automatic reminders switched on."""
    from ..config import get_settings
    base = (get_settings().app_url or "http://localhost:3000").rstrip("/")
    total = {"businesses": 0, "sent": 0, "failed": 0}
    for biz in db.scalars(select(Business).where(Business.reminder_settings.is_not(None))):
        if not settings(biz)["enabled"]:
            continue
        r = run_business(db, biz, base, today)
        total["businesses"] += 1
        total["sent"] += r["sent"]
        total["failed"] += r["failed"]
    return total


def maybe_run_daily(db: Session, now: dt.datetime | None = None) -> dict | None:
    """Called hourly by the scheduler: runs once a day, after 9 AM (server time)."""
    from ..models import PlatformSetting
    now = now or dt.datetime.now()
    if now.hour < 9:
        return None
    row = db.get(PlatformSetting, "reminders_last_run") or PlatformSetting(key="reminders_last_run", value={})
    if (row.value or {}).get("date") == now.date().isoformat():
        db.rollback()  # end the read transaction — the scheduler's session lives on
        return None
    row.value = {"date": now.date().isoformat()}
    db.add(row)
    db.commit()
    result = run_all(db, now.date())
    row.value = {"date": now.date().isoformat(), **result}
    db.commit()
    return result
