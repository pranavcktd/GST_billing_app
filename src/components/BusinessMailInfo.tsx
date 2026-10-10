"use client";

import { Mail, Send } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Input, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Info { effective_source: string | null; from_email: string | null; from_name: string | null; reply_to: string | null; own_sender: boolean }

/** Settings → E-mail: e-mail is managed by the platform; shows the address used and lets the user send a test. */
export function BusinessMailInfo() {
  const { data } = useFetch<Info>("/smtp");
  const [to, setTo] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (!data) return <Loading />;
  return (
    <Card className="max-w-2xl space-y-3 p-5">
      <h2 className="flex items-center gap-2 font-semibold text-gray-900"><Mail size={18} className="text-brand-600" /> E-mail for this business</h2>
      {data.from_email ? (
        <div className="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-700">
          Invoices, reminders and backups are sent as <b>{data.from_name ? `${data.from_name} <${data.from_email}>` : data.from_email}</b>
          {data.reply_to ? <>; your customers’ replies go to <b>{data.reply_to}</b></> : null}.
          {!data.own_sender && <p className="mt-1 text-xs text-gray-500">This is the platform’s address under your business name. To send from your own domain (for example billing@yourcompany.in), contact support — we set it up for you.</p>}
        </div>
      ) : <p className="text-sm text-amber-700">E-mail is not set up on the platform yet.</p>}
      <ErrorBox message={err} />
      {msg && <p className="text-sm text-emerald-700">{msg}</p>}
      {data.from_email && (
        <div className="flex gap-2">
          <Input type="email" placeholder="Send a test e-mail to…" value={to} onChange={(e) => setTo(e.target.value)} />
          <Button variant="secondary" disabled={!to} onClick={async () => {
            setErr(null); setMsg(null);
            try { await api("/smtp/test", { body: { to } }); setMsg(`Test e-mail sent to ${to}.`); } catch (e) { setErr((e as Error).message); }
          }}><Send size={14} /> Test</Button>
        </div>
      )}
    </Card>
  );
}
