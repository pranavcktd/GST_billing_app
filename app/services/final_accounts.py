"""Final accounts for practitioners' clients: trial balance → P&L, balance sheet, capital accounts,
depreciation, notes, ratios and checks, with an explanation for every figure ("learn mode").

Format: ICAI format for non-corporate entities (proprietorship / partnership), vertical.

File data (PracticeFile.data):
  entity_type: PROPRIETORSHIP | PARTNERSHIP
  ledgers:  [{id, name, group, head, partner, cy, py}]   amounts signed: debit +, credit −
  closing_stock: {cy, py}
  depreciation: {method: IT | CA, assets: [...], py_amount}
  partners: [{id, name, pan, share, interest_rate, remuneration}]
  py: {ppe}     previous-year figures that don't come from ledgers (carried forward)
"""

import datetime as dt
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from . import config_store

ZERO = Decimal("0")
CENT = Decimal("0.01")


def D(v) -> Decimal:
    if v is None or v == "":
        return ZERO
    try:
        return Decimal(str(v)).quantize(CENT)
    except (InvalidOperation, ValueError):
        return ZERO


# ================================================================ heads
# code: (section, label, nature Dr/Cr, explanation)
HEADS: dict[str, tuple[str, str, str, str]] = {
    "REVENUE": ("P&L", "Revenue from operations (sales / services)", "Cr",
                "Sales of goods and services, net of returns and GST. GST collected is not income — it belongs under "
                "other current liabilities until paid."),
    "OTHER_INCOME": ("P&L", "Other income", "Cr",
                     "Income not from the main business: interest received, rent received, discount received, "
                     "commission, profit on sale of assets."),
    "OPENING_STOCK": ("P&L", "Opening stock", "Dr",
                      "Stock on hand at the start of the year — the same figure as last year's closing stock."),
    "PURCHASES": ("P&L", "Purchases of stock-in-trade / raw material", "Dr",
                  "Goods bought for resale or production, net of purchase returns. Excludes GST when input credit is claimed."),
    "DIRECT_EXP": ("P&L", "Direct expenses", "Dr",
                   "Costs of making or bringing goods to sale: wages, freight / carriage inward, power & fuel, job work."),
    "EMPLOYEE": ("P&L", "Employee benefit expenses", "Dr", "Salaries, bonus, staff welfare, PF / ESI contribution."),
    "FINANCE": ("P&L", "Finance costs", "Dr", "Interest on loans and overdraft, loan processing fees, bank charges."),
    "OTHER_EXP": ("P&L", "Other expenses", "Dr",
                  "Running costs of the business: rent, electricity, telephone, travel, repairs, professional fees, "
                  "printing & stationery, advertisement and similar."),
    "DEPRECIATION_BOOKED": ("P&L", "Depreciation (already booked in the ledgers)", "Dr",
                            "Depreciation already entered in the books. Leave the depreciation schedule empty in this "
                            "case, or depreciation will be counted twice."),
    "PARTNER_INTEREST": ("P&L", "Interest on partners' capital", "Dr",
                         "Interest paid to partners on their capital, as per the partnership deed."),
    "PARTNER_REMUNERATION": ("P&L", "Remuneration to partners", "Dr",
                             "Salary / remuneration paid to working partners, as per the partnership deed."),
    "TAX_EXPENSE": ("P&L", "Tax expense", "Dr", "Income tax of the firm for the year (partnership firms pay tax themselves)."),
    "CAPITAL": ("Capital", "Capital account", "Cr",
                "Money the owner / partners have in the business, as per the capital ledger before this year's profit."),
    "DRAWINGS": ("Capital", "Drawings", "Dr",
                 "Money or goods taken out by the owner / partners for personal use. Reduces capital, not profit."),
    "LT_SECURED": ("Liabilities", "Long-term borrowings — secured", "Cr",
                   "Loans against security: term loans, vehicle and machinery loans, home loan for business property."),
    "LT_UNSECURED": ("Liabilities", "Long-term borrowings — unsecured", "Cr",
                     "Loans without security, e.g. from relatives, friends or other parties."),
    "ST_BORROWINGS": ("Liabilities", "Short-term borrowings (OD / cash credit)", "Cr",
                      "Bank overdraft and cash-credit accounts, repayable on demand."),
    "TRADE_PAYABLES": ("Liabilities", "Trade payables (sundry creditors)", "Cr",
                       "Amounts owed to suppliers for goods and services bought on credit."),
    "OTHER_CUR_LIAB": ("Liabilities", "Other current liabilities", "Cr",
                       "GST / TDS payable, expenses payable (salary, rent, audit fee), advances received from customers."),
    "PROVISIONS": ("Liabilities", "Short-term provisions", "Cr", "Provision for tax and other provisions."),
    "FIXED_ASSETS": ("Assets", "Property, plant & equipment (fixed assets)", "Dr",
                     "Assets used in the business for more than a year: land, building, machinery, furniture, "
                     "vehicles, computers. Shown net of depreciation."),
    "INVESTMENTS": ("Assets", "Investments", "Dr", "Fixed deposits, mutual funds, shares and similar investments."),
    "LT_LOANS_ADV": ("Assets", "Long-term loans, advances & deposits", "Dr",
                     "Security deposits (rent, electricity, telephone) and loans given for more than a year."),
    "TRADE_RECEIVABLES": ("Assets", "Trade receivables (sundry debtors)", "Dr",
                          "Amounts customers owe for goods and services sold on credit."),
    "CASH_BANK": ("Assets", "Cash and bank balances", "Dr", "Cash in hand and balances in current / savings accounts."),
    "ST_LOANS_ADV": ("Assets", "Short-term loans & advances", "Dr",
                     "Advances to suppliers and staff, prepaid expenses, GST input credit, TDS / TCS receivable, advance tax."),
    "OTHER_CUR_ASSETS": ("Assets", "Other current assets", "Dr", "Interest accrued, other receivables."),
    "SUSPENSE": ("Check", "Suspense / difference", "Dr",
                 "Amounts that could not be classified. Resolve before finalising the accounts."),
}
PL_HEADS = [h for h, v in HEADS.items() if v[0] == "P&L"]

# Tally (and similar) group names → head
GROUPS = {
    "sales accounts": "REVENUE", "direct incomes": "REVENUE", "income (direct)": "REVENUE",
    "indirect incomes": "OTHER_INCOME", "income (indirect)": "OTHER_INCOME",
    "purchase accounts": "PURCHASES", "direct expenses": "DIRECT_EXP", "expenses (direct)": "DIRECT_EXP",
    "indirect expenses": "OTHER_EXP", "expenses (indirect)": "OTHER_EXP",
    "capital account": "CAPITAL", "reserves & surplus": "CAPITAL",
    "secured loans": "LT_SECURED", "unsecured loans": "LT_UNSECURED", "loans (liability)": "LT_UNSECURED",
    "bank od a/c": "ST_BORROWINGS", "bank occ a/c": "ST_BORROWINGS", "bank od accounts": "ST_BORROWINGS",
    "sundry creditors": "TRADE_PAYABLES", "duties & taxes": "OTHER_CUR_LIAB", "current liabilities": "OTHER_CUR_LIAB",
    "provisions": "PROVISIONS", "fixed assets": "FIXED_ASSETS", "investments": "INVESTMENTS",
    "deposits (asset)": "LT_LOANS_ADV", "sundry debtors": "TRADE_RECEIVABLES", "bank accounts": "CASH_BANK",
    "cash-in-hand": "CASH_BANK", "cash in hand": "CASH_BANK", "loans & advances (asset)": "ST_LOANS_ADV",
    "current assets": "OTHER_CUR_ASSETS", "stock-in-hand": "OPENING_STOCK", "suspense a/c": "SUSPENSE",
    "misc. expenses (asset)": "OTHER_CUR_ASSETS",
}
# ledger-name keywords, most specific first
KEYWORDS: list[tuple[str, str]] = [
    (r"interest on (partners'? )?capital", "PARTNER_INTEREST"), (r"partners?'? (salary|remuneration)|remuneration to partner", "PARTNER_REMUNERATION"),
    (r"drawing", "DRAWINGS"), (r"capital", "CAPITAL"),
    (r"opening stock", "OPENING_STOCK"), (r"closing stock", "SUSPENSE"),
    (r"bank charges|bank commission|processing fee|interest (paid )?on .*(loan|od|cc|cash credit|overdraft)", "FINANCE"),
    (r"depreciation", "DEPRECIATION_BOOKED"), (r"provision for (income )?tax|income tax payable", "PROVISIONS"),
    (r"income tax( expense)?$|tax expense", "TAX_EXPENSE"),
    (r"\b(od|occ|cc)\b|overdraft|cash credit", "ST_BORROWINGS"),
    (r"(term|vehicle|car|machinery|home|business|secured) loan", "LT_SECURED"), (r"unsecured|loan from", "LT_UNSECURED"),
    (r"(c|s|i|u)?gst.*(payable|output)|output (c|s|i)?gst|tds payable|tcs payable|payable|outstanding|advance from", "OTHER_CUR_LIAB"),
    (r"(c|s|i)gst|input|itc|tds|tcs|advance tax|prepaid|advance to|advance", "ST_LOANS_ADV"),
    (r"security deposit|deposit", "LT_LOANS_ADV"),
    (r"fixed deposit|\bfd\b|mutual fund|shares|investment", "INVESTMENTS"),
    (r"creditor", "TRADE_PAYABLES"), (r"debtor|receivable", "TRADE_RECEIVABLES"),
    (r"cash|bank|hdfc|sbi|icici|axis|kotak|\bpnb\b|\bbob\b|canara|union bank|yes bank|idfc|indusind", "CASH_BANK"),
    (r"furniture|building|land|machinery|plant|computer|laptop|printer|vehicle|motor|car\b|scooter|equipment|"
     r"air condition|fixture|mobile phone|software", "FIXED_ASSETS"),
    (r"purchase", "PURCHASES"), (r"sales|sale\b|turnover|revenue|service income|fees received|job work income", "REVENUE"),
    (r"interest (received|income)|discount received|rent received|commission received|dividend|other income", "OTHER_INCOME"),
    (r"wages|freight inward|carriage inward|power|fuel|factory|job work|manufactur", "DIRECT_EXP"),
    (r"salar|bonus|staff welfare|\bpf\b|\besi\b|gratuity", "EMPLOYEE"),
    (r"interest|bank charges|processing fee", "FINANCE"),
    (r"rent|electricity|telephone|internet|travel|conveyance|repair|professional|audit fee|printing|stationery|"
     r"advertis|office|insurance|postage|courier|legal|miscellaneous|misc|expense", "OTHER_EXP"),
]


REFINE = {  # a broad group, narrowed by the ledger name
    "OTHER_EXP": {"EMPLOYEE", "FINANCE", "DEPRECIATION_BOOKED", "PARTNER_INTEREST", "PARTNER_REMUNERATION", "TAX_EXPENSE"},
    "DIRECT_EXP": {"EMPLOYEE"},
    "CAPITAL": {"DRAWINGS"},
    "OTHER_CUR_LIAB": {"PROVISIONS"},
    "OTHER_CUR_ASSETS": {"ST_LOANS_ADV"},
}


def _by_name(name: str) -> str | None:
    n = (name or "").lower()
    for pattern, head in KEYWORDS:
        if re.search(pattern, n):
            return head
    return None


def auto_head(name: str, group: str | None = None) -> str | None:
    g = (group or "").strip().lower()
    by_name = _by_name(name)
    if g in GROUPS:
        head = GROUPS[g]
        return by_name if by_name in REFINE.get(head, ()) else head
    return by_name


# ================================================================ depreciation
def _date(v) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def depreciation(dep: dict, fy_from: dt.date, fy_to: dt.date) -> dict:
    """Income-tax block method (WDV, half rate < 180 days) or Companies Act useful life (SLM / WDV)."""
    method = (dep or {}).get("method") or "IT"
    assets = (dep or {}).get("assets") or []
    rows, steps = [], []
    total = {"opening": ZERO, "additions": ZERO, "deletions": ZERO, "depreciation": ZERO, "closing": ZERO}
    if method == "IT":
        rates = config_store.get("it_depreciation_rates", fy_to)
        blocks: dict[str, dict] = defaultdict(lambda: dict(opening=ZERO, add_full=ZERO, add_half=ZERO, deletions=ZERO, items=[]))
        for a in assets:
            b = blocks[a.get("block") or "Plant & machinery - general"]
            b["opening"] += D(a.get("opening"))
            amt = D(a.get("addition"))
            put = _date(a.get("addition_date"))
            if amt:
                used_days = (fy_to - put).days + 1 if put else 366
                if used_days < 180:
                    b["add_half"] += amt
                else:
                    b["add_full"] += amt
            b["deletions"] += D(a.get("sale"))
            b["items"].append(a.get("description") or "")
        for name, b in sorted(blocks.items()):
            rate = D(rates.get(name, 15))
            base_full = b["opening"] + b["add_full"] - b["deletions"]
            half = b["add_half"]
            if base_full < 0:  # sale value above opening + full additions: the excess comes off the half-rate part
                half += base_full
                base_full = ZERO
            half = max(half, ZERO)
            dep_amt = (base_full * rate / 100 + half * rate / 200).quantize(CENT)
            opening, additions = b["opening"], b["add_full"] + b["add_half"]
            closing = opening + additions - b["deletions"] - dep_amt
            rows.append(dict(block=name, rate=rate, items=", ".join(x for x in b["items"] if x), opening=opening,
                             additions_full=b["add_full"], additions_half=b["add_half"], deletions=b["deletions"],
                             depreciation=dep_amt, closing=closing))
            steps.append(f"{name} @ {rate}%: ({opening} + {b['add_full']} − {b['deletions']}) × {rate}%"
                         + (f" + {b['add_half']} × {rate / 2}% (used < 180 days)" if b["add_half"] else "") + f" = {dep_amt}")
            for k, v in (("opening", opening), ("additions", additions), ("deletions", b["deletions"]),
                         ("depreciation", dep_amt), ("closing", closing)):
                total[k] += v
    else:
        residual_pct = D(config_store.get("ca_residual_value_pct", fy_to))
        days_in_year = (fy_to - fy_from).days + 1
        for a in assets:
            cost = D(a.get("cost")) + D(a.get("addition"))
            acc_opening = D(a.get("opening_acc_dep"))
            life = D(a.get("life") or 0)
            put = _date(a.get("addition_date")) or _date(a.get("put_to_use"))
            start = max(put, fy_from) if put else fy_from
            days = max(0, (fy_to - start).days + 1) if not (put and put > fy_to) else 0
            residual = (cost * residual_pct / 100).quantize(CENT)
            opening_wdv = D(a.get("cost")) - acc_opening
            if life <= 0 or cost <= 0:
                dep_amt = ZERO
            elif (a.get("ca_method") or "SLM") == "WDV":
                rate = Decimal(str(1 - float(residual_pct / 100) ** (1 / float(life)))) if residual_pct > 0 else Decimal("1")
                dep_amt = ((opening_wdv + D(a.get("addition"))) * rate * days / days_in_year).quantize(CENT)
            else:
                dep_amt = ((cost - residual) / life * days / days_in_year).quantize(CENT)
            dep_amt = max(ZERO, min(dep_amt, cost - acc_opening - residual))
            sale = D(a.get("sale"))
            closing = opening_wdv + D(a.get("addition")) - sale - dep_amt
            rows.append(dict(block=a.get("description") or "Asset", rate=None, items=f"{a.get('ca_method') or 'SLM'}, life {life} yrs",
                             opening=opening_wdv, additions_full=D(a.get("addition")), additions_half=ZERO, deletions=sale,
                             depreciation=dep_amt, closing=closing))
            steps.append(f"{a.get('description') or 'Asset'}: {a.get('ca_method') or 'SLM'} over {life} years, {days} days this year → {dep_amt}")
            for k, v in (("opening", opening_wdv), ("additions", D(a.get("addition"))), ("deletions", sale),
                         ("depreciation", dep_amt), ("closing", closing)):
                total[k] += v
    return dict(method=method, rows=rows, total=total, steps=steps)


# ================================================================ statements
def _fy_dates(fy: str) -> tuple[dt.date, dt.date]:
    start = int(fy[:4])
    return dt.date(start, 4, 1), dt.date(start + 1, 3, 31)


def _heads_sum(ledgers: list[dict], key: str) -> tuple[dict[str, Decimal], dict[str, list]]:
    tot: dict[str, Decimal] = defaultdict(lambda: ZERO)
    items: dict[str, list] = defaultdict(list)
    for l in ledgers:
        h = l.get("head")
        if not h:
            continue
        amt = D(l.get(key))
        tot[h] += amt
        if amt:
            items[h].append({"name": l.get("name"), "amount": amt, "partner": l.get("partner")})
    return tot, items


def _year(data: dict, key: str, fy_from: dt.date, fy_to: dt.date) -> dict:
    """All figures for one year (key = 'cy' or 'py')."""
    ledgers = list(data.get("ledgers") or [])
    entity = data.get("entity_type") or "PROPRIETORSHIP"
    tot, items = _heads_sum(ledgers, key)
    sgn = lambda h: -tot[h] if HEADS[h][2] == "Cr" else tot[h]  # noqa: E731 — natural-side amount
    closing_stock = D((data.get("closing_stock") or {}).get(key))

    if key == "cy":
        dep = depreciation(data.get("depreciation") or {}, fy_from, fy_to)
        dep_amount = dep["total"]["depreciation"]
        fa_ledgers = tot["FIXED_ASSETS"]
        virtual_fa = ZERO
        if not items["FIXED_ASSETS"] and dep["rows"]:
            # manual entry: the schedule itself gives fixed assets before depreciation
            virtual_fa = dep["total"]["opening"] + dep["total"]["additions"] - dep["total"]["deletions"]
            fa_ledgers = virtual_fa
        ppe = fa_ledgers - dep_amount
    else:
        dep = None
        dep_amount = D((data.get("depreciation") or {}).get("py_amount"))
        virtual_fa = ZERO
        ppe = D((data.get("py") or {}).get("ppe")) if (data.get("py") or {}).get("ppe") not in (None, "") else tot["FIXED_ASSETS"]
    booked_dep = tot["DEPRECIATION_BOOKED"]
    total_dep = dep_amount + booked_dep

    tb_difference = sum(tot.values(), ZERO) + virtual_fa
    revenue, other_income = sgn("REVENUE"), sgn("OTHER_INCOME")
    opening_stock, purchases, direct = tot["OPENING_STOCK"], tot["PURCHASES"], tot["DIRECT_EXP"]
    change_in_stock = opening_stock - closing_stock
    employee, finance, other_exp = tot["EMPLOYEE"], tot["FINANCE"], tot["OTHER_EXP"]
    total_income = revenue + other_income
    expenses_before = purchases + change_in_stock + direct + employee + finance + total_dep + other_exp
    profit_before_appropriation = total_income - expenses_before
    gross_profit = revenue - (purchases + change_in_stock + direct)

    # ---- partners: interest & remuneration (booked in ledgers, or computed from the deed terms)
    partners = (data.get("partners") or []) if entity == "PARTNERSHIP" else []
    cap_by_partner: dict[str, Decimal] = defaultdict(lambda: ZERO)
    drw_by_partner: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for it in items["CAPITAL"]:
        cap_by_partner[it["partner"] or ""] += -it["amount"]
    for it in items["DRAWINGS"]:
        drw_by_partner[it["partner"] or ""] += it["amount"]
    booked_int: dict[str, Decimal] = defaultdict(lambda: ZERO)
    booked_rem: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for it in items["PARTNER_INTEREST"]:
        booked_int[it["partner"] or ""] += it["amount"]
    for it in items["PARTNER_REMUNERATION"]:
        booked_rem[it["partner"] or ""] += it["amount"]
    use_booked_int = bool(items["PARTNER_INTEREST"])
    use_booked_rem = bool(items["PARTNER_REMUNERATION"])
    p_rows = []
    for p in partners:
        pid = p.get("id") or p.get("name")
        capital_ledger = cap_by_partner.get(pid, ZERO)
        interest = booked_int.get(pid, ZERO) if use_booked_int else (capital_ledger * D(p.get("interest_rate")) / 100).quantize(CENT)
        remuneration = booked_rem.get(pid, ZERO) if use_booked_rem else D(p.get("remuneration"))
        p_rows.append(dict(id=pid, name=p.get("name"), share=D(p.get("share")), capital_ledger=capital_ledger,
                           interest=interest, remuneration=remuneration, drawings=drw_by_partner.get(pid, ZERO)))
    if partners:
        # booked amounts not assigned to a partner still reduce profit (and are flagged in the checks)
        interest_total = sum((r["interest"] for r in p_rows), ZERO) + (booked_int.get("", ZERO) if use_booked_int else ZERO)
        remuneration_total = sum((r["remuneration"] for r in p_rows), ZERO) + (booked_rem.get("", ZERO) if use_booked_rem else ZERO)
    else:
        interest_total, remuneration_total = tot["PARTNER_INTEREST"], tot["PARTNER_REMUNERATION"]
    profit_before_tax = profit_before_appropriation - interest_total - remuneration_total
    tax = tot["TAX_EXPENSE"]
    net_profit = profit_before_tax - tax

    # ---- capital
    if partners:
        share_total = sum((r["share"] for r in p_rows), ZERO) or Decimal("100")
        for r in p_rows:
            r["profit_share"] = (net_profit * r["share"] / share_total).quantize(CENT)
            # interest / remuneration already booked were credited to the capital ledger in the books
            add_int = ZERO if use_booked_int else r["interest"]
            add_rem = ZERO if use_booked_rem else r["remuneration"]
            r["closing"] = r["capital_ledger"] + add_int + add_rem + r["profit_share"] - r["drawings"]
        diff = net_profit - sum((r["profit_share"] for r in p_rows), ZERO)
        if p_rows and diff:
            p_rows[0]["profit_share"] += diff
            p_rows[0]["closing"] += diff
        # unassigned capital / drawings still belong to the owners (flagged in the checks)
        capital_closing = sum((r["closing"] for r in p_rows), ZERO) + cap_by_partner.get("", ZERO) - drw_by_partner.get("", ZERO)
    else:
        # interest / remuneration booked in the ledgers were credited to the capital ledger in the books
        capital_closing = sgn("CAPITAL") + net_profit - tot["DRAWINGS"]

    # ---- balance sheet
    def pos(h):
        return sgn(h)
    liabilities = dict(LT_SECURED=pos("LT_SECURED"), LT_UNSECURED=pos("LT_UNSECURED"), ST_BORROWINGS=pos("ST_BORROWINGS"),
                       TRADE_PAYABLES=pos("TRADE_PAYABLES"), OTHER_CUR_LIAB=pos("OTHER_CUR_LIAB"), PROVISIONS=pos("PROVISIONS"))
    suspense = tot["SUSPENSE"]
    assets = dict(FIXED_ASSETS=ppe, INVESTMENTS=pos("INVESTMENTS"), LT_LOANS_ADV=pos("LT_LOANS_ADV"), INVENTORY=closing_stock,
                  TRADE_RECEIVABLES=pos("TRADE_RECEIVABLES"), CASH_BANK=pos("CASH_BANK"), ST_LOANS_ADV=pos("ST_LOANS_ADV"),
                  OTHER_CUR_ASSETS=pos("OTHER_CUR_ASSETS") + (suspense if suspense > 0 else ZERO))
    if suspense < 0:
        liabilities["OTHER_CUR_LIAB"] += -suspense
    total_eq_liab = capital_closing + sum(liabilities.values(), ZERO)
    total_assets = sum(assets.values(), ZERO)
    return dict(tot=tot, items=items, dep=dep, dep_amount=dep_amount, booked_dep=booked_dep, total_dep=total_dep, ppe=ppe,
                fa_ledgers=tot["FIXED_ASSETS"], virtual_fa=virtual_fa, tb_difference=tb_difference,
                revenue=revenue, other_income=other_income, total_income=total_income, opening_stock=opening_stock,
                closing_stock=closing_stock, purchases=purchases, change_in_stock=change_in_stock, direct=direct,
                employee=employee, finance=finance, other_exp=other_exp, expenses_before=expenses_before,
                gross_profit=gross_profit, profit_before_appropriation=profit_before_appropriation,
                interest_total=interest_total, remuneration_total=remuneration_total, profit_before_tax=profit_before_tax,
                tax=tax, net_profit=net_profit, partners=p_rows, capital_ledgers=sgn("CAPITAL"), drawings=tot["DRAWINGS"],
                capital_closing=capital_closing, liabilities=liabilities, assets=assets, suspense=suspense,
                total_eq_liab=total_eq_liab, total_assets=total_assets, difference=total_assets - total_eq_liab,
                use_booked_int=use_booked_int, use_booked_rem=use_booked_rem)


def _ratio(a: Decimal, b: Decimal, pct=False, days=False):
    if not b:
        return None
    v = a / b * (100 if pct else 365 if days else 1)
    return v.quantize(Decimal("0.01"))


def checks(data: dict, y: dict) -> list[dict]:
    out = []
    add = lambda level, text: out.append({"level": level, "text": text})  # noqa: E731
    unmapped = [l.get("name") for l in data.get("ledgers") or [] if not l.get("head") and (D(l.get("cy")) or D(l.get("py")))]
    if unmapped:
        add("error", f"{len(unmapped)} ledger(s) not classified: {', '.join(unmapped[:6])}{'…' if len(unmapped) > 6 else ''}.")
    if y["tb_difference"]:
        side = "debit" if y["tb_difference"] > 0 else "credit"
        add("error", f"Trial balance does not tally: debits and credits differ by {abs(y['tb_difference'])} (excess {side}). "
                     "Check for a missing ledger or a wrong Dr/Cr sign.")
    if y["difference"] and not y["tb_difference"]:
        add("error", f"Balance sheet differs by {y['difference']}.")
    if y["suspense"]:
        add("warn", "Suspense / difference amount is present — clear it before finalising.")
    if y["purchases"] and not y["closing_stock"] and not y["opening_stock"]:
        add("warn", "Purchases are entered but opening and closing stock are nil — enter closing stock if goods remain.")
    if y["assets"]["CASH_BANK"] < 0:
        add("warn", "Cash / bank total is negative — a bank overdraft belongs under short-term borrowings, and cash can't be negative.")
    for h, label in (("TRADE_RECEIVABLES", "Debtors"), ("TRADE_PAYABLES", "Creditors")):
        if (y["assets"].get(h) if h in y["assets"] else y["liabilities"].get(h, ZERO)) < 0:
            add("warn", f"{label} have an opposite balance overall — advances may need to be shown separately.")
    dep = y["dep"] or {}
    if y["booked_dep"] and dep.get("rows"):
        add("warn", "Depreciation is both booked in ledgers and computed in the schedule — it may be counted twice.")
    if dep.get("rows") and y["tot"]["FIXED_ASSETS"]:
        base = dep["total"]["opening"] + dep["total"]["additions"] - dep["total"]["deletions"]
        if (base - y["tot"]["FIXED_ASSETS"]).copy_abs() > 1:
            add("warn", f"Fixed assets in the ledgers ({y['tot']['FIXED_ASSETS']}) differ from the depreciation schedule "
                        f"before depreciation ({base}). Check opening WDV, additions and sales.")
    if y["tot"]["FIXED_ASSETS"] and not dep.get("rows") and not y["booked_dep"]:
        add("info", "Fixed assets are present but no depreciation is computed — add the assets in the Depreciation tab.")
    if data.get("entity_type") == "PARTNERSHIP":
        ps = data.get("partners") or []
        if not ps:
            add("error", "Add the partners and their profit-sharing ratio.")
        elif sum((D(p.get("share")) for p in ps), ZERO) != 100:
            add("warn", "Partners' profit shares do not add up to 100%.")
        if any(not l.get("partner") and l.get("head") in ("CAPITAL", "DRAWINGS", "PARTNER_INTEREST", "PARTNER_REMUNERATION")
               for l in data.get("ledgers") or []):
            add("warn", "Some capital / drawings / partner ledgers are not assigned to a partner.")
    if not out:
        add("ok", "All checks passed — the trial balance tallies and the balance sheet balances.")
    return out


def compute(data: dict, fy: str, client_name: str = "") -> dict:
    fy_from, fy_to = _fy_dates(fy)
    cy = _year(data, "cy", fy_from, fy_to)
    has_py = any(D(l.get("py")) for l in data.get("ledgers") or []) or D((data.get("closing_stock") or {}).get("py"))
    py = _year(data, "py", fy_from.replace(year=fy_from.year - 1), fy_to.replace(year=fy_to.year - 1)) if has_py else None
    return dict(fy=fy, period=dict(start=fy_from, end=fy_to), cy=cy, py=py, checks=checks(data, cy),
                ratios=_ratios(cy), explain=_explain(data, cy))


def _ratios(y: dict) -> list[dict]:
    cur_assets = sum((y["assets"][k] for k in ("INVENTORY", "TRADE_RECEIVABLES", "CASH_BANK", "ST_LOANS_ADV", "OTHER_CUR_ASSETS")), ZERO)
    cur_liab = sum((y["liabilities"][k] for k in ("ST_BORROWINGS", "TRADE_PAYABLES", "OTHER_CUR_LIAB", "PROVISIONS")), ZERO)
    borrowings = y["liabilities"]["LT_SECURED"] + y["liabilities"]["LT_UNSECURED"] + y["liabilities"]["ST_BORROWINGS"]
    cogs = y["purchases"] + y["change_in_stock"] + y["direct"]
    avg_stock = (y["opening_stock"] + y["closing_stock"]) / 2
    return [
        dict(name="Gross profit ratio", value=_ratio(y["gross_profit"], y["revenue"], pct=True), unit="%",
             how="Gross profit ÷ revenue × 100. Gross profit = revenue − (purchases + change in stock + direct expenses)."),
        dict(name="Net profit ratio", value=_ratio(y["net_profit"], y["revenue"], pct=True), unit="%", how="Net profit ÷ revenue × 100."),
        dict(name="Current ratio", value=_ratio(cur_assets, cur_liab), unit="times",
             how="Current assets ÷ current liabilities. Around 1.33 or more is usually expected by banks."),
        dict(name="Quick ratio", value=_ratio(cur_assets - y["assets"]["INVENTORY"], cur_liab), unit="times",
             how="(Current assets − stock) ÷ current liabilities."),
        dict(name="Debt-equity ratio", value=_ratio(borrowings, y["capital_closing"]), unit="times", how="Total borrowings ÷ capital."),
        dict(name="Debtors collection period", value=_ratio(y["assets"]["TRADE_RECEIVABLES"], y["revenue"], days=True), unit="days",
             how="Debtors ÷ revenue × 365 — how many days customers take to pay."),
        dict(name="Creditors payment period", value=_ratio(y["liabilities"]["TRADE_PAYABLES"], y["purchases"], days=True), unit="days",
             how="Creditors ÷ purchases × 365 — how many days the business takes to pay suppliers."),
        dict(name="Stock holding period", value=_ratio(avg_stock, cogs, days=True), unit="days",
             how="Average stock ÷ cost of goods sold × 365."),
    ]


def _explain(data: dict, y: dict) -> dict:
    """Learn mode: what each line means, which ledgers make it, and the working."""
    ex = {}
    for h, (section, label, _nature, text) in HEADS.items():
        ex[h] = dict(title=label, text=text, items=[{"name": i["name"], "amount": float(i["amount"])} for i in y["items"].get(h, [])])
    ex["CHANGE_IN_STOCK"] = dict(title="Changes in inventories", text=(
        f"Opening stock {y['opening_stock']} − closing stock {y['closing_stock']} = {y['change_in_stock']}. "
        "Unsold goods at the year end are not an expense of this year, so closing stock is deducted from cost."), items=[])
    ex["INVENTORY"] = dict(title="Inventories (closing stock)", text=(
        "Value of goods on hand at the year end, at cost or net realisable value, whichever is lower. "
        "It is entered separately because it is not a ledger balance in most books."), items=[])
    dep = y["dep"] or {}
    ex["DEPRECIATION"] = dict(title="Depreciation", text=(
        ("Computed from the depreciation schedule: " + "; ".join(dep.get("steps") or []) + ". " if dep.get("steps") else "")
        + (f"Plus depreciation already booked in ledgers: {y['booked_dep']}. " if y["booked_dep"] else "")
        + "Depreciation spreads the cost of an asset over the years it is used; it reduces profit but no cash is paid."), items=[])
    ex["FIXED_ASSETS"]["text"] += (f" Ledger / schedule value before depreciation {y['fa_ledgers'] or y['virtual_fa']} − "
                                   f"depreciation {y['dep_amount']} = {y['ppe']}.")
    ex["NET_PROFIT"] = dict(title="Net profit", text=(
        f"Total income {y['total_income']} − expenses {y['expenses_before']}"
        + (f" − interest to partners {y['interest_total']} − remuneration {y['remuneration_total']}" if y["interest_total"] or y["remuneration_total"] else "")
        + (f" − tax {y['tax']}" if y["tax"] else "") + f" = {y['net_profit']}."), items=[])
    if data.get("entity_type") == "PARTNERSHIP":
        ex["CAPITAL"]["text"] += (" For each partner: capital ledger + interest on capital + remuneration (unless already "
                                  "credited in the books) + share of profit − drawings.")
    else:
        ex["CAPITAL"]["text"] += (f" Capital ledger {y['capital_ledgers']} + net profit {y['net_profit']} − drawings "
                                  f"{y['drawings']} = closing capital {y['capital_closing']}.")
    ex["GROSS_PROFIT"] = dict(title="Gross profit", text=(
        f"Revenue {y['revenue']} − (purchases {y['purchases']} + change in stock {y['change_in_stock']} + direct expenses "
        f"{y['direct']}) = {y['gross_profit']}. It shows the margin on trading before running costs."), items=[])
    return ex


# ================================================================ presentation (report sections)
def _row(label, key, cy, py, note=None, style=None):
    r = {"label": label, "note": note, "cy": cy, "py": py, "_key": key}
    if style:
        r["_style"] = style
    return r


def statements_doc(comp: dict, client: dict) -> dict:
    """Balance sheet, P&L, notes and ratios in the report shape used for display and PDF / Excel export."""
    cy, py = comp["cy"], comp["py"]
    g = (lambda k: py[k] if py else None)  # noqa: E731
    ga = (lambda d, k: py[d][k] if py else None)  # noqa: E731
    end = comp["period"]["end"]
    ycols = [{"key": "label", "label": "Particulars", "type": "text"}, {"key": "note", "label": "Note", "type": "text"},
             {"key": "cy", "label": f"31-03-{end.year}", "type": "money"}]
    if py:
        ycols.append({"key": "py", "label": f"31-03-{end.year - 1}", "type": "money"})
    partners = client.get("entity_type") == "PARTNERSHIP"
    owners = "Partners' capital accounts" if partners else "Proprietor's capital account"
    L, A = cy["liabilities"], cy["assets"]
    bs = [
        _row("I. EQUITY AND LIABILITIES", None, None, None, style="head"),
        _row("1. Owners' funds", None, None, None, style="sub"),
        _row(f"   {owners}", "CAPITAL", cy["capital_closing"], g("capital_closing"), "1"),
        _row("2. Non-current liabilities", None, None, None, style="sub"),
        _row("   Long-term borrowings", "LT_SECURED", L["LT_SECURED"] + L["LT_UNSECURED"],
             (ga("liabilities", "LT_SECURED") + ga("liabilities", "LT_UNSECURED")) if py else None, "2"),
        _row("3. Current liabilities", None, None, None, style="sub"),
        _row("   Short-term borrowings", "ST_BORROWINGS", L["ST_BORROWINGS"], ga("liabilities", "ST_BORROWINGS"), "2"),
        _row("   Trade payables", "TRADE_PAYABLES", L["TRADE_PAYABLES"], ga("liabilities", "TRADE_PAYABLES"), "3"),
        _row("   Other current liabilities", "OTHER_CUR_LIAB", L["OTHER_CUR_LIAB"], ga("liabilities", "OTHER_CUR_LIAB"), "4"),
        _row("   Short-term provisions", "PROVISIONS", L["PROVISIONS"], ga("liabilities", "PROVISIONS"), "4"),
        _row("TOTAL", None, cy["total_eq_liab"], g("total_eq_liab"), style="bold"),
        _row("II. ASSETS", None, None, None, style="head"),
        _row("1. Non-current assets", None, None, None, style="sub"),
        _row("   Property, plant & equipment", "FIXED_ASSETS", A["FIXED_ASSETS"], ga("assets", "FIXED_ASSETS"), "5"),
        _row("   Investments", "INVESTMENTS", A["INVESTMENTS"], ga("assets", "INVESTMENTS"), "6"),
        _row("   Long-term loans, advances & deposits", "LT_LOANS_ADV", A["LT_LOANS_ADV"], ga("assets", "LT_LOANS_ADV"), "6"),
        _row("2. Current assets", None, None, None, style="sub"),
        _row("   Inventories", "INVENTORY", A["INVENTORY"], ga("assets", "INVENTORY")),
        _row("   Trade receivables", "TRADE_RECEIVABLES", A["TRADE_RECEIVABLES"], ga("assets", "TRADE_RECEIVABLES"), "7"),
        _row("   Cash and bank balances", "CASH_BANK", A["CASH_BANK"], ga("assets", "CASH_BANK"), "8"),
        _row("   Short-term loans & advances", "ST_LOANS_ADV", A["ST_LOANS_ADV"], ga("assets", "ST_LOANS_ADV"), "9"),
        _row("   Other current assets", "OTHER_CUR_ASSETS", A["OTHER_CUR_ASSETS"], ga("assets", "OTHER_CUR_ASSETS"), "9"),
        _row("TOTAL", None, cy["total_assets"], g("total_assets"), style="bold"),
    ]
    bs = [r for r in bs if r.get("_style") or r["cy"] or r["py"] or r["_key"] == "CAPITAL"]

    pl = [
        _row("I. Revenue from operations", "REVENUE", cy["revenue"], g("revenue")),
        _row("II. Other income", "OTHER_INCOME", cy["other_income"], g("other_income")),
        _row("III. Total income", None, cy["total_income"], g("total_income"), style="bold"),
        _row("IV. Expenses", None, None, None, style="sub"),
        _row("   Purchases of stock-in-trade", "PURCHASES", cy["purchases"], g("purchases")),
        _row("   Changes in inventories", "CHANGE_IN_STOCK", cy["change_in_stock"], g("change_in_stock")),
        _row("   Direct expenses", "DIRECT_EXP", cy["direct"], g("direct"), "10"),
        _row("   Employee benefit expenses", "EMPLOYEE", cy["employee"], g("employee"), "10"),
        _row("   Finance costs", "FINANCE", cy["finance"], g("finance"), "10"),
        _row("   Depreciation", "DEPRECIATION", cy["total_dep"], g("total_dep"), "5"),
        _row("   Other expenses", "OTHER_EXP", cy["other_exp"], g("other_exp"), "10"),
        _row("Total expenses", None, cy["expenses_before"], g("expenses_before"), style="bold"),
        _row("Gross profit (for reference)", "GROSS_PROFIT", cy["gross_profit"], g("gross_profit"), style="sub"),
    ]
    if partners or cy["interest_total"] or cy["remuneration_total"]:
        pl += [
            _row("V. Profit before partners' interest & remuneration", None, cy["profit_before_appropriation"], g("profit_before_appropriation"), style="bold"),
            _row("   Less: interest on partners' capital", "PARTNER_INTEREST", cy["interest_total"], g("interest_total")),
            _row("   Less: remuneration to partners", "PARTNER_REMUNERATION", cy["remuneration_total"], g("remuneration_total")),
        ]
    pl += [
        _row("Profit before tax", None, cy["profit_before_tax"], g("profit_before_tax"), style="bold"),
        _row("   Less: tax expense", "TAX_EXPENSE", cy["tax"], g("tax")),
        _row("Net profit for the year", "NET_PROFIT", cy["net_profit"], g("net_profit"), style="bold"),
    ]
    pl = [r for r in pl if r.get("_style") or r["cy"] or r["py"]]

    sections = [
        {"title": "Balance sheet", "columns": ycols, "rows": bs},
        {"title": "Statement of profit and loss", "columns": ycols, "rows": pl},
    ]
    # ---- notes
    money = lambda k, l: {"key": k, "label": l, "type": "money"}  # noqa: E731
    if partners and cy["partners"]:
        cols = [{"key": "label", "label": "Particulars", "type": "text"}] + [money(f"p{i}", p["name"]) for i, p in enumerate(cy["partners"])] + [money("total", "Total")]
        lines = [("Balance as per capital ledger", "capital_ledger"),
                 ("Add: interest on capital" + (" (booked)" if cy["use_booked_int"] else ""), "interest"),
                 ("Add: remuneration" + (" (booked)" if cy["use_booked_rem"] else ""), "remuneration"),
                 ("Add: share of profit", "profit_share"), ("Less: drawings", "drawings"), ("Closing balance", "closing")]
        rows = []
        for label, k in lines:
            r = {"label": label, **{f"p{i}": p[k] for i, p in enumerate(cy["partners"])}}
            r["total"] = sum((p[k] for p in cy["partners"]), ZERO)
            if k == "closing":
                r["_style"] = "bold"
            rows.append(r)
        rows.insert(-1, {"label": "Profit-sharing ratio (%)", **{f"p{i}": p["share"] for i, p in enumerate(cy["partners"])}, "_style": "sub"})
        sections.append({"title": "Note 1 — Partners' capital accounts", "columns": cols, "rows": rows})
    else:
        sections.append({"title": "Note 1 — Proprietor's capital account", "columns": [{"key": "label", "label": "Particulars", "type": "text"}, money("amount", "Amount")],
                         "rows": [{"label": "Balance as per capital ledger (opening + introduced)", "amount": cy["capital_ledgers"]},
                                  {"label": "Add: net profit for the year", "amount": cy["net_profit"]},
                                  {"label": "Less: drawings", "amount": cy["drawings"]},
                                  {"label": "Closing balance", "amount": cy["capital_closing"], "_style": "bold"}]})

    def ledger_note(title, heads):
        rows = []
        for h in heads:
            nat = HEADS[h][2]
            for it in cy["items"].get(h, []):
                rows.append({"label": it["name"], "head": HEADS[h][1], "amount": -it["amount"] if nat == "Cr" else it["amount"]})
        if rows:
            sections.append({"title": title, "columns": [{"key": "label", "label": "Ledger", "type": "text"},
                                                         {"key": "head", "label": "Classification", "type": "text"}, money("amount", "Amount")],
                             "rows": rows, "total": {"amount": sum((r["amount"] for r in rows), ZERO)}})
    ledger_note("Note 2 — Borrowings", ["LT_SECURED", "LT_UNSECURED", "ST_BORROWINGS"])
    ledger_note("Note 3 — Trade payables", ["TRADE_PAYABLES"])
    ledger_note("Note 4 — Other current liabilities & provisions", ["OTHER_CUR_LIAB", "PROVISIONS"])
    dep = cy["dep"] or {}
    if dep.get("rows"):
        it_mode = dep["method"] == "IT"
        cols = [{"key": "block", "label": "Block / asset" if it_mode else "Asset", "type": "text"}]
        if it_mode:
            cols.append({"key": "rate", "label": "Rate %", "type": "pct"})
        cols += [money("opening", "Opening WDV"), money("additions_full", "Additions (180+ days)" if it_mode else "Additions"),
                 *( [money("additions_half", "Additions (< 180 days)")] if it_mode else []),
                 money("deletions", "Sales / deletions"), money("depreciation", "Depreciation"), money("closing", "Closing WDV")]
        t = dep["total"]
        sections.append({"title": "Note 5 — Property, plant & equipment and depreciation" + (" (Income-tax Act rates)" if it_mode else " (useful life, Companies Act)"),
                         "columns": cols, "rows": dep["rows"],
                         "total": {"opening": t["opening"], "additions_full": t["additions"] if not it_mode else sum((r["additions_full"] for r in dep["rows"]), ZERO),
                                   "additions_half": sum((r["additions_half"] for r in dep["rows"]), ZERO), "deletions": t["deletions"],
                                   "depreciation": t["depreciation"], "closing": t["closing"]}})
    else:
        ledger_note("Note 5 — Property, plant & equipment", ["FIXED_ASSETS"])
    ledger_note("Note 6 — Investments, long-term loans & deposits", ["INVESTMENTS", "LT_LOANS_ADV"])
    ledger_note("Note 7 — Trade receivables", ["TRADE_RECEIVABLES"])
    ledger_note("Note 8 — Cash and bank balances", ["CASH_BANK"])
    ledger_note("Note 9 — Short-term loans, advances & other current assets", ["ST_LOANS_ADV", "OTHER_CUR_ASSETS"])
    ledger_note("Note 10 — Expenses", ["DIRECT_EXP", "EMPLOYEE", "FINANCE", "OTHER_EXP"])
    sections.append({"title": "Key ratios", "columns": [{"key": "name", "label": "Ratio", "type": "text"},
                                                       {"key": "value", "label": "Value", "type": "qty"},
                                                       {"key": "unit", "label": "", "type": "text"},
                                                       {"key": "how", "label": "How it is worked out", "type": "text"}],
                     "rows": comp["ratios"]})
    kind = "partnership firm" if partners else "proprietorship"
    return {"title": f"{client.get('name')} — financial statements FY {comp['fy']}",
            "subtitle": f"{kind.title()}{' · PAN ' + client['pan'] if client.get('pan') else ''} · for the year ended 31-03-{end.year}",
            "sections": sections}


# ================================================================ inputs
def tb_template_rows() -> list[list]:
    return [["Ledger", "Group", "Debit", "Credit", "Previous year debit", "Previous year credit"],
            ["Sales", "Sales Accounts", None, 1500000, None, 1200000],
            ["Purchases", "Purchase Accounts", 1100000, None, 900000, None],
            ["Opening stock", "Stock-in-Hand", 150000, None, 120000, None],
            ["Rent", "Indirect Expenses", 60000, None, 60000, None],
            ["Salary", "Indirect Expenses", 120000, None, 100000, None],
            ["HDFC Bank", "Bank Accounts", 85000, None, 60000, None],
            ["Cash", "Cash-in-Hand", 15000, None, 12000, None],
            ["Sundry debtors", "Sundry Debtors", 90000, None, 70000, None],
            ["Sundry creditors", "Sundry Creditors", None, 70000, None, 50000],
            ["Furniture", "Fixed Assets", 50000, None, 55000, None],
            ["Capital - Ramesh", "Capital Account", None, 150000, None, 200000],
            ["Drawings - Ramesh", "Capital Account", 50000, None, 40000, None]]
