"use client";

import { RotateCcw, Save } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading, Select, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

type Plan = Record<string, unknown>;
interface PlansData {
  order: string[]; keys: string[]; addon_code: string; plans: Record<string, Plan>; addon: Plan;
  defaults: Record<string, Plan>; overrides: Record<string, Plan>;
}

const LIMITS: [string, string][] = [
  ["invoices_per_month", "Invoices / month"], ["invoices_per_year", "Invoices / year"], ["businesses", "Businesses"],
  ["users", "Users"], ["godowns", "Godowns"], ["api_quota", "API calls / month"], ["backup_mb", "Backup storage (MB)"],
];
const FLAGS: [string, string][] = [
  ["gst_json", "GST JSON exports"], ["gstr2b", "GSTR-2B matching"], ["audit_view", "Audit trail"],
  ["custom_themes", "Custom invoice themes"], ["barcode", "Barcode labels"], ["custom_roles", "Custom roles"],
  ["tally", "Tally export"], ["watermark", "Watermark on bills"],
];

function PlanEditor({ code, plan, isDefault, onSave }: { code: string; plan: Plan; isDefault: Plan; onSave: (values: Plan) => Promise<void> }) {
  const [p, setP] = useState<Plan>(plan);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: unknown) => setP({ ...p, [k]: v });
  const num = (k: string) => (
    <Input inputMode="numeric" value={p[k] === null || p[k] === undefined ? "" : String(p[k])} placeholder="Unlimited"
      onChange={(e) => set(k, e.target.value === "" ? null : Number(e.target.value))} />
  );
  const run = async (values: Plan) => { setBusy(true); try { await onSave(values); } finally { setBusy(false); } };
  const editable = Object.fromEntries(Object.entries(p).filter(([k]) => k !== "code"));

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">{code}</h3>
        <div className="flex gap-2">
          <Button variant="ghost" disabled={busy} onClick={() => { setP(isDefault); run(isDefault); }} title="Back to built-in defaults"><RotateCcw size={14} /> Defaults</Button>
          <Button disabled={busy} onClick={() => run(editable)}><Save size={14} /> Save</Button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Name"><Input value={String(p.name ?? "")} onChange={(e) => set("name", e.target.value)} /></Field>
        <Field label="Audience" className="lg:col-span-3"><Input value={String(p.audience ?? "")} onChange={(e) => set("audience", e.target.value)} /></Field>
        <Field label="Monthly price (₹, excl. GST)">{num("monthly")}</Field>
        <Field label="Yearly price (₹, excl. GST)">{num("yearly")}</Field>
        {LIMITS.map(([k, l]) => <Field key={k} label={l}>{num(k)}</Field>)}
        <Field label="e-Invoice">
          <Select value={String(p.einvoice ?? "")} onChange={(e) => set("einvoice", e.target.value || null)}>
            <option value="">Not included</option><option value="JSON">JSON download</option><option value="API">Direct API</option>
          </Select>
        </Field>
      </div>
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm">
        {FLAGS.map(([k, l]) => (
          <label key={k} className="flex items-center gap-1.5"><input type="checkbox" checked={!!p[k]} onChange={(e) => set(k, e.target.checked)} /> {l}</label>
        ))}
      </div>
      <Field label="Highlights on the pricing page (one per line)" className="mt-4">
        <Textarea rows={4} value={((p.highlights as string[]) ?? []).join("\n")} onChange={(e) => set("highlights", e.target.value.split("\n"))} />
      </Field>
    </Card>
  );
}

export function AdminPlanConfig() {
  const { data, error, setData } = useFetch<PlansData>("/admin/plans-config");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [addon, setAddon] = useState<Plan | null>(null);
  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;

  const save = (code: string) => async (values: Plan) => {
    setErr(null); setMsg(null);
    try {
      setData(await api<PlansData>(`/admin/plans-config/${code}`, { method: "PUT", body: values }));
      setMsg(`${code} saved — new prices and limits apply immediately.`);
    } catch (e) { setErr((e as Error).message); }
  };
  const a = addon ?? data.addon;

  return (
    <div className="space-y-5">
      <Card className="p-4 text-sm text-gray-600">Plan prices, limits and features used everywhere in the app (pricing page, limits, Razorpay orders). Existing paid periods are not changed.</Card>
      <ErrorBox message={err} />
      {msg && <div className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{msg}</div>}
      {data.order.map((code) => (
        <PlanEditor key={code + JSON.stringify(data.plans[code])} code={code} plan={data.plans[code]} isDefault={data.defaults[code]} onSave={save(code)} />
      ))}
      <Card className="p-5">
        <h3 className="mb-4 font-semibold text-gray-900">Add-on pack</h3>
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Name"><Input value={String(a.name ?? "")} onChange={(e) => setAddon({ ...a, name: e.target.value })} /></Field>
          <Field label="Extra businesses"><Input inputMode="numeric" value={String(a.businesses ?? "")} onChange={(e) => setAddon({ ...a, businesses: Number(e.target.value) })} /></Field>
          <Field label="Yearly price (₹)"><Input inputMode="numeric" value={String(a.yearly ?? "")} onChange={(e) => setAddon({ ...a, yearly: Number(e.target.value) })} /></Field>
          <div className="flex items-end"><Button onClick={() => save(data.addon_code)({ name: a.name, businesses: a.businesses, yearly: a.yearly })}><Save size={14} /> Save</Button></div>
        </div>
      </Card>
    </div>
  );
}
