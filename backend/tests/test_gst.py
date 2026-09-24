from datetime import date
from decimal import Decimal as D

from app.gst.calc import LineIn, calc_invoice, is_inter_state
from app.gst.fy import fy_label, fy_short
from app.gst.gstin import gstin_check_char, validate_gstin
from app.gst.words import amount_in_words


def test_intra_state_splits_cgst_sgst():
    t = calc_invoice([LineIn(qty=D("2"), rate=D("500"), gst_rate=D("18"))], tax_applicable=True, inter_state=False)
    assert t.taxable == D("1000.00")
    assert t.cgst == D("90.00") and t.sgst == D("90.00") and t.igst == 0
    assert t.grand_total == D("1180")


def test_inter_state_uses_igst():
    t = calc_invoice([LineIn(qty=D("1"), rate=D("1000"), gst_rate=D("5"))], tax_applicable=True, inter_state=True)
    assert t.igst == D("50.00") and t.cgst == 0
    assert t.grand_total == D("1050")


def test_tax_inclusive_price_backs_out_tax():
    t = calc_invoice(
        [LineIn(qty=D("1"), rate=D("118"), gst_rate=D("18"), tax_inclusive=True)], tax_applicable=True, inter_state=False
    )
    assert t.taxable == D("100.00")
    assert t.cgst + t.sgst == D("18.00")
    assert t.grand_total == D("118")


def test_discount_and_round_off():
    t = calc_invoice(
        [LineIn(qty=D("3"), rate=D("99.99"), gst_rate=D("12"), discount_pct=D("10"))],
        tax_applicable=True,
        inter_state=False,
    )
    # 299.97 - 30.00 = 269.97 taxable; 6% each = 16.20 → 302.37 → 302
    assert t.discount == D("30.00")
    assert t.taxable == D("269.97")
    assert t.cgst == D("16.20")
    assert t.grand_total == D("302")
    assert t.round_off == D("-0.37")


def test_no_tax_for_bill_of_supply():
    t = calc_invoice([LineIn(qty=D("1"), rate=D("100"), gst_rate=D("18"))], tax_applicable=False, inter_state=False)
    assert t.total_tax == 0 and t.grand_total == D("100")
    assert t.tax_breakup[0].rate == 0


def test_tax_breakup_groups_by_rate():
    t = calc_invoice(
        [
            LineIn(qty=D("1"), rate=D("100"), gst_rate=D("5")),
            LineIn(qty=D("1"), rate=D("200"), gst_rate=D("18")),
            LineIn(qty=D("1"), rate=D("50"), gst_rate=D("5")),
        ],
        tax_applicable=True,
        inter_state=True,
    )
    assert [(b.rate, b.taxable) for b in t.tax_breakup] == [(D("5"), D("150.00")), (D("18"), D("200.00"))]


def test_inter_state_detection():
    assert is_inter_state("27", "29")
    assert not is_inter_state("27", "27")


def test_gstin_checksum():
    # Build a valid GSTIN from a known prefix, then verify validation accepts/rejects.
    prefix = "27AAPFU0939F1Z"
    good = prefix + gstin_check_char(prefix)
    assert validate_gstin(good) is None
    bad_char = "0" if good[-1] != "0" else "1"
    assert validate_gstin(prefix + bad_char) is not None
    assert validate_gstin("27AAPFU0939F1ZV") is None  # widely published sample GSTIN
    assert validate_gstin("99AAPFU0939F1ZV") is not None  # bad state code
    assert validate_gstin("ABC") is not None


def test_amount_in_words_indian_system():
    assert amount_in_words(D("125000.50")) == "Rupees One Lakh Twenty Five Thousand and Fifty Paise Only"
    assert amount_in_words(D("10000000")) == "Rupees One Crore Only"
    assert amount_in_words(D("0")) == "Rupees Zero Only"


def test_financial_year():
    assert fy_label(date(2026, 3, 31)) == "2025-26"
    assert fy_label(date(2026, 4, 1)) == "2026-27"
    assert fy_short(date(2026, 9, 24)) == "26-27"


def test_tcs_added_on_value_including_gst():
    t = calc_invoice([LineIn(qty=D("1"), rate=D("1000"), gst_rate=D("18"))], tax_applicable=True,
                     inter_state=False, tcs_rate=D("1"))
    assert t.tcs == D("11.80") and t.grand_total == D("1192")
    assert t.taxable + t.total_tax + t.tcs + t.round_off == t.grand_total


def test_reverse_charge_excludes_tax_from_amount_due():
    t = calc_invoice([LineIn(qty=D("1"), rate=D("1000"), gst_rate=D("5"))], tax_applicable=True,
                     inter_state=False, reverse_charge=True)
    assert t.cgst == D("25.00") and t.grand_total == D("1000")
