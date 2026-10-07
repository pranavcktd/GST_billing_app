"use client";

import { CalendarDays, Pencil, Plus, Trash2, Wallet } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AccountSelect } from "@/components/AccountSelect";
import { Modal } from "@/components/Modal";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { usePerms } from "@/lib/auth";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

export interface Employee {
  id: string; code: string | null; name: string; phone: string | null; email: string | null; designation: string | null;
  department: string | null; joined_on: string | null; left_on: string | null; is_active: boolean; user_id: string | null;
  salary_type?: "MONTHLY" | "DAILY"; salary?: number; basic_pct?: number; ot_rate?: number; pf?: boolean; esi?: boolean;
  pt_monthly?: number; tds_monthly?: number; uan?: string | null; esic_no?: string | null; pan?: string | null;
  bank_name?: string | null; bank_account?: string | null; bank_ifsc?: string | null; notes?: string | null; advance_due?: number;
}

const blank: Partial<Employee> = { name: "", salary_type: "MONTHLY", salary: 0, basic_pct: 50, ot_rate: 0, pf: false, esi: false,
  pt_monthly: 0, tds_monthly: 0, is_active: true };

export default function StaffPage() {
  const { can } = usePerms();
  const [inactive, setInactive] = useState(false);
  const { data, error, reload } = useFetch<Employee[]>(`/employees${inactive ? "?include_inactive=true" : ""}`);
  const [editing, setEditing] = useState<Partial<Employee> | null>(null);
  const [advanceFor, setAdvanceFor] = useState<Employee | null>(null);
  const pay = can("payroll");

  return (
    <>
      <PageHeader title="Staff" sub="Your employees — attendance and salaries in one place, no separate registers."
        actions={<>
          <Link href="/staff/attendance" className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3.5 py-2 text-sm font-medium hover:bg-gray-50"><CalendarDays size={16} /> Attendance</Link>
          {pay && <Link href="/staff/payroll" className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3.5 py-2 text-sm font-medium hover:bg-gray-50"><Wallet size={16} /> Payroll</Link>}
          {can("payroll", "create") && <Button onClick={() => setEditing({ ...blank })}><Plus size={16} /> Add employee</Button>}
        </>} />
      <label className="mb-3 flex items-center gap-2 text-sm text-gray-600"><input type="checkbox" checked={inactive} onChange={(e) => setInactive(e.target.checked)} /> Show people who have left</label>
      <Card className="overflow-x-auto">
        <ErrorBox message={error} />
        {!data ? <Loading /> : data.length === 0 ? <Empty title="No employees yet — add your staff to mark attendance and run payroll." /> : (
          <table className="tbl">
            <thead><tr><th>Name</th><th>Designation</th><th>Joined</th>{pay && <><th className="num">Salary</th><th>EPF / ESI</th><th className="num">Advance due</th></>}<th /></tr></thead>
            <tbody>
              {data.map((e) => (
                <tr key={e.id} className={e.is_active ? "" : "text-gray-400"}>
                  <td className="font-medium">{e.name}{e.code && <span className="ml-1.5 text-xs text-gray-500">{e.code}</span>}<div className="text-xs font-normal text-gray-500">{e.phone}</div></td>
                  <td>{e.designation ?? "—"}{e.department && <div className="text-xs text-gray-500">{e.department}</div>}</td>
                  <td className="whitespace-nowrap">{e.joined_on ? fmtDate(e.joined_on) : "—"}{e.left_on && <div className="text-xs">left {fmtDate(e.left_on)}</div>}</td>
                  {pay && <>
                    <td className="num">{money(e.salary ?? 0)}<div className="text-xs text-gray-500">{e.salary_type === "DAILY" ? "per day" : "per month"}</div></td>
                    <td className="text-xs">{[e.pf && "EPF", e.esi && "ESI"].filter(Boolean).join(" · ") || "—"}</td>
                    <td className={`num ${e.advance_due ? "text-amber-700" : ""}`}>{e.advance_due ? money(e.advance_due) : "—"}</td>
                  </>}
                  <td className="whitespace-nowrap text-right">
                    {can("payroll", "create") && e.is_active && <Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => setAdvanceFor(e)}>Advance</Button>}
                    {can("payroll", "edit") && <button className="ml-1 text-gray-400 hover:text-gray-700" title="Edit" onClick={() => setEditing(e)}><Pencil size={15} /></button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {editing && <EmployeeForm initial={editing} onClose={() => setEditing(null)} onSaved={reload} />}
      {advanceFor && <AdvanceForm emp={advanceFor} onClose={() => setAdvanceFor(null)} onSaved={reload} />}
    </>
  );
}

function EmployeeForm({ initial, onClose, onSaved }: { initial: Partial<Employee>; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState<Partial<Employee>>(initial);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: logins } = useFetch<{ id: string; name: string; email: string }[]>("/employees/logins");
  const t = (k: keyof Employee) => ({ value: (f[k] as string | null | undefined) ?? "", onChange: (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value }) });
  const n = (k: keyof Employee) => ({ type: "number" as const, min: 0, step: "0.01", value: String(f[k] ?? 0), onChange: (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: Number(e.target.value) }) });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const body = { ...f };
      delete (body as Record<string, unknown>).id; delete (body as Record<string, unknown>).advance_due;
      await api(f.id ? `/employees/${f.id}` : "/employees", { method: f.id ? "PUT" : "POST", body });
      onSaved(); onClose();
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  async function remove() {
    if (!f.id || !confirm(`Delete ${f.name}? (Only possible when there are no salary records — otherwise set a leaving date.)`)) return;
    try { await api(`/employees/${f.id}`, { method: "DELETE" }); onSaved(); onClose(); } catch (x) { setErr((x as Error).message); }
  }

  return (
    <Modal title={f.id ? `Edit ${initial.name}` : "Add employee"} onClose={onClose} wide>
      <form onSubmit={save} className="max-h-[75vh] space-y-4 overflow-y-auto pr-1">
        <ErrorBox message={err} />
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Name" className="sm:col-span-2" info={false}><Input required {...t("name")} /></Field>
          <Field label="Employee code" info={false}><Input {...t("code")} /></Field>
          <Field label="Phone" info={false}><Input {...t("phone")} /></Field>
          <Field label="Designation" info={false}><Input {...t("designation")} /></Field>
          <Field label="Department" info={false}><Input {...t("department")} /></Field>
          <Field label="Joined on" info={false}><Input type="date" {...t("joined_on")} /></Field>
          <Field label="Left on" info={false} hint="Leave empty while working"><Input type="date" {...t("left_on")} /></Field>
          <Field label="App login (for self check-in)" info={false}>
            <Select value={f.user_id ?? ""} onChange={(e) => setF({ ...f, user_id: e.target.value || null })}>
              <option value="">Not linked</option>
              {logins?.map((u) => <option key={u.id} value={u.id}>{u.name} — {u.email}</option>)}
            </Select>
          </Field>
        </div>
        <div className="rounded-lg border border-gray-200 p-3">
          <div className="mb-2 text-sm font-semibold text-gray-900">Salary</div>
          <div className="grid gap-3 sm:grid-cols-4">
            <Field label="Paid" info={false}>
              <Select value={f.salary_type} onChange={(e) => setF({ ...f, salary_type: e.target.value as Employee["salary_type"] })}>
                <option value="MONTHLY">Monthly salary</option><option value="DAILY">Daily wage</option>
              </Select>
            </Field>
            <Field label={f.salary_type === "DAILY" ? "Wage per day (₹)" : "Gross salary per month (₹)"} info={false}><Input {...n("salary")} /></Field>
            <Field label="Overtime per hour (₹)" info={false}><Input {...n("ot_rate")} /></Field>
            <Field label="Basic pay (% of salary)" info={false} hint="Used for EPF"><Input {...n("basic_pct")} max={100} /></Field>
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 p-3">
          <div className="mb-2 text-sm font-semibold text-gray-900">Deductions</div>
          <div className="grid gap-3 sm:grid-cols-4">
            <label className="flex items-center gap-2 pt-5 text-sm"><input type="checkbox" checked={!!f.pf} onChange={(e) => setF({ ...f, pf: e.target.checked })} /> EPF member</label>
            <label className="flex items-center gap-2 pt-5 text-sm"><input type="checkbox" checked={!!f.esi} onChange={(e) => setF({ ...f, esi: e.target.checked })} /> ESI member</label>
            <Field label="Professional tax / month (₹)" info={false}><Input {...n("pt_monthly")} /></Field>
            <Field label="TDS / month (₹)" info={false}><Input {...n("tds_monthly")} /></Field>
            <Field label="UAN (EPF)" info={false}><Input {...t("uan")} /></Field>
            <Field label="ESIC IP no." info={false}><Input {...t("esic_no")} /></Field>
            <Field label="PAN" info={false}><Input {...t("pan")} className="uppercase" maxLength={10} /></Field>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Bank" info={false}><Input {...t("bank_name")} /></Field>
          <Field label="Account no." info={false}><Input {...t("bank_account")} /></Field>
          <Field label="IFSC" info={false}><Input {...t("bank_ifsc")} className="uppercase" maxLength={11} /></Field>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.is_active ?? true} onChange={(e) => setF({ ...f, is_active: e.target.checked })} /> Active (still working here)</label>
        <div className="flex justify-between gap-2">
          {f.id ? <Button type="button" variant="danger" onClick={remove}><Trash2 size={15} /> Delete</Button> : <span />}
          <div className="flex gap-2"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</Button></div>
        </div>
      </form>
    </Modal>
  );
}

function AdvanceForm({ emp, onClose, onSaved }: { emp: Employee; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ amount: "", date: new Date().toISOString().slice(0, 10), mode: "CASH", note: "", account_id: "" });
  const [err, setErr] = useState<string | null>(null);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/payroll/advances", { body: { employee_id: emp.id, amount: Number(f.amount), date: f.date, mode: f.mode, note: f.note || null, account_id: f.account_id || null } });
      onSaved(); onClose();
    } catch (x) { setErr((x as Error).message); }
  }
  return (
    <Modal title={`Salary advance — ${emp.name}`} onClose={onClose}>
      <form onSubmit={save} className="space-y-3">
        <ErrorBox message={err} />
        <p className="text-sm text-gray-600">Paid now (shown as a Salary expense in Cash & Bank) and recovered from a later payroll.{emp.advance_due ? ` Already due: ${money(emp.advance_due)}.` : ""}</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Amount (₹)" info={false}><Input type="number" min="1" step="0.01" required value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></Field>
          <Field label="Date" info={false}><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></Field>
          <Field label="Paid by" info={false}><Select value={f.mode} onChange={(e) => setF({ ...f, mode: e.target.value })}><option value="CASH">Cash</option><option value="BANK">Bank transfer</option><option value="UPI">UPI</option></Select></Field>
          <Field label="Note" info={false}><Input value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
          <Field label="Paid from" info={false} className="col-span-2"><AccountSelect value={f.account_id} onChange={(v) => setF({ ...f, account_id: v })} /></Field>
        </div>
        <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit">Give advance</Button></div>
      </form>
    </Modal>
  );
}
