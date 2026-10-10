"use client";

import { Mail, Pencil, Plus, Send, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Sender {
  id: string; label: string; provider: string; provider_label: string; region: string | null; from_email: string; from_name: string | null; reply_to: string | null;
  is_default: boolean; active: boolean; secret_set: boolean; last_test_at: string | null; last_error: string | null; businesses: number;
}
interface Data { senders: Sender[]; providers: Record<string, string> }
type Draft = Partial<Sender> & { secret?: string };

const KEY_HELP: Record<string, string> = {
  BREVO: "Brevo → SMTP & API → API keys (starts with xkeysib-). Verify the sender domain in Brevo first.",
  ZEPTOMAIL: "ZeptoMail → Mail Agents → SMTP/API → Send Mail token. Choose the data centre of your Zoho account (India = zeptomail.in).",
  RESEND: "Resend → API Keys (starts with re_). The from-address domain must be verified in Resend.",
  SENDGRID: "SendGrid → Settings → API Keys (starts with SG.) with Mail Send permission; verify the sender.",
  POSTMARK: "Postmark → Server → API Tokens (Server API token). Use a verified sender signature.",
};

/** Super admin → Email: senders (API providers only); one is the platform default, others can be given to businesses. */
export function AdminMail() {
  const { data, setData, reload } = useFetch<Data>("/admin/mail/senders");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [testTo, setTestTo] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (!data) return <Loading />;

  async function save() {
    if (!draft) return;
    setErr(null);
    const body = { label: draft.label, provider: draft.provider, secret: draft.secret || null, region: draft.provider === "ZEPTOMAIL" ? draft.region || "IN" : null,
      from_email: draft.from_email, from_name: draft.from_name || null, reply_to: draft.reply_to || null,
      active: draft.active ?? true, is_default: !!draft.is_default };
    try {
      if (draft.id) await api(`/admin/mail/senders/${draft.id}`, { method: "PUT", body });
      else await api("/admin/mail/senders", { body });
      setDraft(null); reload();
    } catch (e) { setErr((e as Error).message); }
  }

  const d = draft;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900"><Mail size={18} className="text-brand-600" /> E-mail senders</h2>
          <p className="max-w-2xl text-sm text-gray-500">
            All e-mail goes through these senders — sign-in codes, invoices, reminders, backups. The <b>default</b> is used by every business
            (sent under the business’s name, replies to the business’s e-mail). Give a business its own sender in Admin → Businesses.
          </p>
        </div>
        <Button onClick={() => setDraft({ provider: "BREVO", active: true, is_default: data.senders.length === 0 })}><Plus size={15} /> Add sender</Button>
      </div>
      <ErrorBox message={err} />
      {msg && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</p>}
      {data.senders.length === 0 && (
        <Card className="p-5 text-sm text-gray-600">
          No senders yet, so nothing can be e-mailed — sign-in codes, password resets, invoices, reminders and backups.
          Add one (ZeptoMail India or Brevo work well) and send yourself a test.
        </Card>
      )}
      <div className="grid gap-3 lg:grid-cols-2">
        {data.senders.map((s) => (
          <Card key={s.id} className={`space-y-2 p-4 ${s.is_default ? "ring-2 ring-brand-200" : ""}`}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2 font-semibold text-gray-900">{s.label}
                  {s.is_default && <span className="rounded bg-brand-50 px-1.5 py-0.5 text-[11px] text-brand-700">Default</span>}
                  {!s.active && <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">Off</span>}</div>
                <div className="text-xs text-gray-500">{s.provider_label}{s.region ? ` · ${s.region}` : ""} · {s.from_name ? `${s.from_name} <${s.from_email}>` : s.from_email}</div>
                <div className="text-xs text-gray-500">{s.businesses ? `Used by ${s.businesses} business${s.businesses === 1 ? "" : "es"}` : s.is_default ? "Used by every business without its own sender" : "Not assigned"}</div>
                {s.last_error ? <div className="text-xs text-red-700">Last test failed: {s.last_error}</div>
                  : s.last_test_at ? <div className="text-xs text-emerald-700">Last test OK {new Date(s.last_test_at).toLocaleString("en-IN")}</div> : null}
              </div>
              <div className="flex shrink-0 gap-1">
                {!s.is_default && <Button variant="ghost" className="!px-2" title="Make default" onClick={async () => {
                  try { await api(`/admin/mail/senders/${s.id}`, { method: "PUT", body: { ...s, secret: null, is_default: true } }); reload(); } catch (e) { setErr((e as Error).message); }
                }}><Star size={15} /></Button>}
                <Button variant="ghost" className="!px-2" title="Edit" onClick={() => setDraft({ ...s })}><Pencil size={15} /></Button>
                <Button variant="ghost" className="!px-2 text-red-600" title="Remove" onClick={async () => {
                  if (!confirm(`Remove ${s.label}? Businesses using it go back to the default.`)) return;
                  try { await api(`/admin/mail/senders/${s.id}`, { method: "DELETE" }); reload(); } catch (e) { setErr((e as Error).message); }
                }}><Trash2 size={15} /></Button>
              </div>
            </div>
            <div className="flex gap-2">
              <Input type="email" placeholder="Send a test to…" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
              <Button variant="secondary" disabled={!testTo} onClick={async () => {
                setErr(null); setMsg(null);
                try { await api(`/admin/mail/senders/${s.id}/test`, { body: { to: testTo } }); setMsg(`Test e-mail sent to ${testTo} via ${s.label}.`); }
                catch (e) { setErr((e as Error).message); }
                setData(await api<Data>("/admin/mail/senders"));
              }}><Send size={14} /> Test</Button>
            </div>
          </Card>
        ))}
      </div>

      {d && (
        <Modal title={d.id ? `Edit ${d.label}` : "Add e-mail sender"} onClose={() => setDraft(null)}>
          <div className="space-y-3 text-sm">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Name (for you)"><Input value={d.label ?? ""} placeholder="e.g. Platform (Brevo)" onChange={(e) => setDraft({ ...d, label: e.target.value })} /></Field>
              <Field label="Provider"><Select value={d.provider} onChange={(e) => setDraft({ ...d, provider: e.target.value })}>
                {Object.entries(data.providers).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select></Field>
            </div>
            <p className="text-xs text-gray-500">{KEY_HELP[d.provider ?? "BREVO"]}</p>
            {d.provider === "ZEPTOMAIL" && (
              <Field label="Data centre"><Select value={d.region ?? "IN"} onChange={(e) => setDraft({ ...d, region: e.target.value })}>
                <option value="IN">India (zeptomail.in)</option><option value="COM">Global (zeptomail.com)</option><option value="EU">Europe (zeptomail.eu)</option>
              </Select></Field>
            )}
            <Field label="API key" hint={d.secret_set ? "Saved — type a new one only to replace it" : "Stored encrypted; never shown again"}>
              <Input type="password" autoComplete="off" value={d.secret ?? ""} onChange={(e) => setDraft({ ...d, secret: e.target.value })} />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="From e-mail" hint="Must be verified with the provider"><Input type="email" value={d.from_email ?? ""} onChange={(e) => setDraft({ ...d, from_email: e.target.value })} /></Field>
              <Field label="From name"><Input value={d.from_name ?? ""} placeholder="e.g. MyBillSync" onChange={(e) => setDraft({ ...d, from_name: e.target.value })} /></Field>
              <Field label="Reply-to (optional)"><Input type="email" value={d.reply_to ?? ""} onChange={(e) => setDraft({ ...d, reply_to: e.target.value })} /></Field>
              <div className="space-y-1 pt-6">
                <label className="flex items-center gap-2"><input type="checkbox" checked={d.active ?? true} onChange={(e) => setDraft({ ...d, active: e.target.checked })} /> Active</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={!!d.is_default} onChange={(e) => setDraft({ ...d, is_default: e.target.checked })} /> Platform default</label>
              </div>
            </div>
            <ErrorBox message={err} />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDraft(null)}>Cancel</Button>
              <Button disabled={!d.label || !d.from_email} onClick={save}>Save sender</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
