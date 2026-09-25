/* eslint-disable @next/next/no-img-element */
import { QR, upiLink } from "@/components/QR";
import { BrandName } from "@/lib/config";
import { fmtDate, money, qty } from "@/lib/format";
import type { Business, VoucherDetail } from "@/lib/types";

/** Receipt for 80 mm / 58 mm thermal printers (print with "Margins: none", scale 100%). */
export function ThermalReceipt({ v, business, width = 80 }: { v: VoucherDetail; business: Business; width?: 80 | 58 }) {
  const narrow = width === 58;
  const upi = business.upi_id && v.type === "SALE" && v.balance > 0 && !v.cancelled;
  return (
    <div className="print-sheet mx-auto bg-white p-2 font-mono text-black" style={{ width: `${width}mm`, fontSize: narrow ? 10 : 11, lineHeight: 1.35 }}>
      <style>{`@media print { @page { size: ${width}mm auto; margin: 0 } }`}</style>
      <div className="text-center">
        {business.logo_url && <img src={business.logo_url} alt="" className="mx-auto mb-1 h-10 object-contain grayscale" />}
        <div className="font-bold" style={{ fontSize: narrow ? 12 : 14 }}>{business.name}</div>
        {business.address && <div>{business.address}{business.city ? `, ${business.city}` : ""}</div>}
        {business.phone && <div>Ph: {business.phone}</div>}
        {business.gstin && <div>GSTIN: {business.gstin}</div>}
        <div className="mt-1 font-bold uppercase">{v.title}</div>
      </div>
      <Dash />
      <div className="flex justify-between"><span>No: {v.number}</span><span>{fmtDate(v.date)}</span></div>
      {v.party_name && <div>To: {v.party_name}{v.party_gstin ? ` (${v.party_gstin})` : ""}</div>}
      <Dash />
      {v.lines.map((l, i) => (
        <div key={l.id ?? i} className="mb-1">
          <div>{l.name}</div>
          <div className="flex justify-between">
            <span>{qty(l.qty)} x {money(l.rate).replace("₹", "")}{v.tax_applicable && l.gst_rate ? ` @${l.gst_rate}%` : ""}</span>
            <span>{money(l.total).replace("₹", "")}</span>
          </div>
        </div>
      ))}
      <Dash />
      <Row k="Taxable" v={v.taxable} />
      {v.tax_applicable && (v.inter_state ? <Row k="IGST" v={v.igst} /> : (<><Row k="CGST" v={v.cgst} /><Row k="SGST" v={v.sgst} /></>))}
      {v.cess > 0 && <Row k="Cess" v={v.cess} />}
      {v.tcs_amount > 0 && <Row k="TCS" v={v.tcs_amount} />}
      {v.round_off !== 0 && <Row k="Round off" v={v.round_off} />}
      <div className="flex justify-between font-bold" style={{ fontSize: narrow ? 12 : 14 }}><span>TOTAL</span><span>{money(v.grand_total)}</span></div>
      {v.paid > 0 && <Row k="Paid" v={v.paid} />}
      {v.balance > 0 && <Row k="Balance" v={v.balance} />}
      <Dash />
      <div className="text-center">{v.amount_in_words}</div>
      {upi && (
        <div className="mt-2 flex flex-col items-center">
          <QR value={upiLink(business.upi_id!, business.name, v.balance, v.number)} size={narrow ? 90 : 110} />
          <div>Scan & pay via UPI</div>
        </div>
      )}
      {v.signed_qr && v.einvoice_status === "GENERATED" && (
        <div className="mt-2 flex flex-col items-center"><QR value={v.signed_qr} size={narrow ? 90 : 110} /><div className="break-all">IRN {v.irn?.slice(0, 16)}…</div></div>
      )}
      <div className="mt-2 text-center">Thank you! Visit again</div>
      {business.plan?.watermark && <div className="mt-1 text-center" style={{ fontSize: 9 }}>Created with <BrandName /></div>}
    </div>
  );
}

const Dash = () => <div className="my-1 overflow-hidden whitespace-nowrap">{"-".repeat(60)}</div>;
const Row = ({ k, v }: { k: string; v: number }) => (
  <div className="flex justify-between"><span>{k}</span><span>{money(v).replace("₹", "")}</span></div>
);
