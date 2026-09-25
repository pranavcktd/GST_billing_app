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
    password_hash: Mapped[str] = mapped_column(String(100))
    platform_role: Mapped[str | None] = mapped_column(String(12))  # SUPERADMIN / RESELLER
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
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan: Mapped[str] = mapped_column(String(20))  # plan code, or ADDON_BUSINESSES
    cycle: Mapped[str] = mapped_column(String(10))  # MONTHLY / YEARLY
    amount: Mapped[Decimal] = mapped_column(Money)   # incl. GST
    order_id: Mapped[str] = mapped_column(String(60), unique=True)
    payment_id: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(10))  # CREATED / PAID / FAILED
    mode: Mapped[str | None] = mapped_column(String(4))  # LIVE / TEST (Razorpay test keys) / DEV (simulated)
    method: Mapped[str | None] = mapped_column(String(20))  # card / upi / netbanking / wallet ...
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


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


class SmtpConfig(Base):
    """Outgoing e-mail server. PLATFORM (one), RESELLER (per reseller user), BUSINESS (per business)."""

    __tablename__ = "smtp_configs"
    __table_args__ = (UniqueConstraint("scope", "owner_id", name="uq_smtp_scope_owner"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    scope: Mapped[str] = mapped_column(String(10))
    owner_id: Mapped[str] = mapped_column(String(32), default="")  # "" for PLATFORM
    host: Mapped[str] = mapped_column(String(200))
    port: Mapped[int] = mapped_column(Integer, default=587)
    security: Mapped[str] = mapped_column(String(10), default="STARTTLS")  # STARTTLS / SSL / NONE
    username: Mapped[str | None] = mapped_column(String(200))
    password_enc: Mapped[str | None] = mapped_column(Text)
    from_email: Mapped[str] = mapped_column(String(200))
    from_name: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


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
