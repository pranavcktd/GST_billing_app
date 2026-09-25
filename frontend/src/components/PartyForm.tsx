"use client";

import { useState } from "react";
import { GstinVerify, type GstinInfo } from "@/components/GstinVerify";
import { Button, Card, ErrorBox, Field, Input, Select, Textarea } from "@/components/ui";
import { PARTY_GST_TYPES, STATES } from "@/lib/constants";
import { gstinError } from "@/lib/gst";
import type { Party, PartyGstType, PartyType } from "@/lib/types";

export type PartyDraft = Omit<Party, "id" | "balance" | "is_active">;

export const emptyParty = (type: PartyType = "CUSTOMER"): PartyDraft => ({
  type, name: "", gst_type: "UNREGISTERED", gstin: "", pan: null, phone: "", email: "", state_code: "",
  billing_address: "", city: "", pincode: "", shipping_address: "", opening_balance: 0, credit_limit: null,
});

const NEEDS_GSTIN: PartyGstType[] = ["REGISTERED", "COMPOSITION", "SEZ"];

export function PartyForm({
  initial,
  onSubmit,
  submitLabel = "Save party",
}: {
  initial: PartyDraft;
  onSubmit: (p: PartyDraft) => Promise<void>;
  submitLabel?: string;
}) {
  const [p, setP] = useState<PartyDraft>(initial);
  const [balType, setBalType] = useState<"receive" | "pay">(initial.opening_balance < 0 ? "pay" : "receive");
  const [balance, setBalance] = useState(Math.abs(initial.opening_balance || 0));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof PartyDraft>(k: K, v: PartyDraft[K]) => setP((prev) => ({ ...prev, [k]: v }));
  const text = (k: keyof PartyDraft) => ({
    value: (p[k] as string | null) ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => set(k, e.target.value as never),
  });

  const needsGstin = NEEDS_GSTIN.includes(p.gst_type);
  const gstErr = p.gstin ? gstinError(p.gstin) : null;

  function onGstin(v: string) {
    const g = v.toUpperCase();
    setP((prev) => ({
      ...prev,
      gstin: g,
      state_code: g.length >= 2 && STATES[g.slice(0, 2)] ? g.slice(0, 2) : prev.state_code,
      gst_type: g && (prev.gst_type === "UNREGISTERED" || prev.gst_type === "CONSUMER") ? "REGISTERED" : prev.gst_type,
    }));
  }

  const [filled, setFilled] = useState<string[]>([]);
  const [names, setNames] = useState<string[]>([]);

  /** Autofill basic details from the GST portal; the user completes the rest. */
  function applyGstin(d: GstinInfo) {
    const name = d.trade_name || d.legal_name || "";
    const next: PartyDraft = { ...p, gst_type: d.party_gst_type as PartyGstType, state_code: d.state_code, pan: d.pan };
    const done = ["GST type", "state", "PAN"];
    if (name && !p.name.trim()) { next.name = name; done.unshift("name"); }
    if (d.address) { next.billing_address = d.address; done.push("address"); }
    if (d.city) { next.city = d.city; done.push("city"); }
    if (d.pincode) { next.pincode = d.pincode; done.push("pincode"); }
    setP(next);
    setFilled(done);
    setNames([d.trade_name, d.legal_name].filter((x, i, a): x is string => !!x && a.indexOf(x) === i));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (gstErr) return setError(`GSTIN: ${gstErr}`);
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        ...p,
        opening_balance: balType === "pay" ? -balance : balance,
        credit_limit: p.credit_limit || null,
      });
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
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Party name" required>
            <Input required autoFocus {...text("name")} />
          </Field>
          <Field label="Party type">
            <Select value={p.type} onChange={(e) => set("type", e.target.value as PartyType)}>
              <option value="CUSTOMER">Customer</option>
              <option value="SUPPLIER">Supplier</option>
              <option value="BOTH">Customer & Supplier</option>
            </Select>
          </Field>
          <Field label="GSTIN" error={gstErr} hint="Fills state and GST type automatically">
            <Input maxLength={15} className="uppercase" value={p.gstin ?? ""} onChange={(e) => onGstin(e.target.value)} required={needsGstin} />
            <GstinVerify gstin={p.gstin} onResult={applyGstin} filled={filled} />
            {names.length > 0 && (
              <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-gray-500">
                Use as party name:
                {names.map((n) => <button key={n} type="button" onClick={() => set("name", n)} className="rounded border border-gray-200 px-1.5 py-0.5 hover:bg-gray-50">{n}</button>)}
              </div>
            )}
          </Field>
          <Field label="GST type">
            <Select value={p.gst_type} onChange={(e) => set("gst_type", e.target.value as PartyGstType)}>
              {Object.entries(PARTY_GST_TYPES).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </Select>
          </Field>
          <Field label="Phone"><Input type="tel" {...text("phone")} /></Field>
          <Field label="Email"><Input type="email" {...text("email")} /></Field>
          <Field label="State" hint="Decides CGST+SGST vs IGST">
            <Select value={p.state_code ?? ""} onChange={(e) => set("state_code", e.target.value)} disabled={!!p.gstin && !gstErr}>
              <option value="">Select state</option>
              {Object.entries(STATES).map(([c, n]) => (
                <option key={c} value={c}>{c} - {n}</option>
              ))}
            </Select>
          </Field>
          <Field label="City"><Input {...text("city")} /></Field>
          <Field label="Billing address" className="sm:col-span-2"><Textarea rows={2} {...text("billing_address")} /></Field>
          <Field label="Pincode"><Input inputMode="numeric" maxLength={6} {...text("pincode")} /></Field>
          <Field label="Shipping address (if different)"><Input {...text("shipping_address")} /></Field>
        </div>
      </Card>
      <Card className="p-5">
        <h2 className="mb-4 font-semibold text-gray-900">Opening balance & credit</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Opening balance (₹)">
            <Input type="number" min={0} step="0.01" value={balance || ""} onChange={(e) => setBalance(Number(e.target.value))} />
          </Field>
          <Field label="Balance type">
            <Select value={balType} onChange={(e) => setBalType(e.target.value as "receive" | "pay")}>
              <option value="receive">To receive (party owes you)</option>
              <option value="pay">To pay (you owe party)</option>
            </Select>
          </Field>
          <Field label="Credit limit (₹)">
            <Input type="number" min={0} step="0.01" value={p.credit_limit ?? ""} onChange={(e) => set("credit_limit", e.target.value ? Number(e.target.value) : null)} />
          </Field>
        </div>
      </Card>
      <div className="flex justify-end">
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : submitLabel}</Button>
      </div>
    </form>
  );
}
