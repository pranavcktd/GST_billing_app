"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { DEFAULT_PRINT, InvoiceDocument } from "@/components/InvoiceDocument";
import { Button, Card, ErrorBox, Field, Input, Select } from "@/components/ui";
import type { Business, PrintSettings, VoucherDetail } from "@/lib/types";

const SAMPLE: VoucherDetail = {
  id: "sample", type: "SALE", number: "INV/26-27/0042", date: new Date().toISOString().slice(0, 10), due_date: null,
  party_id: "p", party_name: "Sample Customer Pvt Ltd", party_gstin: "29AAACK5678D1Z9", party_state_code: "29",
  party_address: "Brigade Road, Bengaluru 560001", party_phone: "9876543210", place_of_supply: "29", inter_state: true,
  tax_applicable: true, reverse_charge: false, supplier_invoice_no: null, supplier_invoice_date: null,
  original_voucher_id: null, reason: null, sub_total: 2000, discount: 100, taxable: 1900, cgst: 0, sgst: 0, igst: 342,
  cess: 0, tcs_rate: 0, tcs_amount: 0, round_off: 0, grand_total: 2242, notes: null, terms: "Goods once sold will not be taken back.",
  cancelled: false, converted_to_id: null, source_voucher_id: null, expense_category_id: null, godown_id: null,
  transport: { vehicle_no: "MH12AB1234", transporter_name: "VRL Logistics", distance_km: 840 },
  extra_fields: null, irn: null, ack_no: null, ack_date: null, signed_qr: null, einvoice_status: null,
  einvoice_sandbox: false, ewb_no: null, ewb_date: null, ewb_valid_till: null, paid: 0, balance: 2242,
  status: "UNPAID", title: "Tax Invoice", amount_in_words: "Rupees Two Thousand Two Hundred Forty Two Only",
  original_number: null,
  lines: [
    { item_id: null, name: "Steel Bottle 1L", description: "Leak-proof", hsn_sac: "7323", unit: "PCS", qty: 4, rate: 500,
      tax_inclusive: false, discount_pct: 5, gst_rate: 18, cess_rate: 0, amount: 2000, discount: 100, taxable: 1900,
      cgst: 0, sgst: 0, igst: 342, cess: 0, total: 2242 },
  ],
  tax_breakup: [{ rate: 18, taxable: 1900, cgst: 0, sgst: 0, igst: 342, cess: 0 }],
};

const TOGGLES: [keyof PrintSettings, string][] = [
  ["show_hsn", "HSN / SAC column"], ["show_discount", "Discount column"], ["show_tax_summary", "Rate-wise tax summary"],
  ["show_item_description", "Item descriptions"], ["show_transport", "Transport details"], ["show_bank", "Bank details"],
  ["show_upi_qr", "UPI QR code (scan to pay)"], ["show_terms", "Terms & conditions"], ["show_signature", "Signature block"],
];

export function PrintSettingsForm({ business, onSave }: { business: Business; onSave: (ps: PrintSettings) => Promise<void> }) {
  const [ps, setPs] = useState<PrintSettings>({ ...DEFAULT_PRINT, ...(business.print_settings ?? {}) });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const themesAllowed = business.plan?.custom_themes;
  const set = <K extends keyof PrintSettings>(k: K, v: PrintSettings[K]) => setPs((p) => ({ ...p, [k]: v }));
  const sample = { ...SAMPLE, extra_fields: Object.fromEntries(ps.custom_fields.map((f) => [f.key, "Sample"])) };

  async function save() {
    setBusy(true); setErr(null);
    try { await onSave(ps); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-5">
      <div className="space-y-5 xl:col-span-2">
        <ErrorBox message={err} />
        <Card className="space-y-4 p-5">
          <h2 className="font-semibold text-gray-900">Look</h2>
          {!themesAllowed && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">Custom themes and colours come with the Professional plan. <Link href="/billing?plan=PROFESSIONAL" className="font-medium underline">Upgrade</Link></p>
          )}
          <div className="grid grid-cols-3 gap-2">
            {(["classic", "modern", "minimal"] as const).map((t) => (
              <button key={t} disabled={!themesAllowed && t !== "classic"} onClick={() => set("theme", t)}
                className={`rounded-lg border px-3 py-2 text-sm capitalize disabled:opacity-40 ${ps.theme === t ? "border-brand-500 bg-brand-50 font-medium" : "border-gray-200"}`}>{t}</button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Accent colour">
              <input type="color" disabled={!themesAllowed} value={ps.accent} onChange={(e) => set("accent", e.target.value)} className="h-9 w-full rounded border border-gray-300" />
            </Field>
            <Field label="Default paper">
              <Select value={ps.paper} onChange={(e) => set("paper", e.target.value as PrintSettings["paper"])}>
                <option value="A4">A4</option><option value="A5">A5</option><option value="THERMAL_80">Thermal 80 mm</option><option value="THERMAL_58">Thermal 58 mm</option>
              </Select>
            </Field>
          </div>
          <Field label="Copies to print for sale invoices">
            <div className="flex gap-4 text-sm">
              {(["ORIGINAL", "DUPLICATE", "TRIPLICATE"] as const).map((c) => (
                <label key={c} className="flex items-center gap-1.5">
                  <input type="checkbox" checked={ps.copy_labels.includes(c)} onChange={(e) => set("copy_labels", e.target.checked ? [...ps.copy_labels, c] : ps.copy_labels.filter((x) => x !== c))} />
                  {c.charAt(0) + c.slice(1).toLowerCase()}
                </label>
              ))}
            </div>
          </Field>
          <Field label="Invoice title (optional)" hint="e.g. “Tax Invoice cum Delivery Challan”"><Input maxLength={40} value={ps.title_override ?? ""} onChange={(e) => set("title_override", e.target.value || null)} /></Field>
          <Field label="Footer note"><Input maxLength={300} value={ps.footer_note ?? ""} onChange={(e) => set("footer_note", e.target.value || null)} placeholder="Thank you for your business!" /></Field>
        </Card>
        <Card className="space-y-2 p-5">
          <h2 className="mb-1 font-semibold text-gray-900">Show on invoice</h2>
          {TOGGLES.map(([k, label]) => (
            <label key={k} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={ps[k] as boolean} onChange={(e) => set(k, e.target.checked as never)} /> {label}
            </label>
          ))}
        </Card>
        <Card className="space-y-3 p-5">
          <h2 className="font-semibold text-gray-900">Custom fields</h2>
          <p className="text-xs text-gray-500">Extra boxes on every bill — PO number, vehicle, site, salesman… (up to 8).</p>
          {ps.custom_fields.map((f, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input value={f.label} placeholder="Label" onChange={(e) => {
                const label = e.target.value;
                const key = f.key || label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 30) || `field_${i + 1}`;
                set("custom_fields", ps.custom_fields.map((x, j) => (j === i ? { ...x, label, key } : x)));
              }} />
              <label className="flex items-center gap-1 text-xs whitespace-nowrap"><input type="checkbox" checked={f.print} onChange={(e) => set("custom_fields", ps.custom_fields.map((x, j) => (j === i ? { ...x, print: e.target.checked } : x)))} /> print</label>
              <button className="text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => set("custom_fields", ps.custom_fields.filter((_, j) => j !== i))}><Trash2 size={15} /></button>
            </div>
          ))}
          {ps.custom_fields.length < 8 && (
            <Button variant="secondary" onClick={() => set("custom_fields", [...ps.custom_fields, { key: "", label: "", print: true }])}><Plus size={15} /> Add field</Button>
          )}
        </Card>
        <div className="flex justify-end"><Button disabled={busy} onClick={save}>{busy ? "Saving…" : "Save print settings"}</Button></div>
      </div>
      <div className="xl:col-span-3">
        <div className="sticky top-20 overflow-x-auto rounded-xl border border-gray-200 bg-gray-100 p-3">
          <div className="mb-2 text-xs text-gray-500">Preview (sample data)</div>
          <div className="min-w-[700px] origin-top-left">
            <InvoiceDocument v={sample} business={{ ...business, print_settings: { ...ps, custom_fields: ps.custom_fields.filter((f) => f.key && f.label) } }} />
          </div>
        </div>
      </div>
    </div>
  );
}
