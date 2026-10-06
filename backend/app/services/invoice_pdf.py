"""Invoice / document PDF generated on the server (download, e-mail attachment, public link).

Covers the Rule 46 (tax invoice) / Rule 49 (bill of supply) particulars and follows the business's
print settings (accent colour, which blocks to show, title, footer, copy labels). Uses the bundled
Noto Sans font so the ₹ sign prints everywhere, including Linux servers.
"""

import datetime as dt
import io
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import httpx
from sqlalchemy.orm import object_session
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..gst.constants import VoucherType, document_title
from ..gst.states import STATES
from ..gst.words import amount_in_words
from ..models import Business, Voucher
from . import config_store

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_fonts_ready = False
DEFAULT_PRINT = dict(theme="classic", accent="#1f65bb", paper="A4", copy_labels=["ORIGINAL"], show_hsn=True, show_discount=True,
                     show_tax_summary=True, show_bank=True, show_upi_qr=True, show_terms=True, show_signature=True,
                     show_item_description=True, show_transport=True, title_override=None, footer_note=None, custom_fields=[])
COPY_TEXT = {"ORIGINAL": "Original for recipient", "DUPLICATE": "Duplicate for transporter", "TRIPLICATE": "Triplicate for supplier"}
MODE = {"1": "Road", "2": "Rail", "3": "Air", "4": "Ship"}


def _fonts() -> tuple[str, str]:
    global _fonts_ready
    if not _fonts_ready:
        try:
            pdfmetrics.registerFont(TTFont("Noto", str(FONT_DIR / "NotoSans-Regular.ttf")))
            pdfmetrics.registerFont(TTFont("Noto-Bold", str(FONT_DIR / "NotoSans-Bold.ttf")))
            pdfmetrics.registerFontFamily("Noto", normal="Noto", bold="Noto-Bold", italic="Noto", boldItalic="Noto-Bold")
            _fonts_ready = True
        except Exception:  # noqa: BLE001 — fall back to the built-in font (₹ prints as "Rs.")
            return "Helvetica", "Helvetica-Bold"
    return "Noto", "Noto-Bold"


def inr(v, sym: bool = True) -> str:
    """₹1,23,456.78 — Indian digit grouping."""
    n = Decimal(str(v or 0)).quantize(Decimal("0.01"))
    neg, s = n < 0, f"{abs(n):.2f}"
    whole, frac = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        whole = ",".join([head, *parts, tail] if head else [*parts, tail])
    out = f"{whole}.{frac}"
    return ("-" if neg else "") + ("₹" if sym and _fonts_ready else "Rs. " if sym else "") + out


def _dmy(s) -> str:
    try:
        return dt.date.fromisoformat(str(s)[:10]).strftime("%d-%m-%Y")
    except ValueError:
        return str(s)


def qty_str(q) -> str:
    d = Decimal(str(q or 0))
    return f"{d.normalize():f}" if d == d.to_integral() else f"{d:.3f}".rstrip("0").rstrip(".")


def _qr(data: str, size: float) -> Drawing:
    w = QrCodeWidget(data)
    b = w.getBounds()
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
    d.add(w)
    return d


def _image(url: str | None, max_w: float, max_h: float):
    if not url:
        return None
    try:
        if url.startswith("http"):
            r = httpx.get(url, timeout=6, follow_redirects=True)
            if r.status_code != 200 or len(r.content) > 3_000_000:
                return None
            data = r.content
        else:
            return None
        img = Image(io.BytesIO(data))
        ratio = min(max_w / img.imageWidth, max_h / img.imageHeight, 1)
        img.drawWidth, img.drawHeight = img.imageWidth * ratio, img.imageHeight * ratio
        return img
    except Exception:  # noqa: BLE001 — a missing logo never blocks the PDF
        return None


def render(v: Voucher, biz: Business, *, watermark: bool = False, copies: list[str] | None = None,
           images: bool = True) -> bytes:
    font, bold = _fonts()
    ps = {**DEFAULT_PRINT, **(biz.print_settings or {})}
    accent = colors.HexColor(ps.get("accent") or "#1f65bb") if str(ps.get("accent") or "").startswith("#") else colors.HexColor("#1f65bb")
    page = A5 if ps.get("paper") == "A5" else A4
    W = page[0] - 20 * mm
    small = page == A5
    fs = 7.2 if small else 8.2

    S = lambda name, **kw: ParagraphStyle(name, fontName=kw.pop("fn", font), fontSize=kw.pop("size", fs), leading=kw.pop("lead", fs + 2.6), **kw)  # noqa: E731
    p = S("p")
    pb = S("pb", fn=bold)
    pr = S("pr", alignment=2)
    prb = S("prb", fn=bold, alignment=2)
    tiny = S("tiny", size=fs - 1.2, lead=fs + 1, textColor=colors.HexColor("#6b7280"))
    head_w = S("hw", fn=bold, textColor=colors.white)
    head_wr = S("hwr", fn=bold, textColor=colors.white, alignment=2)
    title_style = S("title", fn=bold, size=fs + 6, lead=fs + 9, textColor=accent, alignment=2)
    biz_style = S("biz", fn=bold, size=fs + 5, lead=fs + 8)
    P = lambda t, st=p: Paragraph(escape(str(t)) if t is not None else "", st)  # noqa: E731
    PH = lambda html_, st=p: Paragraph(html_, st)  # noqa: E731

    outward = v.type in (VoucherType.SALE, VoucherType.SALE_RETURN, VoucherType.ESTIMATE, VoucherType.SALE_ORDER,
                         VoucherType.DELIVERY_CHALLAN)
    tax = v.tax_applicable
    inter = v.inter_state
    title = (ps.get("title_override") if v.type == VoucherType.SALE else None) or document_title(v.type, tax)
    paid = sum((a.amount for a in v.allocations), Decimal("0"))
    balance = max(v.grand_total - paid, Decimal("0")) if v.type in (VoucherType.SALE, VoucherType.PURCHASE) else None

    def build(copy_label: str | None) -> list:
        story = []
        # ---- header: seller + title
        seller = [PH(escape(biz.legal_name or biz.name), biz_style)]
        if biz.legal_name and biz.legal_name != biz.name:
            seller.append(P(f"Trading as {biz.name}"))
        addr = ", ".join(x for x in (biz.address, biz.city, biz.pincode) if x)
        if addr:
            seller.append(P(addr))
        seller.append(P(" · ".join(x for x in (f"State: {biz.state_code}-{STATES.get(biz.state_code, '')}",
                                                 biz.phone and f"Ph: {biz.phone}", biz.email) if x)))
        if biz.gstin:
            seller.append(PH(f"<b>GSTIN: {escape(biz.gstin)}</b>"))
        logo = _image(biz.logo_url, 28 * mm, 18 * mm) if images else None
        left = Table([[logo, seller]] if logo else [[seller]], colWidths=[30 * mm, W * 0.62 - 30 * mm] if logo else [W * 0.62])
        left.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        right = [P(title.upper(), title_style)]
        if copy_label:
            right.append(P(COPY_TEXT.get(copy_label, copy_label), S("cp", alignment=2, textColor=colors.HexColor("#6b7280"))))
        if v.cancelled:
            right.append(P("CANCELLED", S("cx", fn=bold, size=fs + 4, alignment=2, textColor=colors.HexColor("#b91c1c"))))
        hdr = Table([[left, right]], colWidths=[W * 0.62, W * 0.38])
        hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("LINEBELOW", (0, 0), (-1, 0), 1.2, accent),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story += [hdr, Spacer(1, 5)]

        # ---- e-invoice
        if v.irn and v.einvoice_status == "GENERATED":
            ack = v.ack_date.strftime("%d-%m-%Y %H:%M") if isinstance(v.ack_date, dt.datetime) else (v.ack_date or "")
            irn_txt = [PH(f"<b>IRN:</b> {escape(v.irn)}", tiny), PH(f"<b>Ack No:</b> {escape(str(v.ack_no or ''))} · <b>Ack Date:</b> {escape(str(ack))}", tiny)]
            if v.einvoice_sandbox:
                irn_txt.append(P("Sandbox IRN — not valid for GST", S("sb", textColor=colors.HexColor("#b45309"))))
            cells = [[irn_txt, _qr(v.signed_qr, 26 * mm) if v.signed_qr else ""]]
            t = Table(cells, colWidths=[W - 30 * mm, 30 * mm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db"))]))
            story += [t, Spacer(1, 5)]

        # ---- party & document particulars
        party = [PH(f"<b>{'Bill to' if outward else 'Supplier'}</b>", tiny), PH(f"<b>{escape(v.party_name)}</b>")]
        if v.party_address:
            party.append(P(v.party_address))
        if v.party_gstin:
            party.append(PH(f"GSTIN: <b>{escape(v.party_gstin)}</b>"))
        if v.party_state_code:
            party.append(P(f"State: {v.party_state_code}-{STATES.get(v.party_state_code, '')}"))
        if v.party_phone:
            party.append(P(f"Ph: {v.party_phone}"))
        meta = [("No.", v.number), ("Date", v.date.strftime("%d-%m-%Y"))]
        if v.due_date:
            meta.append(("Due date", v.due_date.strftime("%d-%m-%Y")))
        if tax:
            meta.append(("Place of supply", f"{v.place_of_supply}-{STATES.get(v.place_of_supply, 'Outside India')}"))
            meta.append(("Reverse charge", "Yes" if v.reverse_charge else "No"))
        if v.supplier_invoice_no:
            meta.append(("Supplier bill", f"{v.supplier_invoice_no}{' · ' + v.supplier_invoice_date.strftime('%d-%m-%Y') if v.supplier_invoice_date else ''}"))
        if v.original_voucher_id:
            sess = object_session(v)
            orig = sess.get(Voucher, v.original_voucher_id) if sess is not None else None
            if orig is not None:
                meta.append(("Against", f"{orig.number} · {orig.date:%d-%m-%Y}"))
        if v.reason:
            meta.append(("Reason", v.reason))
        if v.shipping_bill_no:
            meta.append(("Bill of entry" if v.export_type == "IMPORT" else "Shipping bill",
                         f"{v.shipping_bill_no}{' · ' + v.shipping_bill_date.strftime('%d-%m-%Y') if v.shipping_bill_date else ''}{' · ' + v.port_code if v.port_code else ''}"))
        for f in ps.get("custom_fields") or []:
            val = (v.extra_fields or {}).get(f.get("key"))
            if val:
                meta.append((f.get("label") or f.get("key"), val))
        t = v.transport or {}
        if ps.get("show_transport") and t:
            if t.get("vehicle_no"):
                meta.append(("Vehicle", t["vehicle_no"]))
            if t.get("transporter_name"):
                meta.append(("Transporter", t["transporter_name"]))
            if t.get("doc_no"):
                meta.append(("LR / doc no.", f"{t['doc_no']}{' · ' + _dmy(t['doc_date']) if t.get('doc_date') else ''}"))
            if t.get("mode") and t.get("mode") != "1":
                meta.append(("Mode", MODE.get(t["mode"], t["mode"])))
        if v.ewb_no:
            meta.append(("E-way bill", f"{v.ewb_no}{' · valid till ' + v.ewb_valid_till.strftime('%d-%m-%Y') if v.ewb_valid_till else ''}"))
        mt = Table([[P(k, tiny), P(val)] for k, val in meta], colWidths=[26 * mm, W * 0.45 - 26 * mm])
        mt.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        pt = Table([[party, mt]], colWidths=[W * 0.55, W * 0.45])
        pt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                                ("LINEAFTER", (0, 0), (0, 0), 0.4, colors.HexColor("#d1d5db"))]))
        story += [pt, Spacer(1, 6)]

        # ---- items
        show_hsn, show_disc = ps.get("show_hsn", True), ps.get("show_discount", True) and any(l.discount for l in v.lines)
        cols: list[tuple[str, float, bool]] = [("#", 6, True), ("Item", 0, False)]
        if show_hsn:
            cols.append(("HSN/SAC", 18, False))
        cols += [("Qty", 16, True), ("Rate", 19, True)]
        if show_disc:
            cols.append(("Disc.", 15, True))
        if tax:
            cols += [("Taxable", 21, True), ("GST %", 13, True)]
            cols += [("IGST", 17, True)] if inter else [("CGST", 16, True), ("SGST", 16, True)]
        cols.append(("Amount", 22, True))
        fixed = sum(c[1] for c in cols) * mm
        widths = [c[1] * mm if c[1] else W - fixed for c in cols]
        rows = [[P(c[0], head_wr if c[2] else head_w) for c in cols]]
        for i, l in enumerate(v.lines, 1):
            desc = f"<b>{escape(l.name)}</b>"
            if ps.get("show_item_description") and l.description:
                desc += f"<br/><font size='{fs - 1}' color='#6b7280'>{escape(l.description)}</font>"
            extra = [x for x in (l.batch_no and f"Batch {l.batch_no}", l.expiry_date and f"Exp {l.expiry_date:%m/%Y}",
                                 l.serial_nos and f"S/N {l.serial_nos}") if x]
            if extra:
                desc += f"<br/><font size='{fs - 1}' color='#6b7280'>{escape(' · '.join(extra))}</font>"
            r = [P(i, pr), PH(desc)]
            if show_hsn:
                r.append(P(l.hsn_sac or ""))
            r += [P(f"{qty_str(l.qty)} {'' if l.unit == 'NA' else (l.unit or '')}", pr), P(inr(l.rate, False), pr)]
            if show_disc:
                r.append(P(inr(l.discount, False) if l.discount else "", pr))
            if tax:
                r += [P(inr(l.taxable, False), pr), P(f"{qty_str(l.gst_rate)}%", pr)]
                r += [P(inr(l.igst, False), pr)] if inter else [P(inr(l.cgst, False), pr), P(inr(l.sgst, False), pr)]
            r.append(P(inr(l.total, False), pr))
            rows.append(r)
        it = Table(rows, colWidths=widths, repeatRows=1)
        it.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), accent), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
                                ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
        story += [it, Spacer(1, 6)]

        # ---- tax summary + totals
        left_blocks = []
        if tax and ps.get("show_tax_summary", True):
            buckets: dict[Decimal, dict] = {}
            for l in v.lines:
                b = buckets.setdefault(l.gst_rate, dict(taxable=Decimal(0), cgst=Decimal(0), sgst=Decimal(0), igst=Decimal(0), cess=Decimal(0)))
                for k in b:
                    b[k] += getattr(l, k)
            hdr2 = ["GST %", "Taxable"] + (["IGST"] if inter else ["CGST", "SGST"]) + (["Cess"] if v.cess else [])
            trs = [[P(h, head_wr if j else head_w) for j, h in enumerate(hdr2)]]
            for rate, b in sorted(buckets.items()):
                trs.append([P(f"{qty_str(rate)}%"), P(inr(b["taxable"], False), pr)] + ([P(inr(b["igst"], False), pr)] if inter else
                           [P(inr(b["cgst"], False), pr), P(inr(b["sgst"], False), pr)]) + ([P(inr(b["cess"], False), pr)] if v.cess else []))
            ts = Table(trs, colWidths=[(W * 0.5) / len(hdr2)] * len(hdr2))
            ts.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6b7280")),
                                    ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#e5e7eb"))]))
            left_blocks += [ts, Spacer(1, 4)]
        left_blocks.append(PH(f"<b>Amount in words:</b> {escape(amount_in_words(v.grand_total))}"))
        if v.export_type and v.export_type != "IMPORT":
            decl = ("Supply meant for export" if v.export_type.startswith("EXP") else "Supply meant for SEZ unit / developer for authorised operations")
            decl += (f" under bond or Letter of Undertaking{' (' + biz.lut_number + ')' if biz.lut_number else ''} without payment of integrated tax."
                     if v.export_type.endswith("WOP") else " on payment of integrated tax.")
            left_blocks.append(PH(f"<b>{escape(decl)}</b>", tiny))
        if v.reverse_charge:
            left_blocks.append(P("Tax is payable on reverse charge basis.", tiny))
        tot = [("Sub total", v.sub_total)]
        if v.discount:
            tot.append(("Discount", -v.discount))
        if tax:
            tot.append(("Taxable value", v.taxable))
            tot += [("IGST", v.igst)] if inter else [("CGST", v.cgst), ("SGST", v.sgst)]
            if v.cess:
                tot.append(("Cess", v.cess))
        if v.tcs_amount:
            tot.append((f"TCS @ {qty_str(v.tcs_rate)}%", v.tcs_amount))
        if v.round_off:
            tot.append(("Round off", v.round_off))
        trows = [[P(k), P(inr(val), pr)] for k, val in tot]
        trows.append([P("Total", S("tt", fn=bold, size=fs + 2)), P(inr(v.grand_total), S("ttr", fn=bold, size=fs + 2, alignment=2))])
        if balance is not None and paid:
            trows += [[P("Paid"), P(inr(paid), pr)], [P("Balance", pb), P(inr(balance), prb)]]
        tt = Table(trows, colWidths=[W * 0.22, W * 0.2])
        tt.setStyle(TableStyle([("LINEABOVE", (0, len(tot)), (-1, len(tot)), 0.8, accent),
                                ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        bt = Table([[left_blocks, tt]], colWidths=[W * 0.56, W * 0.44])
        bt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story += [KeepTogether([bt]), Spacer(1, 8)]

        # ---- bank, UPI, terms, signature
        foot_left = []
        if outward and ps.get("show_bank", True) and biz.bank_account_no:
            foot_left.append(PH("<b>Bank details</b>"))
            foot_left.append(P(" · ".join(x for x in (biz.bank_name, f"A/c {biz.bank_account_no}", biz.bank_ifsc and f"IFSC {biz.bank_ifsc}",
                                                      biz.bank_branch) if x)))
        qr = None
        if v.type == VoucherType.SALE and ps.get("show_upi_qr", True) and biz.upi_id and (balance or 0) > 0:
            from urllib.parse import quote
            upi = (f"upi://pay?pa={quote(biz.upi_id)}&pn={quote(biz.name)}&am={balance:.2f}&cu=INR&tn={quote('Invoice ' + v.number)}")
            qr = [_qr(upi, 24 * mm), P(f"Scan to pay {inr(balance)}", S("qc", size=fs - 1, alignment=1))]
            foot_left.append(P(f"UPI: {biz.upi_id}"))
        if ps.get("show_terms", True) and v.terms:
            foot_left += [Spacer(1, 3), PH("<b>Terms &amp; conditions</b>"), PH(escape(v.terms).replace("\n", "<br/>"), tiny)]
        if v.notes:
            foot_left += [Spacer(1, 3), PH("<b>Notes</b>"), PH(escape(v.notes).replace("\n", "<br/>"), tiny)]
        sign = []
        if outward and ps.get("show_signature", True):
            sign.append(P(f"For {biz.legal_name or biz.name}", S("sg", alignment=2)))
            img = _image(biz.signature_url, 35 * mm, 14 * mm) if images else None
            sign += [img] if img else [Spacer(1, 14 * mm)]
            sign.append(P("Authorised signatory", S("sg2", alignment=2, textColor=colors.HexColor("#6b7280"))))
        cells = [[foot_left or "", qr or "", sign or ""]]
        ft = Table(cells, colWidths=[W * 0.5, W * 0.2, W * 0.3])
        ft.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("ALIGN", (1, 0), (1, 0), "CENTER")]))
        story += [KeepTogether([ft])]
        note = ps.get("footer_note")
        story += [Spacer(1, 6), P(note or "This is a computer generated document.", S("fn", size=fs - 1, alignment=1, textColor=colors.HexColor("#6b7280")))]
        return story

    labels = copies or (ps.get("copy_labels") if v.type == VoucherType.SALE else None) or [None]
    story: list = []
    for i, lab in enumerate(labels):
        if i:
            story.append(PageBreak())
        story += build(lab)

    brand = config_store.app_name()

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 6.5)
        canvas.setFillColor(colors.HexColor("#9ca3af"))
        canvas.drawRightString(page[0] - 10 * mm, 6 * mm, f"Page {doc.page}")
        if watermark:
            canvas.drawString(10 * mm, 6 * mm, f"Created with {brand} — free billing software")
        if v.cancelled:
            canvas.setFont(bold, 60)
            canvas.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.12))
            canvas.translate(page[0] / 2, page[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "CANCELLED")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=10 * mm, rightMargin=10 * mm, topMargin=9 * mm, bottomMargin=11 * mm,
                            title=f"{title} {v.number}", author=biz.name, subject=f"{title} {v.number} — {v.party_name}")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def _slug(text: str, limit: int) -> str:
    out, dash = [], False
    for ch in text:
        if ch.isalnum():
            out.append(ch)
            dash = False
        elif not dash and out:
            out.append("-")
            dash = True
    return "".join(out).strip("-")[:limit].strip("-")


def short_party(name: str | None) -> str:
    """First two words of the party name, e.g. 'Karan Stores Pvt Ltd' -> 'Karan-Stores'."""
    words = [w for w in (name or "").replace("&", " ").split() if any(c.isalnum() for c in w)]
    while words and words[0].lower().strip(".") in ("m/s", "ms", "messrs", "mr", "mrs", "shri", "smt"):
        words = words[1:]
    return _slug(" ".join(words[:2]), 20) or "Party"


def filename(v: Voucher) -> str:
    """Tax-Invoice_INV-0012_Karan-Stores_06-10-2026.pdf — type, number, party, date: sorts and reads well in a folder."""
    title = document_title(v.type, v.tax_applicable).split("/")[0].strip()
    return f"{_slug(title, 30)}_{_slug(v.number, 30) or 'draft'}_{short_party(v.party_name)}_{v.date.strftime('%d-%m-%Y')}.pdf"
