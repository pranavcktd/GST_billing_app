"""e-Invoice (IRN) and e-Way Bill.

* `einvoice_payload` builds the IRP JSON (NIC schema v1.1) for B2B/SEZ invoices and credit notes.
* `ewaybill_payload` builds the e-way bill JSON in the NIC bulk-upload format.
Both can be downloaded and uploaded on the government portals (offline route, any plan),
or sent through a provider:

* SandboxProvider — local test mode: IRN computed the way the IRP computes it (SHA-256 of
  supplier GSTIN + financial year + document type + number), acknowledgement and QR payload
  generated locally and clearly marked "SANDBOX". Nothing is reported to the government.
* GspProvider — calls your GST Suvidha Provider. Each GSP's API differs slightly, so the
  request/response mapping lives in this one class; fill it in with your GSP's documentation.
"""

import base64
import datetime as dt
import hashlib
import json
import random
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..gst.constants import BusinessGstType, VoucherType
from ..gst.fy import fy_label
from ..models import Business, Item, Party, Voucher
from ..security import decrypt_secret

EINVOICE_TYPES = {VoucherType.SALE: "INV", VoucherType.SALE_RETURN: "CRN"}
EWB_DOC_TYPES = {VoucherType.SALE: "INV", VoucherType.DELIVERY_CHALLAN: "CHL", VoucherType.PURCHASE: "BIL"}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _d(x) -> float:
    return float(Decimal(x or 0).quantize(Decimal("0.01")))


def _pin(v) -> int | None:
    digits = "".join(c for c in str(v or "") if c.isdigit())
    return int(digits) if len(digits) == 6 else None


def _addr(text: str | None) -> tuple[str, str]:
    t = (text or "").replace("\n", ", ").strip()
    return (t[:100] or "", t[100:200])


class PayloadError(HTTPException):
    def __init__(self, problems: list[str]):
        super().__init__(422, "Please complete these details first:\n• " + "\n• ".join(problems))


def _party(db: Session, v: Voucher) -> Party | None:
    return db.get(Party, v.party_id) if v.party_id else None


def _is_service(db: Session, item_id: str | None, hsn: str | None) -> bool:
    it = db.get(Item, item_id) if item_id else None
    return bool(it and it.type.value == "SERVICE") or (hsn or "").startswith("99")


# ---------------------------------------------------------------- e-invoice JSON
def einvoice_payload(db: Session, biz: Business, v: Voucher) -> dict:
    problems = []
    if biz.gst_type != BusinessGstType.REGULAR or not biz.gstin:
        problems.append("e-Invoicing applies to regular GST registered businesses")
    if v.type not in EINVOICE_TYPES:
        problems.append("e-Invoice can be generated for sale invoices and credit notes only")
    export = bool(v.export_type and v.export_type.startswith("EXP"))
    if not v.party_gstin and not export:
        problems.append("The buyer's GSTIN is required (e-Invoice is for B2B supplies and exports)")
    if not biz.address:
        problems.append("Business address (Settings)")
    if not _pin(biz.pincode):
        problems.append("Business 6-digit pincode (Settings)")
    party = _party(db, v)
    if party is not None and not export and not _pin(party.pincode):
        problems.append(f"Pincode of {party.name} (Parties)")
    if party is not None and not (party.billing_address or party.city):
        problems.append(f"Address of {party.name} (Parties)")
    missing_hsn = [l.name for l in v.lines if not l.hsn_sac or len(l.hsn_sac) < 4]
    if missing_hsn:
        problems.append("HSN/SAC for: " + ", ".join(missing_hsn[:5]))
    if v.cancelled:
        problems.append("The document is cancelled")
    if problems:
        raise PayloadError(problems)

    sup_typ = v.export_type if v.export_type in ("EXPWP", "EXPWOP", "SEZWP", "SEZWOP") else "B2B"
    seller_addr1, seller_addr2 = _addr(biz.address)
    buyer_addr1, buyer_addr2 = _addr(party.billing_address if party else v.party_address)
    items = []
    for i, l in enumerate(v.lines, 1):
        gross = l.amount
        item = {
            "SlNo": str(i), "PrdDesc": l.name[:300], "IsServc": "Y" if _is_service(db, l.item_id, l.hsn_sac) else "N",
            "HsnCd": l.hsn_sac, "Qty": float(l.qty), "Unit": (l.unit or "OTH")[:8],
            "UnitPrice": _d(l.rate if not l.tax_inclusive else (l.taxable + l.discount) / l.qty if l.qty else 0),
            "TotAmt": _d(gross if not l.tax_inclusive else l.taxable + l.discount), "Discount": _d(l.discount),
            "AssAmt": _d(l.taxable), "GstRt": float(l.gst_rate),
            "IgstAmt": _d(l.igst), "CgstAmt": _d(l.cgst), "SgstAmt": _d(l.sgst),
            "CesRt": float(l.cess_rate), "CesAmt": _d(l.cess), "CesNonAdvlAmt": 0,
            "StateCesRt": 0, "StateCesAmt": 0, "StateCesNonAdvlAmt": 0, "OthChrg": 0, "TotItemVal": _d(l.total),
        }
        if l.batch_no:
            item["BchDtls"] = {"Nm": l.batch_no[:20],
                               **({"ExpDt": l.expiry_date.strftime("%d/%m/%Y")} if l.expiry_date else {})}
        items.append(item)

    payload = {
        "Version": "1.1",
        "TranDtls": {"TaxSch": "GST", "SupTyp": sup_typ,
                     "RegRev": "Y" if v.reverse_charge else "N", "IgstOnIntra": "N"},
        "DocDtls": {"Typ": EINVOICE_TYPES[v.type], "No": v.number, "Dt": v.date.strftime("%d/%m/%Y")},
        "SellerDtls": {"Gstin": biz.gstin, "LglNm": biz.legal_name or biz.name, "TrdNm": biz.name,
                       "Addr1": seller_addr1, **({"Addr2": seller_addr2} if seller_addr2 else {}),
                       "Loc": (biz.city or "")[:50] or seller_addr1[:50], "Pin": _pin(biz.pincode),
                       "Stcd": biz.state_code,
                       **({"Ph": "".join(c for c in biz.phone if c.isdigit())[-12:]} if biz.phone else {}),
                       **({"Em": biz.email} if biz.email else {})},
        "BuyerDtls": {"Gstin": "URP" if export else v.party_gstin, "LglNm": v.party_name, "TrdNm": v.party_name,
                      "Pos": "96" if export else v.place_of_supply, "Addr1": buyer_addr1 or v.party_name,
                      **({"Addr2": buyer_addr2} if buyer_addr2 else {}),
                      "Loc": ((party.city if party else None) or buyer_addr1 or "NA")[:50],
                      "Pin": 999999 if export else (_pin(party.pincode) if party else None),
                      "Stcd": "96" if export else v.party_gstin[:2],
                      **({"Ph": "".join(c for c in v.party_phone if c.isdigit())[-12:]} if v.party_phone else {})},
        "ItemList": items,
        "ValDtls": {"AssVal": _d(v.taxable), "CgstVal": _d(v.cgst), "SgstVal": _d(v.sgst), "IgstVal": _d(v.igst),
                    "CesVal": _d(v.cess), "StCesVal": 0, "Discount": 0, "OthChrg": _d(v.tcs_amount),
                    "RndOffAmt": _d(v.round_off), "TotInvVal": _d(v.grand_total)},
    }
    if export:
        payload["ExpDtls"] = {k: val for k, val in {
            "ShipBNo": v.shipping_bill_no, "Port": v.port_code, "ForCur": v.currency_code,
            "ShipBDt": v.shipping_bill_date.strftime("%d/%m/%Y") if v.shipping_bill_date else None,
        }.items() if val}
    t = v.transport or {}
    if v.type == VoucherType.SALE and (t.get("vehicle_no") or t.get("transporter_id")) and t.get("distance_km") is not None:
        payload["EwbDtls"] = {k: val for k, val in {
            "TransId": t.get("transporter_id"), "TransName": t.get("transporter_name"),
            "Distance": int(t.get("distance_km") or 0), "TransDocNo": t.get("doc_no"),
            "TransDocDt": dt.date.fromisoformat(t["doc_date"]).strftime("%d/%m/%Y") if t.get("doc_date") else None,
            "VehNo": t.get("vehicle_no"), "VehType": t.get("vehicle_type", "R") if t.get("vehicle_no") else None,
            "TransMode": t.get("mode", "1") if t.get("vehicle_no") or t.get("doc_no") else None,
        }.items() if val not in (None, "")}
    return payload


# ---------------------------------------------------------------- e-way bill JSON
def ewaybill_payload(db: Session, biz: Business, v: Voucher) -> dict:
    problems = []
    if not biz.gstin:
        problems.append("Business GSTIN (e-way bill needs a GST registration)")
    if v.type not in EWB_DOC_TYPES:
        problems.append("e-Way bill can be prepared for sale invoices, delivery challans and purchase bills")
    if not _pin(biz.pincode):
        problems.append("Business 6-digit pincode (Settings)")
    party = _party(db, v)
    if not party or not _pin(party.pincode):
        problems.append("Party with a 6-digit pincode (Parties)")
    t = v.transport or {}
    if not t.get("distance_km"):
        problems.append("Approximate distance in km (Transport details on the bill)")
    if not (t.get("vehicle_no") or t.get("transporter_id")):
        problems.append("Vehicle number or transporter ID (Transport details on the bill)")
    missing_hsn = [l.name for l in v.lines if not l.hsn_sac]
    if missing_hsn:
        problems.append("HSN for: " + ", ".join(missing_hsn[:5]))
    if problems:
        raise PayloadError(problems)

    outward = v.type != VoucherType.PURCHASE
    us = dict(gstin=biz.gstin, name=biz.legal_name or biz.name, addr=_addr(biz.address), place=biz.city or "",
              pin=_pin(biz.pincode), state=int(biz.state_code))
    them = dict(gstin=v.party_gstin or "URP", name=v.party_name, addr=_addr(party.billing_address), place=party.city or "",
                pin=_pin(party.pincode), state=int(v.party_state_code or v.place_of_supply))
    frm, to = (us, them) if outward else (them, us)
    bill = {
        "userGstin": biz.gstin, "supplyType": "O" if outward else "I",
        "subSupplyType": int(t.get("sub_supply_type", "1")), "docType": EWB_DOC_TYPES[v.type],
        "docNo": v.supplier_invoice_no if v.type == VoucherType.PURCHASE and v.supplier_invoice_no else v.number,
        "docDate": (v.supplier_invoice_date or v.date).strftime("%d/%m/%Y"),
        "fromGstin": frm["gstin"], "fromTrdName": frm["name"], "fromAddr1": frm["addr"][0], "fromAddr2": frm["addr"][1],
        "fromPlace": frm["place"], "fromPincode": frm["pin"], "fromStateCode": frm["state"],
        "actFromStateCode": frm["state"],
        "toGstin": to["gstin"], "toTrdName": to["name"], "toAddr1": to["addr"][0], "toAddr2": to["addr"][1],
        "toPlace": to["place"], "toPincode": to["pin"], "toStateCode": to["state"], "actToStateCode": to["state"],
        "transactionType": 1, "totalValue": _d(v.taxable), "cgstValue": _d(v.cgst), "sgstValue": _d(v.sgst),
        "igstValue": _d(v.igst), "cessValue": _d(v.cess), "cessNonAdvolValue": 0,
        "otherValue": _d(v.round_off + v.tcs_amount), "totInvValue": _d(v.grand_total),
        "transporterId": t.get("transporter_id", ""), "transporterName": t.get("transporter_name", ""),
        "transDocNo": t.get("doc_no", ""), "transMode": int(t.get("mode", "1")),
        "transDistance": str(int(t.get("distance_km") or 0)),
        "transDocDate": dt.date.fromisoformat(t["doc_date"]).strftime("%d/%m/%Y") if t.get("doc_date") else "",
        "vehicleNo": t.get("vehicle_no", ""), "vehicleType": t.get("vehicle_type", "R"),
        "itemList": [{
            "itemNo": i, "productName": l.name[:100], "productDesc": (l.description or l.name)[:100],
            "hsnCode": int(l.hsn_sac), "quantity": float(l.qty), "qtyUnit": (l.unit or "OTH")[:3],
            "taxableAmount": _d(l.taxable),
            "cgstRate": float(l.gst_rate) / 2 if l.cgst else 0, "sgstRate": float(l.gst_rate) / 2 if l.sgst else 0,
            "igstRate": float(l.gst_rate) if l.igst else 0, "cessRate": float(l.cess_rate), "cessNonAdvol": 0,
        } for i, l in enumerate(v.lines, 1)],
    }
    return {"version": "1.0.0621", "billLists": [bill]}


# ---------------------------------------------------------------- providers
def compute_irn(gstin: str, doc_date: dt.date, doc_type: str, doc_no: str) -> str:
    """IRN = SHA-256 of supplier GSTIN, financial year, document type and document number."""
    return hashlib.sha256(f"{gstin}{fy_label(doc_date)}{doc_type}{doc_no}".upper().encode()).hexdigest()


class SandboxProvider:
    sandbox = True

    def generate_irn(self, biz: Business, v: Voucher, payload: dict) -> dict:
        irn = compute_irn(biz.gstin, v.date, payload["DocDtls"]["Typ"], v.number)
        now = dt.datetime.now(IST)
        qr_data = {"SellerGstin": biz.gstin, "BuyerGstin": v.party_gstin, "DocNo": v.number,
                   "DocTyp": payload["DocDtls"]["Typ"], "DocDt": payload["DocDtls"]["Dt"],
                   "TotInvVal": payload["ValDtls"]["TotInvVal"], "ItemCnt": len(payload["ItemList"]),
                   "MainHsnCode": payload["ItemList"][0]["HsnCd"], "Irn": irn,
                   "IrnDt": now.strftime("%Y-%m-%d %H:%M:%S"), "Sandbox": True}
        token = base64.urlsafe_b64encode(json.dumps(qr_data, separators=(",", ":")).encode()).decode().rstrip("=")
        return {"irn": irn, "ack_no": str(random.randint(10**14, 10**15 - 1)), "ack_date": now,
                "signed_qr": f"SANDBOX.{token}.NOT-SIGNED-BY-IRP"}

    def cancel_irn(self, biz: Business, v: Voucher, reason: str, remark: str) -> None:
        return None

    def generate_ewb(self, biz: Business, v: Voucher, payload: dict) -> dict:
        now = dt.datetime.now(IST)
        km = int(payload["billLists"][0]["transDistance"] or 0)
        days = max(1, -(-km // 200))  # 1 day per 200 km for regular cargo
        return {"ewb_no": str(random.randint(10**11, 10**12 - 1)), "ewb_date": now,
                "valid_till": (now + dt.timedelta(days=days)).replace(hour=23, minute=59, second=0)}


class GspProvider:
    """Adapter for your GSP. Implement with the GSP's API documentation (auth → generate / cancel)."""

    sandbox = False

    def __init__(self, biz: Business):
        s = get_settings()
        if not (s.gsp_base_url and s.gsp_client_id and s.gsp_client_secret):
            raise HTTPException(503, "GSP is not configured on the server (GSP_BASE_URL / GSP_CLIENT_ID / GSP_CLIENT_SECRET)")
        if not (biz.einvoice_username and biz.einvoice_password_enc):
            raise HTTPException(400, "Add your e-invoice API username and password in Settings → e-Invoice")
        self.base, self.client_id, self.client_secret = s.gsp_base_url, s.gsp_client_id, s.gsp_client_secret
        self.username, self.password = biz.einvoice_username, decrypt_secret(biz.einvoice_password_enc)

    def _todo(self):
        raise HTTPException(501, "GSP integration is not implemented yet — use sandbox mode or the JSON download")

    def generate_irn(self, biz, v, payload):
        self._todo()

    def cancel_irn(self, biz, v, reason, remark):
        self._todo()

    def generate_ewb(self, biz, v, payload):
        self._todo()


def provider(biz: Business):
    return GspProvider(biz) if get_settings().einvoice_provider.lower() == "gsp" else SandboxProvider()
