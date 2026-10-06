"""Compliance calendar: which returns / filings a business must make, when, and what a delay costs.

The rules live in the platform configuration (`compliance_rules`, Admin → GST config → Compliance calendar), so
the super admin can change a due date, add a filing or update a penalty without a code release. Each rule:

    code, name, authority (GST | INCOME_TAX | TDS | MCA | LLP | PAYROLL), description, penalty, link (key of `links`)
    applies:   {"gst": [REGULAR|COMPOSITION|UNREGISTERED], "gst_filing": MONTHLY|QUARTERLY,
                "entities": [PROPRIETORSHIP, ...], "requires": [flags], "excludes": [flags]}   (missing = any)
    frequency: MONTHLY | QUARTERLY | YEARLY
    due:       MONTHLY / QUARTERLY: {"months_after": 1, "day": 20, "state_day": {"27": 22}}  — day 31 = month end
               YEARLY: {"dates": [{"month": 7, "day": 31, "label": "..."}], "within_fy": false}
               (within_fy: dates fall inside the financial year, e.g. advance tax; otherwise in the year after it)
    month_overrides / quarter_overrides: {"3": {...due...}}   e.g. TDS for March is due on 30 April
    months_in_quarter: [1, 2]   monthly items only in these months of each quarter (QRMP tax payment)
    fee_per_day: number or a config key ("late_fee_per_day"), fee_cap: highest late fee — a rough "late fee so far" figure

Business answers (compliance_settings): gst_filing, tax_audit, tds, payroll, track_from.
Whether a filing was made is recorded by the user ("mark as filed") — the app cannot see the government portals.
"""

import calendar
import datetime as dt
from decimal import Decimal

from . import config_store as C

from .compliance_rules import DEFAULT_RULES  # noqa: F401 — re-exported

AUTHORITIES = {"GST": "GST", "INCOME_TAX": "Income tax", "TDS": "TDS", "MCA": "Company law (MCA)",
               "LLP": "LLP (MCA)", "PAYROLL": "PF / ESI"}

DISCLAIMER = ("Due dates and penalties are indicative and are kept up to date by the platform team. The government often "
              "extends due dates or changes rules — please confirm on the official portal or with your tax professional "
              "before relying on them.")

SETTINGS_DEFAULT = {"gst_filing": "MONTHLY", "tax_audit": False, "tds": False, "payroll": False, "track_from": None}


# ================================================================ helpers
def _date(year: int, month: int, day: int) -> dt.date:
    while month > 12:
        month, year = month - 12, year + 1
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _fy_start(d: dt.date) -> int:
    return d.year if d.month >= 4 else d.year - 1


def _fy_label(y: int) -> str:
    return f"FY {y}-{str(y + 1)[-2:]}"


def registration_date(biz) -> dt.date | None:
    return getattr(biz, "gst_registration_date", None)


def settings(biz) -> dict:
    """Business answers. Tracking starts on the GST registration date when known (else the day the business joined)."""
    s = {**SETTINGS_DEFAULT, **(biz.compliance_settings or {})}
    reg = registration_date(biz)
    if not s.get("track_from"):
        s["track_from"] = (reg or (biz.created_at.date() if biz.created_at else dt.date.today())).isoformat()
    elif reg and dt.date.fromisoformat(s["track_from"]) < reg:
        s["track_from"] = reg.isoformat()  # nothing was due before the business was registered
    s["registration_date"] = reg.isoformat() if reg else None
    return s


def _before_registration(o: dict, reg: dt.date | None) -> bool:
    """A period that ended before the registration date never had to be filed."""
    return bool(reg) and o["period_end"] < reg


def applies(rule: dict, biz, s: dict) -> bool:
    if rule.get("disabled"):
        return False  # switched off by the super admin
    a = rule.get("applies") or {}
    gst = biz.gst_type.value if hasattr(biz.gst_type, "value") else str(biz.gst_type)
    if a.get("gst") and gst not in a["gst"]:
        return False
    if a.get("gst_filing") and (s.get("gst_filing") or "MONTHLY") != a["gst_filing"]:
        return False
    if a.get("entities") and (biz.entity_type or "PROPRIETORSHIP") not in a["entities"]:
        return False
    if any(not s.get(f) for f in a.get("requires") or []):
        return False
    return not any(s.get(f) for f in a.get("excludes") or [])


def _fee_per_day(rule: dict) -> Decimal | None:
    f = rule.get("fee_per_day")
    if f is None:
        return None
    if isinstance(f, str):
        try:
            return Decimal(str(C.get(f)))
        except Exception:  # noqa: BLE001 — unknown config key: no estimate
            return None
    return Decimal(str(f))


def render(text: str | None) -> str:
    """Fill {config_key} placeholders (e.g. {late_fee_per_day}) with today's configured values."""
    if not text:
        return ""
    values = C.effective()
    out = text
    for key in ("late_fee_per_day", "interest_rate"):
        v = values.get(key)
        out = out.replace("{" + key + "}", f"{float(v):g}" if v is not None else "")
    return out


# ================================================================ occurrences
def occurrences(rule: dict, state_code: str, start: dt.date, end: dt.date) -> list[dict]:
    """Every (period, due date) of a rule whose due date falls between start and end."""
    out = []
    freq = rule.get("frequency")
    due = rule.get("due") or {}

    def due_on(base_year, base_month, spec):
        day = (spec.get("state_day") or {}).get(state_code, spec.get("day", 1))
        return _date(base_year, base_month + int(spec.get("months_after", 1)), int(day))

    if freq == "MONTHLY":
        y, m = start.year - 1, start.month
        while (y, m) <= (end.year, end.month):
            q_pos = ((m - 4) % 3) + 1  # 1st / 2nd / 3rd month of the FY quarter
            if not rule.get("months_in_quarter") or q_pos in rule["months_in_quarter"]:
                spec = {**due, **((rule.get("month_overrides") or {}).get(str(m)) or {})}
                d = due_on(y, m, spec)
                if start <= d <= end:
                    out.append(dict(period_key=f"{y}-{m:02d}", period=dt.date(y, m, 1).strftime("%b %Y"),
                                    period_start=dt.date(y, m, 1), period_end=_date(y, m, 31), due_date=d))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    elif freq == "QUARTERLY":
        for fy in range(_fy_start(start) - 1, _fy_start(end) + 1):
            for q in range(1, 5):
                q_end_month = 3 + 3 * q  # 6, 9, 12, 15(=Mar next year)
                q_start = _date(fy, q_end_month - 2, 1)
                spec = {**due, **((rule.get("quarter_overrides") or {}).get(str(q)) or {})}
                d = due_on(fy, q_end_month, spec)
                if start <= d <= end:
                    last = _date(fy, q_end_month, 1)
                    out.append(dict(period_key=f"FY{fy}-Q{q}", period_start=q_start, period_end=_date(fy, q_end_month, 31), due_date=d,
                                    period=f"{q_start.strftime('%b')}–{last.strftime('%b %Y')} (Q{q} {_fy_label(fy)})"))
    elif freq == "YEARLY":
        dates = due.get("dates") or []
        for fy in range(_fy_start(start) - 2, _fy_start(end) + 1):
            for i, spec in enumerate(dates):
                month, day = int(spec["month"]), int(spec["day"])
                if due.get("within_fy"):
                    year = fy if month >= 4 else fy + 1
                else:
                    year = fy + 1
                d = _date(year, month, day)
                if start <= d <= end:
                    key = f"FY{fy}" + (f"#{i + 1}" if len(dates) > 1 else "")
                    label = _fy_label(fy) + (f" · {spec['label']}" if spec.get("label") else "")
                    out.append(dict(period_key=key, period=label, period_start=dt.date(fy, 4, 1), period_end=dt.date(fy + 1, 3, 31), due_date=d))
    return out


def calendar_for(biz, rules: list[dict], done: dict[tuple[str, str], dict], today: dt.date | None = None,
                 ahead_days: int = 120) -> dict:
    """The business's filings to `ahead_days` ahead, with status: pending ones from `track_from`, filed ones (by hand or
    from the GST portal) from up to ~15 months back. Nothing from before the registration date."""
    today = today or dt.date.today()
    s = settings(biz)
    track_from = dt.date.fromisoformat(s["track_from"])
    reg = registration_date(biz)
    start = today - dt.timedelta(days=460)
    end = today + dt.timedelta(days=ahead_days)
    items = []
    for rule in rules:
        if not applies(rule, biz, s):
            continue
        fee = _fee_per_day(rule)
        for o in occurrences(rule, biz.state_code, start, end):
            rec = done.get((rule["code"], o["period_key"]))
            if _before_registration(o, reg) or (not rec and o["due_date"] < track_from):
                continue
            days = (today - o["due_date"]).days
            status = "DONE" if rec else "OVERDUE" if days > 0 else "DUE_SOON" if days >= -15 else "UPCOMING"
            items.append(dict(
                code=rule["code"], name=rule["name"], authority=rule.get("authority", ""),
                authority_label=AUTHORITIES.get(rule.get("authority", ""), rule.get("authority", "")),
                description=render(rule.get("description")), penalty=render(rule.get("penalty")),
                link=rule.get("link"), period_key=o["period_key"], period=o["period"],
                due_date=o["due_date"], status=status, days_overdue=max(days, 0) if not rec else 0,
                days_left=max(-days, 0), done=rec,
                late_fee_so_far=float(min(fee * days, Decimal(str(rule.get("fee_cap") or fee * days))))
                if fee is not None and status == "OVERDUE" else None,
            ))
    order = {"OVERDUE": 0, "DUE_SOON": 1, "UPCOMING": 2, "DONE": 3}
    items.sort(key=lambda x: (order[x["status"]], x["due_date"] if x["status"] != "DONE" else -x["due_date"].toordinal()))
    summary = {k: sum(1 for i in items if i["status"] == k) for k in order}
    return dict(settings=s, items=items, summary=summary, disclaimer=DISCLAIMER,
                entity_type=biz.entity_type, gst_type=biz.gst_type.value if hasattr(biz.gst_type, "value") else biz.gst_type)


# ================================================================ validation (super admin edits)
def clean_rules(rules) -> list[dict]:
    if not isinstance(rules, list) or not rules:
        raise ValueError("Compliance rules must be a non-empty list")
    seen = set()
    for r in rules:
        if not isinstance(r, dict):
            raise ValueError("Each compliance rule must be an object")
        code = str(r.get("code") or "").strip()
        if not code or code in seen:
            raise ValueError(f"Rule code '{code}' is missing or repeated")
        seen.add(code)
        if not str(r.get("name") or "").strip():
            raise ValueError(f"{code}: name is required")
        freq = r.get("frequency")
        due = r.get("due")
        if freq not in ("MONTHLY", "QUARTERLY", "YEARLY") or not isinstance(due, dict):
            raise ValueError(f"{code}: frequency must be MONTHLY, QUARTERLY or YEARLY, with a 'due' object")
        if freq == "YEARLY":
            dates = due.get("dates")
            if not isinstance(dates, list) or not dates or any(
                    not (1 <= int(d.get("month", 0)) <= 12 and 1 <= int(d.get("day", 0)) <= 31) for d in dates):
                raise ValueError(f"{code}: yearly rules need 'dates' with month (1-12) and day (1-31)")
        elif not (1 <= int(due.get("day", 0)) <= 31 and 0 <= int(due.get("months_after", 1)) <= 12):
            raise ValueError(f"{code}: 'due' needs day (1-31) and months_after (0-12)")
    return rules


# ================================================================ register (one law, one financial year)
def register(biz, rules: list[dict], done: dict[tuple[str, str], dict], fy: int, law: str,
             today: dt.date | None = None) -> dict:
    """Every filing of `law` for financial year `fy` (Apr fy – Mar fy+1), whatever its due date: for the
    month-by-month / quarter-by-quarter tables of the compliance page. Periods due before the business's
    "track from" date and not recorded are shown as NOT_TRACKED rather than overdue."""
    today = today or dt.date.today()
    s = settings(biz)
    track_from = dt.date.fromisoformat(s["track_from"])
    fy_start, fy_end = dt.date(fy, 4, 1), dt.date(fy + 1, 3, 31)
    rows = []
    for rule in rules:
        if rule.get("authority") != law or not applies(rule, biz, s):
            continue
        fee = _fee_per_day(rule)
        for o in occurrences(rule, biz.state_code, fy_start, dt.date(fy + 2, 12, 31)):
            if not (fy_start <= o["period_start"] <= fy_end) or _before_registration(o, registration_date(biz)):
                continue
            rec = done.get((rule["code"], o["period_key"]))
            days = (today - o["due_date"]).days
            if rec:
                st = "DONE"
            elif days > 0:
                st = "NOT_TRACKED" if o["due_date"] < track_from else "OVERDUE"
            else:
                st = "DUE_SOON" if days >= -15 else "UPCOMING"
            rows.append(dict(
                code=rule["code"], name=rule["name"], frequency=rule.get("frequency"), period_key=o["period_key"],
                period=o["period"], period_start=o["period_start"], due_date=o["due_date"], status=st,
                days_overdue=max(days, 0) if st == "OVERDUE" else 0, days_left=max(-days, 0), done=rec,
                penalty=render(rule.get("penalty")) if st == "OVERDUE" else None,
                late_fee_so_far=float(min(fee * days, Decimal(str(rule.get("fee_cap") or fee * days))))
                if fee is not None and st == "OVERDUE" else None,
                link=rule.get("link"),
            ))
    rows.sort(key=lambda r: (r["period_start"], r["due_date"]))
    columns = []
    for r in rows:  # filings in rule order, once each
        if r["code"] not in [c["code"] for c in columns]:
            columns.append(dict(code=r["code"], name=r["name"], frequency=r["frequency"]))
    return dict(fy=fy, fy_label=f"{fy}-{str(fy + 1)[-2:]}", law=law, columns=columns, rows=rows,
                track_from=s["track_from"], laws=[a for a in AUTHORITIES if any(r.get("authority") == a and applies(r, biz, s) for r in rules)])
