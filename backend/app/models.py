"""Database models. Every tenant-owned table carries business_id; all queries filter on it."""

import uuid
import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    LargeBinary,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .gst.constants import (
    AccountType,
    BusinessGstType,
    CapitalType,
    ExpenseKind,
    LoanTxnType,
    TaxPaymentType,
    ItemType,
    PartyGstType,
    PartyType,
    PaymentMode,
    PaymentType,
    Role,
    StockMoveType,
    VoucherType,
)

Money = Numeric(14, 2)
Qty = Numeric(14, 3)
Rate = Numeric(5, 2)


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _enum(e):
    return SAEnum(e, native_enum=False, length=20, validate_strings=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    mobile: Mapped[str | None] = mapped_column(String(12), unique=True, index=True)  # WhatsApp-verified, 91XXXXXXXXXX
    mobile_verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)  # "Continue with Google"
    legal_version: Mapped[str | None] = mapped_column(String(20))  # Terms / Privacy version last accepted
    password_hash: Mapped[str] = mapped_column(String(100))
    platform_role: Mapped[str | None] = mapped_column(String(12))  # SUPERADMIN / RESELLER / TEAM (company team)
    platform_areas: Mapped[list | None] = mapped_column(JSON)  # TEAM: admin areas they may use (services/platform_team.py)
    platform_team: Mapped[str | None] = mapped_column(String(12))  # TEAM: SUPPORT / TECH / FINANCE / SALES / ADMIN
    reseller_commission_pct: Mapped[Decimal | None] = mapped_column(Rate)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # security
    token_version: Mapped[int] = mapped_column(Integer, default=0)  # bump = sign out everywhere
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    totp_secret_enc: Mapped[str | None] = mapped_column(Text)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    previous_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))  # shown as 'last login'
    # set when a business owner created this login for a staff member (that business may reset its password
    # while the person works for no other business)
    created_by_business_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class Business(Base):
    __tablename__ = "businesses"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    # the subscriber account this business belongs to (its plan and limits apply)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    legal_name: Mapped[str | None] = mapped_column(String(200))
    gst_type: Mapped[BusinessGstType] = mapped_column(_enum(BusinessGstType))
    gstin: Mapped[str | None] = mapped_column(String(15))
    pan: Mapped[str | None] = mapped_column(String(10))
    state_code: Mapped[str] = mapped_column(String(2))
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    pincode: Mapped[str | None] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    signature_url: Mapped[str | None] = mapped_column(String(500))

    bank_name: Mapped[str | None] = mapped_column(String(120))
    bank_account_no: Mapped[str | None] = mapped_column(String(40))
    bank_ifsc: Mapped[str | None] = mapped_column(String(11))
    bank_branch: Mapped[str | None] = mapped_column(String(120))
    upi_id: Mapped[str | None] = mapped_column(String(100))

    invoice_prefix: Mapped[str] = mapped_column(String(8), default="INV")
    credit_note_prefix: Mapped[str] = mapped_column(String(8), default="CN")
    debit_note_prefix: Mapped[str] = mapped_column(String(8), default="DN")
    estimate_prefix: Mapped[str] = mapped_column(String(8), default="EST")
    purchase_prefix: Mapped[str] = mapped_column(String(8), default="PUR")
    receipt_prefix: Mapped[str] = mapped_column(String(8), default="RCT")
    payment_prefix: Mapped[str] = mapped_column(String(8), default="PAY")
    challan_prefix: Mapped[str] = mapped_column(String(8), default="DC")
    sale_order_prefix: Mapped[str] = mapped_column(String(8), default="SO")
    purchase_order_prefix: Mapped[str] = mapped_column(String(8), default="PO")
    expense_prefix: Mapped[str] = mapped_column(String(8), default="EXP")
    invoice_terms: Mapped[str | None] = mapped_column(Text)
    auto_backup: Mapped[bool] = mapped_column(Boolean, default=True)
    backup_email: Mapped[str | None] = mapped_column(String(200))
    reminder_settings: Mapped[dict | None] = mapped_column(JSON)  # payment reminders (see services/reminders.py)
    # date of GST registration (from the GST portal or typed in): the compliance calendar starts here
    gst_registration_date: Mapped[dt.date | None] = mapped_column(Date)
    # constitution of the business (drives the compliance calendar): PROPRIETORSHIP, PARTNERSHIP, LLP, PRIVATE_LIMITED, ...
    entity_type: Mapped[str] = mapped_column(String(20), default="PROPRIETORSHIP", server_default="PROPRIETORSHIP")
    # which menus the business uses: {"mode": "BOTH" | "GOODS" | "SERVICES", "hidden": [module keys]}
    modules: Mapped[dict | None] = mapped_column(JSON)
    # compliance calendar answers: {"gst_filing": "MONTHLY" | "QUARTERLY", "tax_audit": bool, "tds": bool, ...}
    compliance_settings: Mapped[dict | None] = mapped_column(JSON)
    # staff sign-in rules (approval / office IPs / hours) — see services/staff_access.py
    staff_access: Mapped[dict | None] = mapped_column(JSON)
    transfer_prefix: Mapped[str] = mapped_column(String(8), default="ST")
    # exports / SEZ under Letter of Undertaking (zero-rated without paying IGST)
    lut_number: Mapped[str | None] = mapped_column(String(30))
    lut_valid_till: Mapped[dt.date | None] = mapped_column(Date)
    # composition scheme category: TRADER / MANUFACTURER (1%), RESTAURANT (5%), SERVICE (6%)
    composition_type: Mapped[str] = mapped_column(String(12), default="TRADER", server_default="TRADER")
    # invoice look & feel, custom fields, paper size... (see schemas.PrintSettings)
    print_settings: Mapped[dict | None] = mapped_column(JSON)
    # e-invoice / e-way bill API user created on the IRP / EWB portal (password encrypted)
    einvoice_username: Mapped[str | None] = mapped_column(String(100))
    einvoice_password_enc: Mapped[str | None] = mapped_column(Text)
    ewb_username: Mapped[str | None] = mapped_column(String(100))  # e-way bill portal API user (separate from e-invoice)
    ewb_password_enc: Mapped[str | None] = mapped_column(Text)
    # e-invoicing is mandatory for this business (aggregate turnover above the notified limit)
    einvoice_applicable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # selling more than is in stock: WARN (confirm) / BLOCK (manager approval) / ALLOW — see services/stock_control.py
    stock_control: Mapped[str] = mapped_column(String(5), default="WARN", server_default="WARN")
    # Excel backups (.zip) — set by the super admin: None = platform default, True / False = this business only
    excel_backup: Mapped[bool | None] = mapped_column(Boolean)
    # GST filing-status sync — set by the super admin: None = platform default, True / False = this business only
    filing_sync: Mapped[bool | None] = mapped_column(Boolean)
    # e-mail sender assigned by the super admin (None = the platform default, under the business's name)
    mail_sender_id: Mapped[str | None] = mapped_column(ForeignKey("mail_senders.id", ondelete="SET NULL"))
    # payroll defaults: weekly offs, holidays, salary basis — see services/payroll.py
    payroll_settings: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "business_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    role: Mapped[Role] = mapped_column(_enum(Role))
    permissions: Mapped[dict | None] = mapped_column(JSON)  # custom role matrix (Enterprise)
    approval_pin_hash: Mapped[str | None] = mapped_column(String(100))  # managers approve edits of old entries
    # ACTIVE, or INVITED until a person who already has a login accepts the invitation
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE", server_default="ACTIVE")
    invited_by: Mapped[str | None] = mapped_column(String(200))

    user: Mapped[User] = relationship(back_populates="memberships")
    business: Mapped[Business] = relationship()


class Party(Base):
    __tablename__ = "parties"
    __table_args__ = (Index("ix_parties_business_name", "business_id", "name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    type: Mapped[PartyType] = mapped_column(_enum(PartyType))
    name: Mapped[str] = mapped_column(String(200))
    gst_type: Mapped[PartyGstType] = mapped_column(_enum(PartyGstType))
    gstin: Mapped[str | None] = mapped_column(String(15))
    pan: Mapped[str | None] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    state_code: Mapped[str | None] = mapped_column(String(2))
    billing_address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    pincode: Mapped[str | None] = mapped_column(String(10))
    shipping_address: Mapped[str | None] = mapped_column(Text)
    # Signed: positive = receivable (party owes us), negative = payable.
    opening_balance: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    credit_limit: Mapped[Decimal | None] = mapped_column(Money)
    price_list_id: Mapped[str | None] = mapped_column(ForeignKey("price_lists.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (Index("ix_items_business_name", "business_id", "name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    type: Mapped[ItemType] = mapped_column(_enum(ItemType))
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(50))
    hsn_sac: Mapped[str | None] = mapped_column(String(8))
    unit: Mapped[str] = mapped_column(String(10), default="NOS")
    category: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    sale_price: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    sale_price_tax_inclusive: Mapped[bool] = mapped_column(Boolean, default=False)
    purchase_price: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    purchase_price_tax_inclusive: Mapped[bool] = mapped_column(Boolean, default=False)
    mrp: Mapped[Decimal | None] = mapped_column(Money)
    gst_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"))
    cess_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"))
    low_stock_level: Mapped[Decimal | None] = mapped_column(Qty)
    track_batch: Mapped[bool] = mapped_column(Boolean, default=False)
    track_serial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Account(Base):
    """A cash-in-hand or bank account that money moves through."""

    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    type: Mapped[AccountType] = mapped_column(_enum(AccountType))
    name: Mapped[str] = mapped_column(String(120))
    bank_name: Mapped[str | None] = mapped_column(String(120))
    account_no: Mapped[str | None] = mapped_column(String(40))
    ifsc: Mapped[str | None] = mapped_column(String(11))
    opening_balance: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    opening_date: Mapped[dt.date | None] = mapped_column(Date)
    is_default_cash: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Godown(Base):
    """A warehouse / shop / store location that holds stock."""

    __tablename__ = "godowns"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class StockTransfer(Base):
    """Move stock from one godown to another (no effect on quantity overall or on accounts)."""

    __tablename__ = "stock_transfers"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    number: Mapped[str] = mapped_column(String(30))
    date: Mapped[dt.date] = mapped_column(Date)
    from_godown_id: Mapped[str] = mapped_column(ForeignKey("godowns.id", ondelete="RESTRICT"))
    to_godown_id: Mapped[str] = mapped_column(ForeignKey("godowns.id", ondelete="RESTRICT"))
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_expense_category"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[ExpenseKind] = mapped_column(_enum(ExpenseKind), default=ExpenseKind.INDIRECT)
    # Sec 17(5) blocked credit (food & beverages, personal use, motor vehicles…): GST becomes cost
    itc_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExpenseItem(Base):
    __tablename__ = "expense_items"
    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_expense_item"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("expense_categories.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120))
    hsn_sac: Mapped[str | None] = mapped_column(String(8))
    rate: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    gst_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Voucher(Base):
    """Any billing document: sale invoice, purchase bill, credit/debit note, estimate."""

    __tablename__ = "vouchers"
    __table_args__ = (
        UniqueConstraint("business_id", "type", "number", name="uq_voucher_number"),
        UniqueConstraint("business_id", "client_ref", name="uq_voucher_client_ref"),
        Index("ix_vouchers_business_type_date", "business_id", "type", "date"),
        Index("ix_vouchers_party", "party_id"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    type: Mapped[VoucherType] = mapped_column(_enum(VoucherType))
    number: Mapped[str] = mapped_column(String(30))
    date: Mapped[dt.date] = mapped_column(Date)
    due_date: Mapped[dt.date | None] = mapped_column(Date)

    # Party snapshot — the document must not change if the party master is edited later.
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"))
    party_name: Mapped[str] = mapped_column(String(200))
    party_gstin: Mapped[str | None] = mapped_column(String(15))
    party_state_code: Mapped[str | None] = mapped_column(String(2))
    party_address: Mapped[str | None] = mapped_column(Text)
    party_phone: Mapped[str | None] = mapped_column(String(20))

    place_of_supply: Mapped[str] = mapped_column(String(2))
    inter_state: Mapped[bool] = mapped_column(Boolean)
    tax_applicable: Mapped[bool] = mapped_column(Boolean)
    reverse_charge: Mapped[bool] = mapped_column(Boolean, default=False)

    supplier_invoice_no: Mapped[str | None] = mapped_column(String(50))
    supplier_invoice_date: Mapped[dt.date | None] = mapped_column(Date)
    original_voucher_id: Mapped[str | None] = mapped_column(ForeignKey("vouchers.id", ondelete="SET NULL"))
    reason: Mapped[str | None] = mapped_column(String(200))
    expense_category_id: Mapped[str | None] = mapped_column(ForeignKey("expense_categories.id", ondelete="RESTRICT"))
    source_voucher_id: Mapped[str | None] = mapped_column(String(32))  # order / challan / estimate it came from
    godown_id: Mapped[str | None] = mapped_column(ForeignKey("godowns.id", ondelete="RESTRICT"))
    # vehicle no, transporter, distance, LR... used on the bill and for the e-way bill
    transport: Mapped[dict | None] = mapped_column(JSON)
    extra_fields: Mapped[dict | None] = mapped_column(JSON)  # business-defined custom fields (PO no. etc.)
    # e-invoice (IRN) and e-way bill
    irn: Mapped[str | None] = mapped_column(String(64))
    ack_no: Mapped[str | None] = mapped_column(String(20))
    ack_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    signed_qr: Mapped[str | None] = mapped_column(Text)
    einvoice_status: Mapped[str | None] = mapped_column(String(12))  # GENERATED / CANCELLED
    einvoice_sandbox: Mapped[bool] = mapped_column(Boolean, default=False)
    ewb_no: Mapped[str | None] = mapped_column(String(20))
    ewb_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    ewb_valid_till: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    sub_total: Mapped[Decimal] = mapped_column(Money)
    discount: Mapped[Decimal] = mapped_column(Money)
    taxable: Mapped[Decimal] = mapped_column(Money)
    cgst: Mapped[Decimal] = mapped_column(Money)
    sgst: Mapped[Decimal] = mapped_column(Money)
    igst: Mapped[Decimal] = mapped_column(Money)
    cess: Mapped[Decimal] = mapped_column(Money)
    tcs_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"))
    tcs_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    round_off: Mapped[Decimal] = mapped_column(Money)
    grand_total: Mapped[Decimal] = mapped_column(Money)

    notes: Mapped[str | None] = mapped_column(Text)
    terms: Mapped[str | None] = mapped_column(Text)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    share_token: Mapped[str | None] = mapped_column(String(40), unique=True)  # public view link
    recurring_id: Mapped[str | None] = mapped_column(ForeignKey("recurring_invoices.id", ondelete="SET NULL"), index=True)
    client_ref: Mapped[str | None] = mapped_column(String(40))  # set by the app for bills made offline (idempotent upload)
    # exports / SEZ / imports: EXPWP, EXPWOP, SEZWP, SEZWOP (outward) or IMPORT (inward)
    export_type: Mapped[str | None] = mapped_column(String(8))
    shipping_bill_no: Mapped[str | None] = mapped_column(String(20))  # or bill of entry no. for imports
    shipping_bill_date: Mapped[dt.date | None] = mapped_column(Date)
    port_code: Mapped[str | None] = mapped_column(String(10))
    currency_code: Mapped[str | None] = mapped_column(String(3))
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    converted_to_id: Mapped[str | None] = mapped_column(String(32))  # estimate -> invoice
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    lines: Mapped[list["VoucherLine"]] = relationship(
        back_populates="voucher", cascade="all, delete-orphan", order_by="VoucherLine.sort_order"
    )
    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        back_populates="voucher", cascade="all, delete-orphan"
    )
    party: Mapped[Party | None] = relationship()
    expense_category: Mapped[ExpenseCategory | None] = relationship()


class VoucherLine(Base):
    __tablename__ = "voucher_lines"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    voucher_id: Mapped[str] = mapped_column(ForeignKey("vouchers.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))
    expense_item_id: Mapped[str | None] = mapped_column(ForeignKey("expense_items.id", ondelete="SET NULL"))
    batch_no: Mapped[str | None] = mapped_column(String(50))
    mfg_date: Mapped[dt.date | None] = mapped_column(Date)
    expiry_date: Mapped[dt.date | None] = mapped_column(Date)
    serial_nos: Mapped[str | None] = mapped_column(Text)  # comma separated
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    hsn_sac: Mapped[str | None] = mapped_column(String(8))
    unit: Mapped[str | None] = mapped_column(String(10))
    qty: Mapped[Decimal] = mapped_column(Qty)
    rate: Mapped[Decimal] = mapped_column(Money)
    tax_inclusive: Mapped[bool] = mapped_column(Boolean, default=False)
    discount_pct: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"))
    gst_rate: Mapped[Decimal] = mapped_column(Rate)
    cess_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(Money)
    discount: Mapped[Decimal] = mapped_column(Money)
    taxable: Mapped[Decimal] = mapped_column(Money)
    cgst: Mapped[Decimal] = mapped_column(Money)
    sgst: Mapped[Decimal] = mapped_column(Money)
    igst: Mapped[Decimal] = mapped_column(Money)
    cess: Mapped[Decimal] = mapped_column(Money)
    total: Mapped[Decimal] = mapped_column(Money)

    voucher: Mapped[Voucher] = relationship(back_populates="lines")


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (Index("ix_stock_business_item_date", "business_id", "item_id", "date"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    date: Mapped[dt.date] = mapped_column(Date)
    type: Mapped[StockMoveType] = mapped_column(_enum(StockMoveType))
    qty: Mapped[Decimal] = mapped_column(Qty)  # signed: + in, - out
    rate: Mapped[Decimal | None] = mapped_column(Money)
    batch_no: Mapped[str | None] = mapped_column(String(50))
    godown_id: Mapped[str | None] = mapped_column(ForeignKey("godowns.id", ondelete="RESTRICT"), index=True)
    transfer_id: Mapped[str | None] = mapped_column(ForeignKey("stock_transfers.id", ondelete="CASCADE"), index=True)
    production_id: Mapped[str | None] = mapped_column(ForeignKey("productions.id", ondelete="CASCADE"), index=True)
    voucher_id: Mapped[str | None] = mapped_column(ForeignKey("vouchers.id", ondelete="CASCADE"), index=True)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("business_id", "type", "number", name="uq_payment_number"),
        Index("ix_payments_business_date", "business_id", "date"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    type: Mapped[PaymentType] = mapped_column(_enum(PaymentType))
    number: Mapped[str] = mapped_column(String(30))
    date: Mapped[dt.date] = mapped_column(Date)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)  # money that moved through the account
    tds_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))  # tax deducted at source
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), index=True)
    mode: Mapped[PaymentMode] = mapped_column(_enum(PaymentMode))
    reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    # cheques: money reaches the account only when cleared; a bounced cheque is void
    cheque_status: Mapped[str | None] = mapped_column(String(10))  # OPEN / CLEARED / BOUNCED
    cheque_date: Mapped[dt.date | None] = mapped_column(Date)
    cleared_on: Mapped[dt.date | None] = mapped_column(Date)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan"
    )
    party: Mapped[Party | None] = relationship()
    account: Mapped[Account] = relationship()

    @property
    def settled(self) -> Decimal:
        """Amount of the party's dues this payment clears (cash + TDS)."""
        return self.amount + (self.tds_amount or Decimal("0"))


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), index=True)
    voucher_id: Mapped[str] = mapped_column(ForeignKey("vouchers.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)

    payment: Mapped[Payment] = relationship(back_populates="allocations")
    voucher: Mapped[Voucher] = relationship(back_populates="allocations")

    @property
    def voucher_number(self) -> str:
        return self.voucher.number


class Counter(Base):
    """Per-business, per-series, per-financial-year running number."""

    __tablename__ = "counters"
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(20), primary_key=True)
    fy: Mapped[str] = mapped_column(String(7), primary_key=True)
    next: Mapped[int] = mapped_column(Integer, default=1)


class AccountTransfer(Base):
    """Cash deposit / withdrawal / bank-to-bank transfer."""

    __tablename__ = "account_transfers"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    from_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    to_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    amount: Mapped[Decimal] = mapped_column(Money)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CapitalEntry(Base):
    """Owner's capital introduced into, or drawings taken out of, the business."""

    __tablename__ = "capital_entries"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    type: Mapped[CapitalType] = mapped_column(_enum(CapitalType))
    amount: Mapped[Decimal] = mapped_column(Money)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Loan(Base):
    """A loan taken by the business (term loan, OD, vehicle loan, from a person)."""

    __tablename__ = "loans"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    lender: Mapped[str | None] = mapped_column(String(120))
    account_no: Mapped[str | None] = mapped_column(String(40))
    interest_rate: Mapped[Decimal | None] = mapped_column(Rate)
    opening_balance: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    opening_date: Mapped[dt.date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    txns: Mapped[list["LoanTxn"]] = relationship(back_populates="loan", cascade="all, delete-orphan")


class LoanTxn(Base):
    __tablename__ = "loan_txns"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    loan_id: Mapped[str] = mapped_column(ForeignKey("loans.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    type: Mapped[LoanTxnType] = mapped_column(_enum(LoanTxnType))
    principal: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    interest: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))  # interest, or the charge amount
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    loan: Mapped[Loan] = relationship(back_populates="txns")


class TaxPayment(Base):
    """GST / TDS / TCS deposited with the government (challan)."""

    __tablename__ = "tax_payments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    type: Mapped[TaxPaymentType] = mapped_column(_enum(TaxPaymentType))
    amount: Mapped[Decimal] = mapped_column(Money)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    reference: Mapped[str | None] = mapped_column(String(100))  # CIN / challan no.
    period: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class HsnCode(Base):
    """Business's HSN/SAC master with current GST rates (importable from the official list)."""

    __tablename__ = "hsn_codes"
    __table_args__ = (UniqueConstraint("business_id", "code", name="uq_hsn_code"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(8))
    description: Mapped[str | None] = mapped_column(Text)
    gst_rate: Mapped[Decimal] = mapped_column(Rate)
    cess_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"))
    effective_from: Mapped[dt.date | None] = mapped_column(Date)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Backup(Base):
    """A compressed JSON snapshot of one business's data."""

    __tablename__ = "backups"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # AUTO / MANUAL
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    emailed_to: Mapped[str | None] = mapped_column(String(200))
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LegalAcceptance(Base):
    """Each acceptance of the Terms / Privacy Policy: which version, when, from where, how (consent record)."""

    __tablename__ = "legal_acceptances"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(20))
    method: Mapped[str] = mapped_column(String(10))  # SIGNUP / GOOGLE / PROMPT / ADMIN
    ip: Mapped[str | None] = mapped_column(String(45))
    accepted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DataRequest(Base):
    """Data-protection rights request or grievance (Privacy centre → Admin → Privacy & security)."""

    __tablename__ = "data_requests"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    user_email: Mapped[str] = mapped_column(String(200))
    user_name: Mapped[str | None] = mapped_column(String(120))
    business_id: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(12))  # ACCESS / CORRECTION / ERASURE / WITHDRAW / GRIEVANCE
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="OPEN")  # OPEN / IN_PROGRESS / CLOSED / REJECTED
    response: Mapped[str | None] = mapped_column(Text)
    due_on: Mapped[dt.date | None] = mapped_column(Date)
    handled_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class SecurityIncident(Base):
    """Security-incident register kept by the platform (data processor) — affected businesses are notified."""

    __tablename__ = "security_incidents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    affected: Mapped[str | None] = mapped_column(Text)
    actions: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(8), default="MEDIUM")  # LOW / MEDIUM / HIGH
    status: Mapped[str] = mapped_column(String(12), default="OPEN")  # OPEN / CONTAINED / CLOSED
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    notified_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditChange(Base):
    """Edit log: values before and after every change to a book-of-account record (services/edit_log.py). Append-only."""

    __tablename__ = "audit_changes"
    __table_args__ = (Index("ix_audit_changes_business_at", "business_id", "at"), Index("ix_audit_changes_row", "row_id"))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    table_name: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(40))
    row_id: Mapped[str | None] = mapped_column(String(32))
    op: Mapped[str] = mapped_column(String(6))  # INSERT / UPDATE / DELETE
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    user_id: Mapped[str | None] = mapped_column(String(32))
    user_name: Mapped[str | None] = mapped_column(String(120))
    ip: Mapped[str | None] = mapped_column(String(45))
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    """Who changed what, when. Written automatically for every successful change."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_business_created", "business_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    user_name: Mapped[str | None] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(12))  # CREATE / UPDATE / DELETE / CANCEL / ACTION
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(String(300))
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Subscription(Base):
    """The subscriber account's plan. It covers every business the account owns."""

    __tablename__ = "subscriptions"
    account_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    plan: Mapped[str] = mapped_column(String(20))           # FREE / STARTER / PROFESSIONAL / ENTERPRISE
    status: Mapped[str] = mapped_column(String(10))         # TRIAL / ACTIVE / EXPIRED
    valid_until: Mapped[dt.date | None] = mapped_column(Date)
    extra_businesses: Mapped[int] = mapped_column(Integer, default=0)  # add-on packs
    feature_flags: Mapped[dict | None] = mapped_column(JSON)          # per-account overrides by super admin
    reseller_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"
    __table_args__ = (UniqueConstraint("receipt_no", name="uq_subscription_payments_receipt_no"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan: Mapped[str] = mapped_column(String(20))  # plan code, or ADDON_BUSINESSES
    cycle: Mapped[str] = mapped_column(String(10))  # MONTHLY / YEARLY
    amount: Mapped[Decimal] = mapped_column(Money)   # incl. GST
    order_id: Mapped[str] = mapped_column(String(60), unique=True)
    payment_id: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(10))  # CREATED / PAID / FAILED / CANCELLED (checkout closed)
    mode: Mapped[str | None] = mapped_column(String(4))  # LIVE / TEST (Razorpay test keys) / DEV (simulated)
    method: Mapped[str | None] = mapped_column(String(20))  # card / upi / netbanking / wallet ...
    business_id: Mapped[str | None] = mapped_column(String(32))  # business the owner was in when paying
    user_id: Mapped[str | None] = mapped_column(String(32))  # who started the payment
    gst_rate: Mapped[Decimal | None] = mapped_column(Rate)  # GST % included in amount
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_reason: Mapped[str | None] = mapped_column(String(300))
    receipt_no: Mapped[str | None] = mapped_column(String(20))  # given when paid
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class LicenseSale(Base):
    """A plan pack issued by a reseller to an account (drives commission & payouts)."""

    __tablename__ = "license_sales"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    reseller_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plan: Mapped[str] = mapped_column(String(20))
    months: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Money)       # list price incl. GST
    commission: Mapped[Decimal] = mapped_column(Money)
    payout_status: Mapped[str] = mapped_column(String(10), default="PENDING")  # PENDING / PAID
    paid_on: Mapped[dt.date | None] = mapped_column(Date)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PasswordReset(Base):
    __tablename__ = "password_resets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    temp_hash: Mapped[str | None] = mapped_column(String(100))  # bcrypt hash of an e-mailed temporary password
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    requested_ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SitePage(Base):
    """Website page text edited by the super admin (Admin → Website); missing = the built-in text."""

    __tablename__ = "site_pages"
    slug: Mapped[str] = mapped_column(String(30), primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SitePageVersion(Base):
    """Earlier text of a website page — kept on every save, restorable."""

    __tablename__ = "site_page_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    slug: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(300))
    saved_by: Mapped[str | None] = mapped_column(String(120))
    saved_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MailSender(Base):
    """An e-mail sender (API provider + from-address) managed by the super admin; one is the platform default and
    businesses can be given their own (services/mailer.py)."""

    __tablename__ = "mail_senders"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    label: Mapped[str] = mapped_column(String(80))
    provider: Mapped[str] = mapped_column(String(10))  # BREVO / ZEPTOMAIL / RESEND / SENDGRID / POSTMARK
    secret_enc: Mapped[str | None] = mapped_column(Text)  # API key, encrypted
    region: Mapped[str | None] = mapped_column(String(5))  # ZeptoMail data centre: IN / COM / EU
    from_email: Mapped[str] = mapped_column(String(200))
    from_name: Mapped[str | None] = mapped_column(String(120))
    reply_to: Mapped[str | None] = mapped_column(String(200))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_test_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PlatformBackup(Base):
    """Super-admin backups: FULL (whole platform) or ACCOUNT (every business of one owner)."""

    __tablename__ = "platform_backups"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    scope: Mapped[str] = mapped_column(String(10))  # FULL / ACCOUNT
    ref_id: Mapped[str | None] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10))  # AUTO / MANUAL / SAFETY
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_by_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Notification(Base):
    """An alert shown under the bell (and usually also e-mailed): payments, tickets ... (services/notify.py)."""

    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # PAYMENT_OK / PAYMENT_FAILED / PAYMENT_CANCELLED / TICKET ...
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class Ticket(Base):
    """Helpdesk: an issue, question, feedback or feature request raised from inside the app (routers/support.py)."""

    __tablename__ = "tickets"
    __table_args__ = (UniqueConstraint("number", name="uq_ticket_number"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    number: Mapped[int] = mapped_column(Integer)  # shown as T-1001
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[str | None] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(10))  # ISSUE / QUESTION / FEEDBACK / FEATURE / BILLING
    subject: Mapped[str] = mapped_column(String(200))
    priority: Mapped[str] = mapped_column(String(8), default="NORMAL")  # LOW / NORMAL / HIGH / URGENT
    status: Mapped[str] = mapped_column(String(12), default="OPEN", index=True)  # OPEN / IN_PROGRESS / WAITING / RESOLVED / CLOSED
    team: Mapped[str] = mapped_column(String(12), default="SUPPORT")  # SUPPORT / TECH / FINANCE / SALES
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    module: Mapped[str | None] = mapped_column(String(80))  # where in the app it was raised
    page: Mapped[str | None] = mapped_column(String(300))
    device: Mapped[str | None] = mapped_column(String(300))
    first_response_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    rating: Mapped[int | None] = mapped_column(Integer)  # 1–5, given by the user after resolution
    rating_note: Mapped[str | None] = mapped_column(String(300))
    last_activity_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    by_team: Mapped[bool] = mapped_column(Boolean, default=False)  # written by our support team
    internal: Mapped[bool] = mapped_column(Boolean, default=False)  # team-only note, never shown to the user
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str | None] = mapped_column(String(32))
    uploaded_by: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SiteVisit(Base):
    """A page view on the public website (first-party analytics: a random browser id, no IP address kept)."""

    __tablename__ = "site_visits"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    day: Mapped[dt.date] = mapped_column(Date, index=True)
    visitor: Mapped[str] = mapped_column(String(40), index=True)  # random id kept in the browser
    user_id: Mapped[str | None] = mapped_column(String(32))  # when signed in
    path: Mapped[str] = mapped_column(String(200))
    referrer: Mapped[str | None] = mapped_column(String(120))  # site only (e.g. google.com)
    utm_source: Mapped[str | None] = mapped_column(String(60))
    utm_campaign: Mapped[str | None] = mapped_column(String(60))
    device: Mapped[str | None] = mapped_column(String(10))  # mobile / tablet / desktop
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SiteEvent(Base):
    """Something a visitor or user did that sales cares about: looked at pricing, clicked a plan, changed the billing cycle."""

    __tablename__ = "site_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    day: Mapped[dt.date] = mapped_column(Date, index=True)
    visitor: Mapped[str | None] = mapped_column(String(40))
    user_id: Mapped[str | None] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # PRICING_VIEW / PLAN_CLICK / CYCLE / SIGNUP_START
    plan: Mapped[str | None] = mapped_column(String(30))
    cycle: Mapped[str | None] = mapped_column(String(12))
    page: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ModuleUsage(Base):
    """How often each person opened each module of the app, per day (Admin → Analytics)."""

    __tablename__ = "module_usage"
    __table_args__ = (UniqueConstraint("day", "user_id", "business_id", "module", name="uq_module_usage"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    day: Mapped[dt.date] = mapped_column(Date, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[str] = mapped_column(String(32), default="")
    module: Mapped[str] = mapped_column(String(80))
    views: Mapped[int] = mapped_column(Integer, default=0)
    last_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PlatformSetting(Base):
    __tablename__ = "platform_settings"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[dict | None] = mapped_column(JSON)


# ================================================================ platform compliance masters
class MasterHsn(Base):
    """Platform-wide HSN/SAC master maintained by super admins; businesses look codes up and copy from it."""

    __tablename__ = "master_hsn"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)  # 2-8 digits; SAC codes start with 99
    description: Mapped[str | None] = mapped_column(Text)
    gst_rate: Mapped[Decimal | None] = mapped_column(Rate, nullable=True)  # suggested rate; blank until set
    cess_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"), server_default="0")
    effective_from: Mapped[dt.date | None] = mapped_column(Date)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class RateNotice(Base):
    """A GST rate change (e.g. a CBIC notification) published to every business.

    changes: [{"hsn_prefix": "8471", "description": "...", "new_rate": 18, "new_cess": 0}]
    """

    __tablename__ = "rate_notices"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    title: Mapped[str] = mapped_column(String(200))
    reference: Mapped[str | None] = mapped_column(String(100))  # notification no.
    effective_from: Mapped[dt.date] = mapped_column(Date)
    changes: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RateNoticeAction(Base):
    """What a business did with a rate notice (applied to its items, or dismissed)."""

    __tablename__ = "rate_notice_actions"
    notice_id: Mapped[str] = mapped_column(ForeignKey("rate_notices.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    action: Mapped[str] = mapped_column(String(12))  # APPLIED | DISMISSED
    items_changed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    by_name: Mapped[str | None] = mapped_column(String(200))
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class HsnRequest(Base):
    """A business asks the platform to add an HSN/SAC code missing from the master."""

    __tablename__ = "hsn_requests"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(8))
    description: Mapped[str] = mapped_column(Text)
    gst_rate: Mapped[Decimal | None] = mapped_column(Rate, nullable=True)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="PENDING", server_default="PENDING")
    admin_note: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class GstinLookup(Base):
    """Every GSTIN verification: live API calls (billed by the provider) and answers from the cache."""

    __tablename__ = "gstin_lookups"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    gstin: Mapped[str] = mapped_column(String(15), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"), index=True)
    account_id: Mapped[str | None] = mapped_column(String(32), index=True)  # subscriber account (owner user id)
    source: Mapped[str] = mapped_column(String(8))  # LIVE | CACHE
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(300))
    data: Mapped[dict | None] = mapped_column(JSON)
    credits_remaining: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


# ================================================================ practitioner workspace (final accounts)
class PracticeClient(Base):
    """A client of a tax practitioner / accountant / CA, whose final accounts are prepared in the workspace."""

    __tablename__ = "practice_clients"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)  # the practitioner
    name: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(20), default="PROPRIETORSHIP")  # PROPRIETORSHIP | PARTNERSHIP
    pan: Mapped[str | None] = mapped_column(String(10))
    gstin: Mapped[str | None] = mapped_column(String(15))
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    nature_of_business: Mapped[str | None] = mapped_column(String(200))
    linked_business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"))
    mappings: Mapped[dict | None] = mapped_column(JSON)  # remembered ledger → head / partner
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class PracticeFile(Base):
    """One financial year's accounts of a practice client."""

    __tablename__ = "practice_files"
    __table_args__ = (UniqueConstraint("client_id", "fy", name="uq_practice_file_fy"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    client_id: Mapped[str] = mapped_column(ForeignKey("practice_clients.id", ondelete="CASCADE"), index=True)
    fy: Mapped[str] = mapped_column(String(7))  # 2025-26
    status: Mapped[str] = mapped_column(String(10), default="DRAFT", server_default="DRAFT")  # DRAFT | FINAL
    source: Mapped[str | None] = mapped_column(String(20))  # MANUAL | TRIAL_BALANCE | BOOKS
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    final_snapshot: Mapped[dict | None] = mapped_column(JSON)  # statements as finalised
    finalized_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Document(Base):
    """A paper the business keeps in its document vault: an uploaded file or a link (see services/documents.py)."""

    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60), default="Other")
    financial_year: Mapped[str | None] = mapped_column(String(7))  # 2025-26
    doc_date: Mapped[dt.date | None] = mapped_column(Date)
    expiry_date: Mapped[dt.date | None] = mapped_column(Date)  # licences: FSSAI, trade licence…
    kind: Mapped[str] = mapped_column(String(5), default="FILE")  # FILE / LINK
    url: Mapped[str | None] = mapped_column(String(1000))  # LINK
    storage: Mapped[str | None] = mapped_column(String(12))  # CLOUDINARY / DATABASE
    storage_id: Mapped[str | None] = mapped_column(String(300))
    file_name: Mapped[str | None] = mapped_column(String(200))
    file_ext: Mapped[str | None] = mapped_column(String(10))
    content_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Employee(Base):
    """A person on the business's payroll (need not have an app login; `user_id` links one for self check-in)."""

    __tablename__ = "employees"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    code: Mapped[str | None] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    designation: Mapped[str | None] = mapped_column(String(80))
    department: Mapped[str | None] = mapped_column(String(80))
    joined_on: Mapped[dt.date | None] = mapped_column(Date)
    left_on: Mapped[dt.date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    salary_type: Mapped[str] = mapped_column(String(8), default="MONTHLY")  # MONTHLY / DAILY
    salary: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))  # monthly gross, or rate per day
    basic_pct: Mapped[Decimal] = mapped_column(Rate, default=Decimal("50"))  # share of pay that is basic (EPF wage)
    ot_rate: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))  # overtime pay per hour
    pf: Mapped[bool] = mapped_column(Boolean, default=False)
    esi: Mapped[bool] = mapped_column(Boolean, default=False)
    pt_monthly: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))  # professional tax deducted each month
    tds_monthly: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    uan: Mapped[str | None] = mapped_column(String(20))
    esic_no: Mapped[str | None] = mapped_column(String(20))
    pan: Mapped[str | None] = mapped_column(String(10))
    bank_name: Mapped[str | None] = mapped_column(String(120))
    bank_account: Mapped[str | None] = mapped_column(String(40))
    bank_ifsc: Mapped[str | None] = mapped_column(String(11))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Attendance(Base):
    """One employee on one day: P present, A absent, HD half day, L paid leave, WO weekly off, H holiday."""

    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("employee_id", "date", name="uq_attendance_day"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(2))
    check_in: Mapped[str | None] = mapped_column(String(5))  # HH:MM
    check_out: Mapped[str | None] = mapped_column(String(5))
    ot_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    note: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(6), default="MANUAL")  # MANUAL / SELF
    marked_by: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class SalaryAdvance(Base):
    """Money given to an employee ahead of salary; recovered through payroll."""

    __tablename__ = "salary_advances"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money)
    note: Mapped[str | None] = mapped_column(String(200))
    voucher_id: Mapped[str | None] = mapped_column(ForeignKey("vouchers.id", ondelete="SET NULL"))  # the expense entry
    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PayrollRun(Base):
    """Salaries of one month: DRAFT (editable) -> FINAL (locked) -> PAID (salary expense posted)."""

    __tablename__ = "payroll_runs"
    __table_args__ = (UniqueConstraint("business_id", "month", name="uq_payroll_month"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    status: Mapped[str] = mapped_column(String(6), default="DRAFT")
    paid_on: Mapped[dt.date | None] = mapped_column(Date)
    voucher_id: Mapped[str | None] = mapped_column(ForeignKey("vouchers.id", ondelete="SET NULL"))
    statutory_paid: Mapped[dict | None] = mapped_column(JSON)  # {"PF": {...}, "ESI": {...}, ...}
    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    lines: Mapped[list["PayrollLine"]] = relationship(cascade="all, delete-orphan", order_by="PayrollLine.name")


class PayrollLine(Base):
    """One employee's salary in a payroll run (a snapshot: later changes to the employee do not alter it)."""

    __tablename__ = "payroll_lines"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("payroll_runs.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    data: Mapped[dict] = mapped_column(JSON)  # days, rates, earnings, deductions (see services/payroll.py)
    bonus: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    other_additions: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    advance_recovery: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    other_deductions: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    gross: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    deductions: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    net: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    note: Mapped[str | None] = mapped_column(String(200))


class BusinessCertificate(Base):
    """Digital signature certificate (.pfx / .p12) of a business, stored encrypted (services/dsc.py).
    Not part of business backups: it holds a private key."""

    __tablename__ = "business_certificates"
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    pfx_enc: Mapped[str] = mapped_column(Text)
    password_enc: Mapped[str] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(String(200))
    organisation: Mapped[str | None] = mapped_column(String(200))
    issuer: Mapped[str | None] = mapped_column(String(200))
    serial: Mapped[str | None] = mapped_column(String(64))
    not_before: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    not_after: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    mode: Mapped[str] = mapped_column(String(10), default="AUTO")  # AUTO = every PDF / ON_REQUEST
    uploaded_by: Mapped[str | None] = mapped_column(String(120))
    uploaded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EmailOtp(Base):
    """E-mail verification codes at sign-up (only a keyed hash of the code is kept)."""

    __tablename__ = "email_otps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(200), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    ip: Mapped[str | None] = mapped_column(String(45), index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class PhoneOtp(Base):
    """One-time sign-in / verification codes sent on WhatsApp (only a keyed hash of the code is kept)."""

    __tablename__ = "phone_otps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    phone: Mapped[str] = mapped_column(String(12), index=True)
    purpose: Mapped[str] = mapped_column(String(8))  # LOGIN / SIGNUP / VERIFY
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    ip: Mapped[str | None] = mapped_column(String(45), index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class WhatsAppMessage(Base):
    """Every WhatsApp message sent through the API, with its delivery status (from the provider's webhook)."""

    __tablename__ = "whatsapp_messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str | None] = mapped_column(String(32), index=True)
    account_id: Mapped[str | None] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(8))  # OTP / INVOICE / REMINDER
    to: Mapped[str] = mapped_column(String(15))
    template: Mapped[str | None] = mapped_column(String(80))
    wamid: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(10), default="SENT")  # SENT / DELIVERED / READ / FAILED
    error: Mapped[str | None] = mapped_column(String(300))
    preview: Mapped[str | None] = mapped_column(String(1000))  # sandbox: what would have been sent
    ref: Mapped[str | None] = mapped_column(String(64))
    by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class ApiCredit(Base):
    """API credit ledger of a subscriber account: packs bought (+), paid actions used (see services/api_credits.py)."""

    __tablename__ = "api_credits"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    account_id: Mapped[str] = mapped_column(String(32), index=True)  # owner user id (the subscription)
    business_id: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(6))  # PACK / ADMIN / USE
    action: Mapped[str | None] = mapped_column(String(15))  # EINVOICE / EWAYBILL / CANCEL / FILING_SYNC
    units: Mapped[int] = mapped_column(Integer, default=0)  # credits an action used
    delta: Mapped[int] = mapped_column(Integer, default=0)  # + added / - used
    from_pack: Mapped[int] = mapped_column(Integer, default=0)  # part of `units` taken from prepaid packs
    ref: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ImageFile(Base):
    """A logo, signature or item photo kept in our database (when image storage is 'database')."""

    __tablename__ = "image_files"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(12))  # logo / signature / item
    content_type: Mapped[str] = mapped_column(String(40))
    ext: Mapped[str] = mapped_column(String(5))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DocumentBlob(Base):
    """File content when the vault stores files in the database."""

    __tablename__ = "document_blobs"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)


class DocumentShare(Base):
    """A link to a vault file that opens without signing in until it expires."""

    __tablename__ = "document_shares"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(200))
    opened: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class StaffSession(Base):
    """A staff member's use of a business in one signed-in session (device): when, where, and its approval."""

    __tablename__ = "staff_sessions"
    __table_args__ = (UniqueConstraint("business_id", "user_id", "sid", name="uq_staff_session"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sid: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(10))  # AUTO (no approval needed) / PENDING / APPROVED / DENIED
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    first_seen: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    requested_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class GstReturnStatus(Base):
    """A GST return exactly as the GST portal listed it (filed or not), saved at the last sync of that year."""

    __tablename__ = "gst_return_status"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    fy: Mapped[str] = mapped_column(String(7))  # 2025-26
    return_type: Mapped[str] = mapped_column(String(20))  # GSTR1, GSTR3B, CMP08, GSTR4, GSTR9, IFF…
    return_period: Mapped[str] = mapped_column(String(7))  # YYYY-MM (last month of the quarter / year)
    status: Mapped[str | None] = mapped_column(String(30))
    filed: Mapped[bool] = mapped_column(Boolean, default=False)
    filed_on: Mapped[dt.date | None] = mapped_column(Date)
    arn: Mapped[str | None] = mapped_column(String(30))
    mode: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ComplianceFiling(Base):
    """A filing the business marked as done on the compliance calendar (rule code + period)."""

    __tablename__ = "compliance_filings"
    __table_args__ = (UniqueConstraint("business_id", "rule_code", "period_key", name="uq_compliance_filing"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    rule_code: Mapped[str] = mapped_column(String(30))
    period_key: Mapped[str] = mapped_column(String(20))
    done_on: Mapped[dt.date] = mapped_column(Date)
    reference: Mapped[str | None] = mapped_column(String(100))  # ARN / SRN / challan no.
    source: Mapped[str] = mapped_column(String(10), default="MANUAL", server_default="MANUAL")  # MANUAL / SYNC
    note: Mapped[str | None] = mapped_column(String(300))
    by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReminderLog(Base):
    """A payment reminder sent to a customer (automatic or by a user)."""

    __tablename__ = "reminder_logs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.id", ondelete="SET NULL"), index=True)
    voucher_id: Mapped[str | None] = mapped_column(ForeignKey("vouchers.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(20))  # BEFORE_3 / DUE / AFTER_7 / MANUAL
    channel: Mapped[str] = mapped_column(String(10), default="EMAIL")
    sent_to: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10), default="SENT")  # SENT / FAILED
    error: Mapped[str | None] = mapped_column(String(300))
    automatic: Mapped[bool] = mapped_column(Boolean, default=False)
    amount: Mapped[Decimal | None] = mapped_column(Money)
    by_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class RecurringInvoice(Base):
    """A sale invoice repeated on a schedule (rent, AMC, subscriptions). `template` holds the invoice body."""

    __tablename__ = "recurring_invoices"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    template: Mapped[dict] = mapped_column(JSON)
    frequency: Mapped[str] = mapped_column(String(12))  # WEEKLY | MONTHLY | QUARTERLY | HALF_YEARLY | YEARLY
    interval: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    next_date: Mapped[dt.date | None] = mapped_column(Date, index=True)
    due_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    auto_email: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE", server_default="ACTIVE")  # ACTIVE | PAUSED | ENDED
    generated_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_generated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PriceList(Base):
    """Special selling prices for a group of customers (wholesale, dealer, VIP …)."""

    __tablename__ = "price_lists"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    based_on: Mapped[str] = mapped_column(String(12), default="SALE_PRICE", server_default="SALE_PRICE")  # SALE_PRICE | MRP
    adjust_pct: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"), server_default="0")  # -5 = 5% below
    note: Mapped[str | None] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PriceListItem(Base):
    __tablename__ = "price_list_items"
    __table_args__ = (UniqueConstraint("price_list_id", "item_id", name="uq_price_list_item"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    price_list_id: Mapped[str] = mapped_column(ForeignKey("price_lists.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    rate: Mapped[Decimal] = mapped_column(Money)


# ================================================================ manufacturing
class Bom(Base):
    """Bill of materials: what goes into making `output_qty` of a finished item."""

    __tablename__ = "boms"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    output_qty: Mapped[Decimal] = mapped_column(Qty, default=Decimal("1"))
    other_cost: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), server_default="0")  # labour / overheads per batch
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    lines: Mapped[list["BomLine"]] = relationship(cascade="all, delete-orphan", order_by="BomLine.sort_order")


class BomLine(Base):
    __tablename__ = "bom_lines"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    bom_id: Mapped[str] = mapped_column(ForeignKey("boms.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    qty: Mapped[Decimal] = mapped_column(Qty)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Production(Base):
    """A production entry: raw materials consumed, finished goods added to stock."""

    __tablename__ = "productions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    number: Mapped[str] = mapped_column(String(30))
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    bom_id: Mapped[str | None] = mapped_column(ForeignKey("boms.id", ondelete="SET NULL"))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    qty: Mapped[Decimal] = mapped_column(Qty)
    godown_id: Mapped[str | None] = mapped_column(ForeignKey("godowns.id", ondelete="RESTRICT"))
    batch_no: Mapped[str | None] = mapped_column(String(50))
    material_cost: Mapped[Decimal] = mapped_column(Money)
    other_cost: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    unit_cost: Mapped[Decimal] = mapped_column(Money)
    consumed: Mapped[list] = mapped_column(JSON, default=list)  # [{item_id, name, qty, rate, amount}]
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
