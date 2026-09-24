/* eslint-disable @next/next/no-img-element */
import { STATES, stateLabel } from "@/lib/constants";
import { fmtDate, money, qty } from "@/lib/format";
import type { Business, VoucherDetail } from "@/lib/types";

/**
 * A4 invoice layout covering the Rule 46 (Tax Invoice) / Rule 49 (Bill of Supply) particulars:
 * supplier name/address/GSTIN, serial number & date, recipient details and GSTIN, place of supply
 * with state, HSN/SAC, quantity & unit, value, taxable value, rate & amount of CGST/SGST/IGST/cess,
 * reverse-charge declaration and authorised signature.
 */
export function InvoiceDocument({ v, business }: { v: VoucherDetail; business: Business }) {
  const outward = v.type === "SALE" || v.type === "SALE_RETURN" || v.type === "ESTIMATE";
  const seller = outward
    ? { name: business.legal_name || business.name, trade: business.name, gstin: business.gstin, address: [business.address, business.city, business.pincode].filter(Boolean).join(", "), state: business.state_code, phone: business.phone }
    : { name: v.party_name, trade: v.party_name, gstin: v.party_gstin, address: v.party_address ?? "", state: v.party_state_code, phone: v.party_phone };
  const buyer = outward
    ? { name: v.party_name, gstin: v.party_gstin, address: v.party_address ?? "", state: v.party_state_code, phone: v.party_phone }
    : { name: business.name, gstin: business.gstin, address: [business.address, business.city].filter(Boolean).join(", "), state: business.state_code, phone: business.phone };
  const showTax = v.tax_applicable;
  const inter = v.inter_state;

  return (
    <div className="print-sheet mx-auto max-w-[210mm] bg-white p-8 text-[12px] leading-relaxed text-gray-900 shadow-sm">
      {v.cancelled && (
        <div className="mb-3 rounded border border-red-300 bg-red-50 py-1 text-center text-sm font-semibold tracking-widest text-red-700">CANCELLED</div>
      )}
      <div className="flex items-start justify-between gap-6 border-b-2 border-gray-800 pb-4">
        <div className="flex gap-4">
          {outward && business.logo_url && <img src={business.logo_url} alt="" className="h-16 w-16 object-contain" />}
          <div>
            <div className="text-lg font-bold">{seller.trade}</div>
            {seller.name !== seller.trade && <div className="text-gray-600">{seller.name}</div>}
            <div className="max-w-sm text-gray-700">{seller.address}</div>
            {seller.state && <div className="text-gray-700">State: {stateLabel(seller.state)}</div>}
            {seller.phone && <div className="text-gray-700">Phone: {seller.phone}</div>}
            {seller.gstin && <div className="font-semibold">GSTIN: {seller.gstin}</div>}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xl font-bold tracking-wide uppercase">{v.title}</div>
          {outward && v.type === "SALE" && <div className="text-[10px] text-gray-500">ORIGINAL FOR RECIPIENT</div>}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6 border-b border-gray-300 py-3">
        <div>
          <div className="text-[10px] font-semibold text-gray-500 uppercase">{outward ? "Bill to" : "Supplier"}</div>
          <div className="font-semibold">{outward ? buyer.name : v.party_name}</div>
          <div className="text-gray-700">{outward ? buyer.address : v.party_address}</div>
          {(outward ? buyer.phone : v.party_phone) && <div className="text-gray-700">Phone: {outward ? buyer.phone : v.party_phone}</div>}
          {(outward ? buyer.gstin : v.party_gstin) && <div className="font-semibold">GSTIN: {outward ? buyer.gstin : v.party_gstin}</div>}
          {v.party_state_code && <div className="text-gray-700">State: {stateLabel(v.party_state_code)}</div>}
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 self-start">
          <span className="text-gray-500">No.</span><span className="font-semibold">{v.number}</span>
          <span className="text-gray-500">Date</span><span>{fmtDate(v.date)}</span>
          {v.due_date && (<><span className="text-gray-500">Due date</span><span>{fmtDate(v.due_date)}</span></>)}
          {showTax && (<><span className="text-gray-500">Place of supply</span><span>{v.place_of_supply}-{STATES[v.place_of_supply]}</span></>)}
          {v.supplier_invoice_no && (<><span className="text-gray-500">Supplier bill</span><span>{v.supplier_invoice_no}{v.supplier_invoice_date ? ` · ${fmtDate(v.supplier_invoice_date)}` : ""}</span></>)}
          {v.original_number && (<><span className="text-gray-500">Against</span><span>{v.original_number}</span></>)}
          {v.reason && (<><span className="text-gray-500">Reason</span><span>{v.reason}</span></>)}
          {showTax && (<><span className="text-gray-500">Reverse charge</span><span>{v.reverse_charge ? "Yes" : "No"}</span></>)}
        </div>
      </div>

      <table className="mt-3 w-full border-collapse text-[11px]">
        <thead>
          <tr className="bg-gray-100 text-left">
            <th className="border border-gray-300 px-1.5 py-1">#</th>
            <th className="border border-gray-300 px-1.5 py-1">Item</th>
            <th className="border border-gray-300 px-1.5 py-1">HSN/SAC</th>
            <th className="border border-gray-300 px-1.5 py-1 text-right">Qty</th>
            <th className="border border-gray-300 px-1.5 py-1 text-right">Rate</th>
            {v.discount > 0 && <th className="border border-gray-300 px-1.5 py-1 text-right">Disc</th>}
            <th className="border border-gray-300 px-1.5 py-1 text-right">Taxable</th>
            {showTax && <th className="border border-gray-300 px-1.5 py-1 text-right">GST</th>}
            {showTax && (inter ? (
              <th className="border border-gray-300 px-1.5 py-1 text-right">IGST</th>
            ) : (
              <>
                <th className="border border-gray-300 px-1.5 py-1 text-right">CGST</th>
                <th className="border border-gray-300 px-1.5 py-1 text-right">SGST</th>
              </>
            ))}
            <th className="border border-gray-300 px-1.5 py-1 text-right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {v.lines.map((l, i) => (
            <tr key={l.id ?? i}>
              <td className="border border-gray-300 px-1.5 py-1 align-top">{i + 1}</td>
              <td className="border border-gray-300 px-1.5 py-1 align-top">
                <div className="font-medium">{l.name}</div>
                {l.description && <div className="text-gray-600">{l.description}</div>}
                {(l.batch_no || l.expiry_date) && (
                  <div className="text-[10px] text-gray-600">
                    {l.batch_no && `Batch: ${l.batch_no}`}{l.batch_no && l.expiry_date && " · "}{l.expiry_date && `Exp: ${fmtDate(l.expiry_date)}`}
                  </div>
                )}
                {l.serial_nos && <div className="text-[10px] text-gray-600">S/N: {l.serial_nos}</div>}
              </td>
              <td className="border border-gray-300 px-1.5 py-1 align-top">{l.hsn_sac}</td>
              <td className="border border-gray-300 px-1.5 py-1 text-right align-top whitespace-nowrap">{qty(l.qty)} {l.unit}</td>
              <td className="border border-gray-300 px-1.5 py-1 text-right align-top">{money(l.rate)}{l.tax_inclusive && showTax ? "*" : ""}</td>
              {v.discount > 0 && <td className="border border-gray-300 px-1.5 py-1 text-right align-top">{money(l.discount)}</td>}
              <td className="border border-gray-300 px-1.5 py-1 text-right align-top">{money(l.taxable)}</td>
              {showTax && <td className="border border-gray-300 px-1.5 py-1 text-right align-top">{l.gst_rate}%</td>}
              {showTax && (inter ? (
                <td className="border border-gray-300 px-1.5 py-1 text-right align-top">{money(l.igst)}</td>
              ) : (
                <>
                  <td className="border border-gray-300 px-1.5 py-1 text-right align-top">{money(l.cgst)}</td>
                  <td className="border border-gray-300 px-1.5 py-1 text-right align-top">{money(l.sgst)}</td>
                </>
              ))}
              <td className="border border-gray-300 px-1.5 py-1 text-right align-top font-medium">{money(l.total)}</td>
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
          {showTax && v.tax_breakup.length > 0 && (
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
          {outward && (business.bank_account_no || business.upi_id) && (
            <div>
              <div className="text-[10px] font-semibold text-gray-500 uppercase">Bank details</div>
              {business.bank_name && <div>{business.bank_name}{business.bank_branch ? `, ${business.bank_branch}` : ""}</div>}
              {business.bank_account_no && <div>A/c: {business.bank_account_no} · IFSC: {business.bank_ifsc}</div>}
              {business.upi_id && <div>UPI: {business.upi_id}</div>}
            </div>
          )}
          {v.notes && (<div><div className="text-[10px] font-semibold text-gray-500 uppercase">Notes</div><div className="whitespace-pre-line">{v.notes}</div></div>)}
          {v.terms && (<div><div className="text-[10px] font-semibold text-gray-500 uppercase">Terms & conditions</div><div className="whitespace-pre-line text-gray-700">{v.terms}</div></div>)}
        </div>
        <div className="col-span-2">
          <div className="space-y-0.5">
            <TotalRow label="Taxable amount" value={v.taxable} />
            {showTax && (inter ? <TotalRow label="IGST" value={v.igst} /> : (<><TotalRow label="CGST" value={v.cgst} /><TotalRow label="SGST" value={v.sgst} /></>))}
            {v.cess > 0 && <TotalRow label="Cess" value={v.cess} />}
            {v.tcs_amount > 0 && <TotalRow label={`TCS @ ${v.tcs_rate}%`} value={v.tcs_amount} />}
            {v.round_off !== 0 && <TotalRow label="Round off" value={v.round_off} />}
            <div className="mt-1 flex justify-between border-t-2 border-gray-800 pt-1 text-sm font-bold">
              <span>Total</span><span>{money(v.grand_total)}</span>
            </div>
            {v.paid > 0 && (
              <>
                <TotalRow label="Paid" value={v.paid} />
                <TotalRow label="Balance" value={v.balance} />
              </>
            )}
            {v.reverse_charge && <div className="pt-1 text-[10px]">Tax is payable on reverse charge basis.</div>}
          </div>
          {outward && (
            <div className="mt-10 text-right">
              <div className="text-[11px]">For {business.name}</div>
              {business.signature_url ? <img src={business.signature_url} alt="" className="ml-auto h-12 object-contain" /> : <div className="h-12" />}
              <div className="text-[11px] text-gray-600">Authorised Signatory</div>
            </div>
          )}
        </div>
      </div>
      <div className="mt-6 border-t border-gray-200 pt-2 text-center text-[10px] text-gray-400">This is a computer generated document.</div>
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
