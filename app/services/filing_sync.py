"""Fetch GST return filing status (GSTR-1, GSTR-3B, CMP-08, GSTR-4, GSTR-9) from the GST data provider and mark the
matching items of the compliance calendar as filed.

Provider: gstinapi.in  GET /v1/gstin/{gstin}/returns?fy=2025-26  (same API key as GSTIN verification) — one call
returns every return filed in that financial year. The GST portal's own response shape (EFiledlist with
rtntype / ret_prd / dof / arn) is understood too, in case the provider passes it through.

Saving API credit
  * one call per financial year, and only for years that still have unfiled GST returns in the calendar
  * a year is not fetched again within `filing_sync_hours` (super admin setting) of the last fetch
  * filings already recorded (by sync or by hand) are never changed

Income tax, TDS, MCA / LLP and PF / ESI have no public filing-status API — those stay "mark as filed".
"""

import datetime as dt

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Business, ComplianceFiling
from . import compliance_calendar as CC
from . import gstin_verify as G

SYNCABLE = {"GSTR1_M", "GSTR1_Q", "GSTR3B_M", "GSTR3B_Q", "CMP08", "GSTR4", "GSTR9"}


def _fy_of_month(y: int, m: int) -> int:
    return y if m >= 4 else y - 1


def _quarter_key(y: int, m: int) -> str:
    return f"FY{_fy_of_month(y, m)}-Q{((m - 4) % 12) // 3 + 1}"


def _fy_of_item(item: dict) -> int:
    k = item["period_key"]
    if k.startswith("FY"):
        return int(k[2:6])
    y, m = int(k[:4]), int(k[5:7])
    return _fy_of_month(y, m)


def _parse_date(s) -> dt.date | None:
    if not s:
        return None
    s = str(s).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _period(s) -> tuple[int, int] | None:
    """'2025-06' / '062025' / '06-2025' -> (2025, 6)."""
    s = str(s or "").strip().replace("/", "-")
    try:
        if len(s) == 7 and s[4] == "-":
            return int(s[:4]), int(s[5:7])
        if len(s) == 6 and s.isdigit():
            return int(s[2:]), int(s[:2])
        if len(s) == 7 and s[2] == "-":
            return int(s[3:]), int(s[:2])
    except ValueError:
        return None
    return None


def _rtype(s) -> str:
    t = str(s or "").upper().replace("-", "").replace(" ", "")
    return {"R1": "GSTR1", "R3B": "GSTR3B", "R9": "GSTR9", "R4": "GSTR4"}.get(t, t)


def parse(body: dict) -> list[dict]:
    """Provider answer -> [{type, year, month, filed_on, arn}] for filed returns."""
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    rows = data.get("returns") or data.get("EFiledlist") or data.get("filings") or []
    out = []
    for r in rows if isinstance(rows, list) else []:
        status = str(r.get("filing_status") or r.get("status") or "Filed").lower()
        valid = str(r.get("valid") or "Y").upper()
        if "filed" not in status or "not" in status or "pending" in status or valid == "N":
            continue
        per = _period(r.get("return_period") or r.get("ret_prd") or r.get("period"))
        if not per:
            continue
        out.append(dict(type=_rtype(r.get("return_type") or r.get("rtntype")), year=per[0], month=per[1],
                        filed_on=_parse_date(r.get("filing_date") or r.get("dof")), arn=(r.get("arn") or None)))
    return out


def keys_for(ret: dict) -> list[tuple[str, str]]:
    """Calendar items (rule code, period key) a filed return can satisfy."""
    y, m, t = ret["year"], ret["month"], ret["type"]
    month_key, q_key, fy_key = f"{y}-{m:02d}", _quarter_key(y, m), f"FY{_fy_of_month(y, m)}"
    if t == "GSTR1":
        return [("GSTR1_M", month_key), ("GSTR1_Q", q_key)]
    if t == "GSTR3B":
        return [("GSTR3B_M", month_key), ("GSTR3B_Q", q_key)]
    if t == "CMP08":
        return [("CMP08", q_key)]
    if t in ("GSTR4", "GSTR9"):
        # annual returns are reported against the financial year (period = March, or the year's first month)
        fy = _fy_of_month(y, m) if m != 3 else y - 1
        return [(t, f"FY{fy}"), (t, fy_key)]
    return []


def sync(db: Session, biz: Business, rules: list[dict], user_name: str, today: dt.date | None = None) -> dict:
    s = G.settings(db)
    if not (s.get("enabled") and G._key(s)) or not s.get("filing_sync", True):
        raise HTTPException(503, "Fetching filing status is not switched on by the platform administrator — mark filings yourself.")
    if not biz.gstin or biz.gst_type.value not in ("REGULAR", "COMPOSITION"):
        raise HTTPException(400, "Only GST-registered businesses (with a GSTIN) can fetch return status.")
    today = today or dt.date.today()
    hours = int(s.get("filing_sync_hours") or 24)
    done = {(r.rule_code, r.period_key) for r in db.scalars(select(ComplianceFiling).where(ComplianceFiling.business_id == biz.id))}
    cal = CC.calendar_for(biz, rules, {k: {"id": ""} for k in done}, today=today, ahead_days=31)  # also returns filed early
    applicable = {i["code"] for i in cal["items"]}
    pending = [i for i in cal["items"] if i["code"] in SYNCABLE and i["status"] != "DONE"]
    years = sorted({_fy_of_item(i) for i in pending})

    cs = dict(biz.compliance_settings or {})
    log: dict = dict(cs.get("sync") or {})
    now = dt.datetime.now(dt.UTC)
    fetched, skipped, added, errors = [], [], 0, []
    for fy in years:
        label = f"{fy}-{str(fy + 1)[-2:]}"
        last = log.get(label)
        if last and now - dt.datetime.fromisoformat(last) < dt.timedelta(hours=hours):
            skipped.append(label)
            continue
        try:
            body, _ = G._call(s, f"gstin/{biz.gstin}/returns?fy={label}")
        except G.ProviderError as e:
            errors.append(f"{label}: {G.FRIENDLY.get(e.status, 'the GST data service did not answer')}")
            continue
        fetched.append(label)
        log[label] = now.isoformat()
        for ret in parse(body):
            for code, key in keys_for(ret):
                if code not in applicable or (code, key) in done:
                    continue
                db.add(ComplianceFiling(business_id=biz.id, rule_code=code, period_key=key, source="SYNC",
                                        done_on=ret["filed_on"] or today, reference=ret["arn"], by=f"GST portal (synced by {user_name})"))
                done.add((code, key))
                added += 1
    cs["sync"] = log
    cs["last_sync_at"] = now.isoformat()
    biz.compliance_settings = cs
    db.commit()
    if not years:
        msg = "All GST returns in the calendar are already marked as filed — nothing to fetch."
    elif not fetched and skipped and not errors:
        msg = f"Already fetched in the last {hours} hours — try again later."
    else:
        msg = f"{added} return{'s' if added != 1 else ''} marked as filed from the GST portal." + (" " + " ".join(errors) if errors else "")
    return dict(fetched_years=fetched, skipped_years=skipped, added=added, calls=len(fetched), errors=errors, message=msg)
