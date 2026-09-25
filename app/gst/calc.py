"""Invoice tax calculation — the single source of truth for every amount stored.

Rules implemented:
* Intra-state supply (supplier state == place of supply): CGST + SGST, each half the rate.
* Inter-state supply: IGST at the full rate.
* Tax-inclusive prices are backed out to a taxable value: taxable = net / (1 + (gst+cess)/100).
* Line amounts are rounded to paise; the grand total is rounded to the nearest rupee
  with the difference shown as "Round off" (optional).
* TCS (Sec. 206C) is computed on the invoice value including GST and added before rounding.
* When tax is not applicable (composition / unregistered business, or a supplier who
  did not charge GST) the rate is kept on the line for reporting but no tax is computed.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
HUNDRED = Decimal("100")
PAISE = Decimal("0.01")


def r2(x: Decimal) -> Decimal:
    return x.quantize(PAISE, rounding=ROUND_HALF_UP)


def is_inter_state(supplier_state: str | None, place_of_supply: str | None) -> bool:
    if not supplier_state or not place_of_supply:
        return False
    return supplier_state != place_of_supply


@dataclass
class LineIn:
    qty: Decimal
    rate: Decimal
    gst_rate: Decimal = ZERO
    cess_rate: Decimal = ZERO
    discount_pct: Decimal = ZERO
    tax_inclusive: bool = False


@dataclass
class LineOut:
    amount: Decimal      # qty * rate (as entered)
    discount: Decimal
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    cess: Decimal
    total: Decimal


@dataclass
class TaxBucket:
    rate: Decimal
    taxable: Decimal = ZERO
    cgst: Decimal = ZERO
    sgst: Decimal = ZERO
    igst: Decimal = ZERO
    cess: Decimal = ZERO


@dataclass
class InvoiceTotals:
    lines: list[LineOut]
    sub_total: Decimal
    discount: Decimal
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    cess: Decimal
    round_off: Decimal
    grand_total: Decimal
    tcs: Decimal = ZERO
    tax_breakup: list[TaxBucket] = field(default_factory=list)

    @property
    def total_tax(self) -> Decimal:
        return self.cgst + self.sgst + self.igst + self.cess


def calc_line(line: LineIn, *, tax_applicable: bool, inter_state: bool) -> LineOut:
    amount = r2(line.qty * line.rate)
    discount = r2(amount * line.discount_pct / HUNDRED)
    net = amount - discount
    gst_rate = line.gst_rate if tax_applicable else ZERO
    cess_rate = line.cess_rate if tax_applicable else ZERO

    if line.tax_inclusive and (gst_rate or cess_rate):
        taxable = r2(net * HUNDRED / (HUNDRED + gst_rate + cess_rate))
    else:
        taxable = net

    cgst = sgst = igst = ZERO
    if gst_rate:
        if inter_state:
            igst = r2(taxable * gst_rate / HUNDRED)
        else:
            cgst = sgst = r2(taxable * gst_rate / 2 / HUNDRED)
    cess = r2(taxable * cess_rate / HUNDRED)
    total = taxable + cgst + sgst + igst + cess
    return LineOut(amount, discount, taxable, cgst, sgst, igst, cess, total)


def calc_invoice(
    lines: list[LineIn],
    *,
    tax_applicable: bool,
    inter_state: bool,
    round_off: bool = True,
    tcs_rate: Decimal = ZERO,
    reverse_charge: bool = False,
    zero_rated: bool = False,
) -> InvoiceTotals:
    """`reverse_charge`: tax is computed (recipient pays it) but not added to the amount due to the supplier."""
    # zero-rated (export / SEZ under LUT): rates stay on the lines for reporting, no tax is charged
    outs = [calc_line(l, tax_applicable=tax_applicable and not zero_rated, inter_state=inter_state) for l in lines]
    buckets: dict[Decimal, TaxBucket] = {}
    for li, lo in zip(lines, outs):
        rate = li.gst_rate if tax_applicable else ZERO
        b = buckets.setdefault(rate, TaxBucket(rate=rate))
        b.taxable += lo.taxable
        b.cgst += lo.cgst
        b.sgst += lo.sgst
        b.igst += lo.igst
        b.cess += lo.cess

    s = lambda attr: sum((getattr(o, attr) for o in outs), ZERO)  # noqa: E731
    raw_total = s("taxable") if reverse_charge else s("total")
    tcs = r2(raw_total * tcs_rate / HUNDRED) if tcs_rate else ZERO
    raw_total += tcs
    grand = raw_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP) if round_off else raw_total
    return InvoiceTotals(
        lines=outs,
        sub_total=s("amount"),
        discount=s("discount"),
        taxable=s("taxable"),
        cgst=s("cgst"),
        sgst=s("sgst"),
        igst=s("igst"),
        cess=s("cess"),
        round_off=grand - raw_total,
        grand_total=grand,
        tcs=tcs,
        tax_breakup=sorted(buckets.values(), key=lambda b: b.rate),
    )
