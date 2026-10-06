"use client";

import { Pause, Pencil, Play, Repeat, Trash2, Zap } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";
import { Modal } from "@/components/Modal";
import { FREQ } from "@/components/RecurringForm";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Rec {
  id: string; name: string; party: string | null; frequency: string; interval: number; start_date: string; end_date: string | null;
  next_date: string | null; due_days: number; auto_email: boolean; status: "ACTIVE" | "PAUSED" | "ENDED"; generated_count: number;
  last_generated_at: string | null; last_error: string | null; lines: number; approx_value: number; upcoming: string[];
}
const TONE = { ACTIVE: "bg-emerald-50 text-emerald-700", PAUSED: "bg-amber-50 text-amber-800", ENDED: "bg-gray-100 text-gray-600" };
const every = (r: Rec) => (r.interval > 1 ? `Every ${r.interval} × ` : "") + FREQ[r.frequency];

export default function RecurringPage() {
  const { data, error, reload } = useFetch<Rec[]>("/recurring");
  const [edit, setEdit] = useState<Rec | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function act(fn: () => Promise<unknown>, ok?: string) {
    setErr(null); setMsg(null);
    try { await fn(); if (ok) setMsg(ok); reload(); } catch (e) { setErr((e as Error).message); }
  }

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;
  return (
    <>
      <PageHeader title="Recurring invoices" sub="Invoices created automatically on a schedule — rent, AMC, subscriptions, retainers" />
      <ErrorBox message={err} />
      {msg && <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      {!data.length ? (
        <Card><Empty title="No recurring invoices yet. Open any sale invoice and choose “Make recurring”." action={<Link href="/v/sales" className="text-brand-600 hover:underline">Go to sale invoices</Link>} /></Card>
      ) : (
        <Card className="overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>Schedule</th><th>Customer</th><th>Repeats</th><th className="num">Approx. value</th><th>Next invoice</th><th>Made</th><th>Status</th><th /></tr></thead>
            <tbody>
              {data.map((r) => (
                <Fragment key={r.id}>
                  <tr>
                    <td><div className="flex items-center gap-1.5 font-medium"><Repeat size={14} className="text-brand-600" /> {r.name}</div>
                      {r.last_error && <div className="max-w-72 text-xs text-red-700">⚠ {r.last_error}</div>}</td>
                    <td>{r.party}</td>
                    <td className="text-sm">{every(r)}{r.auto_email ? " · e-mailed" : ""}{r.due_days ? ` · due in ${r.due_days} days` : ""}</td>
                    <td className="num">{money(r.approx_value)}<div className="text-[10px] text-gray-400">before GST, {r.lines} line{r.lines > 1 ? "s" : ""}</div></td>
                    <td>{r.next_date ? fmtDate(r.next_date) : "—"}{r.end_date && <div className="text-xs text-gray-500">until {fmtDate(r.end_date)}</div>}</td>
                    <td><button className="text-brand-600 hover:underline" onClick={() => setOpen(open === r.id ? null : r.id)}>{r.generated_count} invoice{r.generated_count === 1 ? "" : "s"}</button></td>
                    <td><span className={`rounded px-2 py-0.5 text-xs ${TONE[r.status]}`}>{r.status === "ACTIVE" ? "Active" : r.status === "PAUSED" ? "Paused" : "Ended"}</span></td>
                    <td className="whitespace-nowrap text-right">
                      {r.status === "ACTIVE" && r.next_date && r.next_date <= new Date().toISOString().slice(0, 10) && (
                        <Button variant="ghost" className="!px-2 !py-1" title="Create the due invoice(s) now" onClick={() => act(() => api(`/recurring/${r.id}/run`, { body: {} }), "Invoice(s) created.")}><Zap size={15} /></Button>
                      )}
                      {r.status === "ACTIVE" && <Button variant="ghost" className="!px-2 !py-1" title="Pause" onClick={() => act(() => api(`/recurring/${r.id}`, { method: "PUT", body: { status: "PAUSED" } }))}><Pause size={15} /></Button>}
                      {r.status === "PAUSED" && <Button variant="ghost" className="!px-2 !py-1" title="Resume" onClick={() => act(() => api(`/recurring/${r.id}`, { method: "PUT", body: { status: "ACTIVE" } }))}><Play size={15} /></Button>}
                      <Button variant="ghost" className="!px-2 !py-1" title="Edit schedule" onClick={() => setEdit(r)}><Pencil size={15} /></Button>
                      <Button variant="ghost" className="!px-2 !py-1" title="Delete schedule" onClick={() => confirm(`Delete “${r.name}”? Invoices already created stay.`) && act(() => api(`/recurring/${r.id}`, { method: "DELETE" }))}><Trash2 size={15} /></Button>
                    </td>
                  </tr>
                  {open === r.id && <tr className="bg-gray-50"><td colSpan={8}><History id={r.id} upcoming={r.upcoming} /></td></tr>}
                </Fragment>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      <p className="mt-3 text-xs text-gray-500">Invoices are created automatically within an hour of their date, numbered in your normal series. To change items or rates, edit a normal invoice the way you want and use “Use items from invoice” in Edit.</p>
      {edit && <EditSchedule r={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); reload(); }} />}
    </>
  );
}

function History({ id, upcoming }: { id: string; upcoming: string[] }) {
  const { data } = useFetch<{ id: string; number: string; date: string; total: number; cancelled: boolean }[]>(`/recurring/${id}/invoices`);
  return (
    <div className="grid gap-4 py-2 text-xs sm:grid-cols-2">
      <div>
        <div className="mb-1 font-semibold text-gray-700">Created</div>
        {!data ? "…" : !data.length ? <span className="text-gray-500">None yet</span> : data.map((v) => (
          <div key={v.id}><Link href={`/v/sales/${v.id}`} className="text-brand-600 hover:underline">{v.number}</Link> · {fmtDate(v.date)} · {money(v.total)}{v.cancelled ? " · cancelled" : ""}</div>
        ))}
      </div>
      <div>
        <div className="mb-1 font-semibold text-gray-700">Coming up</div>
        {upcoming.length ? upcoming.map((d) => <div key={d}>{fmtDate(d)}</div>) : <span className="text-gray-500">Nothing scheduled</span>}
      </div>
    </div>
  );
}

function EditSchedule({ r, onClose, onSaved }: { r: Rec; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ name: r.name, frequency: r.frequency, interval: String(r.interval), next_date: r.next_date ?? "", end_date: r.end_date ?? "",
    due_days: String(r.due_days), auto_email: r.auto_email, template_from_voucher_id: "" });
  const { data: invoices } = useFetch<{ id: string; number: string; party_name: string; date: string }[]>("/vouchers?type=SALE&limit=50");
  const [err, setErr] = useState<string | null>(null);
  async function save() {
    setErr(null);
    try {
      await api(`/recurring/${r.id}`, { method: "PUT", body: { name: f.name, frequency: f.frequency, interval: Number(f.interval) || 1,
        next_date: f.next_date || null, end_date: f.end_date || null, clear_end_date: !f.end_date, due_days: Number(f.due_days) || 0,
        auto_email: f.auto_email, template_from_voucher_id: f.template_from_voucher_id || null } });
      onSaved();
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <Modal title="Edit schedule" onClose={onClose}>
      <div className="space-y-3 text-sm">
        <Field label="Name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Repeat"><Select value={f.frequency} onChange={(e) => setF({ ...f, frequency: e.target.value })}>{Object.entries(FREQ).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
          <Field label="Every"><Input inputMode="numeric" value={f.interval} onChange={(e) => setF({ ...f, interval: e.target.value })} /></Field>
          <Field label="Next invoice on"><Input type="date" value={f.next_date} onChange={(e) => setF({ ...f, next_date: e.target.value })} /></Field>
          <Field label="Stop after"><Input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} /></Field>
          <Field label="Payment due after (days)"><Input inputMode="numeric" value={f.due_days} onChange={(e) => setF({ ...f, due_days: e.target.value })} /></Field>
        </div>
        <label className="flex items-center gap-2"><input type="checkbox" checked={f.auto_email} onChange={(e) => setF({ ...f, auto_email: e.target.checked })} /> E-mail each invoice to the customer</label>
        <Field label="Use items & rates from invoice (optional)" hint="Replaces the items, rates and notes of this schedule">
          <Select value={f.template_from_voucher_id} onChange={(e) => setF({ ...f, template_from_voucher_id: e.target.value })}>
            <option value="">Keep current items</option>
            {(invoices ?? []).map((v) => <option key={v.id} value={v.id}>{v.number} · {v.party_name} · {fmtDate(v.date)}</option>)}
          </Select>
        </Field>
        <ErrorBox message={err} />
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save}>Save</Button></div>
      </div>
    </Modal>
  );
}
