"""Create / update / cancel billing documents, keeping stock and payments consistent."""

import datetime as dt
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select

from ..deps import Ctx
from ..gst.calc import LineIn, calc_invoice, is_inter_state
from ..gst.constants import (
    CONVERSIONS,
    NON_LEDGER_TYPES,
    VOUCHER_META,
    BusinessGstType,
    ItemType,
    PartyGstType,
    PaymentMode,
    PaymentType,
    StockMoveType,
    VoucherType,
    document_title,
)
from ..gst.states import state_label
from ..gst.words import amount_in_words
from ..models import (
    ExpenseCategory,
    ExpenseItem,
    Item,
    Party,
    Payment,
    PaymentAllocation,
    StockMovement,
    Voucher,
    VoucherLine,
)
from ..schemas import TaxBucketOut, VoucherDetailOut, VoucherIn, VoucherLineOut, VoucherOut
from .accounts import resolve_account
from .godowns import resolve_godown
from .plans import check_invoice_limit
from .numbering import allocate_number

ZERO = Decimal("0")

# The document a return must point back to.
RETURN_OF = {VoucherType.SALE_RETURN: VoucherType.SALE, VoucherType.PURCHASE_RETURN: VoucherType.PURCHASE}
PARTY_REQUIRED = {
    VoucherType.PURCHASE, VoucherType.PURCHASE_RETURN, VoucherType.SALE_RETURN,
    VoucherType.SALE_ORDER, VoucherType.PURCHASE_ORDER,
}


def bad(msg: str, code: int = 400) -> HTTPException:
    return HTTPException(code, msg)


def payment_type_for(vtype: VoucherType) -> PaymentType:
    """Money that settles this document flows in if the document makes the party owe us."""
    return PaymentType.IN if VOUCHER_META[vtype]["ledger"] > 0 else PaymentType.OUT


def _get_owned(ctx: Ctx, model, obj_id: str | None, label: str):
    obj = ctx.db.get(model, obj_id) if obj_id else None
    if not obj or obj.business_id != ctx.bid:
        raise bad(f"{label} not found", 404)
    return obj


def number_exists(ctx: Ctx, vtype: VoucherType, number: str, exclude_id: str | None = None) -> bool:
    q = select(Voucher.id).where(Voucher.business_id == ctx.bid, Voucher.type == vtype, Voucher.number == number)
    if exclude_id:
        q = q.where(Voucher.id != exclude_id)
    return ctx.db.scalar(q) is not None


def save_voucher(ctx: Ctx, data: VoucherIn, voucher: Voucher | None = None) -> Voucher:
    db, biz = ctx.db, ctx.business
    vtype = data.type
    meta = VOUCHER_META[vtype]
    outward = meta["outward"]

    if voucher is not None:
        if voucher.type != vtype:
            raise bad("Document type cannot be changed")
        if voucher.cancelled:
            raise bad("A cancelled document cannot be edited")
        if voucher.einvoice_status == "GENERATED":
            raise bad("An e-invoice (IRN) exists for this document — cancel the IRN before editing")

    # ---- party ----
    party: Party | None = _get_owned(ctx, Party, data.party_id, "Party") if data.party_id else None
    if party is None and vtype in PARTY_REQUIRED:
        raise bad("Please select a party")

    # ---- tax applicability & place of supply ----
    export_type = None
    zero_rated = False
    if outward:
        tax_applicable = biz.gst_type == BusinessGstType.REGULAR
        supplier_state = biz.state_code
        pos = data.place_of_supply or (party.state_code if party else None) or biz.state_code
        kind = None
        if party is not None and party.gst_type == PartyGstType.OVERSEAS:
            kind, pos = "EXP", "96"  # export: place of supply is outside India
        elif party is not None and party.gst_type == PartyGstType.SEZ:
            kind = "SEZ"
        if kind and tax_applicable:
            lut_ok = bool(biz.lut_number) and (biz.lut_valid_till is None or biz.lut_valid_till >= data.date)
            with_payment = data.export_with_payment if data.export_with_payment is not None else not lut_ok
            if not with_payment and not lut_ok:
                raise bad("Add a valid LUT number in Settings to export / supply to SEZ without paying IGST")
            export_type = f"{kind}{'WP' if with_payment else 'WOP'}"
            zero_rated = not with_payment
        inter_state = kind is not None or is_inter_state(supplier_state, pos)  # exports & SEZ are inter-state
    else:
        default_tax = party is not None and party.gst_type in (PartyGstType.REGISTERED, PartyGstType.SEZ, PartyGstType.OVERSEAS)
        tax_applicable = data.tax_applicable if data.tax_applicable is not None else default_tax
        supplier_state = (party.state_code if party else None) or biz.state_code
        pos = data.place_of_supply or biz.state_code
        if party is not None and party.gst_type == PartyGstType.OVERSEAS:
            export_type = "IMPORT"  # IGST paid at customs (goods) or under reverse charge (services)
            inter_state = True
        else:
            inter_state = is_inter_state(supplier_state, pos)

    # ---- expense category ----
    category = None
    if vtype == VoucherType.EXPENSE:
        category = _get_owned(ctx, ExpenseCategory, data.expense_category_id, "Expense category")

    # ---- original document for credit / debit notes ----
    if vtype in RETURN_OF and data.original_voucher_id:
        orig = _get_owned(ctx, Voucher, data.original_voucher_id, "Original document")
        if orig.type != RETURN_OF[vtype] or orig.party_id != (party.id if party else None):
            raise bad("The original document must be a bill of the same party")

    # ---- items ----
    if vtype == VoucherType.EXPENSE and any(l.item_id for l in data.lines):
        raise bad("Expenses use expense items, not stock items")
    item_ids = {l.item_id for l in data.lines if l.item_id}
    items = {i.id: i for i in db.scalars(select(Item).where(Item.business_id == ctx.bid, Item.id.in_(item_ids)))}
    if len(items) != len(item_ids):
        raise bad("One or more items were not found")
    exp_ids = {l.expense_item_id for l in data.lines if l.expense_item_id}
    if exp_ids and vtype != VoucherType.EXPENSE:
        raise bad("Expense items can only be used on expenses")
    exp_items = {i.id: i for i in db.scalars(
        select(ExpenseItem).where(ExpenseItem.business_id == ctx.bid, ExpenseItem.id.in_(exp_ids)))}
    if len(exp_items) != len(exp_ids):
        raise bad("One or more expense items were not found")

    reverse_charge = data.reverse_charge and not outward and tax_applicable
    totals = calc_invoice(
        [LineIn(qty=l.qty, rate=l.rate, gst_rate=l.gst_rate, cess_rate=l.cess_rate,
                discount_pct=l.discount_pct, tax_inclusive=l.tax_inclusive) for l in data.lines],
        tax_applicable=tax_applicable,
        inter_state=inter_state,
        round_off=data.round_off,
        tcs_rate=data.tcs_rate,
        reverse_charge=reverse_charge,
        zero_rated=zero_rated,
    )

    if data.fully_paid and voucher is None and vtype not in NON_LEDGER_TYPES:
        data = data.model_copy(update={"amount_paid": totals.grand_total})
    if data.amount_paid and vtype in NON_LEDGER_TYPES:
        raise bad("Payments cannot be recorded against this document")
    if voucher is None and data.amount_paid > totals.grand_total:
        raise bad("Amount paid cannot be more than the bill total")
    if (party is None and voucher is None and data.amount_paid < totals.grand_total
            and vtype not in NON_LEDGER_TYPES):
        raise bad("Select a party for credit (unpaid) bills — bills without a party must be fully paid")

    source = None
    if voucher is None and data.source_voucher_id:
        source = _get_owned(ctx, Voucher, data.source_voucher_id, "Source document")
        if CONVERSIONS.get(source.type) != vtype:
            raise bad(f"A {source.type.value.replace('_', ' ').lower()} cannot be converted into this document")
        if source.cancelled or source.converted_to_id:
            raise bad("The source document is cancelled or already converted")

    godown = resolve_godown(db, ctx.bid, data.godown_id) if meta["stock"] else None
    if voucher is None and vtype == VoucherType.SALE:
        check_invoice_limit(db, ctx.bid)
    custom_keys = {f["key"] for f in ((biz.print_settings or {}).get("custom_fields") or [])}
    extra = {k: v for k, v in (data.extra_fields or {}).items() if k in custom_keys and v} or None

    # ---- header ----
    is_new = voucher is None
    if is_new:
        voucher = Voucher(business_id=ctx.bid, type=vtype, created_by_id=ctx.user.id)
        prefix = getattr(biz, meta["prefix"])
        voucher.number = data.number or allocate_number(
            db, ctx.bid, vtype.value, prefix, data.date, lambda n: number_exists(ctx, vtype, n)
        )
        db.add(voucher)
    else:
        if data.number:
            voucher.number = data.number
        voucher.lines.clear()
        db.execute(delete(StockMovement).where(StockMovement.voucher_id == voucher.id))

    if data.number and number_exists(ctx, vtype, data.number, exclude_id=voucher.id if not is_new else None):
        raise bad(f"Number {data.number} is already used", 409)

    voucher.date = data.date
    voucher.due_date = data.due_date
    voucher.party_id = party.id if party else None
    default_name = category.name if category else ("Cash Sale" if outward else "Cash Purchase")
    voucher.party_name = party.name if party else (data.party_name or default_name)
    voucher.party_gstin = party.gstin if party else None
    voucher.party_state_code = party.state_code if party else pos
    voucher.party_address = None
    if party:
        voucher.party_address = ", ".join(x for x in (party.billing_address, party.city, party.pincode) if x) or None
    voucher.party_phone = party.phone if party else data.party_phone
    voucher.place_of_supply = pos
    voucher.inter_state = inter_state
    voucher.tax_applicable = tax_applicable
    voucher.reverse_charge = reverse_charge
    voucher.expense_category_id = category.id if category else None
    voucher.tcs_rate = data.tcs_rate
    voucher.godown_id = godown.id if godown else None
    voucher.export_type = export_type
    voucher.shipping_bill_no = data.shipping_bill_no
    voucher.shipping_bill_date = data.shipping_bill_date
    voucher.port_code = data.port_code
    voucher.currency_code = data.currency_code.upper() if data.currency_code else None
    voucher.exchange_rate = data.exchange_rate
    voucher.transport = data.transport.model_dump(mode="json", exclude_none=True) if data.transport else None
    voucher.extra_fields = extra
    voucher.tcs_amount = totals.tcs
    voucher.supplier_invoice_no = data.supplier_invoice_no
    voucher.supplier_invoice_date = data.supplier_invoice_date
    voucher.original_voucher_id = data.original_voucher_id if vtype in RETURN_OF else None
    voucher.reason = data.reason
    voucher.notes = data.notes
    voucher.terms = data.terms if data.terms is not None else (biz.invoice_terms if outward and is_new else None)
    for f in ("sub_total", "discount", "taxable", "cgst", "sgst", "igst", "cess", "round_off", "grand_total"):
        setattr(voucher, f, getattr(totals, f))

    for i, (li, lo) in enumerate(zip(data.lines, totals.lines)):
        item = items.get(li.item_id) if li.item_id else None
        voucher.lines.append(VoucherLine(
            item_id=li.item_id, expense_item_id=li.expense_item_id, sort_order=i, name=li.name,
            description=li.description, batch_no=li.batch_no, mfg_date=li.mfg_date, expiry_date=li.expiry_date,
            serial_nos=li.serial_nos,
            hsn_sac=li.hsn_sac or (item.hsn_sac if item else None),
            unit=li.unit or (item.unit if item else None),
            qty=li.qty, rate=li.rate, tax_inclusive=li.tax_inclusive, discount_pct=li.discount_pct,
            gst_rate=li.gst_rate, cess_rate=li.cess_rate,
            amount=lo.amount, discount=lo.discount, taxable=lo.taxable,
            cgst=lo.cgst, sgst=lo.sgst, igst=lo.igst, cess=lo.cess, total=lo.total,
        ))
    db.flush()

    # ---- stock ----
    if meta["stock"]:
        for li, lo in zip(data.lines, totals.lines):
            item = items.get(li.item_id) if li.item_id else None
            if item and item.type == ItemType.GOODS:
                db.add(StockMovement(
                    business_id=ctx.bid, item_id=item.id, date=data.date, type=StockMoveType(vtype.value),
                    qty=meta["stock"] * li.qty, rate=(lo.taxable / li.qty).quantize(Decimal("0.01")),
                    voucher_id=voucher.id, batch_no=li.batch_no, godown_id=godown.id,
                ))

    # ---- payment received / paid on the spot ----
    if is_new and data.amount_paid > 0:
        biz_prefix = biz.receipt_prefix if payment_type_for(vtype) == PaymentType.IN else biz.payment_prefix
        ptype = payment_type_for(vtype)
        account = resolve_account(db, ctx.bid, data.payment_account_id)
        payment = Payment(
            business_id=ctx.bid, type=ptype, date=data.date, party_id=voucher.party_id,
            amount=data.amount_paid, mode=data.payment_mode, account_id=account.id,
            cheque_status="OPEN" if data.payment_mode == PaymentMode.CHEQUE else None,
            cheque_date=data.date if data.payment_mode == PaymentMode.CHEQUE else None,
            number=allocate_number(db, ctx.bid, f"PAYMENT_{ptype.value}", biz_prefix, data.date,
                                   lambda n: payment_number_exists(ctx, ptype, n)),
            notes=f"Against {voucher.number}",
        )
        payment.allocations.append(PaymentAllocation(voucher_id=voucher.id, amount=data.amount_paid))
        db.add(payment)

    # ---- conversion from estimate / order / challan ----
    if source is not None:
        source.converted_to_id = voucher.id
        voucher.source_voucher_id = source.id

    db.flush()
    return voucher


def payment_number_exists(ctx: Ctx, ptype: PaymentType, number: str) -> bool:
    return ctx.db.scalar(
        select(Payment.id).where(Payment.business_id == ctx.bid, Payment.type == ptype, Payment.number == number)
    ) is not None


def cancel_voucher(ctx: Ctx, voucher: Voucher) -> None:
    """GST-compliant cancellation: the number stays used, the document stops counting."""
    voucher.cancelled = True
    ctx.db.execute(delete(StockMovement).where(StockMovement.voucher_id == voucher.id))
    # the order / challan it was created from becomes open again
    if voucher.source_voucher_id:
        src = ctx.db.get(Voucher, voucher.source_voucher_id)
        if src is not None and src.converted_to_id == voucher.id:
            src.converted_to_id = None
    # Money already received stays with the party as an advance (unallocated payment).
    ctx.db.execute(delete(PaymentAllocation).where(PaymentAllocation.voucher_id == voucher.id))
    ctx.db.flush()


def voucher_status(v: Voucher, paid: Decimal, today: dt.date | None = None) -> str:
    if v.cancelled:
        return "CANCELLED"
    if v.type in NON_LEDGER_TYPES:
        return "CONVERTED" if v.converted_to_id else "OPEN"
    if paid >= v.grand_total:
        return "PAID"
    if v.due_date and v.due_date < (today or dt.date.today()):
        return "OVERDUE"
    return "PARTIAL" if paid > 0 else "UNPAID"


def to_out(v: Voucher, paid: Decimal | None = None) -> VoucherOut:
    if paid is None:
        paid = sum((a.amount for a in v.allocations), ZERO)
    out = VoucherOut.model_validate(v)
    out.paid = paid
    out.balance = ZERO if v.type in NON_LEDGER_TYPES or v.cancelled else max(v.grand_total - paid, ZERO)
    out.status = voucher_status(v, paid)
    out.title = document_title(v.type, v.tax_applicable)
    return out


def to_detail(ctx: Ctx, v: Voucher) -> VoucherDetailOut:
    base = to_out(v)
    buckets: dict[Decimal, dict] = {}
    for l in v.lines:
        rate = l.gst_rate if v.tax_applicable else ZERO
        b = buckets.setdefault(rate, dict(rate=rate, taxable=ZERO, cgst=ZERO, sgst=ZERO, igst=ZERO, cess=ZERO))
        for f in ("taxable", "cgst", "sgst", "igst", "cess"):
            b[f] += getattr(l, f)
    original = ctx.db.get(Voucher, v.original_voucher_id) if v.original_voucher_id else None
    return VoucherDetailOut(
        **base.model_dump(),
        lines=[VoucherLineOut.model_validate(l) for l in v.lines],
        tax_breakup=[TaxBucketOut(**b) for _, b in sorted(buckets.items())],
        amount_in_words=amount_in_words(v.grand_total),
        original_number=original.number if original else None,
    )


def pos_label(v: Voucher) -> str:
    return state_label(v.place_of_supply)
