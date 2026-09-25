"""Company backup (gzip JSON snapshot) and restore-as-new-company.

Restore never overwrites live data: it creates a fresh company, giving every
record a new id and remapping all references to it.
"""

import datetime as dt
import gzip
import json
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import Date, DateTime, Numeric, delete, insert, select, update
from sqlalchemy.orm import Session

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
    """Daily automatic backup, triggered lazily when the business is used (skipped when storage is full)."""
    if not business.auto_backup:
        return None
    from .plans import check_backup_quota

    try:
        check_backup_quota(db, business.id, 0)
    except HTTPException:
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


def email_backup(db: Session, business: Business, to: str, blob: bytes, created: dt.datetime) -> None:
    from . import mailer
    from .plans import account_of

    cfg = mailer.business_smtp(db, business.id, account_of(db, business.id))
    body = mailer.layout(f"Backup of {business.name}", f"<p>Attached is the backup of <b>{business.name}</b> taken on "
                         f"{created:%d %b %Y %H:%M}.</p><p>Restore it from Utilities → Backup & Restore.</p>")
    mailer.send(cfg, [to], f"Backup of {business.name} — {created:%d %b %Y}", body,
                attachments=[(filename(business.name, created), blob, "application/octet-stream")])


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
                out["owner_id"] = user_id
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

    start_trial(db, user_id)
    db.flush()
    return db.get(Business, new_bid)


# ================================================================ platform backups (super admin)
import base64  # noqa: E402

from sqlalchemy import LargeBinary  # noqa: E402

from ..db import Base  # noqa: E402

ACCOUNT_FORMAT = "gst-billing-account-backup"
FULL_FORMAT = "gst-billing-full-backup"
FULL_EXCLUDE = {"platform_backups"}          # never nest platform backups inside each other
KEEP_PLATFORM_AUTO = 7


def _snapshot_dict(db: Session, business: Business) -> dict:
    return json.loads(gzip.decompress(snapshot(db, business)))


def account_snapshot(db: Session, owner) -> bytes:
    """Every business owned by one account, in one file."""
    businesses = db.scalars(select(Business).where(Business.owner_id == owner.id)).all()
    data = {"format": ACCOUNT_FORMAT, "version": VERSION, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "account": {"name": owner.name, "email": owner.email},
            "businesses": [_snapshot_dict(db, b) for b in businesses]}
    return gzip.compress(json.dumps(data, separators=(",", ":")).encode())


def _enc_full(col, v):
    if isinstance(v, bytes):
        return base64.b64encode(v).decode()
    return _encode(v)


def full_snapshot(db: Session, include_business_backups: bool = False) -> bytes:
    tables = {}
    for t in Base.metadata.sorted_tables:
        if t.name in FULL_EXCLUDE or (t.name == "backups" and not include_business_backups):
            continue
        tables[t.name] = [{k: _enc_full(t.c[k], v) for k, v in r._mapping.items()} for r in db.execute(select(t))]
    data = {"format": FULL_FORMAT, "version": VERSION, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "tables": tables}
    return gzip.compress(json.dumps(data, separators=(",", ":")).encode())


def detect(blob: bytes) -> tuple[str, dict]:
    try:
        data = json.loads(gzip.decompress(blob))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, "This is not a valid backup file") from e
    fmt = data.get("format")
    if fmt not in (FORMAT, ACCOUNT_FORMAT, FULL_FORMAT):
        raise HTTPException(400, "This is not a valid backup file")
    if data.get("version", 0) > VERSION:
        raise HTTPException(400, "This backup was made by a newer version of the app")
    return fmt, data


def restore_account(db: Session, data: dict, owner_id: str) -> list[Business]:
    out = []
    for snap in data.get("businesses", []):
        blob = gzip.compress(json.dumps(snap).encode())
        out.append(restore_as_new(db, blob, owner_id, None))
    return out


def _dec_full(col, v):
    if v is None:
        return None
    if isinstance(col.type, LargeBinary):
        return base64.b64decode(v)
    return _decode(col, v)


def restore_full(db: Session, data: dict, keep_user) -> dict:
    """Replace ALL data with the backup. The acting super admin's login is preserved."""
    keep = {c.name: getattr(keep_user, c.name) for c in keep_user.__table__.c}
    tables = data["tables"]
    ordered = [t for t in Base.metadata.sorted_tables if t.name not in FULL_EXCLUDE]
    for t in reversed(ordered):
        if t.name == "backups" and "backups" not in tables:
            continue  # keep business backups if the file does not carry them
        db.execute(delete(t))
    counts = {}
    deferred = []
    for t in ordered:
        rows = []
        for row in tables.get(t.name, []):
            out = {c.name: _dec_full(c, row.get(c.name)) for c in t.c if c.name in row}
            for sc in SELF_REFS.get(t.name, []):
                if out.get(sc):
                    deferred.append((t, out["id"], sc, out[sc]))
                    out[sc] = None
            rows.append(out)
        if rows:
            db.execute(insert(t), rows)
        counts[t.name] = len(rows)
    for t, rid, colname, val in deferred:
        db.execute(update(t).where(t.c.id == rid).values({colname: val}))
    users = Base.metadata.tables["users"]
    if not db.execute(select(users.c.id).where(users.c.id == keep["id"])).first():
        by_email = db.execute(select(users.c.id).where(users.c.email == keep["email"])).first()
        if by_email:
            db.execute(update(users).where(users.c.id == by_email[0]).values(platform_role="SUPERADMIN", is_active=True))
        else:
            db.execute(insert(users), [keep])
    db.flush()
    return counts


def create_platform_backup(db: Session, scope: str, label: str, blob: bytes, kind: str, user_id: str | None,
                           ref_id: str | None = None):
    from ..models import PlatformBackup

    b = PlatformBackup(scope=scope, ref_id=ref_id, label=label, kind=kind, size=len(blob), data=blob,
                       created_by_id=user_id)
    db.add(b)
    db.flush()
    if kind == "AUTO":
        old = db.scalars(select(PlatformBackup.id).where(PlatformBackup.scope == scope, PlatformBackup.kind == "AUTO")
                         .order_by(PlatformBackup.created_at.desc())).all()
        if len(old) > KEEP_PLATFORM_AUTO:
            db.execute(delete(PlatformBackup).where(PlatformBackup.id.in_(old[KEEP_PLATFORM_AUTO:])))
    return b


def maybe_auto_full_backup(db: Session) -> None:
    """Daily full platform backup (called by the background scheduler)."""
    from ..models import PlatformBackup, PlatformSetting

    setting = db.get(PlatformSetting, "auto_full_backup")
    if setting is not None and not (setting.value or {}).get("enabled", True):
        return
    last = db.scalar(select(PlatformBackup.created_at).where(PlatformBackup.scope == "FULL", PlatformBackup.kind == "AUTO")
                     .order_by(PlatformBackup.created_at.desc()).limit(1))
    if last is not None:
        last = last if last.tzinfo else last.replace(tzinfo=dt.timezone.utc)
        if dt.datetime.now(dt.timezone.utc) - last < dt.timedelta(hours=24):
            return
    blob = full_snapshot(db)
    create_platform_backup(db, "FULL", f"Automatic full backup {dt.date.today():%d-%m-%Y}", blob, "AUTO", None)
    db.commit()
