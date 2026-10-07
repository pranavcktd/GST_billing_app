"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { usePerms } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";

type Status = "P" | "A" | "HD" | "L" | "WO" | "H";
interface Cell { status: Status; marked: boolean; check_in?: string | null; check_out?: string | null; ot_hours?: number; note?: string | null; source?: string }
interface Row { id: string; name: string; designation: string | null; code: string | null; days: Record<string, Cell | null>; counts: Record<string, number> }
interface Grid { month: string; days: string[]; employees: Row[]; statuses: Record<Status, string>; today: string; settings: { holidays: { date: string; name: string }[] } }

const STATUS_STYLE: Record<Status, string> = {
  P: "bg-emerald-100 text-emerald-800", A: "bg-red-100 text-red-700", HD: "bg-amber-100 text-amber-800",
  L: "bg-sky-100 text-sky-800", WO: "bg-gray-100 text-gray-500", H: "bg-violet-100 text-violet-700",
};
const thisMonth = () => new Date().toISOString().slice(0, 7);
const shift = (m: string, by: number) => { const d = new Date(Number(m.slice(0, 4)), Number(m.slice(5, 7)) - 1 + by, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; };

export default function AttendancePage() {
  const { can } = usePerms();
  const [month, setMonth] = useState(thisMonth());
  const { data, error, reload } = useFetch<Grid>(`/attendance?month=${month}`);
  const [open, setOpen] = useState<{ row: Row; date: string; cell: Cell } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const edit = can("attendance", "edit");

  async function mark(row: Row, date: string, status: Status | null, extra: Partial<Cell> = {}) {
    setErr(null);
    try {
      await api("/attendance", { method: "PUT", body: { marks: [{ employee_id: row.id, date, status, ...extra }] } });
      reload();
    } catch (e) { setErr((e as Error).message); }
  }
  async function markDay(date: string, status: Status) {
    if (!data || !confirm(`Mark everyone ${data.statuses[status].toLowerCase()} on ${new Date(date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}?`)) return;
    try {
      await api("/attendance", { method: "PUT", body: { marks: data.employees.filter((r) => r.days[date]).map((r) => ({ employee_id: r.id, date, status })) } });
      reload();
    } catch (e) { setErr((e as Error).message); }
  }

  const label = new Date(`${month}-01`).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
  const holidays = Object.fromEntries((data?.settings.holidays ?? []).map((h) => [h.date, h.name]));
  return (
    <>
      <PageHeader title="Attendance" sub="Tap a day to mark it. Days you don't mark follow your payroll settings (usually present; Sundays and holidays off)." />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Button variant="secondary" className="!px-2" onClick={() => setMonth(shift(month, -1))} aria-label="Previous month"><ChevronLeft size={16} /></Button>
        <span className="min-w-36 text-center font-semibold">{label}</span>
        <Button variant="secondary" className="!px-2" onClick={() => setMonth(shift(month, 1))} aria-label="Next month"><ChevronRight size={16} /></Button>
        <div className="ml-auto flex flex-wrap gap-1.5 text-xs">
          {data && (Object.keys(data.statuses) as Status[]).map((s) => <span key={s} className={`rounded px-1.5 py-0.5 ${STATUS_STYLE[s]}`}>{s} {data.statuses[s]}</span>)}
          <span className="rounded border border-dashed border-gray-300 px-1.5 py-0.5 text-gray-500">faded = not marked (default)</span>
        </div>
      </div>
      <ErrorBox message={err ?? error} />
      <Card className="overflow-x-auto">
        {!data ? <Loading /> : data.employees.length === 0 ? <Empty title="No active employees — add them under Staff." /> : (
          <table className="text-xs">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="sticky left-0 z-10 min-w-40 bg-white px-3 py-2 text-left font-semibold">Employee</th>
                {data.days.map((d) => {
                  const dt = new Date(d);
                  return (
                    <th key={d} className={`px-0.5 py-1 text-center font-normal ${dt.getDay() === 0 || holidays[d] ? "text-red-600" : "text-gray-500"} ${d === data.today ? "bg-brand-50" : ""}`} title={holidays[d]}>
                      <div>{"SMTWTFS"[dt.getDay()]}</div>
                      {edit ? <button className="font-semibold hover:underline" title="Mark everyone…" onClick={() => markDay(d, "P")}>{dt.getDate()}</button> : <div className="font-semibold">{dt.getDate()}</div>}
                    </th>
                  );
                })}
                <th className="px-2 text-center">P</th><th className="px-2 text-center">A</th><th className="px-2 text-center">½</th><th className="px-2 text-center">L</th>
              </tr>
            </thead>
            <tbody>
              {data.employees.map((r) => (
                <tr key={r.id} className="border-b border-gray-100">
                  <td className="sticky left-0 z-10 bg-white px-3 py-1.5"><div className="font-medium text-gray-900">{r.name}</div><div className="text-[11px] text-gray-500">{r.designation}</div></td>
                  {data.days.map((d) => {
                    const c = r.days[d];
                    if (!c) return <td key={d} className="px-0.5 text-center text-gray-300">·</td>;
                    return (
                      <td key={d} className={`px-0.5 py-1 text-center ${d === data.today ? "bg-brand-50" : ""}`}>
                        <button disabled={!edit} onClick={() => setOpen({ row: r, date: d, cell: c })}
                          title={[data.statuses[c.status], c.check_in && `in ${c.check_in}`, c.check_out && `out ${c.check_out}`, c.ot_hours ? `OT ${c.ot_hours} h` : "", c.note].filter(Boolean).join(" · ")}
                          className={`h-7 w-7 rounded text-[11px] font-semibold ${STATUS_STYLE[c.status]} ${c.marked ? "" : "opacity-40"} ${c.ot_hours ? "ring-1 ring-amber-400" : ""}`}>
                          {c.status === "HD" ? "½" : c.status}
                        </button>
                      </td>
                    );
                  })}
                  <td className="px-2 text-center">{r.counts.P}</td><td className="px-2 text-center text-red-700">{r.counts.A || ""}</td>
                  <td className="px-2 text-center">{r.counts.HD || ""}</td><td className="px-2 text-center">{r.counts.L || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {open && <DayDialog o={open} statuses={data!.statuses} onClose={() => setOpen(null)} onSave={(s, extra) => { mark(open.row, open.date, s, extra); setOpen(null); }} />}
    </>
  );
}

function DayDialog({ o, statuses, onClose, onSave }: {
  o: { row: Row; date: string; cell: Cell }; statuses: Record<Status, string>; onClose: () => void;
  onSave: (s: Status | null, extra: Partial<Cell>) => void;
}) {
  const [f, setF] = useState({ check_in: o.cell.check_in ?? "", check_out: o.cell.check_out ?? "", ot_hours: String(o.cell.ot_hours ?? ""), note: o.cell.note ?? "" });
  const extra = () => ({ check_in: f.check_in || null, check_out: f.check_out || null, ot_hours: Number(f.ot_hours) || 0, note: f.note || null });
  return (
    <Modal title={`${o.row.name} — ${new Date(o.date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}`} onClose={onClose}>
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-2">
          {(Object.keys(statuses) as Status[]).map((s) => (
            <button key={s} onClick={() => onSave(s, extra())}
              className={`rounded-lg px-2 py-2.5 text-sm font-medium ${STATUS_STYLE[s]} ${o.cell.status === s && o.cell.marked ? "ring-2 ring-brand-500" : ""}`}>{statuses[s]}</button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Field label="In" info={false}><Input type="time" value={f.check_in} onChange={(e) => setF({ ...f, check_in: e.target.value })} /></Field>
          <Field label="Out" info={false}><Input type="time" value={f.check_out} onChange={(e) => setF({ ...f, check_out: e.target.value })} /></Field>
          <Field label="Overtime (hours)" info={false}><Input type="number" min="0" max="24" step="0.5" value={f.ot_hours} onChange={(e) => setF({ ...f, ot_hours: e.target.value })} /></Field>
        </div>
        <Field label="Note" info={false}><Input value={f.note} maxLength={200} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
        <p className="text-xs text-gray-500">Pick a status to save. Times and overtime are saved with it.{o.cell.source === "SELF" ? " Marked by the employee (self check-in)." : ""}</p>
        <div className="flex justify-between">
          {o.cell.marked ? <Button variant="ghost" onClick={() => onSave(null, {})}>Clear (back to default)</Button> : <span />}
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </div>
      </div>
    </Modal>
  );
}
