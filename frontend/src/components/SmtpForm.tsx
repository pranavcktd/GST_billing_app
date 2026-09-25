"use client";

import { Mail, Send, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface SmtpState {
  configured: boolean;
  settings: { host: string; port: number; security: string; username: string | null; from_email: string; from_name: string | null; password_set: boolean } | null;
  effective_source: string | null;
  effective_from: string | null;
}

const PRESETS: Record<string, { host: string; port: number; security: string; note: string }> = {
  Gmail: { host: "smtp.gmail.com", port: 587, security: "STARTTLS", note: "Use a Google App Password (Google Account → Security → App passwords)" },
  "Outlook / Office 365": { host: "smtp.office365.com", port: 587, security: "STARTTLS", note: "Your Microsoft 365 mailbox password or app password" },
  Zoho: { host: "smtp.zoho.in", port: 465, security: "SSL", note: "Zoho Mail India; use an app-specific password" },
  "Brevo (Sendinblue)": { host: "smtp-relay.brevo.com", port: 587, security: "STARTTLS", note: "SMTP key from Brevo → SMTP & API" },
  "Amazon SES (Mumbai)": { host: "email-smtp.ap-south-1.amazonaws.com", port: 587, security: "STARTTLS", note: "SES SMTP credentials; verify the from address" },
};
const SOURCE: Record<string, string> = {
  BUSINESS: "this business's own settings", RESELLER: "your reseller's settings", PLATFORM: "the platform settings", ENV: "the server settings",
};

/** SMTP settings for one level. `base` is /smtp (business), /reseller/smtp or /admin/smtp. */
export function SmtpForm({ base, title, help, canEdit = true }: { base: string; title: string; help: string; canEdit?: boolean }) {
  const { data, reload } = useFetch<SmtpState>(base);
  const [f, setF] = useState<{ host: string; port: number; security: string; username: string; password: string; from_email: string; from_name: string } | null>(null);
  const [testTo, setTestTo] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!data) return <Loading />;
  const form = f ?? {
    host: data.settings?.host ?? "", port: data.settings?.port ?? 587, security: data.settings?.security ?? "STARTTLS",
    username: data.settings?.username ?? "", password: "", from_email: data.settings?.from_email ?? "", from_name: data.settings?.from_name ?? "",
  };
  const set = (patch: Partial<typeof form>) => setF({ ...form, ...patch });
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true); setErr(null); setMsg(null);
    try { await fn(); setMsg(ok); reload(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <Card className="max-w-3xl space-y-4 p-5">
      <div>
        <h2 className="flex items-center gap-2 font-semibold text-gray-900"><Mail size={17} /> {title}</h2>
        <p className="mt-1 text-sm text-gray-600">{help}</p>
        <p className="mt-2 text-xs text-gray-500">
          {data.effective_source ? <>Currently e-mails go out from <b>{data.effective_from}</b> using {SOURCE[data.effective_source]}.</> : "No e-mail server is set up at any level yet."}
        </p>
      </div>
      <ErrorBox message={err} />
      {msg && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      <Field label="Quick setup">
        <Select value="" disabled={!canEdit} onChange={(e) => { const p = PRESETS[e.target.value]; if (p) { set({ host: p.host, port: p.port, security: p.security }); setMsg(p.note); } }}>
          <option value="">Choose a provider…</option>
          {Object.keys(PRESETS).map((k) => <option key={k}>{k}</option>)}
        </Select>
      </Field>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="SMTP host" className="sm:col-span-2"><Input disabled={!canEdit} value={form.host} onChange={(e) => set({ host: e.target.value })} placeholder="smtp.gmail.com" /></Field>
        <Field label="Port"><Input disabled={!canEdit} type="number" value={form.port} onChange={(e) => set({ port: Number(e.target.value) })} /></Field>
        <Field label="Security">
          <Select disabled={!canEdit} value={form.security} onChange={(e) => set({ security: e.target.value })}>
            <option value="STARTTLS">STARTTLS (587)</option><option value="SSL">SSL/TLS (465)</option><option value="NONE">None</option>
          </Select>
        </Field>
        <Field label="Username"><Input disabled={!canEdit} autoComplete="off" value={form.username} onChange={(e) => set({ username: e.target.value })} /></Field>
        <Field label="Password" hint={data.settings?.password_set ? "Saved — leave blank to keep" : undefined}>
          <Input disabled={!canEdit} type="password" autoComplete="new-password" value={form.password} onChange={(e) => set({ password: e.target.value })} />
        </Field>
        <Field label="From e-mail" className="sm:col-span-2"><Input disabled={!canEdit} type="email" value={form.from_email} onChange={(e) => set({ from_email: e.target.value })} /></Field>
        <Field label="From name"><Input disabled={!canEdit} value={form.from_name} onChange={(e) => set({ from_name: e.target.value })} /></Field>
      </div>
      {canEdit && (
        <div className="flex flex-wrap justify-between gap-2">
          {data.configured ? (
            <Button variant="danger" disabled={busy} onClick={() => confirm("Remove these e-mail settings? The next level up will be used.") &&
              run(() => api(base, { method: "DELETE" }), "Removed — falling back to the next level")}><Trash2 size={15} /> Remove</Button>
          ) : <span />}
          <Button disabled={busy || !form.host || !form.from_email} onClick={() => run(() => api(base, { method: "PUT", body: {
            ...form, username: form.username || null, password: form.password || null, from_name: form.from_name || null,
          } }), "E-mail settings saved")}>Save</Button>
        </div>
      )}
      <div className="flex flex-wrap items-end gap-2 border-t border-gray-100 pt-4">
        <Field label="Send a test e-mail to" className="flex-1"><Input type="email" value={testTo} onChange={(e) => setTestTo(e.target.value)} /></Field>
        <Button variant="secondary" disabled={busy || !testTo} onClick={() => run(() => api(`${base}/test`, { body: { to: testTo } }), `Test e-mail sent to ${testTo}`)}><Send size={15} /> Send test</Button>
      </div>
    </Card>
  );
}
