/* eslint-disable @next/next/no-img-element */
import { QR, upiLink } from "@/components/QR";
import { STATES, stateLabel } from "@/lib/constants";
import { fmtDate, money, qty } from "@/lib/format";
import type { Business, PrintSettings, VoucherDetail } from "@/lib/types";

export const DEFAULT_PRINT: PrintSettings = {
  theme: "classic", accent: "#1f65bb", paper: "A4", copy_labels: ["ORIGINAL"], show_hsn: true, show_discount: true,
  show_tax_summary: true, show_bank: true, show_upi_qr: true, show_terms: true, show_signature: true,
  show_item_description: true, show_transport: true, title_override: null, footer_note: null, custom_fields: [],
};

const COPY_TEXT = { ORIGINAL: "Original for recipient", DUPLICATE: "Duplicate for transporter", TRIPLICATE: "Triplicate for supplier" };
const MODE = { "1": "Road", "2": "Rail", "3": "Air", "4": "Ship" } as const;

/**
 * A4 / A5 invoice covering Rule 46 (Tax Invoice) / Rule 49 (Bill of Supply) particulars, with the
 * business's print settings (theme, accent, fields), custom fields, transport, e-invoice IRN + QR,
 * UPI payment QR and — on the free plan — the app watermark.
 */
export function InvoiceDocument({ v, business, copy }: { v: VoucherDetail; business: Business; copy?: keyof typeof COPY_TEXT }) {
  const ps = { ...DEFAULT_PRINT, ...(business.print_settings ?? {}) };
  const outward = ["SALE", "SALE_RETURN", "ESTIMATE", "SALE_ORDER", "DELIVERY_CHALLAN"].includes(v.type);
  const accent = ps.accent;
  const modern = ps.theme === "modern";
  const minimal = ps.theme === "minimal";
  const seller = outward
    ? { name: business.legal_name || business.name, trade: business.name, gstin: business.gstin, address: [business.address, business.city, business.pincode].filter(Boolean).join(", "), state: business.state_code, phone: business.phone }
    : { name: v.party_name, trade: v.party_name, gstin: v.party_gstin, address: v.party_address ?? "", state: v.party_state_code, phone: v.party_phone };
  const buyer = outward
    ? { name: v.party_name, gstin: v.party_gstin, address: v.party_address ?? "", state: v.party_state_code, phone: v.party_phone }
    : { name: business.name, gstin: business.gstin, address: [business.address, business.city].filter(Boolean).join(", "), state: business.state_code, phone: business.phone };
  const showTax = v.tax_applicable;
  const inter = v.inter_state;
  const showHsn = ps.show_hsn;
  const showDisc = ps.show_discount && v.discount > 0;
  const custom = ps.custom_fields.filter((f) => f.print && v.extra_fields?.[f.key]);
  const t = v.transport ?? {};
  const hasTransport = ps.show_transport && (t.vehicle_no || t.transporter_name || t.doc_no || t.ship_to);
  const upi = ps.show_upi_qr && outward && v.type === "SALE" && business.upi_id && v.balance > 0 && !v.cancelled;
  const title = ps.title_override && v.type === "SALE" ? ps.title_override : v.title;
  const th = `border px-1.5 py-1 ${minimal ? "border-gray-200" : "border-gray-300"}`;
  const cell = `border px-1.5 py-1 align-top ${minimal ? "border-gray-200" : "border-gray-300"}`;

  return (
    <div className={`print-sheet relative mx-auto bg-white p-8 leading-relaxed text-gray-900 shadow-sm ${ps.paper === "A5" ? "max-w-[148mm] text-[10px]" : "max-w-[210mm] text-[12px]"}`}>
      {v.cancelled && (
        <div className="mb-3 rounded border border-red-300 bg-red-50 py-1 text-center text-sm font-semibold tracking-widest text-red-700">CANCELLED</div>
      )}
      {v.einvoice_sandbox && (
        <div className="mb-3 rounded border border-amber-300 bg-amber-50 py-1 text-center text-xs font-semibold text-amber-800">SANDBOX e-invoice / e-way bill — for testing, not valid for GST</div>
      )}
      <div className={`flex items-start justify-between gap-6 pb-4 ${minimal ? "border-b border-gray-200" : "border-b-2"}`}
        style={minimal ? undefined : { borderColor: modern ? accent : "#1f2937" }}>
        <div className="flex gap-4">
          {outward && business.logo_url && <img src={business.logo_url} alt="" className="h-16 w-16 object-contain" />}
          <div>
            <div className="text-lg font-bold" style={modern ? { color: accent } : undefined}>{seller.trade}</div>
            {seller.name !== seller.trade && <div className="text-gray-600">{seller.name}</div>}
            <div className="max-w-sm text-gray-700">{seller.address}</div>
            {seller.state && <div className="text-gray-700">State: {stateLabel(seller.state)}</div>}
            {seller.phone && <div className="text-gray-700">Phone: {seller.phone}</div>}
            {seller.gstin && <div className="font-semibold">GSTIN: {seller.gstin}</div>}
          </div>
        </div>
        <div className="flex items-start gap-3 text-right">
          <div>
            <div className={`font-bold tracking-wide uppercase ${modern ? "rounded px-3 py-1 text-base text-white" : "text-xl"}`}
              style={modern ? { background: accent } : undefined}>{title}</div>
            {outward && v.type === "SALE" && <div className="mt-1 text-[10px] text-gray-500 uppercase">{COPY_TEXT[copy ?? "ORIGINAL"]}</div>}
          </div>
          {v.signed_qr && v.einvoice_status === "GENERATED" && <QR value={v.signed_qr} size={84} />}
        </div>
      </div>

      {v.irn && v.einvoice_status === "GENERATED" && (
        <div className="border-b border-gray-200 py-1.5 text-[10px] break-all text-gray-700">
          <b>IRN:</b> {v.irn} · <b>Ack No:</b> {v.ack_no} · <b>Ack Date:</b> {v.ack_date ? new Date(v.ack_date).toLocaleString("en-IN") : ""}
          {v.ewb_no && <> · <b>E-way bill:</b> {v.ewb_no}</>}
        </div>
      )}
      {!v.irn && v.ewb_no && (
        <div className="border-b border-gray-200 py-1.5 text-[10px] text-gray-700"><b>E-way bill no:</b> {v.ewb_no}
          {v.ewb_valid_till && <> · valid till {new Date(v.ewb_valid_till).toLocaleString("en-IN")}</>}</div>
      )}

      <div className="grid grid-cols-2 gap-6 border-b border-gray-300 py-3">
        <div>
          <div className="text-[10px] font-semibold text-gray-500 uppercase">{outward ? "Bill to" : "Supplier"}</div>
          <div className="font-semibold">{outward ? buyer.name : v.party_name}</div>
          <div className="text-gray-700">{outward ? buyer.address : v.party_address}</div>
          {(outward ? buyer.phone : v.party_phone) && <div className="text-gray-700">Phone: {outward ? buyer.phone : v.party_phone}</div>}
          {(outward ? buyer.gstin : v.party_gstin) && <div className="font-semibold">GSTIN: {outward ? buyer.gstin : v.party_gstin}</div>}
          {v.party_state_code && <div className="text-gray-700">State: {stateLabel(v.party_state_code)}</div>}
          {hasTransport && t.ship_to && (
            <div className="mt-2">
              <div className="text-[10px] font-semibold text-gray-500 uppercase">Ship to</div>
              <div className="whitespace-pre-line text-gray-700">{t.ship_to}</div>
            </div>
          )}
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 self-start">
          <span className="text-gray-500">No.</span><span className="font-semibold">{v.number}</span>
          <span className="text-gray-500">Date</span><span>{fmtDate(v.date)}</span>
          {v.due_date && (<><span className="text-gray-500">Due date</span><span>{fmtDate(v.due_date)}</span></>)}
          {showTax && (<><span className="text-gray-500">Place of supply</span><span>{v.place_of_supply}-{STATES[v.place_of_supply] ?? "Outside India"}</span></>)}
          {v.shipping_bill_no && (<><span className="text-gray-500">{v.export_type === "IMPORT" ? "Bill of entry" : "Shipping bill"}</span><span>{v.shipping_bill_no}{v.shipping_bill_date ? ` · ${fmtDate(v.shipping_bill_date)}` : ""}{v.port_code ? ` · ${v.port_code}` : ""}</span></>)}
          {v.currency_code && v.exchange_rate && (<><span className="text-gray-500">Currency</span><span>{v.currency_code} @ ₹{v.exchange_rate} · {v.currency_code} {(v.grand_total / v.exchange_rate).toFixed(2)}</span></>)}
          {v.supplier_invoice_no && (<><span className="text-gray-500">Supplier bill</span><span>{v.supplier_invoice_no}{v.supplier_invoice_date ? ` · ${fmtDate(v.supplier_invoice_date)}` : ""}</span></>)}
          {v.original_number && (<><span className="text-gray-500">Against</span><span>{v.original_number}</span></>)}
          {v.reason && (<><span className="text-gray-500">Reason</span><span>{v.reason}</span></>)}
          {showTax && (<><span className="text-gray-500">Reverse charge</span><span>{v.reverse_charge ? "Yes" : "No"}</span></>)}
          {custom.map((f) => (<span key={f.key} className="contents"><span className="text-gray-500">{f.label}</span><span>{v.extra_fields![f.key]}</span></span>))}
          {hasTransport && t.vehicle_no && (<><span className="text-gray-500">Vehicle</span><span>{t.vehicle_no}</span></>)}
          {hasTransport && t.transporter_name && (<><span className="text-gray-500">Transporter</span><span>{t.transporter_name}</span></>)}
          {hasTransport && t.doc_no && (<><span className="text-gray-500">{MODE[t.mode ?? "1"] === "Road" ? "LR" : "Transport doc"}</span><span>{t.doc_no}{t.doc_date ? ` · ${fmtDate(t.doc_date)}` : ""}</span></>)}
        </div>
      </div>

      <table className="mt-3 w-full border-collapse text-[11px]">
        <thead>
          <tr className="text-left" style={modern ? { background: accent, color: "#fff" } : { background: "#f3f4f6" }}>
            <th className={th}>#</th>
            <th className={th}>Item</th>
            {showHsn && <th className={th}>HSN/SAC</th>}
            <th className={`${th} text-right`}>Qty</th>
            <th className={`${th} text-right`}>Rate</th>
            {showDisc && <th className={`${th} text-right`}>Disc</th>}
            <th className={`${th} text-right`}>Taxable</th>
            {showTax && <th className={`${th} text-right`}>GST</th>}
            {showTax && (inter ? <th className={`${th} text-right`}>IGST</th> : (<><th className={`${th} text-right`}>CGST</th><th className={`${th} text-right`}>SGST</th></>))}
            <th className={`${th} text-right`}>Amount</th>
          </tr>
        </thead>
        <tbody>
          {v.lines.map((l, i) => (
            <tr key={l.id ?? i}>
              <td className={cell}>{i + 1}</td>
              <td className={cell}>
                <div className="font-medium">{l.name}</div>
                {ps.show_item_description && l.description && <div className="text-gray-600">{l.description}</div>}
                {(l.batch_no || l.expiry_date) && (
                  <div className="text-[10px] text-gray-600">
                    {l.batch_no && `Batch: ${l.batch_no}`}{l.batch_no && l.expiry_date && " · "}{l.expiry_date && `Exp: ${fmtDate(l.expiry_date)}`}
                  </div>
                )}
                {l.serial_nos && <div className="text-[10px] text-gray-600">S/N: {l.serial_nos}</div>}
              </td>
              {showHsn && <td className={cell}>{l.hsn_sac}</td>}
              <td className={`${cell} text-right whitespace-nowrap`}>{qty(l.qty)} {l.unit}</td>
              <td className={`${cell} text-right`}>{money(l.rate)}{l.tax_inclusive && showTax ? "*" : ""}</td>
              {showDisc && <td className={`${cell} text-right`}>{money(l.discount)}</td>}
              <td className={`${cell} text-right`}>{money(l.taxable)}</td>
              {showTax && <td className={`${cell} text-right`}>{l.gst_rate}%</td>}
              {showTax && (inter ? <td className={`${cell} text-right`}>{money(l.igst)}</td> : (<><td className={`${cell} text-right`}>{money(l.cgst)}</td><td className={`${cell} text-right`}>{money(l.sgst)}</td></>))}
              <td className={`${cell} text-right font-medium`}>{money(l.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {v.lines.some((l) => l.tax_inclusive) && showTax && <div className="mt-1 text-[10px] text-gray-500">* rate inclusive of tax</div>}

      <div className="mt-4 grid grid-cols-5 gap-6">
        <div className="col-span-3 space-y-3">
          <div>
            <div className="text-[10px] font-semibold text-gray-500 uppercase">Amount in words</div>
            <div className="font-medium">{v.amount_in_words}</div>
          </div>
          {ps.show_tax_summary && showTax && v.tax_breakup.length > 0 && (
            <table className="w-full border-collapse text-[10px]">
              <thead>
                <tr className="bg-gray-50">
                  <th className="border border-gray-300 px-1 py-0.5 text-left">GST rate</th>
                  <th className="border border-gray-300 px-1 py-0.5 text-right">Taxable</th>
                  {inter ? <th className="border border-gray-300 px-1 py-0.5 text-right">IGST</th> : (<><th className="border border-gray-300 px-1 py-0.5 text-right">CGST</th><th className="border border-gray-300 px-1 py-0.5 text-right">SGST</th></>)}
                  <th className="border border-gray-300 px-1 py-0.5 text-right">Total tax</th>
                </tr>
              </thead>
              <tbody>
                {v.tax_breakup.map((b) => (
                  <tr key={b.rate}>
                    <td className="border border-gray-300 px-1 py-0.5">{b.rate}%</td>
                    <td className="border border-gray-300 px-1 py-0.5 text-right">{money(b.taxable)}</td>
                    {inter ? <td className="border border-gray-300 px-1 py-0.5 text-right">{money(b.igst)}</td> : (<><td className="border border-gray-300 px-1 py-0.5 text-right">{money(b.cgst)}</td><td className="border border-gray-300 px-1 py-0.5 text-right">{money(b.sgst)}</td></>)}
                    <td className="border border-gray-300 px-1 py-0.5 text-right">{money(b.cgst + b.sgst + b.igst + b.cess)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!showTax && outward && business.gst_type === "COMPOSITION" && (
            <div className="font-medium">Composition taxable person, not eligible to collect tax on supplies.</div>
          )}
          <div className="flex items-start gap-4">
            {ps.show_bank && outward && (business.bank_account_no || business.upi_id) && (
              <div className="flex-1">
                <div className="text-[10px] font-semibold text-gray-500 uppercase">Bank details</div>
                {business.bank_name && <div>{business.bank_name}{business.bank_branch ? `, ${business.bank_branch}` : ""}</div>}
                {business.bank_account_no && <div>A/c: {business.bank_account_no} · IFSC: {business.bank_ifsc}</div>}
                {business.upi_id && <div>UPI: {business.upi_id}</div>}
              </div>
            )}
            {upi && (
              <div className="text-center">
                <QR value={upiLink(business.upi_id!, business.name, v.balance, `${v.number}`)} size={80} />
                <div className="mt-0.5 text-[9px] text-gray-600">Scan to pay {money(v.balance)}</div>
              </div>
            )}
          </div>
          {v.notes && (<div><div className="text-[10px] font-semibold text-gray-500 uppercase">Notes</div><div className="whitespace-pre-line">{v.notes}</div></div>)}
          {ps.show_terms && v.terms && (<div><div className="text-[10px] font-semibold text-gray-500 uppercase">Terms & conditions</div><div className="whitespace-pre-line text-gray-700">{v.terms}</div></div>)}
        </div>
        <div className="col-span-2">
          <div className="space-y-0.5">
            <TotalRow label="Taxable amount" value={v.taxable} />
            {showTax && (inter ? <TotalRow label="IGST" value={v.igst} /> : (<><TotalRow label="CGST" value={v.cgst} /><TotalRow label="SGST" value={v.sgst} /></>))}
            {v.cess > 0 && <TotalRow label="Cess" value={v.cess} />}
            {v.tcs_amount > 0 && <TotalRow label={`TCS @ ${v.tcs_rate}%`} value={v.tcs_amount} />}
            {v.round_off !== 0 && <TotalRow label="Round off" value={v.round_off} />}
            <div className="mt-1 flex justify-between border-t-2 pt-1 text-sm font-bold" style={{ borderColor: modern ? accent : "#1f2937" }}>
              <span>Total</span><span>{money(v.grand_total)}</span>
            </div>
            {v.paid > 0 && (
              <>
                <TotalRow label="Paid" value={v.paid} />
                <TotalRow label="Balance" value={v.balance} />
              </>
            )}
            {v.reverse_charge && <div className="pt-1 text-[10px]">Tax is payable on reverse charge basis.</div>}
            {v.export_type && v.export_type !== "IMPORT" && (
              <div className="pt-1 text-[10px] font-medium">
                {v.export_type.startsWith("EXP") ? "Supply meant for export" : "Supply meant for SEZ unit / developer for authorised operations"}
                {v.export_type.endsWith("WOP")
                  ? ` under bond or Letter of Undertaking${business.lut_number ? ` (${business.lut_number})` : ""} without payment of integrated tax.`
                  : " on payment of integrated tax."}
              </div>
            )}
          </div>
          {outward && ps.show_signature && (
            <div className="mt-10 text-right">
              <div className="text-[11px]">For {business.name}</div>
              {business.signature_url ? <img src={business.signature_url} alt="" className="ml-auto h-12 object-contain" /> : <div className="h-12" />}
              <div className="text-[11px] text-gray-600">Authorised Signatory</div>
            </div>
          )}
        </div>
      </div>
      {ps.footer_note && <div className="mt-4 text-center text-[11px] text-gray-600">{ps.footer_note}</div>}
      <div className="mt-6 border-t border-gray-200 pt-2 text-center text-[10px] text-gray-400">
        This is a computer generated document.
        {business.plan?.watermark && <span className="ml-1 font-medium text-gray-500">Billed via GST Billing — free billing app</span>}
      </div>
    </div>
  );
}

function TotalRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-600">{label}</span>
      <span>{money(value)}</span>
    </div>
  );
}
