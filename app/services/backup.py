"""Company backup (gzip JSON snapshot) and restore-as-new-company.

Restore never overwrites live data: it creates a fresh company, giving every
record a new id and remapping all references to it.
"""

import datetime as dt
import gzip
import json
import smtplib
import uuid
from decimal import Decimal
from email.message import EmailMessage

from fastapi import HTTPException
from sqlalchemy import Date, DateTime, Numeric, delete, insert, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..gst.constants import Role
from ..models import (
    Account,
    AccountTransfer,
    Backup,
    Business,
    CapitalEntry,
    Godown,
    StockTransfer,
    Counter,
    ExpenseCategory,
    ExpenseItem,
    HsnCode,
    Item,
    Loan,
    LoanTxn,
    Membership,
    Party,
    Payment,
    PaymentAllocation,
    StockMovement,
    TaxPayment,
    Voucher,
    VoucherLine,
)

FORMAT = "gst-billing-backup"
VERSION = 1

# insert order respects foreign keys
TABLES = [Business, Account, Godown, ExpenseCategory, ExpenseItem, Party, Item, Loan, HsnCode, Voucher, VoucherLine,
          StockTransfer, StockMovement, Payment, PaymentAllocation, Counter, AccountTransfer, CapitalEntry, LoanTxn, TaxPayment]
# id references stored without a foreign key
LOOSE_REFS = {"vouchers": ["source_voucher_id", "converted_to_id"]}
SELF_REFS = {"vouchers": ["original_voucher_id"]}
USER_REFS = {"created_by_id"}
KEEP_BACKUPS = 7


def _encode(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, bytes):
        return None
    return v.value if hasattr(v, "value") else v


def _rows(db: Session, model, bid: str) -> list[dict]:
    t = model.__table__
    if "business_id" in t.c:
        q = select(t).where(t.c.business_id == bid)
    elif model is Business:
        q = select(t).where(t.c.id == bid)
    elif model is VoucherLine:
        q = select(t).where(t.c.voucher_id.in_(select(Voucher.id).where(Voucher.business_id == bid)))
    elif model is PaymentAllocation:
        q = select(t).where(t.c.payment_id.in_(select(Payment.id).where(Payment.business_id == bid)))
    else:
        return []
    return [{k: _encode(v) for k, v in r._mapping.items()} for r in db.execute(q)]


def snapshot(db: Session, business: Business) -> bytes:
    data = {
        "format": FORMAT, "version": VERSION, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "business_name": business.name,
        "tables": {m.__tablename__: _rows(db, m, business.id) for m in TABLES},
    }
    return gzip.compress(json.dumps(data, separators=(",", ":")).encode())


def create_backup(db: Session, business: Business, user_id: str | None, kind: str = "MANUAL") -> Backup:
    blob = snapshot(db, business)
    b = Backup(business_id=business.id, kind=kind, size=len(blob), data=blob, created_by_id=user_id)
    db.add(b)
    db.flush()
    # keep only the newest automatic backups
    autos = db.scalars(select(Backup.id).where(Backup.business_id == business.id, Backup.kind == "AUTO")
                       .order_by(Backup.created_at.desc())).all()
    if len(autos) > KEEP_BACKUPS:
        db.execute(delete(Backup).where(Backup.id.in_(autos[KEEP_BACKUPS:])))
    return b


def maybe_auto_backup(db: Session, business: Business) -> Backup | None:
    """Daily automatic backup, triggered lazily when the business is used."""
    if not business.auto_backup:
        return None
    last = db.scalar(select(Backup.created_at).where(Backup.business_id == business.id)
                     .order_by(Backup.created_at.desc()).limit(1))
    if last is not None:
        last = last if last.tzinfo else last.replace(tzinfo=dt.timezone.utc)
        if dt.datetime.now(dt.timezone.utc) - last < dt.timedelta(hours=24):
            return None
    b = create_backup(db, business, None, "AUTO")
    db.commit()
    return b


def filename(business_name: str, created: dt.datetime) -> str:
    safe = "".join(c if c.isalnum() else "-" for c in business_name).strip("-")[:40] or "company"
    return f"{safe}-{created:%Y%m%d-%H%M}.gstbak"


def email_backup(to: str, business_name: str, blob: bytes, created: dt.datetime) -> None:
    s = get_settings()
    if not s.smtp_host:
        raise HTTPException(503, "Email is not configured on the server (SMTP_HOST)")
    msg = EmailMessage()
    msg["Subject"] = f"Backup of {business_name} — {created:%d %b %Y %H:%M}"
    msg["From"] = s.smtp_from or s.smtp_user
    msg["To"] = to
    msg.set_content(f"Attached is the backup of {business_name}. Restore it from Utilities → Backup & Restore.")
    msg.add_attachment(blob, maintype="application", subtype="octet-stream", filename=filename(business_name, created))
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password or "")
        smtp.send_message(msg)


def _decode(col, v):
    if v is None:
        return None
    if isinstance(col.type, Numeric):
        return Decimal(v)
    if isinstance(col.type, DateTime):
        return dt.datetime.fromisoformat(v)
    if isinstance(col.type, Date):
        return dt.date.fromisoformat(v)
    return v


def restore_as_new(db: Session, blob: bytes, user_id: str, new_name: str | None = None) -> Business:
    try:
        data = json.loads(gzip.decompress(blob))
        assert data.get("format") == FORMAT
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, "This is not a valid backup file") from e
    if data.get("version", 0) > VERSION:
        raise HTTPException(400, "This backup was made by a newer version of the app")

    tables = data["tables"]
    idmap: dict[str, str] = {}
    for m in TABLES:
        for row in tables.get(m.__tablename__, []):
            if "id" in row:
                idmap[row["id"]] = uuid.uuid4().hex
    biz_rows = tables.get("businesses") or []
    if not biz_rows:
        raise HTTPException(400, "Backup has no company data")
    new_bid = idmap[biz_rows[0]["id"]]

    fk_cols = {}
    for m in TABLES:
        t = m.__table__
        fk_cols[t.name] = [c.name for c in t.c if c.foreign_keys] + LOOSE_REFS.get(t.name, [])

    deferred = []
    for m in TABLES:
        t = m.__table__
        rows = []
        for row in tables.get(t.name, []):
            out = {}
            for c in t.c:
                if c.name not in row:
                    continue
                v = _decode(c, row[c.name])
                if c.name == "id":
                    v = idmap[v]
                elif c.name in USER_REFS:
                    v = user_id
                elif c.name in fk_cols[t.name] and v is not None:
                    v = idmap.get(v, v)
                out[c.name] = v
            if t.name == "businesses":
                out["name"] = new_name or f"{out['name']} (restored)"
            for sc in SELF_REFS.get(t.name, []):
                if out.get(sc):
                    deferred.append((t, out["id"], sc, out[sc]))
                    out[sc] = None
            rows.append(out)
        if rows:
            db.execute(insert(t), rows)
    for t, rid, colname, val in deferred:
        db.execute(update(t).where(t.c.id == rid).values({colname: val}))
    db.add(Membership(user_id=user_id, business_id=new_bid, role=Role.OWNER))
    from .plans import start_trial

    start_trial(db, new_bid)
    db.flush()
    return db.get(Business, new_bid)
