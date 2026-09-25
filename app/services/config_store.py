"""Platform configuration that super admins change from the admin panel — no code release needed.

Compliance values (GST slabs, limits, masters, file-format versions, company details) are
*effective-dated*: each saved version applies from its `effective_from` date, so documents dated
before a change keep the old rule and documents after it follow the new one.

    get("b2cl_limit", on=invoice.date)   # value in force on a date (default: today)
    rates_on(date)                       # GST slabs allowed on a date
    all_rates()                          # every slab ever configured (validating old documents)

Plans (prices, limits, features) are not dated: overrides are merged into plans.PLANS in place.

Storage: platform_settings["config"] = {"versions": [{id, effective_from, values, note, by, at}]}
         platform_settings["plans"]  = {"FREE": {...overrides}, ..., "ADDON_BUSINESSES": {...}}
The cache is reloaded at the start of every request (one primary-key read), so every worker sees
changes immediately.
"""

import copy
import datetime as dt
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..gst.constants import GST_RATES, UQC
from ..gst.states import STATES
from ..models import PlatformSetting


@dataclass
class Field:
    key: str
    group: str
    label: str
    type: str          # money | int | number | text | bool | rates | list | map_text | map_number
    default: Any
    help: str = ""
    options: list = field(default_factory=list)


CREDIT_NOTE_REASONS = ["Sales return", "Post-sale discount", "Deficiency in services", "Correction in invoice",
                       "Change in POS", "Finalization of provisional assessment", "Others"]

FIELDS: list[Field] = [
    # ---- GST rules
    Field("gst_rates", "GST rules", "GST rate slabs (%)", "rates", [float(r) for r in GST_RATES],
          "Rates selectable on items and bills. Remove a slab from a date to stop new bills using it."),
    Field("b2cl_limit", "GST rules", "B2C Large invoice limit (₹)", "money", 100000,
          "Inter-state invoices to unregistered buyers above this are reported invoice-wise in GSTR-1 (B2CL)."),
    Field("invoice_number_max_len", "GST rules", "Maximum invoice number length", "int", 16,
          "Rule 46: up to 16 characters."),
    Field("ewb_threshold", "GST rules", "e-Way bill required above (₹)", "money", 50000,
          "Consignment value above which an e-way bill is required (shown as a reminder on invoices)."),
    Field("einvoice_turnover_limit", "GST rules", "e-Invoicing mandatory above turnover (₹)", "money", 50000000,
          "Aggregate annual turnover from which e-invoicing is mandatory."),
    Field("composition_rates", "GST rules", "Composition scheme rates (%)", "map_number",
          {"TRADER": 1, "MANUFACTURER": 1, "RESTAURANT": 5, "SERVICE": 6},
          "Tax rate on turnover per composition category (CMP-08 / GSTR-4)."),
    Field("hsn_digits_small", "GST rules", "HSN digits — turnover up to ₹5 crore", "int", 4,
          "Minimum HSN digits on B2B invoices and GSTR-1 table 12."),
    Field("hsn_digits_large", "GST rules", "HSN digits — turnover above ₹5 crore", "int", 6),
    Field("hsn_strict", "GST rules", "Only allow HSN/SAC codes from the official master", "bool", False,
          "On: items and bills must use a code from Admin → HSN master (businesses can request missing codes). "
          "Off: other codes are allowed with a warning."),
    Field("late_fee_per_day", "GST rules", "Late fee per day (CGST + SGST, ₹)", "money", 50,
          "For GSTR-1 / GSTR-3B with tax liability (₹20 for nil returns)."),
    Field("interest_rate", "GST rules", "Interest on late tax payment (% p.a.)", "number", 18),
    Field("gstr1_due_day", "GST rules", "GSTR-1 due day of next month", "int", 11),
    Field("gstr3b_due_day", "GST rules", "GSTR-3B due day of next month", "int", 20),
    # ---- file formats
    Field("gstr1_json_version", "File formats", "GSTR-1 JSON version", "text", "GST3.2",
          "The `version` value the GST offline tool expects."),
    Field("einvoice_schema_version", "File formats", "e-Invoice schema version", "text", "1.1"),
    # ---- masters
    Field("uqc", "Masters", "Units (UQC)", "map_text", dict(UQC), "Unit quantity codes accepted by the GST portal."),
    Field("states", "Masters", "State / UT codes", "map_text", dict(STATES), "GST state codes."),
    Field("credit_note_reasons", "Masters", "Credit / debit note reasons", "list", CREDIT_NOTE_REASONS),
    Field("blocked_itc_categories", "Masters", "Expense categories with blocked ITC (new businesses)", "list",
          ["Tea & Refreshments"], "Sec. 17(5) — ticked as 'ITC blocked' when a business is created."),
    # ---- billing & brand
    Field("subscription_gst_rate", "Subscription & company", "GST on subscription fees (%)", "number", 18),
    Field("trial_days", "Subscription & company", "Free trial days", "int", 14),
    Field("brand", "Subscription & company", "Product brand", "map_text",
          {"app_name": "SmartHisab", "by_line": "by Corenexgen",
           "tagline": "Billing, stock and accounts — made simple for Indian businesses"},
          "Shown in the app, website, e-mails and on bills of Free-plan users."),
    Field("company", "Subscription & company", "Company details (legal pages, footer)", "map_text",
          {"name": "Corenexgen AI Technologies Pvt Ltd", "email": "corenexgenaipvtltd@gmail.com",
           "address": "Registered office address — to be filled in", "phone": "Phone — to be filled in",
           "gstin": "", "website": ""}),
]
BY_KEY = {f.key: f for f in FIELDS}
EPOCH = dt.date(2017, 7, 1)

_versions: list[dict] = []
_plan_overrides: dict = {}
_plans_default: dict | None = None


# ================================================================ reading
def _sorted(versions: list[dict]) -> list[dict]:
    return sorted(versions, key=lambda v: (v["effective_from"], v.get("at") or ""))


_memo: dict[dt.date, dict] = {}


def effective(on: dt.date | None = None) -> dict:
    """Values in force on a date. Treat the result as read-only (it is shared)."""
    on = on or dt.date.today()
    if on in _memo:
        return _memo[on]
    out = {f.key: copy.deepcopy(f.default) for f in FIELDS}
    for v in _sorted(_versions):
        if dt.date.fromisoformat(v["effective_from"]) <= on:
            out.update({k: copy.deepcopy(x) for k, x in v["values"].items() if k in BY_KEY})
    if len(_memo) > 2000:
        _memo.clear()
    _memo[on] = out
    return out


def get(key: str, on: dt.date | None = None):
    value = effective(on)[key]
    return Decimal(str(value)) if BY_KEY[key].type in ("money", "number") else value


def rates_on(on: dt.date | None = None) -> list[Decimal]:
    return [Decimal(str(r)) for r in effective(on)["gst_rates"]]


def all_rates() -> set[Decimal]:
    rates = {Decimal(str(r)) for r in BY_KEY["gst_rates"].default}
    for v in _versions:
        rates |= {Decimal(str(r)) for r in v["values"].get("gst_rates", [])}
    return rates


def composition_rate(category: str | None, on: dt.date | None = None) -> Decimal:
    rates = effective(on)["composition_rates"]
    return Decimal(str(rates.get(category or "TRADER", rates.get("TRADER", 1))))


def app_name() -> str:
    return effective()["brand"].get("app_name") or "SmartHisab"


def public(on: dt.date | None = None) -> dict:
    """What every client may see (used by /api/meta)."""
    return copy.deepcopy(effective(on))


# ================================================================ loading / applying
def _apply_globals() -> None:
    """Keep module-level masters (used across the codebase) in step with today's values."""
    today = effective()
    for target, values in ((STATES, today["states"]), (UQC, today["uqc"])):
        target.clear()
        target.update(values)
    GST_RATES[:] = sorted(all_rates())

    from . import plans as P  # local import: plans imports this module lazily too
    global _plans_default
    if _plans_default is None:
        _plans_default = {"plans": copy.deepcopy(P.PLANS), "addon": copy.deepcopy(P.ADDON)}
    for code, base in _plans_default["plans"].items():
        P.PLANS[code] = {**copy.deepcopy(base), **_decode_plan(_plan_overrides.get(code, {}))}
    P.ADDON.clear()
    P.ADDON.update({**copy.deepcopy(_plans_default["addon"]), **_decode_plan(_plan_overrides.get(P.ADDON_CODE, {}))})


def _decode_plan(o: dict) -> dict:
    return {k: Decimal(str(v)) if k in ("monthly", "yearly") and v is not None else v for k, v in o.items()}


def load(db: Session) -> None:
    global _versions, _plan_overrides
    row = db.get(PlatformSetting, "config")
    plans_row = db.get(PlatformSetting, "plans")
    versions = list((row.value or {}).get("versions", [])) if row else []
    overrides = dict(plans_row.value or {}) if plans_row else {}
    if versions != _versions or overrides != _plan_overrides or _plans_default is None:
        _versions, _plan_overrides = versions, overrides
        _memo.clear()
        _apply_globals()


def refresh_dep(db: Session = Depends(get_db)) -> None:
    """App-wide dependency: reload configuration at the start of each request."""
    try:
        load(db)
    except Exception:  # noqa: BLE001 — a config read must never take the app down
        db.rollback()


def plan_defaults() -> dict:
    return _plans_default or {}


def plan_overrides() -> dict:
    return copy.deepcopy(_plan_overrides)


# ================================================================ writing (super admin)
class ConfigError(ValueError):
    pass


def _num(v, label) -> float:
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        raise ConfigError(f"{label}: '{v}' is not a number") from None
    if d < 0:
        raise ConfigError(f"{label}: cannot be negative")
    return float(d)


def clean_values(values: dict) -> dict:
    out = {}
    for key, v in values.items():
        f = BY_KEY.get(key)
        if f is None:
            raise ConfigError(f"Unknown setting '{key}'")
        if f.type in ("money", "number"):
            out[key] = _num(v, f.label)
        elif f.type == "int":
            n = _num(v, f.label)
            if n != int(n) or n < 1:
                raise ConfigError(f"{f.label}: must be a whole number")
            out[key] = int(n)
        elif f.type == "bool":
            if isinstance(v, str):
                v = v.strip().lower() in ("1", "true", "yes", "on")
            out[key] = bool(v)
        elif f.type == "text":
            if not str(v).strip():
                raise ConfigError(f"{f.label}: cannot be empty")
            out[key] = str(v).strip()
        elif f.type == "rates":
            rates = sorted({_num(x, f.label) for x in (v or [])})
            if not rates or any(r > 100 for r in rates):
                raise ConfigError(f"{f.label}: give at least one rate between 0 and 100")
            out[key] = rates
        elif f.type == "list":
            items = [str(x).strip() for x in (v or []) if str(x).strip()]
            out[key] = items
        elif f.type in ("map_text", "map_number"):
            if not isinstance(v, dict) or not v:
                raise ConfigError(f"{f.label}: add at least one entry")
            m = {}
            for k, x in v.items():
                k = str(k).strip()
                if not k:
                    raise ConfigError(f"{f.label}: code cannot be empty")
                m[k.upper() if key in ("uqc", "composition_rates") else k] = (
                    _num(x, f"{f.label} {k}") if f.type == "map_number" else str(x).strip())
            if key == "states" and any(not (c.isdigit() and len(c) == 2) for c in m):
                raise ConfigError("State codes must be 2 digits")
            out[key] = m
    return out


def _save(db: Session, key: str, value) -> None:
    row = db.get(PlatformSetting, key) or PlatformSetting(key=key)
    row.value = value
    db.add(row)
    db.commit()
    load(db)


def add_version(db: Session, effective_from: dt.date, values: dict, note: str | None, by: str) -> dict:
    if effective_from < EPOCH:
        raise ConfigError("Effective date cannot be before GST started (1 July 2017)")
    cleaned = clean_values(values)
    if not cleaned:
        raise ConfigError("Change at least one value")
    v = {"id": uuid.uuid4().hex, "effective_from": effective_from.isoformat(), "values": cleaned,
         "note": (note or "").strip() or None, "by": by, "at": dt.datetime.now(dt.UTC).isoformat()}
    _save(db, "config", {"versions": [*_versions, v]})
    return v


def delete_version(db: Session, version_id: str) -> dict:
    v = next((x for x in _versions if x["id"] == version_id), None)
    if v is None:
        raise ConfigError("Version not found")
    _save(db, "config", {"versions": [x for x in _versions if x["id"] != version_id]})
    return v


def versions() -> list[dict]:
    return list(reversed(_sorted(_versions)))


PLAN_KEYS = {"name": str, "audience": str, "monthly": "money", "yearly": "money", "invoices_per_month": "limit",
             "invoices_per_year": "limit", "businesses": "limit", "users": "limit", "godowns": "limit",
             "einvoice": ("JSON", "API", None), "gst_json": bool, "gstr2b": bool, "api_quota": "limit",
             "audit_view": bool, "custom_themes": bool, "watermark": bool, "barcode": bool, "custom_roles": bool,
             "tally": bool, "backup_mb": "limit", "highlights": list}


def set_plan_overrides(db: Session, code: str, values: dict) -> dict:
    from . import plans as P
    if code not in P.PLANS and code != P.ADDON_CODE:
        raise ConfigError("Unknown plan")
    allowed = {"name": str, "yearly": "money", "businesses": "limit"} if code == P.ADDON_CODE else PLAN_KEYS
    clean = {}
    for k, v in values.items():
        t = allowed.get(k)
        if t is None:
            raise ConfigError(f"'{k}' cannot be changed")
        if t == "money":
            clean[k] = _num(v, k)
        elif t == "limit":
            clean[k] = None if v in (None, "") else int(_num(v, k))
        elif t is bool:
            clean[k] = bool(v)
        elif t is list:
            clean[k] = [str(x).strip() for x in v if str(x).strip()]
        elif isinstance(t, tuple):
            if v not in t:
                raise ConfigError(f"{k} must be one of {t}")
            clean[k] = v
        else:
            clean[k] = str(v).strip()
    base = (_plans_default or {}).get("addon" if code == P.ADDON_CODE else "plans", {})
    base = base if code == P.ADDON_CODE else base.get(code, {})
    # store only the differences from the built-in defaults
    diff = {k: v for k, v in clean.items() if _jsonable(base.get(k)) != v}
    overrides = {**_plan_overrides}
    if diff:
        overrides[code] = diff
    else:
        overrides.pop(code, None)
    _save(db, "plans", overrides)
    return diff


def _jsonable(v):
    return float(v) if isinstance(v, Decimal) else v
