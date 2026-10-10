"use client";

import { CircleCheck, Wrench } from "lucide-react";
import { useState } from "react";
import { istTime, useCountdown } from "@/components/Maintenance";
import { Button, Card, ErrorBox, Field, Input, Loading, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Status {
  active: boolean; scheduled: boolean; starts_at: string | null; ends_at: string | null; message: string; auto_end: boolean;
  whatsapp_template: string; whatsapp_lang: string; set_by: string | null; owners: number; email_ready: boolean; whatsapp_ready: boolean;
  notified: { kind: string; at: string; email: boolean; whatsapp: boolean; recipients: number } | null;
}

const local = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
const iso = (v: string) => (v ? new Date(v).toISOString() : null);

/** Admin → Maintenance: planned downtime. Everyone except super admins is signed out and kept out until it ends. */
export function AdminMaintenance() {
  const { data, setData } = useFetch<Status>("/admin/maintenance", { refreshMs: 30000 });
  if (!data) return <Loading />;
  return <Panel key={`${data.active}-${data.scheduled}`} s={data} onChange={setData} />;
}

function Panel({ s, onChange }: { s: Status; onChange: (s: Status) => void }) {
  const [when, setWhen] = useState<"now" | "later">("now");
  const [start, setStart] = useState(() => local(new Date(Date.now() + 3600000)));
  const [minutes, setMinutes] = useState(60);
  const [autoEnd, setAutoEnd] = useState(true);
  const [message, setMessage] = useState(s.message);
  const [email, setEmail] = useState(true);
  const [wa, setWa] = useState(false);
  const [tpl, setTpl] = useState(s.whatsapp_template);
  const [endNotify, setEndNotify] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const left = useCountdown(s.active ? s.ends_at : s.scheduled ? s.starts_at : null);

  async function go() {
    setErr(null);
    const startAt = when === "later" ? new Date(start) : new Date();
    const endAt = minutes ? new Date(startAt.getTime() + minutes * 60000) : null;
    if (when === "now" && !confirm(`Start maintenance now? Everyone except super admins is signed out immediately${email ? ` and ${s.owners} business owner(s) are told` : ""}.`)) return;
    setBusy(true);
    try {
      onChange(await api<Status>("/admin/maintenance", { method: "PUT", body: {
        starts_at: when === "later" ? iso(start) : null, ends_at: endAt?.toISOString() ?? null, auto_end: autoEnd, message,
        whatsapp_template: tpl, notify_email: email, notify_whatsapp: wa } }));
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }
  async function end() {
    setBusy(true); setErr(null);
    try { onChange(await api<Status>("/admin/maintenance/end", { body: { notify_email: endNotify && s.active, notify_whatsapp: false } })); }
    catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900"><Wrench size={18} className="text-brand-600" /> Maintenance &amp; downtime</h2>
        <p className="max-w-2xl text-sm text-gray-500">
          For upgrades. While it is on, everyone except super admins is signed out and cannot sign in; the login page shows your message and a countdown.
          You can always sign in as super admin.
        </p>
      </div>
      <ErrorBox message={err} />

      {s.active || s.scheduled ? (
        <Card className={`p-5 ${s.active ? "border-rose-200 bg-rose-50/60" : "border-amber-200 bg-amber-50/60"}`}>
          <div className="text-sm font-semibold text-gray-900">{s.active ? "Maintenance is ON" : "Maintenance is scheduled"}</div>
          <p className="mt-1 text-sm text-gray-700">“{s.message}”</p>
          <p className="mt-2 text-sm text-gray-700">
            {s.active ? <>Started {istTime(s.starts_at)}{s.ends_at ? <> · expected back {istTime(s.ends_at)} (in <b className="tabular-nums">{left}</b>){s.auto_end ? ", then live automatically" : ""}</> : " · no end time — mark live when ready"}</>
              : <>Starts {istTime(s.starts_at)} (in <b className="tabular-nums">{left}</b>){s.ends_at ? ` · until ${istTime(s.ends_at)}` : ""}. Everyone sees a countdown banner now.</>}
          </p>
          {s.notified && <p className="mt-1 text-xs text-gray-500">Notice sent {istTime(s.notified.at)} to {s.notified.recipients} owner(s) by {[s.notified.email && "e-mail", s.notified.whatsapp && "WhatsApp"].filter(Boolean).join(" and ")}.</p>}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {s.active && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={endNotify} onChange={(e) => setEndNotify(e.target.checked)} /> E-mail owners that we&apos;re back</label>}
            <Button disabled={busy} onClick={end}><CircleCheck size={16} /> {s.active ? "Mark platform live" : "Cancel scheduled maintenance"}</Button>
          </div>
        </Card>
      ) : (
        <Card className="space-y-4 p-5 text-sm">
          <p className="flex items-center gap-2 text-emerald-700"><CircleCheck size={16} /> The platform is live.</p>
          <div className="flex gap-1 rounded-lg bg-gray-100 p-1 sm:w-fit">
            {(["now", "later"] as const).map((w) => (
              <button key={w} onClick={() => setWhen(w)} className={`rounded-md px-3 py-1.5 ${when === w ? "bg-white font-medium shadow-sm" : "text-gray-600"}`}>{w === "now" ? "Start now" : "Schedule for later"}</button>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {when === "later" && <Field label="Starts at"><Input type="datetime-local" value={start} min={local(new Date())} onChange={(e) => setStart(e.target.value)} /></Field>}
            <Field label="Expected duration" hint="Shown as a countdown on the login page">
              <div className="flex flex-wrap gap-1.5">
                {[15, 30, 60, 120, 240].map((m) => (
                  <button key={m} type="button" onClick={() => setMinutes(m)} className={`rounded-full px-3 py-1 text-xs ring-1 ${minutes === m ? "bg-brand-600 text-white ring-brand-600" : "ring-gray-300"}`}>{m < 60 ? `${m} min` : `${m / 60} h`}</button>
                ))}
                <button type="button" onClick={() => setMinutes(0)} className={`rounded-full px-3 py-1 text-xs ring-1 ${minutes === 0 ? "bg-brand-600 text-white ring-brand-600" : "ring-gray-300"}`}>Until I mark live</button>
              </div>
            </Field>
          </div>
          {minutes > 0 && <label className="flex items-center gap-2"><input type="checkbox" checked={autoEnd} onChange={(e) => setAutoEnd(e.target.checked)} /> Go live automatically when the time is up (untick to keep it closed until you mark it live)</label>}
          <Field label="Message for users"><Textarea rows={2} value={message} onChange={(e) => setMessage(e.target.value)} /></Field>
          <div className="space-y-2 rounded-lg bg-gray-50 p-3">
            <div className="text-xs font-semibold text-gray-600 uppercase">Tell business owners ({s.owners})</div>
            <label className="flex items-center gap-2"><input type="checkbox" checked={email} onChange={(e) => setEmail(e.target.checked)} disabled={!s.email_ready} />
              By e-mail {!s.email_ready && <span className="text-xs text-amber-700">— add an e-mail sender in Admin → Email first</span>}</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={wa} onChange={(e) => setWa(e.target.checked)} disabled={!s.whatsapp_ready} />
              On WhatsApp {!s.whatsapp_ready && <span className="text-xs text-amber-700">— set up WhatsApp in Integrations first</span>}</label>
            {wa && (
              <Field label="Approved WhatsApp template name" hint="WhatsApp only allows pre-approved templates. Create one with two variables: {{1}} = message, {{2}} = when.">
                <Input value={tpl} onChange={(e) => setTpl(e.target.value)} placeholder="e.g. maintenance_notice" />
              </Field>
            )}
          </div>
          <Button disabled={busy || message.trim().length < 5} onClick={go}>{when === "now" ? "Start maintenance now" : "Schedule maintenance"}</Button>
        </Card>
      )}
    </div>
  );
}
