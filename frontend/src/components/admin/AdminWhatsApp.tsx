"use client";

import { MessageCircle, Save, Send } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Preset { label: string; base_url: string; api_version: string; auth_header: string }
interface Settings {
  enabled: boolean; sandbox: boolean; sandbox_active: boolean; dev_server: boolean; provider: string; base_url: string; api_version: string; auth_header: string; phone_number_id: string;
  api_key_set: boolean; api_key_hint: string | null; ready: boolean; webhook_key: string | null;
  login_enabled: boolean; signup_verify: boolean;
  otp_template: string; otp_lang: string; otp_button: boolean;
  invoice_template: string; invoice_lang: string; reminder_template: string; reminder_lang: string;
  presets: Record<string, Preset>;
}
interface Data {
  settings: Settings; webhook_url: string | null; this_month: Record<string, number>;
  recent: { at: string; kind: string; to: string; template: string | null; status: string; error: string | null; ref: string | null; preview: string | null }[];
}

/** Super admin: WhatsApp Business API vendor (any Meta-compatible API), templates, sign-in options, delivery log. */
export function AdminWhatsApp() {
  const { data, setData } = useFetch<Data>("/admin/whatsapp");
  const [edit, setEdit] = useState<Partial<Settings> & { api_key?: string }>({});
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  if (!data) return <Loading />;
  const s = { ...data.settings, ...edit };
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setEdit({ ...edit, [k]: v });

  async function save(extra: Record<string, unknown> = {}) {
    setErr(null); setMsg(null);
    try {
      setData(await api<Data>("/admin/whatsapp", { method: "PUT", body: { ...edit, ...extra } }));
      setEdit({});
      setMsg("Saved.");
    } catch (e) { setErr((e as Error).message); }
  }
  async function test() {
    setErr(null); setMsg(null);
    try {
      const r = await api<{ to: string }>("/admin/whatsapp/test", { body: { phone } });
      setMsg(`Test sign-in code (123456) sent to ${r.to}. Check that phone's WhatsApp.`);
    } catch (e) { setErr((e as Error).message); }
  }
  function choose(provider: string) {
    const p = s.presets[provider];
    setEdit({ ...edit, provider, api_version: p.api_version, auth_header: p.auth_header, ...(p.base_url ? { base_url: p.base_url } : {}) });
  }
  const tpl = (k: "otp" | "invoice" | "reminder", label: string, hint: string) => (
    <div className="grid grid-cols-3 gap-2">
      <div className="col-span-2"><Field label={label} hint={hint}><Input value={s[`${k}_template`]} onChange={(e) => set(`${k}_template`, e.target.value)} /></Field></div>
      <Field label="Language"><Input value={s[`${k}_lang`]} onChange={(e) => set(`${k}_lang`, e.target.value)} /></Field>
    </div>
  );

  return (
    <div className="space-y-4">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900"><MessageCircle size={18} className="text-emerald-600" /> WhatsApp Business API</h2>
      <ErrorBox message={err} />
      {msg && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="space-y-3 p-5">
          <h3 className="font-semibold">Vendor & connection</h3>
          <p className="text-xs text-gray-500">Any vendor using the Meta Cloud API message format works. Switching vendors later only needs these fields changed.</p>
          <Field label="Vendor">
            <Select value={s.provider} onChange={(e) => choose(e.target.value)}>
              {Object.entries(s.presets).map(([k, p]) => <option key={k} value={k}>{p.label}</option>)}
            </Select>
          </Field>
          <Field label="API base URL" hint="Spring Edge gives this after onboarding (the WhatsApp service URL)">
            <Input placeholder="https://…" value={s.base_url} onChange={(e) => set("base_url", e.target.value)} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="API version path"><Input value={s.api_version} onChange={(e) => set("api_version", e.target.value)} /></Field>
            <Field label="Key header" hint="apikey (Spring Edge) or Bearer (Meta)"><Input value={s.auth_header} onChange={(e) => set("auth_header", e.target.value)} /></Field>
          </div>
          <Field label="Phone number ID" hint="The WhatsApp sender number's ID from your vendor (not the phone number itself)">
            <Input value={s.phone_number_id} onChange={(e) => set("phone_number_id", e.target.value)} />
          </Field>
          <Field label="API key" hint={s.api_key_set ? `Saved (${s.api_key_hint ?? "hidden"}) — type a new one to replace it` : "Stored encrypted; never shown again"}>
            <Input type="password" autoComplete="off" value={edit.api_key ?? ""} onChange={(e) => setEdit({ ...edit, api_key: e.target.value })} />
          </Field>
          <label className="flex items-center gap-2 pt-1 text-sm"><input type="checkbox" checked={s.enabled} onChange={(e) => set("enabled", e.target.checked)} /> Live sending {s.enabled ? "on" : "off"}</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={s.sandbox} onChange={(e) => set("sandbox", e.target.checked)} /> Sandbox while live is off (development server only)</label>
          <p className={`text-xs ${data.settings.ready ? "text-emerald-700" : data.settings.sandbox_active ? "text-amber-700" : "text-gray-500"}`}>
            {data.settings.ready ? "Live — real WhatsApp messages are sent through the vendor."
              : data.settings.sandbox_active ? "Sandbox — every feature works, but messages are only recorded below (not sent, not charged) and sign-in codes are shown on screen."
              : !data.settings.dev_server && s.sandbox ? "Off — the sandbox never runs on a production server. Fill in the vendor details and switch live on."
              : "Off — fill in URL, phone number ID and API key, then switch live on."}
          </p>
        </Card>

        <Card className="space-y-3 p-5">
          <h3 className="font-semibold">Approved templates</h3>
          <p className="text-xs text-gray-500">Names must match the templates approved by Meta exactly. Variables in order:</p>
          {tpl("otp", "Sign-in code template", "Authentication category · {{1}} = code")}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={s.otp_button} onChange={(e) => set("otp_button", e.target.checked)} /> Template has a copy-code button</label>
          {tpl("invoice", "Invoice template", "Utility · document header (PDF) · {{1}} customer {{2}} bill no. {{3}} amount {{4}} business")}
          {tpl("reminder", "Payment reminder template", "Utility · {{1}} customer {{2}} amount due {{3}} business {{4}} link")}
          <h3 className="pt-2 font-semibold">Sign-in</h3>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={s.login_enabled} onChange={(e) => set("login_enabled", e.target.checked)} /> Offer “Sign in with WhatsApp”</label>
          <p className="text-xs text-gray-500">How new accounts are verified (WhatsApp / e-mail / Google) is set in the “Sign-up &amp; sign-in” card above.</p>
        </Card>
      </div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-end gap-2">
          <Field label="Send a test code to"><Input type="tel" placeholder="10-digit mobile" value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
          <Button variant="secondary" disabled={!(data.settings.ready || data.settings.sandbox_active) || phone.replace(/\D/g, "").length < 10} onClick={test}><Send size={15} /> Test</Button>
        </div>
        <Button onClick={() => save()}><Save size={16} /> Save WhatsApp settings</Button>
      </div>

      {data.webhook_url && (
        <Card className="p-5 text-sm">
          <div className="font-medium">Delivery status webhook</div>
          <p className="mt-1 text-xs text-gray-500">Give this URL to your vendor (Spring Edge: ask their support to set it) so delivered / read / failed statuses show below.</p>
          <div className="mt-2 rounded bg-gray-50 px-2 py-1.5 font-mono text-xs break-all">{data.webhook_url}</div>
          <button className="mt-2 text-xs text-gray-500 underline" onClick={() => save({ new_webhook_key: true })}>Make a new secret link</button>
        </Card>
      )}

      <div className="grid grid-cols-3 gap-3">
        {(["OTP", "INVOICE", "REMINDER"] as const).map((k) => (
          <Card key={k} className="p-4"><div className="text-xs text-gray-500">{{ OTP: "Sign-in codes", INVOICE: "Invoices", REMINDER: "Reminders" }[k]} this month</div><div className="mt-1 text-2xl font-semibold">{data.this_month[k] ?? 0}</div></Card>
        ))}
      </div>
      <Card className="overflow-x-auto">
        <h3 className="px-5 pt-4 pb-2 font-semibold">Recent messages</h3>
        {data.recent.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">None yet.</p> : (
          <table className="tbl">
            <thead><tr><th>When</th><th>Type</th><th>To</th><th>Template</th><th>Reference</th><th>Status</th></tr></thead>
            <tbody>
              {data.recent.map((r, i) => (
                <tr key={i}>
                  <td className="whitespace-nowrap text-xs">{new Date(r.at).toLocaleString("en-IN")}</td>
                  <td className="text-xs">{r.kind}</td><td className="text-xs">{r.to}</td><td className="text-xs">{r.template}</td><td className="text-xs">{r.ref}</td>
                  <td className={`text-xs ${r.status === "FAILED" ? "text-red-700" : r.status === "SANDBOX" ? "text-amber-700" : "text-emerald-700"}`}>
                    {r.status}{r.error ? ` — ${r.error}` : ""}
                    {r.preview && <div className="mt-0.5 max-w-md text-[11px] break-words text-gray-500">{r.preview}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
