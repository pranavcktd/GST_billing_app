"use client";

import { useState } from "react";
import { ImageUpload } from "@/components/ImageUpload";
import { DEFAULT_PRINT } from "@/components/InvoiceDocument";
import { Button, Card, ErrorBox, Field, Input, Select, Textarea } from "@/components/ui";
import { STATES } from "@/lib/constants";
import { gstinError } from "@/lib/gst";
import type { Business, BusinessGstType } from "@/lib/types";

export type BusinessDraft = Omit<Business, "id" | "plan" | "einvoice_password_set"> & { einvoice_password?: string | null };

export const emptyBusiness: BusinessDraft = {
  name: "", legal_name: null, gst_type: "REGULAR", gstin: "", pan: null, state_code: "", address: null,
  city: null, pincode: null, phone: null, email: null, logo_url: null, signature_url: null, bank_name: null,
  bank_account_no: null, bank_ifsc: null, bank_branch: null, upi_id: null, invoice_prefix: "INV",
  credit_note_prefix: "CN", debit_note_prefix: "DN", estimate_prefix: "EST", purchase_prefix: "PUR",
  receipt_prefix: "RCT", payment_prefix: "PAY", challan_prefix: "DC", sale_order_prefix: "SO",
  purchase_order_prefix: "PO", expense_prefix: "EXP", invoice_terms: null, auto_backup: true, backup_email: null,
  transfer_prefix: "ST", print_settings: null, einvoice_username: null,
};

const GST_TYPES: { value: BusinessGstType; label: string; hint: string }[] = [
  { value: "REGULAR", label: "GST Registered — Regular", hint: "Issue Tax Invoices, collect CGST/SGST/IGST" },
  { value: "COMPOSITION", label: "GST Registered — Composition", hint: "Issue Bills of Supply, no GST on bills" },
  { value: "UNREGISTERED", label: "Not registered under GST", hint: "Simple bills without GST" },
];

export function BusinessForm({
  initial,
  onSubmit,
  submitLabel,
  showUploads,
}: {
  initial: BusinessDraft;
  onSubmit: (b: BusinessDraft) => Promise<void>;
  submitLabel: string;
  showUploads?: boolean;
}) {
  const [b, setB] = useState<BusinessDraft>(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof BusinessDraft>(k: K, v: BusinessDraft[K]) => setB((prev) => ({ ...prev, [k]: v }));
  const text = (k: keyof BusinessDraft) => ({
    value: (b[k] as string | null) ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => set(k, e.target.value as never),
  });

  const registered = b.gst_type !== "UNREGISTERED";
  const gstErr = registered && b.gstin ? gstinError(b.gstin) : null;

  function onGstin(v: string) {
    const g = v.toUpperCase();
    setB((prev) => ({ ...prev, gstin: g, state_code: g.length >= 2 && STATES[g.slice(0, 2)] ? g.slice(0, 2) : prev.state_code }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (gstErr) return setError(`GSTIN: ${gstErr}`);
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ ...b, gstin: registered ? b.gstin : null, print_settings: b.print_settings ?? DEFAULT_PRINT });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <ErrorBox message={error} />

      <Card className="p-5">
        <h2 className="mb-4 font-semibold text-gray-900">Business details</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Business name" required>
            <Input required {...text("name")} />
          </Field>
          <Field label="Legal name (as per GST)">
            <Input {...text("legal_name")} />
          </Field>
          <Field label="GST registration" className="sm:col-span-2">
            <div className="grid gap-2 sm:grid-cols-3">
              {GST_TYPES.map((t) => (
                <label
                  key={t.value}
                  className={`cursor-pointer rounded-lg border p-3 text-sm ${b.gst_type === t.value ? "border-brand-500 bg-brand-50" : "border-gray-200"}`}
                >
                  <input type="radio" className="sr-only" checked={b.gst_type === t.value} onChange={() => set("gst_type", t.value)} />
                  <span className="block font-medium text-gray-900">{t.label}</span>
                  <span className="mt-0.5 block text-xs text-gray-500">{t.hint}</span>
                </label>
              ))}
            </div>
          </Field>
          {registered && (
            <Field label="GSTIN" required error={gstErr}>
              <Input required maxLength={15} value={b.gstin ?? ""} onChange={(e) => onGstin(e.target.value)} className="uppercase" />
            </Field>
          )}
          <Field label="State" required hint={registered ? "Filled from GSTIN" : undefined}>
            <Select required value={b.state_code} onChange={(e) => set("state_code", e.target.value)}>
              <option value="">Select state</option>
              {Object.entries(STATES).map(([c, n]) => (
                <option key={c} value={c}>
                  {c} - {n}
                </option>
              ))}
            </Select>
          </Field>
          {!registered && (
            <Field label="PAN">
              <Input maxLength={10} className="uppercase" {...text("pan")} />
            </Field>
          )}
          <Field label="Phone">
            <Input type="tel" {...text("phone")} />
          </Field>
          <Field label="Email">
            <Input type="email" {...text("email")} />
          </Field>
          <Field label="Address" className="sm:col-span-2">
            <Textarea rows={2} {...text("address")} />
          </Field>
          <Field label="City">
            <Input {...text("city")} />
          </Field>
          <Field label="Pincode">
            <Input inputMode="numeric" maxLength={6} {...text("pincode")} />
          </Field>
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="mb-4 font-semibold text-gray-900">Bank & UPI (printed on invoices)</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Bank name"><Input {...text("bank_name")} /></Field>
          <Field label="Account number"><Input {...text("bank_account_no")} /></Field>
          <Field label="IFSC"><Input maxLength={11} className="uppercase" {...text("bank_ifsc")} /></Field>
          <Field label="Branch"><Input {...text("bank_branch")} /></Field>
          <Field label="UPI ID" hint="e.g. shopname@okicici"><Input {...text("upi_id")} /></Field>
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="mb-1 font-semibold text-gray-900">Document numbering</h2>
        <p className="mb-4 text-xs text-gray-500">
          Numbers are generated as PREFIX/YY-YY/0001 and restart every financial year (max 16 characters as per GST rules).
        </p>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Field label="Sale invoice"><Input maxLength={5} {...text("invoice_prefix")} /></Field>
          <Field label="Credit note"><Input maxLength={5} {...text("credit_note_prefix")} /></Field>
          <Field label="Debit note"><Input maxLength={5} {...text("debit_note_prefix")} /></Field>
          <Field label="Estimate"><Input maxLength={5} {...text("estimate_prefix")} /></Field>
          <Field label="Purchase"><Input maxLength={5} {...text("purchase_prefix")} /></Field>
          <Field label="Receipt (in)"><Input maxLength={5} {...text("receipt_prefix")} /></Field>
          <Field label="Payment (out)"><Input maxLength={5} {...text("payment_prefix")} /></Field>
          <Field label="Delivery challan"><Input maxLength={5} {...text("challan_prefix")} /></Field>
          <Field label="Sale order"><Input maxLength={5} {...text("sale_order_prefix")} /></Field>
          <Field label="Purchase order"><Input maxLength={5} {...text("purchase_order_prefix")} /></Field>
          <Field label="Expense"><Input maxLength={5} {...text("expense_prefix")} /></Field>
        </div>
        <Field label="Default terms & conditions" className="mt-4">
          <Textarea rows={3} {...text("invoice_terms")} placeholder="1. Goods once sold will not be taken back.&#10;2. Subject to local jurisdiction." />
        </Field>
      </Card>

      {showUploads && (
        <Card className="p-5">
          <h2 className="mb-4 font-semibold text-gray-900">Branding</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <ImageUpload kind="logo" label="Logo" value={b.logo_url} onChange={(u) => set("logo_url", u)} />
            <ImageUpload kind="signature" label="Authorised signature" value={b.signature_url} onChange={(u) => set("signature_url", u)} />
          </div>
        </Card>
      )}

      <div className="flex justify-end">
        <Button type="submit" disabled={busy}>
          {busy ? "Saving…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}
