"""Edit log of the books of account (Companies (Accounts) Rules, rule 3(1) proviso — "audit trail"; CGST s.35/36).

Every insert, change and delete of a book-of-account record is written to `audit_changes` in the same database
transaction, with the values before and after, who did it and when. It cannot be switched off (a SQLAlchemy hook
on every session) and, on PostgreSQL, triggers refuse any UPDATE / DELETE of the log tables — except inside a
transaction that sets `app.audit_purge = 'on'` (a super admin deleting a whole account after a safety backup, or a
full platform restore). Bulk deletes done with SQL (Clear data) are covered by a backup taken first and a log line.
"""

import contextvars
import datetime as dt
import enum
from decimal import Decimal

from sqlalchemy import DDL, event, inspect, text
from sqlalchemy.orm import Session

from ..models import AuditChange, AuditLog

# who is acting outside a request (scripts); in requests deps.current_user puts it on the session: db.info["actor"]
actor: contextvars.ContextVar[dict | None] = contextvars.ContextVar("audit_actor", default=None)

TRACKED = {
    "vouchers": "document", "voucher_lines": "document line", "payments": "payment", "payment_allocations": "payment link",
    "parties": "party", "items": "item", "accounts": "bank / cash account", "account_transfers": "money transfer",
    "capital_entries": "capital entry", "tax_payments": "tax payment", "loans": "loan", "loan_txns": "loan entry",
    "stock_movements": "stock entry", "stock_transfers": "stock transfer", "expense_categories": "expense category",
    "expense_items": "expense item", "employees": "employee", "payroll_runs": "payroll", "payroll_lines": "payroll line",
    "salary_advances": "salary advance", "productions": "production", "godowns": "godown", "businesses": "company settings",
}
SKIP_COLS = {"password_enc", "einvoice_password_enc", "ewb_password_enc", "share_token", "signed_qr", "updated_at"}


def _plain(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (dt.date, dt.datetime, dt.time)):
        return v.isoformat()
    if isinstance(v, enum.Enum):
        return v.value
    if isinstance(v, (bytes, bytearray)):
        return "<binary>"
    if isinstance(v, (dict, list)):
        return v
    return str(v)


def _business_id(obj) -> str | None:
    if obj.__tablename__ == "businesses":
        return obj.id
    bid = getattr(obj, "business_id", None)
    if bid:
        return bid
    for rel in ("voucher", "payment", "run"):  # child rows: the parent's business
        parent = getattr(obj, rel, None)
        if parent is not None and getattr(parent, "business_id", None):
            return parent.business_id
    return None


def _cols(obj) -> list[str]:
    return [c.key for c in inspect(obj).mapper.column_attrs if c.key not in SKIP_COLS]


def _row(obj) -> dict:
    return {k: _plain(getattr(obj, k, None)) for k in _cols(obj)}


@event.listens_for(Session, "before_flush")
def _record(session: Session, flush_context, instances) -> None:
    who = session.info.get("actor") or actor.get() or {}
    now = dt.datetime.now(dt.UTC)
    entries = []
    for op, objs in (("INSERT", session.new), ("UPDATE", session.dirty), ("DELETE", session.deleted)):
        for obj in list(objs):
            table = getattr(obj, "__tablename__", None)
            if table not in TRACKED:
                continue
            before = after = None
            if op == "INSERT":
                after = _row(obj)
            elif op == "DELETE":
                before = _row(obj)
            else:
                state = inspect(obj)
                before, after = {}, {}
                for key in _cols(obj):
                    hist = state.attrs[key].history
                    if hist.has_changes():
                        before[key] = _plain(hist.deleted[0]) if hist.deleted else None
                        after[key] = _plain(hist.added[0]) if hist.added else None
                if not after:
                    continue  # touched but nothing changed
            row_id = getattr(obj, "id", None) or getattr(obj, "voucher_id", None)
            entries.append(AuditChange(business_id=_business_id(obj), table_name=table, entity=TRACKED[table], row_id=row_id,
                                       op=op, before=before, after=after, user_id=who.get("user_id"),
                                       user_name=who.get("user_name"), ip=who.get("ip"), at=now))
    for e in entries:
        session.add(e)


# ---------------------------------------------------------------- PostgreSQL: the log cannot be changed or deleted
_FN = DDL("""
CREATE OR REPLACE FUNCTION audit_immutable() RETURNS trigger AS $$
BEGIN
  IF coalesce(current_setting('app.audit_purge', true), '') = 'on' THEN
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
  END IF;
  -- a deleted user is kept as a name only (user_id set to NULL by the foreign key); nothing else may change
  IF TG_OP = 'UPDATE' AND (to_jsonb(NEW) - 'user_id') = (to_jsonb(OLD) - 'user_id') THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'The audit trail cannot be changed or deleted';
END $$ LANGUAGE plpgsql;
""")


def _trigger(table: str) -> DDL:
    return DDL(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}; "
               f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
               f"FOR EACH ROW EXECUTE FUNCTION audit_immutable();")


for _model in (AuditLog, AuditChange):
    event.listen(_model.__table__, "after_create", _FN.execute_if(dialect="postgresql"))
    event.listen(_model.__table__, "after_create", _trigger(_model.__tablename__).execute_if(dialect="postgresql"))


def allow_purge(db: Session) -> None:
    """Only for deleting a whole account after a safety backup, or a full platform restore (this transaction only)."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET LOCAL app.audit_purge = 'on'"))
