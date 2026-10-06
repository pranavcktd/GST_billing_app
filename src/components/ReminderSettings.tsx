"use client";

import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface S { enabled: boolean; before_days: number[]; on_due: boolean; after_days: number[]; default_credit_days: number; cc_me: boolean; attach_pdf: boolean }
interface Log { id: string; party: string | null; number: string | null; stage: string; channel: string; to: string | null; status: string; error: string | null; automatic: boolean; amount: number; by: string | null; at: string }

const list = (s: string) => s.split(/[,\s]+/).map(Number).filter((n) => Number.isFinite(n) && n > 0);
const stageText = (s: string) => s === "DUE" ? "On due date" : s === "MANUAL" ? "Sent by hand" : s.startsWith("BEFORE_") ? `${s.slice(7)} days before due` : `${s.slice(6)} days overdue`;

/** Settings → Reminders: automatic payment reminders and the history of reminders sent. */
export function ReminderSettings({ canEdit }: { canEdit: boolean }) {
  const { data, setData } = useFetch<S>("/reminders/settings");
  const { data: log } = useFetch<Log[]>("/reminders/log?limit=50");
  const [f, setF] = useState<(S & { beforeText: string; afterText: string }) | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  if (!data) return <Loading />;
  const v = f ?? { ...data, beforeText: data.before_days.join(", "), afterText: data.after_days.join(", ") };
  const set = (patch: Partial<typeof v>) => { setF({ ...v, ...patch }); setSaved(false); };

  async function save() {
    setErr(null);
    try {
      const r = await api<S>("/reminders/settings", { method: "PUT", body: { ...v, before_days: list(v.beforeText), after_days: list(v.afterText) } });
      setData(r); setF(null); setSaved(true);
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <h2 className="mb-1 font-semibold text-gray-900">Automatic payment reminders</h2>
        <p className="mb-4 text-sm text-gray-600">Every morning, customers with unpaid sale invoices get one polite e-mail listing what is due, with the invoice PDFs,
          a link to view each invoice, your UPI ID and bank details. Each reminder step is sent only once per invoice. Customers whose advance or credit covers the bills are skipped.</p>
        <ErrorBox message={err} />
        {saved && <div className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Saved.</div>}
        <label className="mb-4 flex items-center gap-2 text-sm font-medium"><input type="checkbox" disabled={!canEdit} checked={v.enabled} onChange={(e) => set({ enabled: e.target.checked })} /> Send reminders automatically</label>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Days before the due date" hint="e.g. 3 — leave empty for none"><Input disabled={!canEdit} value={v.beforeText} onChange={(e) => set({ beforeText: e.target.value })} /></Field>
          <Field label="On the due date"><label className="flex items-center gap-2 pt-2 text-sm"><input type="checkbox" disabled={!canEdit} checked={v.on_due} onChange={(e) => set({ on_due: e.target.checked })} /> Remind on the due date</label></Field>
          <Field label="Days after the due date" hint="e.g. 3, 7, 15, 30"><Input disabled={!canEdit} value={v.afterText} onChange={(e) => set({ afterText: e.target.value })} /></Field>
          <Field label="Due date when the invoice has none" hint="Invoice date + these days"><Input disabled={!canEdit} inputMode="numeric" value={String(v.default_credit_days)} onChange={(e) => set({ default_credit_days: Number(e.target.value) || 0 })} /></Field>
        </div>
        <div className="mt-4 flex flex-wrap gap-5 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" disabled={!canEdit} checked={v.attach_pdf} onChange={(e) => set({ attach_pdf: e.target.checked })} /> Attach invoice PDFs</label>
          <label className="flex items-center gap-2"><input type="checkbox" disabled={!canEdit} checked={v.cc_me} onChange={(e) => set({ cc_me: e.target.checked })} /> Send me a copy (business e-mail)</label>
        </div>
        {canEdit && <Button className="mt-4" disabled={!f} onClick={save}>Save</Button>}
        <p className="mt-3 text-xs text-gray-500">Reminders use the e-mail settings in Settings → Email. Customers need an e-mail address on their party record.</p>
      </Card>
      <Card className="overflow-x-auto">
        <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Recent reminders</h2>
        {!log ? <Loading /> : !log.length ? <p className="px-5 pb-4 text-sm text-gray-500">None sent yet.</p> : (
          <table className="tbl">
            <thead><tr><th>When</th><th>Customer</th><th>Invoice</th><th>Step</th><th>Via</th><th className="num">Amount</th><th>Result</th></tr></thead>
            <tbody>
              {log.map((r) => (
                <tr key={r.id}>
                  <td className="whitespace-nowrap text-xs">{new Date(r.at).toLocaleString("en-IN")}</td>
                  <td>{r.party}</td><td className="text-xs">{r.number}</td>
                  <td className="text-xs">{stageText(r.stage)}{r.automatic ? " · auto" : r.by ? ` · ${r.by}` : ""}</td>
                  <td className="text-xs">{r.channel === "WHATSAPP" ? "WhatsApp" : "E-mail"}</td>
                  <td className="num">{money(r.amount)}</td>
                  <td className={`text-xs ${r.status === "SENT" ? "text-emerald-700" : "text-red-700"}`}>{r.status === "SENT" ? "Sent" : r.error ?? "Failed"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
