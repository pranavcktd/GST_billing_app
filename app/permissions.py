"""Staff permissions: module × action matrix per role, overridable per member (custom roles).

Flags:
* view_cost  — may see purchase rates, costs, margins and profit
* edit_past  — may edit/cancel documents dated before today without a manager's approval PIN
"""

from .gst.constants import Role

MODULES: dict[str, str] = {
    "sales": "Sales (invoices, estimates, orders, challans, credit notes)",
    "purchases": "Purchases (bills, purchase orders, debit notes)",
    "expenses": "Expenses",
    "payments_in": "Payment in (receipts)",
    "payments_out": "Payment out",
    "parties": "Parties",
    "items": "Items, stock & godowns",
    "cashbank": "Cash & bank, cheques, loans, capital",
    "reports_sales": "Sales reports, day book, party statement",
    "reports_stock": "Stock & item reports",
    "reports_financial": "P&L, balance sheet, ledgers, profit reports",
    "reports_gst": "GST returns & tax reports",
    "settings": "Company settings, print, HSN master",
    "users": "Staff & permissions",
    "backup": "Backup & restore",
    "audit": "Audit trail",
}
ACTIONS = ("view", "create", "edit", "delete", "export")
FLAGS = ("view_cost", "edit_past")

ALL = set(ACTIONS)
READ = {"view", "export"}


def _matrix(spec: dict[str, set[str]], flags: set[str]) -> dict:
    return {"modules": {m: sorted(spec.get(m, set())) for m in MODULES}, "flags": sorted(flags)}


DEFAULTS: dict[Role, dict] = {
    Role.OWNER: _matrix({m: ALL for m in MODULES}, set(FLAGS)),
    Role.ADMIN: _matrix({m: ALL for m in MODULES}, set(FLAGS)),
    # Store manager: runs the shop — everything except staff, backups and company settings
    Role.MANAGER: _matrix({**{m: ALL for m in MODULES if m not in ("users", "backup", "settings", "audit")},
                           "settings": {"view"}, "audit": {"view"}}, set(FLAGS)),
    # Billing desk / cashier
    Role.BILLING: _matrix({"sales": {"view", "create"}, "payments_in": {"view", "create"},
                           "parties": {"view", "create"}, "items": {"view"}, "reports_sales": {"view"}}, set()),
    # Purchase & inventory clerk
    Role.INVENTORY: _matrix({"purchases": {"view", "create", "edit"}, "items": {"view", "create", "edit"},
                             "parties": {"view", "create"}, "reports_stock": READ}, {"view_cost"}),
    # Chartered accountant / auditor: read-only books, GST and audit trail
    Role.ACCOUNTANT: _matrix({**{m: READ for m in MODULES if m not in ("users", "backup", "settings")},
                              "settings": {"view"}}, {"view_cost"}),
}

ROLE_LABELS = {
    Role.OWNER: "Owner", Role.ADMIN: "Business admin", Role.MANAGER: "Store manager",
    Role.BILLING: "Billing operator", Role.INVENTORY: "Inventory manager", Role.ACCOUNTANT: "Accountant / CA (read-only)",
}


def effective(role: Role, custom: dict | None) -> dict:
    """Permissions for a member: the role's defaults, or the custom matrix when one is set."""
    if role == Role.OWNER or not custom:
        return DEFAULTS[role]
    mods = {m: sorted(set(custom.get("modules", {}).get(m, [])) & ALL) for m in MODULES}
    mods["users"] = mods["users"] if role == Role.ADMIN else []  # only admins can manage staff
    return {"modules": mods, "flags": sorted(set(custom.get("flags", [])) & set(FLAGS))}


def normalise(custom: dict) -> dict:
    return {"modules": {m: sorted(set((custom.get("modules") or {}).get(m, [])) & ALL) for m in MODULES},
            "flags": sorted(set(custom.get("flags") or []) & set(FLAGS))}


# which module a document type belongs to
def voucher_module(vtype) -> str:
    v = getattr(vtype, "value", vtype)
    if v == "EXPENSE":
        return "expenses"
    if v in ("PURCHASE", "PURCHASE_RETURN", "PURCHASE_ORDER"):
        return "purchases"
    return "sales"


REPORT_MODULE = {
    "Transaction": "reports_financial", "Party": "reports_financial", "GST": "reports_gst",
    "Item / Stock": "reports_stock", "Business status": "reports_financial", "Taxes": "reports_gst",
    "Expense": "reports_financial", "Sale / Purchase orders": "reports_sales", "Loan": "reports_financial",
}
# individual reports that sales staff may see
SALES_REPORTS = {"sale", "day-book", "payments", "party-statement", "all-parties", "sale-orders", "delivery-challans",
                 "estimates", "sale-aging"}


def report_module(slug: str, category: str) -> str:
    return "reports_sales" if slug in SALES_REPORTS else REPORT_MODULE.get(category, "reports_financial")
