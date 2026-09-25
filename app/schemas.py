"""Pydantic request / response models."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    StringConstraints,
    field_validator,
    model_validator,
)

from .gst.constants import (
    GST_RATES,
    AccountType,
    CapitalType,
    ExpenseKind,
    LoanTxnType,
    TaxPaymentType,
    GSTIN_REQUIRED_PARTY_TYPES,
    UQC,
    BusinessGstType,
    ItemType,
    PartyGstType,
    PartyType,
    PaymentMode,
    PaymentType,
    Role,
    StockMoveType,
    VoucherType,
)
from .gst.gstin import PAN_RE, pan_from_gstin, validate_gstin
from .gst.states import STATES

# Decimals go over the wire as JSON numbers (pydantic's default is strings).
Num = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


def _blank_to_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def Opt(max_len: int = 200):
    return Annotated[
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=max_len)] | None,
        BeforeValidator(_blank_to_none),
    ]


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Prefix = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9-]{1,5}$")]
DocNumber = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9/-]{1,16}$")]
NonNeg = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


def _check_gst_rate(v: Decimal) -> Decimal:
    if v not in GST_RATES:
        raise ValueError(f"GST rate must be one of {', '.join(str(r) for r in GST_RATES)}")
    return v


def _check_state(v: str | None) -> str | None:
    if v is not None and v not in STATES:
        raise ValueError("Invalid state code")
    return v


def _check_gstin(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.upper()
    err = validate_gstin(v)
    if err:
        raise ValueError(err)
    return v


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth ----------
class RegisterIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]
    phone: Opt(20) = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORM):
    id: str
    name: str
    email: str
    phone: str | None


class MyBusinessOut(BaseModel):
    id: str
    name: str
    gstin: str | None
    gst_type: BusinessGstType
    role: Role
    owned: bool = False
    permissions: dict | None = None


class MeOut(BaseModel):
    user: UserOut
    platform_role: str | None = None
    businesses: list[MyBusinessOut]


class TokenOut(MeOut):
    token: str


# ---------- business ----------
class CustomField(BaseModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,30}$")]
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    print: bool = True


class PrintSettings(BaseModel):
    """How invoices look. Stored as JSON on the business."""
    theme: Literal["classic", "modern", "minimal"] = "classic"
    accent: Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")] = "#1f65bb"
    paper: Literal["A4", "A5", "THERMAL_80", "THERMAL_58"] = "A4"
    copy_labels: list[Literal["ORIGINAL", "DUPLICATE", "TRIPLICATE"]] = ["ORIGINAL"]
    show_hsn: bool = True
    show_discount: bool = True
    show_tax_summary: bool = True
    show_bank: bool = True
    show_upi_qr: bool = True
    show_terms: bool = True
    show_signature: bool = True
    show_item_description: bool = True
    show_transport: bool = True
    title_override: Opt(40) = None
    footer_note: Opt(300) = None
    custom_fields: Annotated[list[CustomField], Field(max_length=8)] = []


class BusinessIn(BaseModel):
    name: Name
    legal_name: Opt() = None
    gst_type: BusinessGstType
    gstin: Opt(15) = None
    pan: Opt(10) = None
    state_code: str
    address: Opt(500) = None
    city: Opt(100) = None
    pincode: Opt(10) = None
    phone: Opt(20) = None
    email: Opt(200) = None
    logo_url: Opt(500) = None
    signature_url: Opt(500) = None
    bank_name: Opt(120) = None
    bank_account_no: Opt(40) = None
    bank_ifsc: Opt(11) = None
    bank_branch: Opt(120) = None
    upi_id: Opt(100) = None
    invoice_prefix: Prefix = "INV"
    credit_note_prefix: Prefix = "CN"
    debit_note_prefix: Prefix = "DN"
    estimate_prefix: Prefix = "EST"
    purchase_prefix: Prefix = "PUR"
    receipt_prefix: Prefix = "RCT"
    payment_prefix: Prefix = "PAY"
    challan_prefix: Prefix = "DC"
    sale_order_prefix: Prefix = "SO"
    purchase_order_prefix: Prefix = "PO"
    expense_prefix: Prefix = "EXP"
    invoice_terms: Opt(2000) = None
    auto_backup: bool = True
    backup_email: Opt(200) = None
    transfer_prefix: Prefix = "ST"
    print_settings: PrintSettings = PrintSettings()
    einvoice_username: Opt(100) = None
    einvoice_password: Opt(100) = None  # write-only; stored encrypted

    _gstin = field_validator("gstin")(_check_gstin)
    _state = field_validator("state_code")(_check_state)

    @field_validator("bank_ifsc", "pan")
    @classmethod
    def _upper(cls, v):
        return v.upper() if v else v

    @model_validator(mode="after")
    def _gst_rules(self):
        if self.gst_type != BusinessGstType.UNREGISTERED and not self.gstin:
            raise ValueError("GSTIN is required for GST registered businesses")
        if self.gst_type == BusinessGstType.UNREGISTERED:
            self.gstin = None
        if self.gstin:
            if self.gstin[:2] != self.state_code:
                raise ValueError("State does not match the state code in the GSTIN")
            self.pan = pan_from_gstin(self.gstin)
        if self.pan and not PAN_RE.match(self.pan):
            raise ValueError("Invalid PAN")
        return self


class BusinessOut(ORM):
    id: str
    name: str
    legal_name: str | None
    gst_type: BusinessGstType
    gstin: str | None
    pan: str | None
    state_code: str
    address: str | None
    city: str | None
    pincode: str | None
    phone: str | None
    email: str | None
    logo_url: str | None
    signature_url: str | None
    bank_name: str | None
    bank_account_no: str | None
    bank_ifsc: str | None
    bank_branch: str | None
    upi_id: str | None
    invoice_prefix: str
    credit_note_prefix: str
    debit_note_prefix: str
    estimate_prefix: str
    purchase_prefix: str
    receipt_prefix: str
    payment_prefix: str
    challan_prefix: str
    sale_order_prefix: str
    purchase_order_prefix: str
    expense_prefix: str
    invoice_terms: str | None
    auto_backup: bool
    backup_email: str | None
    transfer_prefix: str
    print_settings: PrintSettings | None
    einvoice_username: str | None
    einvoice_password_set: bool = False
    plan: dict | None = None


# ---------- parties ----------
class PartyIn(BaseModel):
    type: PartyType = PartyType.CUSTOMER
    name: Name
    gst_type: PartyGstType = PartyGstType.UNREGISTERED
    gstin: Opt(15) = None
    pan: Opt(10) = None
    phone: Opt(20) = None
    email: Opt(200) = None
    state_code: Opt(2) = None
    billing_address: Opt(500) = None
    city: Opt(100) = None
    pincode: Opt(10) = None
    shipping_address: Opt(500) = None
    opening_balance: Annotated[Decimal, Field(max_digits=14, decimal_places=2)] = Decimal("0")
    credit_limit: NonNeg | None = None

    _gstin = field_validator("gstin")(_check_gstin)
    _state = field_validator("state_code")(_check_state)

    @model_validator(mode="after")
    def _gst_rules(self):
        if self.gst_type in GSTIN_REQUIRED_PARTY_TYPES and not self.gstin:
            raise ValueError(f"GSTIN is required for a {self.gst_type.value.lower()} party")
        if self.gstin:
            if self.state_code and self.state_code != self.gstin[:2]:
                raise ValueError("State does not match the state code in the GSTIN")
            self.state_code = self.gstin[:2]
            self.pan = pan_from_gstin(self.gstin)
            if self.gst_type in (PartyGstType.UNREGISTERED, PartyGstType.CONSUMER):
                self.gst_type = PartyGstType.REGISTERED
        return self


class PartyOut(ORM):
    id: str
    type: PartyType
    name: str
    gst_type: PartyGstType
    gstin: str | None
    pan: str | None
    phone: str | None
    email: str | None
    state_code: str | None
    billing_address: str | None
    city: str | None
    pincode: str | None
    shipping_address: str | None
    opening_balance: Num
    credit_limit: Num | None
    is_active: bool
    balance: Num = Decimal("0")  # + receivable / - payable


# ---------- items ----------
class ItemIn(BaseModel):
    type: ItemType = ItemType.GOODS
    name: Name
    code: Opt(50) = None
    hsn_sac: Annotated[str | None, BeforeValidator(_blank_to_none), Field(pattern=r"^\d{4,8}$")] = None
    unit: str = "NOS"
    category: Opt(100) = None
    description: Opt(1000) = None
    image_url: Opt(500) = None
    sale_price: NonNeg = Decimal("0")
    sale_price_tax_inclusive: bool = False
    purchase_price: NonNeg = Decimal("0")
    purchase_price_tax_inclusive: bool = False
    mrp: NonNeg | None = None
    gst_rate: Decimal = Decimal("0")
    cess_rate: Annotated[Decimal, Field(ge=0, le=300)] = Decimal("0")
    low_stock_level: Annotated[Decimal, Field(ge=0)] | None = None
    track_batch: bool = False
    track_serial: bool = False
    opening_stock: Decimal = Decimal("0")  # used on create only
    opening_stock_date: dt.date | None = None

    _rate = field_validator("gst_rate")(_check_gst_rate)

    @field_validator("unit")
    @classmethod
    def _unit(cls, v: str):
        v = v.upper()
        if v not in UQC:
            raise ValueError("Unknown unit")
        return v


class ItemOut(ORM):
    id: str
    type: ItemType
    name: str
    code: str | None
    hsn_sac: str | None
    unit: str
    category: str | None
    description: str | None
    image_url: str | None
    sale_price: Num
    sale_price_tax_inclusive: bool
    purchase_price: Num
    purchase_price_tax_inclusive: bool
    mrp: Num | None
    gst_rate: Num
    cess_rate: Num
    low_stock_level: Num | None
    track_batch: bool
    track_serial: bool
    is_active: bool
    stock: Num = Decimal("0")


class StockAdjustIn(BaseModel):
    qty: Annotated[Decimal, Field(gt=0)]
    direction: Literal["ADD", "REDUCE"]
    date: dt.date
    note: Opt(200) = None


class StockMoveOut(ORM):
    id: str
    date: dt.date
    type: StockMoveType
    qty: Num
    rate: Num | None
    voucher_id: str | None
    note: str | None


# ---------- vouchers ----------
class VoucherLineIn(BaseModel):
    item_id: str | None = None
    expense_item_id: str | None = None
    batch_no: Opt(50) = None
    mfg_date: dt.date | None = None
    expiry_date: dt.date | None = None
    serial_nos: Opt(2000) = None
    name: Name
    description: Opt(500) = None
    hsn_sac: Opt(8) = None
    unit: Opt(10) = None
    qty: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
    rate: NonNeg
    discount_pct: Annotated[Decimal, Field(ge=0, le=100)] = Decimal("0")
    gst_rate: Decimal = Decimal("0")
    cess_rate: Annotated[Decimal, Field(ge=0, le=300)] = Decimal("0")
    tax_inclusive: bool = False

    _rate = field_validator("gst_rate")(_check_gst_rate)


class TransportIn(BaseModel):
    """Transport details printed on the bill and used for the e-way bill."""
    mode: Literal["1", "2", "3", "4"] = "1"  # road / rail / air / ship
    vehicle_no: Opt(20) = None
    vehicle_type: Literal["R", "O"] = "R"  # regular / over-dimensional cargo
    transporter_name: Opt(100) = None
    transporter_id: Opt(15) = None  # transporter GSTIN / TRANSIN
    doc_no: Opt(20) = None          # LR / RR / airway bill no.
    doc_date: dt.date | None = None
    distance_km: Annotated[int, Field(ge=0, le=4000)] = 0
    sub_supply_type: Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"] = "1"
    ship_to: Opt(300) = None

    @field_validator("vehicle_no")
    @classmethod
    def _veh(cls, v):
        return v.upper().replace(" ", "") if v else v


class VoucherIn(BaseModel):
    type: VoucherType
    number: DocNumber | None = None  # auto-generated when blank
    date: dt.date
    due_date: dt.date | None = None
    party_id: str | None = None
    party_name: Opt() = None  # walk-in customer name when no party is selected
    party_phone: Opt(20) = None
    place_of_supply: Opt(2) = None
    tax_applicable: bool | None = None  # purchases only: did the supplier charge GST?
    reverse_charge: bool = False
    supplier_invoice_no: Opt(50) = None
    supplier_invoice_date: dt.date | None = None
    original_voucher_id: str | None = None
    reason: Opt(200) = None
    notes: Opt(2000) = None
    terms: Opt(2000) = None
    round_off: bool = True
    tcs_rate: Annotated[Decimal, Field(ge=0, le=10)] = Decimal("0")
    expense_category_id: str | None = None  # expenses only
    lines: Annotated[list[VoucherLineIn], Field(min_length=1, max_length=500)]
    amount_paid: NonNeg = Decimal("0")  # create only: received/paid right now
    fully_paid: bool = False  # create only: pay the full bill total now
    payment_mode: PaymentMode = PaymentMode.CASH
    payment_account_id: str | None = None  # defaults to cash in hand
    source_voucher_id: str | None = None   # estimate / order / challan being converted
    godown_id: str | None = None           # stock location; default godown when empty
    transport: "TransportIn | None" = None
    extra_fields: dict[str, Annotated[str, StringConstraints(max_length=200)]] | None = None

    _pos = field_validator("place_of_supply")(_check_state)

    @field_validator("number", mode="before")
    @classmethod
    def _blank_number(cls, v):
        return _blank_to_none(v)


class VoucherLineOut(ORM):
    id: str
    item_id: str | None
    expense_item_id: str | None
    batch_no: str | None
    mfg_date: dt.date | None
    expiry_date: dt.date | None
    serial_nos: str | None
    name: str
    description: str | None
    hsn_sac: str | None
    unit: str | None
    qty: Num
    rate: Num
    tax_inclusive: bool
    discount_pct: Num
    gst_rate: Num
    cess_rate: Num
    amount: Num
    discount: Num
    taxable: Num
    cgst: Num
    sgst: Num
    igst: Num
    cess: Num
    total: Num


class VoucherOut(ORM):
    id: str
    type: VoucherType
    number: str
    date: dt.date
    due_date: dt.date | None
    party_id: str | None
    party_name: str
    party_gstin: str | None
    party_state_code: str | None
    party_address: str | None
    party_phone: str | None
    place_of_supply: str
    inter_state: bool
    tax_applicable: bool
    reverse_charge: bool
    supplier_invoice_no: str | None
    supplier_invoice_date: dt.date | None
    original_voucher_id: str | None
    reason: str | None
    sub_total: Num
    discount: Num
    taxable: Num
    cgst: Num
    sgst: Num
    igst: Num
    cess: Num
    tcs_rate: Num
    tcs_amount: Num
    round_off: Num
    grand_total: Num
    notes: str | None
    terms: str | None
    cancelled: bool
    converted_to_id: str | None
    source_voucher_id: str | None
    expense_category_id: str | None
    godown_id: str | None
    transport: dict | None
    extra_fields: dict | None
    irn: str | None
    ack_no: str | None
    ack_date: dt.datetime | None
    signed_qr: str | None
    einvoice_status: str | None
    einvoice_sandbox: bool
    ewb_no: str | None
    ewb_date: dt.datetime | None
    ewb_valid_till: dt.datetime | None
    paid: Num = Decimal("0")
    balance: Num = Decimal("0")
    status: str = ""
    title: str = ""


class TaxBucketOut(BaseModel):
    rate: Num
    taxable: Num
    cgst: Num
    sgst: Num
    igst: Num
    cess: Num


class VoucherDetailOut(VoucherOut):
    lines: list[VoucherLineOut]
    tax_breakup: list[TaxBucketOut] = []
    amount_in_words: str = ""
    original_number: str | None = None


# ---------- payments ----------
class PaymentIn(BaseModel):
    type: PaymentType
    date: dt.date
    party_id: str
    amount: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
    tds_amount: NonNeg = Decimal("0")
    account_id: str | None = None  # defaults to cash in hand
    mode: PaymentMode = PaymentMode.CASH
    reference: Opt(100) = None
    notes: Opt(1000) = None
    cheque_date: dt.date | None = None
    voucher_id: str | None = None  # settle this bill first
    auto_allocate: bool = True     # then settle oldest open bills (FIFO)


class AllocationOut(ORM):
    voucher_id: str
    voucher_number: str
    amount: Num


class PaymentOut(ORM):
    id: str
    type: PaymentType
    number: str
    date: dt.date
    party_id: str | None
    party_name: str | None = None
    amount: Num
    tds_amount: Num
    account_id: str
    account_name: str | None = None
    mode: PaymentMode
    reference: str | None
    notes: str | None
    cheque_status: str | None
    cheque_date: dt.date | None
    cleared_on: dt.date | None
    allocated: Num = Decimal("0")
    allocations: list[AllocationOut] = []


# ---------- cash & bank ----------
class AccountIn(BaseModel):
    type: AccountType = AccountType.BANK
    name: Name
    bank_name: Opt(120) = None
    account_no: Opt(40) = None
    ifsc: Opt(11) = None
    opening_balance: Annotated[Decimal, Field(max_digits=14, decimal_places=2)] = Decimal("0")
    opening_date: dt.date | None = None


class AccountOut(ORM):
    id: str
    type: AccountType
    name: str
    bank_name: str | None
    account_no: str | None
    ifsc: str | None
    opening_balance: Num
    opening_date: dt.date | None
    is_default_cash: bool
    is_active: bool
    balance: Num = Decimal("0")


class TransferIn(BaseModel):
    date: dt.date
    from_account_id: str
    to_account_id: str
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    note: Opt(200) = None


class TransferOut(ORM):
    id: str
    date: dt.date
    from_account_id: str
    to_account_id: str
    amount: Num
    note: str | None


class CapitalIn(BaseModel):
    date: dt.date
    type: CapitalType
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    account_id: str | None = None
    note: Opt(200) = None


class CapitalOut(ORM):
    id: str
    date: dt.date
    type: CapitalType
    amount: Num
    account_id: str
    note: str | None


class TaxPaymentIn(BaseModel):
    date: dt.date
    type: TaxPaymentType
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    account_id: str | None = None
    reference: Opt(100) = None
    period: Opt(20) = None
    note: Opt(200) = None


class TaxPaymentOut(ORM):
    id: str
    date: dt.date
    type: TaxPaymentType
    amount: Num
    account_id: str
    reference: str | None
    period: str | None
    note: str | None


# ---------- loans ----------
class LoanIn(BaseModel):
    name: Name
    lender: Opt(120) = None
    account_no: Opt(40) = None
    interest_rate: Annotated[Decimal, Field(ge=0, le=100)] | None = None
    opening_balance: NonNeg = Decimal("0")
    opening_date: dt.date | None = None
    notes: Opt(1000) = None


class LoanOut(ORM):
    id: str
    name: str
    lender: str | None
    account_no: str | None
    interest_rate: Num | None
    opening_balance: Num
    opening_date: dt.date | None
    notes: str | None
    is_active: bool
    outstanding: Num = Decimal("0")


class LoanTxnIn(BaseModel):
    date: dt.date
    type: LoanTxnType
    principal: NonNeg = Decimal("0")
    interest: NonNeg = Decimal("0")
    account_id: str | None = None
    note: Opt(200) = None

    @model_validator(mode="after")
    def _amounts(self):
        if self.principal + self.interest <= 0:
            raise ValueError("Enter an amount")
        if self.type == LoanTxnType.DISBURSEMENT:
            self.interest = Decimal("0")
        if self.type == LoanTxnType.CHARGES:
            self.interest, self.principal = self.interest + self.principal, Decimal("0")
        return self


class LoanTxnOut(ORM):
    id: str
    loan_id: str
    date: dt.date
    type: LoanTxnType
    principal: Num
    interest: Num
    account_id: str
    note: str | None


# ---------- expenses ----------
class ExpenseCategoryIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    kind: ExpenseKind = ExpenseKind.INDIRECT


class ExpenseCategoryOut(ORM):
    id: str
    name: str
    kind: ExpenseKind
    is_active: bool
    total: Num = Decimal("0")


class ExpenseItemIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    category_id: str | None = None
    hsn_sac: Opt(8) = None
    rate: NonNeg = Decimal("0")
    gst_rate: Decimal = Decimal("0")

    _rate = field_validator("gst_rate")(_check_gst_rate)


class ExpenseItemOut(ORM):
    id: str
    name: str
    category_id: str | None
    hsn_sac: str | None
    rate: Num
    gst_rate: Num
    is_active: bool


# ---------- godowns ----------
class GodownIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    address: Opt(300) = None


class GodownOut(ORM):
    id: str
    name: str
    address: str | None
    is_default: bool
    is_active: bool
    stock_value: Num = Decimal("0")


class TransferLineIn(BaseModel):
    item_id: str
    qty: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
    batch_no: Opt(50) = None


class StockTransferIn(BaseModel):
    date: dt.date
    from_godown_id: str
    to_godown_id: str
    note: Opt(200) = None
    lines: Annotated[list[TransferLineIn], Field(min_length=1, max_length=500)]
