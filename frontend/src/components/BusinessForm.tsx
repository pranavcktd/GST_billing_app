"use client";

import { ArrowLeft, ArrowRight, BadgeCheck, Building2, FileX2, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { ImageUpload } from "@/components/ImageUpload";
import { DEFAULT_PRINT } from "@/components/InvoiceDocument";
import { GstinVerify, type GstinInfo } from "@/components/GstinVerify";
import { Button, Card, ErrorBox, Field, Input, Select, Textarea } from "@/components/ui";
import { ENTITY_TYPES, guessEntityType, STATES } from "@/lib/constants";
import { gstinError } from "@/lib/gst";
import type { Business, BusinessGstType, GstPortalDetails } from "@/lib/types";

export type BusinessDraft = Omit<Business, "id" | "plan" | "einvoice_password_set" | "gst_portal"> & { einvoice_password?: string | null };

/** "01/10/2020", "01-10-2020" or "2020-10-01" -> "2020-10-01" */
function isoDate(v: string | null | undefined): string | null {
  if (!v) return null;
  const t = v.trim().slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(t)) return t;
  const m = /^(\d{2})[/-](\d{2})[/-](\d{4})$/.exec(t);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : null;
}

export const emptyBusiness: BusinessDraft = {
  name: "", legal_name: null, gst_type: "REGULAR", gstin: "", pan: null, state_code: "", address: null,
  city: null, pincode: null, phone: null, email: null, logo_url: null, signature_url: null, bank_name: null,
  bank_account_no: null, bank_ifsc: null, bank_branch: null, upi_id: null, invoice_prefix: "INV",
  credit_note_prefix: "CN", debit_note_prefix: "DN", estimate_prefix: "EST", purchase_prefix: "PUR",
  receipt_prefix: "RCT", payment_prefix: "PAY", challan_prefix: "DC", sale_order_prefix: "SO",
  purchase_order_prefix: "PO", expense_prefix: "EXP", invoice_terms: null, auto_backup: true, backup_email: null,
  transfer_prefix: "ST", print_settings: null, einvoice_username: null,
  lut_number: null, lut_valid_till: null, composition_type: "TRADER", entity_type: "PROPRIETORSHIP", gst_registration_date: null,
};

const GST_TYPES: { value: BusinessGstType; label: string; hint: string }[] = [
  { value: "REGULAR", label: "Regular", hint: "Tax invoices with CGST / SGST / IGST" },
  { value: "COMPOSITION", label: "Composition", hint: "Bills of supply, tax on turnover" },
  { value: "UNREGISTERED", label: "Not registered", hint: "Simple bills without GST" },
];

type Step = "ASK" | "GSTIN" | "FORM";
type Key = keyof BusinessDraft;
const PORTAL = "From the GST portal — check and edit if needed";

/**
 * Business details. A new business (onboarding, `wizard`) is set up GSTIN-first:
 *   1. GST registered?  2. GSTIN → fetch the public registration details  3. the rest of the form,
 * laid out in the order of the GST registration certificate, with everything fetched already filled in.
 * Settings shows the same layout without the first two steps.
 */
export function BusinessForm({
  initial,
  onSubmit,
  submitLabel,
  showUploads,
  wizard = false,
  portal,
}: {
  initial: BusinessDraft;
  /** registration details last fetched from the GST portal (Settings) */
  portal?: GstPortalDetails | null;
  onSubmit: (b: BusinessDraft) => Promise<void>;
  submitLabel: string;
  showUploads?: boolean;
  wizard?: boolean;
}) {
  const [b, setB] = useState<BusinessDraft>(initial);
  const [step, setStep] = useState<Step>(wizard ? "ASK" : "FORM");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fromPortal, setFromPortal] = useState<Set<Key>>(new Set());
  const [fetched, setFetched] = useState<GstinInfo | null>(null);
  const set = <K extends Key>(k: K, v: BusinessDraft[K]) => setB((prev) => ({ ...prev, [k]: v }));
  const text = (k: Key) => ({
    value: (b[k] as string | null) ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => set(k, e.target.value as never),
  });
  const hint = (k: Key, other?: string) => (fromPortal.has(k) ? PORTAL : other);

  const registered = b.gst_type !== "UNREGISTERED";
  const gstErr = registered && b.gstin ? gstinError(b.gstin) : null;

  function onGstin(v: string) {
    const g = v.toUpperCase().replace(/\s/g, "");
    setB((prev) => ({ ...prev, gstin: g, state_code: g.length >= 2 && STATES[g.slice(0, 2)] ? g.slice(0, 2) : prev.state_code,
      // a first guess of the constitution from the PAN inside the GSTIN (replaced by the portal's answer)
      entity_type: g.length === 15 && (prev.entity_type ?? "PROPRIETORSHIP") === "PROPRIETORSHIP" ? ((guessEntityType(null, g) as BusinessDraft["entity_type"]) ?? prev.entity_type) : prev.entity_type }));
  }

  function applyGstin(d: GstinInfo) {
    const got = new Set<Key>(["legal_name", "state_code", "gst_type"]);
    const next: BusinessDraft = { ...b, legal_name: d.legal_name ?? b.legal_name, state_code: d.state_code, gst_type: d.business_gst_type, pan: d.pan || b.pan };
    const ent = guessEntityType(d.constitution, b.gstin);
    if (ent) { next.entity_type = ent as BusinessDraft["entity_type"]; got.add("entity_type"); }
    if (d.trade_name || d.legal_name) {
      if (!b.name.trim() || wizard) { next.name = (d.trade_name || d.legal_name)!; got.add("name"); }
    }
    if (d.address) { next.address = d.address; got.add("address"); }
    if (d.city) { next.city = d.city; got.add("city"); }
    if (d.pincode) { next.pincode = d.pincode; got.add("pincode"); }
    const reg = isoDate(d.registration_date);
    if (reg) { next.gst_registration_date = reg; got.add("gst_registration_date"); }
    setB(next);
    setFromPortal(got);
    setFetched(d);
    if (wizard) setStep("FORM");
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

  // ------------------------------------------------------------------ wizard step 1: registered?
  if (step === "ASK") {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Is your business registered under GST?</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <button type="button" onClick={() => { set("gst_type", "REGULAR"); setStep("GSTIN"); }}
            className="rounded-xl border border-gray-200 bg-white p-5 text-left hover:border-brand-500 hover:bg-brand-50">
            <BadgeCheck className="text-brand-600" />
            <div className="mt-2 font-semibold text-gray-900">Yes, I have a GSTIN</div>
            <div className="mt-1 text-sm text-gray-600">Enter your GST number — we fill your registered name, address and type of business for you.</div>
          </button>
          <button type="button" onClick={() => { setB((p) => ({ ...p, gst_type: "UNREGISTERED", gstin: "" })); setStep("FORM"); }}
            className="rounded-xl border border-gray-200 bg-white p-5 text-left hover:border-brand-500 hover:bg-brand-50">
            <FileX2 className="text-gray-500" />
            <div className="mt-2 font-semibold text-gray-900">No, not registered</div>
            <div className="mt-1 text-sm text-gray-600">Bill without GST. You can add your GSTIN later in Settings.</div>
          </button>
        </div>
      </div>
    );
  }

  // ------------------------------------------------------------------ wizard step 2: GSTIN
  if (step === "GSTIN") {
    const valid = (b.gstin ?? "").length === 15 && !gstErr;
    return (
      <Card className="max-w-xl space-y-4 p-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Your GSTIN</h2>
          <p className="text-sm text-gray-600">The 15-character number on your GST registration certificate.</p>
        </div>
        <Field label="GSTIN" required error={gstErr} info={false}>
          <Input autoFocus maxLength={15} value={b.gstin ?? ""} onChange={(e) => onGstin(e.target.value)} className="font-mono text-lg tracking-wider uppercase" placeholder="27AABCS1429B1Z5" />
          <GstinVerify gstin={b.gstin} onResult={applyGstin} filled={[]} />
        </Field>
        {valid && <p className="text-xs text-gray-500">State: {STATES[(b.gstin ?? "").slice(0, 2)] ?? "—"} · PAN: {(b.gstin ?? "").slice(2, 12)}</p>}
        <div className="flex flex-wrap justify-between gap-2">
          <Button type="button" variant="ghost" onClick={() => setStep("ASK")}><ArrowLeft size={15} /> Back</Button>
          <Button type="button" variant="secondary" disabled={!valid} onClick={() => { set("pan", (b.gstin ?? "").slice(2, 12)); setStep("FORM"); }}
            title="Fill the details yourself">
            Continue without fetching <ArrowRight size={15} />
          </Button>
        </div>
      </Card>
    );
  }

  // ------------------------------------------------------------------ the form (GST certificate order)
  return (
    <form onSubmit={submit} className="space-y-5">
      <ErrorBox message={error} />

      {fetched && (
        <div className={`flex flex-wrap items-start gap-3 rounded-lg border px-4 py-3 text-sm ${fetched.active ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-red-200 bg-red-50 text-red-900"}`}>
          {fetched.active ? <BadgeCheck size={18} className="mt-0.5" /> : <ShieldAlert size={18} className="mt-0.5" />}
          <div className="flex-1">
            <b>{fetched.status || "Status unknown"}</b> · {fetched.taxpayer_type ?? "—"}{fetched.constitution ? ` · ${fetched.constitution}` : ""}
            {fetched.registration_date ? ` · registered ${fetched.registration_date}` : ""}
            <div className="text-xs opacity-80">
              {fetched.active ? "Details below were filled from the GST portal. Please check them, then add your contact and bank details." :
                "This GSTIN is not active on the GST portal. You can continue, but tax invoices need an active registration."}
            </div>
          </div>
        </div>
      )}

      {!wizard && portal && registered && (
        <Card className="p-5">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="flex items-center gap-2 font-semibold text-gray-900"><BadgeCheck size={17} className="text-sky-600" /> GST registration details — from the GST portal</h2>
            <span className="text-xs text-gray-500">Fetched {new Date(portal.fetched_at).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric" })} · use “Verify again” below to refresh</span>
          </div>
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
            {([
              ["Status", portal.status], ["Taxpayer type", portal.taxpayer_type], ["Constitution", portal.constitution],
              ["Legal name", portal.legal_name], ["Trade name", portal.trade_name], ["Registered on", portal.registration_date],
              ["Cancelled on", portal.cancellation_date], ["State", portal.state], ["Jurisdiction", portal.jurisdiction],
              ["PAN", portal.pan], ["Nature of business", portal.nature_of_business?.join(", ")], ["Principal place", portal.address],
            ] as [string, string | null | undefined][]).filter(([, v]) => v).map(([k, v]) => (
              <div key={k} className={k === "Principal place" || k === "Nature of business" ? "sm:col-span-3" : ""}>
                <dt className="text-xs text-gray-500">{k}</dt>
                <dd className={k === "Status" ? (portal.active ? "font-medium text-emerald-700" : "font-medium text-red-700") : "text-gray-900"}>{v}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      <Card className="p-5">
        <h2 className="mb-4 flex items-center gap-2 font-semibold text-gray-900"><Building2 size={17} /> {registered ? "As per GST registration" : "Business details"}</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {wizard ? (
            <div className="sm:col-span-2 flex flex-wrap items-center gap-3 rounded-lg bg-gray-50 px-3 py-2 text-sm">
              {registered ? <>GSTIN <b className="font-mono">{b.gstin}</b> · {GST_TYPES.find((t) => t.value === b.gst_type)?.label}</> : <>Not registered under GST</>}
              <button type="button" className="text-brand-600 hover:underline" onClick={() => { setFetched(null); setFromPortal(new Set()); setStep(registered ? "GSTIN" : "ASK"); }}>Change</button>
            </div>
          ) : (
            <>
              <Field label="GST registration" className="sm:col-span-2">
                <div className="grid gap-2 sm:grid-cols-3">
                  {GST_TYPES.map((t) => (
                    <label key={t.value} className={`cursor-pointer rounded-lg border p-3 text-sm ${b.gst_type === t.value ? "border-brand-500 bg-brand-50" : "border-gray-200"}`}>
                      <input type="radio" className="sr-only" checked={b.gst_type === t.value} onChange={() => set("gst_type", t.value)} />
                      <span className="block font-medium text-gray-900">{t.label}</span>
                      <span className="mt-0.5 block text-xs text-gray-500">{t.hint}</span>
                    </label>
                  ))}
                </div>
              </Field>
              {registered && (
                <Field label="GSTIN" required error={gstErr} className="sm:col-span-2">
                  <Input required maxLength={15} value={b.gstin ?? ""} onChange={(e) => onGstin(e.target.value)} className="font-mono uppercase sm:max-w-xs" />
                  <GstinVerify gstin={b.gstin} onResult={applyGstin} filled={[...fromPortal].map(String)} />
                </Field>
              )}
            </>
          )}
          {wizard && registered && (
            <Field label="Registration type" hint={hint("gst_type")}>
              <Select value={b.gst_type} onChange={(e) => set("gst_type", e.target.value as BusinessGstType)}>
                <option value="REGULAR">Regular</option><option value="COMPOSITION">Composition</option>
              </Select>
            </Field>
          )}
          {registered && <Field label="Legal name (as per GST)" hint={hint("legal_name")}><Input {...text("legal_name")} /></Field>}
          {registered && (
            <Field label="GST registration date" hint={hint("gst_registration_date", "Your compliance calendar starts from this date")}>
              <Input type="date" value={b.gst_registration_date ?? ""} onChange={(e) => set("gst_registration_date", e.target.value || null)} />
            </Field>
          )}
          <Field label={registered ? "Trade name (printed on bills)" : "Business name"} required hint={hint("name", registered ? "Usually your shop / brand name" : undefined)}>
            <Input required {...text("name")} />
          </Field>
          <Field label="Type of business (constitution)" hint={hint("entity_type", "Decides which MCA / income-tax filings apply to you")}>
            <Select value={b.entity_type ?? "PROPRIETORSHIP"} onChange={(e) => set("entity_type", e.target.value as BusinessDraft["entity_type"])}>
              {Object.entries(ENTITY_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </Field>
          <Field label="State" required hint={registered ? "From the GSTIN" : undefined}>
            <Select required value={b.state_code} disabled={registered && (b.gstin ?? "").length >= 2 && !!STATES[(b.gstin ?? "").slice(0, 2)]} onChange={(e) => set("state_code", e.target.value)}>
              <option value="">Select state</option>
              {Object.entries(STATES).map(([c, n]) => <option key={c} value={c}>{c} - {n}</option>)}
            </Select>
          </Field>
          {registered
            ? <Field label="PAN" hint="Part of the GSTIN"><Input value={(b.gstin ?? "").slice(2, 12)} disabled className="uppercase" /></Field>
            : <Field label="PAN"><Input maxLength={10} className="uppercase" {...text("pan")} /></Field>}
          <Field label={registered ? "Principal place of business" : "Address"} className="sm:col-span-2" hint={hint("address")}>
            <Textarea rows={2} {...text("address")} />
          </Field>
          <Field label="City" hint={hint("city")}><Input {...text("city")} /></Field>
          <Field label="Pincode" hint={hint("pincode")}><Input inputMode="numeric" maxLength={6} {...text("pincode")} /></Field>
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="mb-1 font-semibold text-gray-900">Contact</h2>
        <p className="mb-4 text-xs text-gray-500">Printed on your bills — not available from the GST portal.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Phone"><Input type="tel" {...text("phone")} /></Field>
          <Field label="Email"><Input type="email" {...text("email")} /></Field>
        </div>
      </Card>

      {b.gst_type === "COMPOSITION" && (
        <Card className="p-5">
          <h2 className="mb-4 font-semibold text-gray-900">Composition scheme</h2>
          <Field label="Category (decides the CMP-08 tax rate)" className="max-w-md">
            <Select value={b.composition_type} onChange={(e) => set("composition_type", e.target.value as BusinessDraft["composition_type"])}>
              <option value="TRADER">Trader — 1%</option>
              <option value="MANUFACTURER">Manufacturer — 1%</option>
              <option value="RESTAURANT">Restaurant (no alcohol) — 5%</option>
              <option value="SERVICE">Service provider — 6%</option>
            </Select>
          </Field>
        </Card>
      )}

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

      {b.gst_type === "REGULAR" && (
        <OptionalCard open={!wizard} title="Exports & SEZ — Letter of Undertaking (LUT)" sub="Only if you export or supply to SEZ units">
          <p className="mb-4 text-xs text-gray-500">With a valid LUT, exports and SEZ supplies are billed without IGST (zero rated). Without it, IGST is charged and can be claimed as a refund.</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="LUT ARN / reference number"><Input maxLength={30} className="uppercase" {...text("lut_number")} /></Field>
            <Field label="Valid till" hint="Usually 31 March of the financial year">
              <Input type="date" value={b.lut_valid_till ?? ""} onChange={(e) => set("lut_valid_till", e.target.value || null)} />
            </Field>
          </div>
        </OptionalCard>
      )}

      <OptionalCard open={!wizard} title="Document numbering & terms" sub="Ready-made defaults — change only if you need to">
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
      </OptionalCard>

      {showUploads && (
        <Card className="p-5">
          <h2 className="mb-4 font-semibold text-gray-900">Branding</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <ImageUpload kind="logo" label="Logo" value={b.logo_url} onChange={(u) => set("logo_url", u)} />
            <ImageUpload kind="signature" label="Authorised signature" value={b.signature_url} onChange={(u) => set("signature_url", u)} />
          </div>
        </Card>
      )}

      <div className="flex justify-between">
        {wizard ? <Button type="button" variant="ghost" onClick={() => setStep(registered ? "GSTIN" : "ASK")}><ArrowLeft size={15} /> Back</Button> : <span />}
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : submitLabel}</Button>
      </div>
    </form>
  );
}

/** A card that starts folded during onboarding (optional details) and open in Settings. */
function OptionalCard({ open, title, sub, children }: { open: boolean; title: string; sub: string; children: React.ReactNode }) {
  return (
    <details open={open} className="group rounded-xl border border-gray-200 bg-white shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-5">
        <span><span className="font-semibold text-gray-900">{title}</span><span className="block text-xs text-gray-500">{sub}</span></span>
        <span className="text-xs text-brand-600 group-open:hidden">Show</span>
      </summary>
      <div className="px-5 pb-5">{children}</div>
    </details>
  );
}
