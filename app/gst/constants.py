"""GST domain constants shared across the backend."""

from decimal import Decimal
from enum import Enum

# GST 2.0 (from 22-Sep-2025) main slabs are 5% / 18% / 40%; 12% and 28% are kept
# for older bills and the few items still taxed at those rates.
GST_RATES = [Decimal(x) for x in ("0", "0.25", "3", "5", "12", "18", "28", "40")]

# B2C inter-state invoices above this value are reported invoice-wise in GSTR-1 (B2CL).
B2CL_LIMIT = Decimal("100000")

# Unit Quantity Codes accepted by the GST portal (HSN summary).
UQC = {
    "NOS": "Numbers", "PCS": "Pieces", "KGS": "Kilograms", "GMS": "Grams",
    "LTR": "Litres", "MLT": "Millilitre", "MTR": "Metres", "CMS": "Centimetres",
    "SQF": "Square Feet", "SQM": "Square Metres", "BOX": "Box", "PAC": "Packs",
    "SET": "Sets", "DOZ": "Dozens", "BAG": "Bags", "BTL": "Bottles", "CTN": "Cartons",
    "QTL": "Quintal", "TON": "Tonnes", "UNT": "Units", "OTH": "Others",
}


class Role(str, Enum):
    OWNER = "OWNER"            # subscriber: owns the account, its plan and businesses
    ADMIN = "ADMIN"            # business admin / branch manager
    MANAGER = "MANAGER"        # store manager
    BILLING = "BILLING"        # billing operator / cashier
    INVENTORY = "INVENTORY"    # purchase & inventory clerk
    ACCOUNTANT = "ACCOUNTANT"  # CA / auditor (read-only)


class PlatformRole(str, Enum):
    SUPERADMIN = "SUPERADMIN"  # SaaS owner / tech team
    RESELLER = "RESELLER"      # channel partner: sells licences, never sees business data


class BusinessGstType(str, Enum):
    REGULAR = "REGULAR"            # charges GST, issues Tax Invoices
    COMPOSITION = "COMPOSITION"    # issues Bill of Supply, cannot collect GST
    UNREGISTERED = "UNREGISTERED"  # not GST registered


class PartyType(str, Enum):
    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"
    BOTH = "BOTH"


class PartyGstType(str, Enum):
    REGISTERED = "REGISTERED"
    COMPOSITION = "COMPOSITION"
    UNREGISTERED = "UNREGISTERED"
    CONSUMER = "CONSUMER"
    SEZ = "SEZ"
    OVERSEAS = "OVERSEAS"


GSTIN_REQUIRED_PARTY_TYPES = {PartyGstType.REGISTERED, PartyGstType.COMPOSITION, PartyGstType.SEZ}


class ItemType(str, Enum):
    GOODS = "GOODS"
    SERVICE = "SERVICE"


class VoucherType(str, Enum):
    SALE = "SALE"
    SALE_RETURN = "SALE_RETURN"            # Credit Note
    PURCHASE = "PURCHASE"
    PURCHASE_RETURN = "PURCHASE_RETURN"    # Debit Note
    ESTIMATE = "ESTIMATE"                  # Quotation (no stock / ledger effect)
    DELIVERY_CHALLAN = "DELIVERY_CHALLAN"  # goods/services sent; stock moves when invoiced
    SALE_ORDER = "SALE_ORDER"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    EXPENSE = "EXPENSE"                    # business expense (lines use expense items)


class PaymentType(str, Enum):
    IN = "IN"    # received from party
    OUT = "OUT"  # paid to party


class PaymentMode(str, Enum):
    CASH = "CASH"
    BANK = "BANK"
    UPI = "UPI"
    CHEQUE = "CHEQUE"
    CARD = "CARD"
    OTHER = "OTHER"


class AccountType(str, Enum):
    CASH = "CASH"
    BANK = "BANK"


class ExpenseKind(str, Enum):
    DIRECT = "DIRECT"      # part of cost of goods (manufacturing, freight inward, wages)
    INDIRECT = "INDIRECT"  # operating expense (rent, salary, petrol, tea)


class CapitalType(str, Enum):
    INTRODUCED = "INTRODUCED"
    DRAWINGS = "DRAWINGS"


class LoanTxnType(str, Enum):
    DISBURSEMENT = "DISBURSEMENT"  # loan amount received
    EMI = "EMI"                    # repayment: principal + interest
    CHARGES = "CHARGES"            # processing fee / penalty


class TaxPaymentType(str, Enum):
    GST = "GST"
    TDS = "TDS"
    TCS = "TCS"


class StockMoveType(str, Enum):
    OPENING = "OPENING"
    SALE = "SALE"
    SALE_RETURN = "SALE_RETURN"
    PURCHASE = "PURCHASE"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    ADJUSTMENT = "ADJUSTMENT"
    TRANSFER = "TRANSFER"  # between godowns; nets to zero overall


# Per voucher type: stock direction, party ledger direction (+ = party owes us more),
# default number prefix field on Business, and which item price to prefill.
VOUCHER_META = {
    VoucherType.SALE: dict(stock=-1, ledger=1, prefix="invoice_prefix", price="sale", outward=True),
    VoucherType.SALE_RETURN: dict(stock=1, ledger=-1, prefix="credit_note_prefix", price="sale", outward=True),
    VoucherType.PURCHASE: dict(stock=1, ledger=-1, prefix="purchase_prefix", price="purchase", outward=False),
    VoucherType.PURCHASE_RETURN: dict(stock=-1, ledger=1, prefix="debit_note_prefix", price="purchase", outward=False),
    VoucherType.ESTIMATE: dict(stock=0, ledger=0, prefix="estimate_prefix", price="sale", outward=True),
    VoucherType.DELIVERY_CHALLAN: dict(stock=0, ledger=0, prefix="challan_prefix", price="sale", outward=True),
    VoucherType.SALE_ORDER: dict(stock=0, ledger=0, prefix="sale_order_prefix", price="sale", outward=True),
    VoucherType.PURCHASE_ORDER: dict(stock=0, ledger=0, prefix="purchase_order_prefix", price="purchase", outward=False),
    VoucherType.EXPENSE: dict(stock=0, ledger=-1, prefix="expense_prefix", price="purchase", outward=False),
}

# Documents that can be converted into a bill, and what they become.
CONVERSIONS = {
    VoucherType.ESTIMATE: VoucherType.SALE,
    VoucherType.SALE_ORDER: VoucherType.SALE,
    VoucherType.DELIVERY_CHALLAN: VoucherType.SALE,
    VoucherType.PURCHASE_ORDER: VoucherType.PURCHASE,
}
NON_LEDGER_TYPES = {t for t, m in VOUCHER_META.items() if not m["ledger"]}

PAYMENT_LEDGER = {PaymentType.IN: -1, PaymentType.OUT: 1}


def document_title(vtype: VoucherType, tax_applicable: bool) -> str:
    if vtype == VoucherType.SALE:
        return "Tax Invoice" if tax_applicable else "Bill of Supply"
    return {
        VoucherType.SALE_RETURN: "Credit Note",
        VoucherType.PURCHASE: "Purchase Bill",
        VoucherType.PURCHASE_RETURN: "Debit Note",
        VoucherType.ESTIMATE: "Estimate / Quotation",
        VoucherType.DELIVERY_CHALLAN: "Delivery Challan",
        VoucherType.SALE_ORDER: "Sale Order",
        VoucherType.PURCHASE_ORDER: "Purchase Order",
        VoucherType.EXPENSE: "Expense",
    }[vtype]
