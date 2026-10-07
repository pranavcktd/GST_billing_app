"use client";

import { CheckCircle2, FileText, Lock, RefreshCw, Settings2, Trash2, Unlock, Wallet } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AccountSelect } from "@/components/AccountSelect";
import { Modal } from "@/components/Modal";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { usePerms } from "@/lib/auth";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Totals { gross: number; deductions: number; net: number; pf_employee: number; pf_employer: number; esi_employee: number; esi_employer: number; pt: number; tds: number; advance_recovery: number }
interface RunSummary { id: string; month: string; status: "DRAFT" | "FINAL" | "PAID"; paid_on: string | null; employees: number; totals: Totals }
interface Line {
  id: string; employee_id: string; name: string; bonus: number; other_additions: number; advance_recovery: number; other_deductions: number;
  gross: number; deductions: number; net: number; note: string | null;
  data: { paid_days: number; days_in_month: number; present: number; absent: number; half_days: number; leave: number; earned: number; ot_pay: number; ot_hours: number;
    pf_employee: number; esi_employee: number; pt: number; tds: number; salary_type: string; rate: number; designation: string | null };
}
interface Run extends RunSummary { voucher_id: string | null; statutory_paid: Record<string, { date: string; amount: number; reference: string | null }>; lines: Line[] }

const monthLabel = (m: string) => new Date(`${m}-01`).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
const lastMonth = () => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1); return d.toISOString().slice(0, 7); };
const STATUS: Record<string, string> = { DRAFT: "bg-amber-100 text-amber-800", FINAL: "bg-sky-100 text-sky-800", PAID: "bg-emerald-100 text-emerald-800" };

export default function PayrollPage() {
  const { can } = usePerms();
  const { data: runs, error, reload } = useFetch<RunSummary[]>("/payroll/runs");
  const [openId, setOpenId] = useState<string | null>(null);
  const [month, setMonth] = useState(lastMonth());
  const [err, setErr] = useState<string | null>(null);
  const [settings, setSettings] = useState(false);

  async function prepare() {
    setErr(null);
    try { const r = await api<Run>("/payroll/runs", { body: { month } }); reload(); setOpenId(r.id); } catch (e) { setErr((e as Error).message); }
  }

  if (openId) return <RunView id={openId} onBack={() => { setOpenId(null); reload(); }} />;
  return (
    <>
      <PageHeader title="Payroll" sub="Monthly salaries worked out from attendance — with EPF, ESI, professional tax, TDS and advances."
        actions={<>
          <Link href="/staff" className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-3.5 py-2 text-sm font-medium hover:bg-gray-50">Staff</Link>
          {can("payroll", "edit") && <Button variant="secondary" onClick={() => setSettings(true)}><Settings2 size={16} /> Settings</Button>}
        </>} />
      <ErrorBox message={err ?? error} />
      {can("payroll", "create") && (
        <Card className="mb-4 flex flex-wrap items-end gap-3 p-4">
          <Field label="Month" info={false}><Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} /></Field>
          <Button onClick={prepare}><RefreshCw size={16} /> Prepare payroll</Button>
          <p className="text-xs text-gray-500">Uses the month&apos;s attendance. You can review and adjust before finalising and paying.</p>
        </Card>
      )}
      <Card className="overflow-x-auto">
        {!runs ? <Loading /> : runs.length === 0 ? <Empty title="No payroll yet — mark attendance, then prepare the month's payroll." /> : (
          <table className="tbl">
            <thead><tr><th>Month</th><th>Status</th><th className="num">Employees</th><th className="num">Gross</th><th className="num">Net pay</th><th /></tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td className="font-medium">{monthLabel(r.month)}</td>
                  <td><span className={`rounded px-1.5 py-0.5 text-xs font-medium ${STATUS[r.status]}`}>{r.status === "FINAL" ? "Finalised" : r.status === "PAID" ? `Paid ${r.paid_on ? fmtDate(r.paid_on) : ""}` : "Draft"}</span></td>
                  <td className="num">{r.employees}</td><td className="num">{money(r.totals.gross)}</td><td className="num font-semibold">{money(r.totals.net)}</td>
                  <td className="text-right"><Button variant="secondary" className="!py-1" onClick={() => setOpenId(r.id)}>Open</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Advances />
      {settings && <PayrollSettings onClose={() => setSettings(false)} />}
    </>
  );
}

function RunView({ id, onBack }: { id: string; onBack: () => void }) {
  const { can } = usePerms();
  const { data: run, error, setData } = useFetch<Run>(`/payroll/runs/${id}`);
  const [err, setErr] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);
  const [statutory, setStatutory] = useState<string | null>(null);
  const draft = run?.status === "DRAFT" && can("payroll", "edit");

  async function act(fn: () => Promise<Run | void>) {
    setErr(null);
    try { const r = await fn(); if (r) setData(r); } catch (e) { setErr((e as Error).message); }
  }
  const edit = (l: Line, k: keyof Line, v: string) => act(() => api<Run>(`/payroll/runs/${id}/lines/${l.id}`, { method: "PUT",
    body: { bonus: l.bonus, other_additions: l.other_additions, advance_recovery: l.advance_recovery, other_deductions: l.other_deductions, note: l.note, [k]: Number(v) || 0 } }));

  if (error) return <ErrorBox message={error} />;
  if (!run) return <Loading />;
  const t = run.totals;
  const dues = [
    { k: "PF", label: "EPF (employee + employer)", amount: t.pf_employee + t.pf_employer },
    { k: "ESI", label: "ESI (employee + employer)", amount: t.esi_employee + t.esi_employer },
    { k: "PT", label: "Professional tax", amount: t.pt },
    { k: "TDS", label: "TDS on salaries", amount: t.tds },
  ].filter((d) => d.amount > 0);
  const num = (l: Line, k: "bonus" | "advance_recovery" | "other_deductions") => draft
    ? <input className="input !w-24 !py-1 text-right" inputMode="decimal" defaultValue={l[k] || ""} placeholder="0" onBlur={(e) => Number(e.target.value || 0) !== l[k] && edit(l, k, e.target.value)} />
    : (l[k] ? money(l[k]) : "—");

  return (
    <>
      <PageHeader title={`Payroll — ${monthLabel(run.month)}`} sub={`${run.lines.length} employees · ${run.status === "DRAFT" ? "Draft: change bonus, advance recovery and other deductions; attendance changes flow in when you rebuild" : run.status === "FINAL" ? "Finalised: attendance of this month is locked" : `Paid on ${run.paid_on ? fmtDate(run.paid_on) : ""}`}`}
        actions={<>
          <Button variant="secondary" onClick={onBack}>All months</Button>
          {draft && <Button variant="secondary" onClick={() => act(() => api<Run>("/payroll/runs", { body: { month: run.month } }))}><RefreshCw size={16} /> Rebuild from attendance</Button>}
          {draft && <Button onClick={() => act(() => api<Run>(`/payroll/runs/${id}/finalize`, { body: {} }))}><Lock size={16} /> Finalise</Button>}
          {run.status === "FINAL" && can("payroll", "edit") && <Button variant="secondary" onClick={() => act(() => api<Run>(`/payroll/runs/${id}/reopen`, { body: {} }))}><Unlock size={16} /> Reopen</Button>}
          {run.status === "FINAL" && can("payroll", "edit") && <Button onClick={() => setPaying(true)}><Wallet size={16} /> Pay salaries</Button>}
          {run.status === "DRAFT" && can("payroll", "delete") && <Button variant="danger" onClick={() => confirm("Delete this draft?") && act(async () => { await api(`/payroll/runs/${id}`, { method: "DELETE" }); onBack(); })}><Trash2 size={16} /></Button>}
        </>} />
      <ErrorBox message={err} />
      <Card className="overflow-x-auto">
        <table className="tbl">
          <thead><tr>
            <th>Employee</th><th className="num">Paid days</th><th className="num">Earned</th><th className="num">Overtime</th><th className="num">Bonus</th>
            <th className="num">Gross</th><th className="num">EPF</th><th className="num">ESI</th><th className="num">PT + TDS</th><th className="num">Advance</th>
            <th className="num">Other ded.</th><th className="num">Net pay</th><th />
          </tr></thead>
          <tbody>
            {run.lines.map((l) => (
              <tr key={l.id}>
                <td className="font-medium">{l.name}<div className="text-xs font-normal text-gray-500">{l.data.salary_type === "DAILY" ? `${money(l.data.rate)}/day` : `${money(l.data.rate)}/month`}</div></td>
                <td className="num" title={`Present ${l.data.present} · absent ${l.data.absent} · half days ${l.data.half_days} · leave ${l.data.leave}`}>{l.data.paid_days}<span className="text-xs text-gray-500">/{l.data.days_in_month}</span></td>
                <td className="num">{money(l.data.earned)}</td>
                <td className="num">{l.data.ot_pay ? <>{money(l.data.ot_pay)}<div className="text-xs text-gray-500">{l.data.ot_hours} h</div></> : "—"}</td>
                <td className="num">{num(l, "bonus")}</td>
                <td className="num font-medium">{money(l.gross)}</td>
                <td className="num">{l.data.pf_employee ? money(l.data.pf_employee) : "—"}</td>
                <td className="num">{l.data.esi_employee ? money(l.data.esi_employee) : "—"}</td>
                <td className="num">{l.data.pt + l.data.tds ? money(l.data.pt + l.data.tds) : "—"}</td>
                <td className="num">{num(l, "advance_recovery")}</td>
                <td className="num">{num(l, "other_deductions")}</td>
                <td className="num font-semibold">{money(l.net)}</td>
                <td><Link href={`/print/payslip/${id}/${l.id}`} title="Payslip" className="text-gray-400 hover:text-gray-700"><FileText size={16} /></Link></td>
              </tr>
            ))}
          </tbody>
          <tfoot><tr>
            <td>Total</td><td /><td /><td /><td /><td className="num">{money(t.gross)}</td><td className="num">{money(t.pf_employee)}</td><td className="num">{money(t.esi_employee)}</td>
            <td className="num">{money(t.pt + t.tds)}</td><td className="num">{money(t.advance_recovery)}</td><td /><td className="num">{money(t.net)}</td><td />
          </tr></tfoot>
        </table>
      </Card>

      {run.status !== "DRAFT" && dues.length > 0 && (
        <Card className="mt-4 p-5">
          <h2 className="mb-1 font-semibold text-gray-900">Statutory dues for {monthLabel(run.month)}</h2>
          <p className="mb-3 text-xs text-gray-500">Deposit by the 15th of next month (EPF / ESI). Recording a deposit adds it to Cash & Bank and the P&L (TDS goes to Tax payments).</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {dues.map((d) => (
              <div key={d.k} className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2 text-sm">
                <span>{d.label}<div className="font-semibold">{money(d.amount)}</div></span>
                {run.statutory_paid[d.k]
                  ? <span className="text-xs text-emerald-700"><CheckCircle2 size={14} className="mr-1 inline" />Deposited {fmtDate(run.statutory_paid[d.k].date)}{run.statutory_paid[d.k].reference ? ` · ${run.statutory_paid[d.k].reference}` : ""}</span>
                  : can("payroll", "edit") && <Button variant="secondary" className="!py-1" onClick={() => setStatutory(d.k)}>Record deposit</Button>}
              </div>
            ))}
          </div>
        </Card>
      )}
      {paying && <PayDialog title={`Pay salaries — ${monthLabel(run.month)}`} amount={t.net} onClose={() => setPaying(false)}
        onPay={(b) => act(() => api<Run>(`/payroll/runs/${id}/pay`, { body: b })).then(() => setPaying(false))} />}
      {statutory && <PayDialog title={`Record ${statutory} deposit — ${monthLabel(run.month)}`} amount={dues.find((d) => d.k === statutory)?.amount ?? 0} withReference
        onClose={() => setStatutory(null)} onPay={(b) => act(() => api<Run>(`/payroll/runs/${id}/statutory`, { body: { ...b, kind: statutory } })).then(() => setStatutory(null))} />}
    </>
  );
}

function PayDialog({ title, amount, withReference, onClose, onPay }: {
  title: string; amount: number; withReference?: boolean; onClose: () => void; onPay: (b: Record<string, unknown>) => void;
}) {
  const [f, setF] = useState({ date: new Date().toISOString().slice(0, 10), account_id: "", mode: "BANK", reference: "" });
  return (
    <Modal title={title} onClose={onClose}>
      <div className="space-y-3">
        <p className="text-sm">Amount: <b>{money(amount)}</b></p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date" info={false}><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></Field>
          <Field label="Paid by" info={false}><Select value={f.mode} onChange={(e) => setF({ ...f, mode: e.target.value })}><option value="BANK">Bank transfer</option><option value="CASH">Cash</option><option value="UPI">UPI</option><option value="CHEQUE">Cheque</option></Select></Field>
          <Field label="Paid from" info={false} className="col-span-2"><AccountSelect value={f.account_id} onChange={(v) => setF({ ...f, account_id: v })} /></Field>
          {withReference && <Field label="Challan / reference no." info={false} className="col-span-2"><Input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} /></Field>}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => onPay({ date: f.date, account_id: f.account_id || null, mode: f.mode, reference: f.reference || null })}>Confirm</Button>
        </div>
      </div>
    </Modal>
  );
}

function Advances() {
  const { can } = usePerms();
  const { data, reload } = useFetch<{ id: string; name: string; date: string; amount: number; note: string | null }[]>("/payroll/advances");
  if (!data?.length) return null;
  return (
    <Card className="mt-4 overflow-x-auto">
      <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Salary advances</h2>
      <table className="tbl">
        <thead><tr><th>Date</th><th>Employee</th><th>Note</th><th className="num">Amount</th><th /></tr></thead>
        <tbody>
          {data.map((a) => (
            <tr key={a.id}>
              <td>{fmtDate(a.date)}</td><td>{a.name}</td><td className="text-gray-600">{a.note}</td><td className="num">{money(a.amount)}</td>
              <td className="text-right">{can("payroll", "delete") && <button className="text-gray-400 hover:text-red-600" title="Delete (cancels its expense entry)"
                onClick={async () => { if (confirm("Delete this advance? Its expense entry is cancelled.")) { try { await api(`/payroll/advances/${a.id}`, { method: "DELETE" }); reload(); } catch (e) { alert((e as Error).message); } } }}><Trash2 size={15} /></button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function PayrollSettings({ onClose }: { onClose: () => void }) {
  const { data } = useFetch<{ weekly_off: number[]; holidays: { date: string; name: string }[]; unmarked: string; basis: string }>("/payroll/settings");
  if (!data) return <Modal title="Payroll settings" onClose={onClose}><Loading /></Modal>;
  return <SettingsForm initial={data} onClose={onClose} />;
}

function SettingsForm({ initial, onClose }: { initial: { weekly_off: number[]; holidays: { date: string; name: string }[]; unmarked: string; basis: string }; onClose: () => void }) {
  const [s, setS] = useState(initial);
  const [h, setH] = useState({ date: "", name: "" });
  const [err, setErr] = useState<string | null>(null);
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  async function save() {
    try { await api("/payroll/settings", { method: "PUT", body: s }); onClose(); } catch (e) { setErr((e as Error).message); }
  }
  return (
    <Modal title="Payroll settings" onClose={onClose} wide>
      <div className="space-y-4 text-sm">
        <ErrorBox message={err} />
        <div>
          <div className="mb-1 font-medium">Weekly off</div>
          <div className="flex flex-wrap gap-3">{DAYS.map((d, i) => (
            <label key={d} className="flex items-center gap-1.5"><input type="checkbox" checked={s.weekly_off.includes(i)}
              onChange={(e) => setS({ ...s, weekly_off: e.target.checked ? [...s.weekly_off, i] : s.weekly_off.filter((x) => x !== i) })} /> {d}</label>
          ))}</div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Days not marked count as" info={false}>
            <Select value={s.unmarked} onChange={(e) => setS({ ...s, unmarked: e.target.value })}>
              <option value="PRESENT">Present (mark only absences)</option><option value="ABSENT">Absent (mark every working day)</option>
            </Select>
          </Field>
          <Field label="Monthly salary is divided by" info={false}>
            <Select value={s.basis} onChange={(e) => setS({ ...s, basis: e.target.value })}>
              <option value="CALENDAR">Days in the month (28–31)</option><option value="FIXED_30">30 days, every month</option><option value="WORKING">Working days (without weekly offs & holidays)</option>
            </Select>
          </Field>
        </div>
        <div>
          <div className="mb-1 font-medium">Paid holidays</div>
          <ul className="mb-2 space-y-1">{s.holidays.map((x) => (
            <li key={x.date} className="flex items-center gap-2">{fmtDate(x.date)} — {x.name}
              <button className="text-gray-400 hover:text-red-600" onClick={() => setS({ ...s, holidays: s.holidays.filter((y) => y.date !== x.date) })}><Trash2 size={13} /></button></li>
          ))}</ul>
          <div className="flex flex-wrap gap-2">
            <Input type="date" className="!w-40" value={h.date} onChange={(e) => setH({ ...h, date: e.target.value })} />
            <Input className="!w-56" placeholder="e.g. Diwali" value={h.name} onChange={(e) => setH({ ...h, name: e.target.value })} />
            <Button variant="secondary" disabled={!h.date} onClick={() => { setS({ ...s, holidays: [...s.holidays.filter((y) => y.date !== h.date), { date: h.date, name: h.name || "Holiday" }] }); setH({ date: "", name: "" }); }}>Add</Button>
          </div>
        </div>
        <div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={save}>Save settings</Button></div>
      </div>
    </Modal>
  );
}
