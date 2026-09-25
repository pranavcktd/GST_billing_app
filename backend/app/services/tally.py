"""Tally Prime / ERP 9 export (XML import: Gateway of Tally → Import → Masters/Vouchers).

Accounting-invoice mode: ledgers first (parties, sales/purchase, GST, expenses, banks), then
balanced vouchers. Tally convention: a debit has ISDEEMEDPOSITIVE=Yes and a negative AMOUNT.
Create the company in Tally with the same name before importing.
"""

import datetime as dt
from decimal import Decimal
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..gst.constants import PaymentType, VoucherType
from ..gst.states import state_name
from ..models import (
    Account,
    AccountTransfer,
    Business,
    ExpenseCategory,
    Party,
    Payment,
    PaymentAllocation,
    Voucher,
)
from ..reports.accounting import itc_claimable

ZERO = Decimal("0")
CASH_PARTY = "Cash Sales / Purchases (walk-in)"
TAX_LEDGERS = {
    "out": {"igst": "Output IGST", "cgst": "Output CGST", "sgst": "Output SGST", "cess": "Output Cess"},
    "in": {"igst": "Input IGST", "cgst": "Input CGST", "sgst": "Input SGST", "cess": "Input Cess"},
    "rcm": {"igst": "IGST Payable (RCM)", "cgst": "CGST Payable (RCM)", "sgst": "SGST Payable (RCM)", "cess": "Cess Payable (RCM)"},
}
VCH_TYPE = {VoucherType.SALE: "Sales", VoucherType.SALE_RETURN: "Credit Note", VoucherType.PURCHASE: "Purchase",
            VoucherType.PURCHASE_RETURN: "Debit Note", VoucherType.EXPENSE: "Purchase"}


def _e(s) -> str:
    return escape(str(s or ""), {'"': "&quot;"})


def _amt(x: Decimal) -> str:
    return f"{x:.2f}"


class Builder:
    def __init__(self):
        self.ledgers: dict[str, dict] = {}
        self.vouchers: list[str] = []

    def ledger(self, name: str, parent: str, **extra) -> str:
        self.ledgers.setdefault(name, {"parent": parent, **extra})
        return name

    def voucher(self, vtype: str, date: dt.date, number: str, narration: str, entries: list[tuple[str, Decimal]],
                party: str | None = None):
        """entries: (ledger, amount) with + = debit, - = credit. Must sum to zero."""
        entries = [(l, a) for l, a in entries if a]
        diff = sum((a for _, a in entries), ZERO)
        if diff:  # never emit an unbalanced voucher; park paise differences in round off
            entries.append((self.ledger("Round Off", "Indirect Expenses"), -diff))
        lines = []
        for led, a in entries:
            deemed = "Yes" if a > 0 else "No"
            lines.append(
                f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{_e(led)}</LEDGERNAME><ISDEEMEDPOSITIVE>{deemed}</ISDEEMEDPOSITIVE>"
                f"<AMOUNT>{_amt(-a)}</AMOUNT></ALLLEDGERENTRIES.LIST>")
        self.vouchers.append(
            f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><VOUCHER VCHTYPE="{_e(vtype)}" ACTION="Create">'
            f"<DATE>{date:%Y%m%d}</DATE><VOUCHERTYPENAME>{_e(vtype)}</VOUCHERTYPENAME>"
            f"<VOUCHERNUMBER>{_e(number)}</VOUCHERNUMBER>"
            + (f"<PARTYLEDGERNAME>{_e(party)}</PARTYLEDGERNAME>" if party else "")
            + f"<NARRATION>{_e(narration)}</NARRATION>{''.join(lines)}</VOUCHER></TALLYMESSAGE>")

    def xml(self, company: str) -> str:
        masters = []
        for name, d in self.ledgers.items():
            extra = ""
            if d.get("gstin"):
                extra += f"<PARTYGSTIN>{_e(d['gstin'])}</PARTYGSTIN><GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>"
            if d.get("state"):
                extra += f"<LEDSTATENAME>{_e(d['state'])}</LEDSTATENAME>"
            if d.get("opening"):
                extra += f"<OPENINGBALANCE>{_amt(-d['opening'])}</OPENINGBALANCE>"
            masters.append(
                f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><LEDGER NAME="{_e(name)}" ACTION="Create">'
                f"<NAME.LIST><NAME>{_e(name)}</NAME></NAME.LIST><PARENT>{_e(d['parent'])}</PARENT>"
                f"<ISBILLWISEON>{'Yes' if d['parent'] in ('Sundry Debtors', 'Sundry Creditors') else 'No'}</ISBILLWISEON>"
                f"{extra}</LEDGER></TALLYMESSAGE>")
        return ("<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>"
                "<REQUESTDESC><REPORTNAME>All Masters</REPORTNAME><STATICVARIABLES>"
                f"<SVCURRENTCOMPANY>{_e(company)}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>"
                f"<REQUESTDATA>{''.join(masters)}{''.join(self.vouchers)}</REQUESTDATA>"
                "</IMPORTDATA></BODY></ENVELOPE>")


def export(db: Session, biz: Business, date_from: dt.date, date_to: dt.date) -> str:
    b = Builder()
    parties = {p.id: p for p in db.scalars(select(Party).where(Party.business_id == biz.id))}
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.business_id == biz.id))}
    cats = {c.id: c for c in db.scalars(select(ExpenseCategory).where(ExpenseCategory.business_id == biz.id))}

    def party_ledger(pid: str | None) -> str:
        p = parties.get(pid)
        if not p:
            return b.ledger(CASH_PARTY, "Sundry Debtors")
        parent = "Sundry Creditors" if p.type.value == "SUPPLIER" else "Sundry Debtors"
        return b.ledger(p.name, parent, gstin=p.gstin, state=state_name(p.state_code), opening=p.opening_balance)

    def account_ledger(aid: str) -> str:
        a = accounts[aid]
        return b.ledger(a.name, "Cash-in-Hand" if a.type.value == "CASH" else "Bank Accounts", opening=a.opening_balance)

    def taxes(v: Voucher, kind: str) -> list[tuple[str, Decimal]]:
        return [(b.ledger(TAX_LEDGERS[kind][k], "Duties & Taxes"), getattr(v, k)) for k in ("igst", "cgst", "sgst", "cess")]

    docs = db.scalars(select(Voucher).where(
        Voucher.business_id == biz.id, Voucher.cancelled.is_(False), Voucher.date >= date_from, Voucher.date <= date_to,
        Voucher.type.in_(list(VCH_TYPE))).order_by(Voucher.date, Voucher.created_at)).all()
    round_off = b.ledger("Round Off", "Indirect Expenses")
    for v in docs:
        party = party_ledger(v.party_id)
        narr = f"{v.number}" + (f" | Supplier bill {v.supplier_invoice_no}" if v.supplier_invoice_no else "") + \
               (f" | {v.notes}" if v.notes else "")
        if v.type in (VoucherType.SALE, VoucherType.SALE_RETURN):
            s = 1 if v.type == VoucherType.SALE else -1  # sale: Dr party / Cr sales, taxes
            entries = [(party, s * v.grand_total), (b.ledger("Sales", "Sales Accounts"), -s * v.taxable)]
            entries += [(led, -s * a) for led, a in taxes(v, "out")]
            entries += [(b.ledger("TCS Payable", "Duties & Taxes"), -s * v.tcs_amount), (round_off, -s * v.round_off)]
        else:
            s = -1 if v.type == VoucherType.PURCHASE_RETURN else 1  # purchase: Dr purchase, taxes / Cr party
            if v.type == VoucherType.EXPENSE:
                cat = cats.get(v.expense_category_id)
                head = b.ledger(cat.name if cat else "Expenses",
                                "Direct Expenses" if cat and cat.kind.value == "DIRECT" else "Indirect Expenses")
            else:
                head = b.ledger("Purchase", "Purchase Accounts")
            claim = itc_claimable(v, biz)
            tax_total = v.igst + v.cgst + v.sgst + v.cess
            entries = [(head, s * (v.taxable + (ZERO if claim else tax_total)))]
            if claim:
                entries += [(led, s * a) for led, a in taxes(v, "in")]
            if v.reverse_charge:
                entries += [(led, -s * a) for led, a in taxes(v, "rcm")]
            entries += [(b.ledger("TCS Receivable", "Current Assets"), s * v.tcs_amount), (round_off, s * v.round_off),
                        (party, -s * v.grand_total)]
        b.voucher(VCH_TYPE[v.type], v.date, v.number, narr, entries, party)

    pays = db.scalars(select(Payment).options(selectinload(Payment.allocations).selectinload(PaymentAllocation.voucher))
                      .where(Payment.business_id == biz.id, Payment.date >= date_from, Payment.date <= date_to)
                      .order_by(Payment.date)).all()
    for p in pays:
        if p.cheque_status == "BOUNCED":
            continue
        party = party_ledger(p.party_id)
        acc = account_ledger(p.account_id)
        bills = ", ".join(a.voucher.number for a in p.allocations)
        narr = f"{p.number}" + (f" | against {bills}" if bills else "") + (f" | Ref {p.reference}" if p.reference else "")
        if p.type == PaymentType.IN:
            entries = [(acc, p.amount), (b.ledger("TDS Receivable", "Current Assets"), p.tds_amount),
                       (party, -(p.amount + p.tds_amount))]
            b.voucher("Receipt", p.date, p.number, narr, entries, party)
        else:
            entries = [(party, p.amount + p.tds_amount), (acc, -p.amount),
                       (b.ledger("TDS Payable", "Duties & Taxes"), -p.tds_amount)]
            b.voucher("Payment", p.date, p.number, narr, entries, party)

    for t in db.scalars(select(AccountTransfer).where(AccountTransfer.business_id == biz.id,
                                                      AccountTransfer.date >= date_from, AccountTransfer.date <= date_to)):
        b.voucher("Contra", t.date, "", t.note or "Transfer",
                  [(account_ledger(t.to_account_id), t.amount), (account_ledger(t.from_account_id), -t.amount)])
    return b.xml(biz.legal_name or biz.name)
