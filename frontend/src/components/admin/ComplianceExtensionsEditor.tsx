"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button, Input, Select } from "@/components/ui";
import type { Rule } from "@/components/admin/ComplianceRulesEditor";

export interface Extension { code: string; period_key: string; due_date: string; note?: string }

const thisFy = () => { const d = new Date(); return d.getMonth() >= 3 ? d.getFullYear() : d.getFullYear() - 1; };
const FYS = Array.from({ length: 4 }, (_, i) => thisFy() - 2 + i);

/** Period picker that writes the calendar's period key: 2026-09 (month), FY2026-Q2 (quarter), FY2026 / FY2026#2 (year). */
function PeriodPicker({ rule, value, onChange }: { rule?: Rule; value: string; onChange: (v: string) => void }) {
  if (!rule) return <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder="Period" />;
  if (rule.frequency === "MONTHLY") {
    return <Input type="month" value={/^\d{4}-\d{2}$/.test(value) ? value : ""} onChange={(e) => onChange(e.target.value)} />;
  }
  const m = /^FY(\d{4})(?:-Q(\d)|#(\d))?$/.exec(value) ?? [];
  const fy = Number(m[1]) || thisFy();
  if (rule.frequency === "QUARTERLY") {
    const q = Number(m[2]) || 1;
    return (
      <div className="flex gap-1">
        <Select value={fy} onChange={(e) => onChange(`FY${e.target.value}-Q${q}`)}>{FYS.map((y) => <option key={y} value={y}>FY {y}-{String(y + 1).slice(-2)}</option>)}</Select>
        <Select value={q} onChange={(e) => onChange(`FY${fy}-Q${e.target.value}`)}>{[1, 2, 3, 4].map((x) => <option key={x} value={x}>Q{x}</option>)}</Select>
      </div>
    );
  }
  const dates = rule.due.dates ?? [];
  const n = Number(m[3]) || 1;
  const key = (y: number, i: number) => `FY${y}${dates.length > 1 ? `#${i}` : ""}`;
  return (
    <div className="flex gap-1">
      <Select value={fy} onChange={(e) => onChange(key(Number(e.target.value), n))}>{FYS.map((y) => <option key={y} value={y}>FY {y}-{String(y + 1).slice(-2)}</option>)}</Select>
      {dates.length > 1 && (
        <Select value={n} onChange={(e) => onChange(key(fy, Number(e.target.value)))}>{dates.map((d, i) => <option key={i} value={i + 1}>{d.label ?? `Date ${i + 1}`}</option>)}</Select>
      )}
    </div>
  );
}

/** Super admin: one-off due-date extensions announced by the government (Admin → GST config → Compliance calendar). */
export function ComplianceExtensionsEditor({ rows, rules, onChange }: { rows: Extension[]; rules: Rule[]; onChange: (r: Extension[]) => void }) {
  const byCode = Object.fromEntries(rules.map((r) => [r.code, r]));
  const set = (i: number, patch: Partial<Extension>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <div className="space-y-2">
      {rows.length === 0 && <p className="text-xs text-gray-500">No extensions. Add one when a notification extends a due date for a period.</p>}
      {rows.map((e, i) => (
        <div key={i} className="grid items-center gap-2 rounded-lg border border-gray-200 p-2 sm:grid-cols-[1.4fr_1.2fr_0.9fr_1.6fr_auto]">
          <Select value={e.code} onChange={(x) => { const r = byCode[x.target.value]; set(i, { code: x.target.value, period_key: r?.frequency === "MONTHLY" ? "" : `FY${thisFy()}${r?.frequency === "QUARTERLY" ? "-Q1" : ""}` }); }}>
            <option value="">Choose filing</option>
            {rules.filter((r) => !r.disabled).map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
          </Select>
          <PeriodPicker rule={byCode[e.code]} value={e.period_key} onChange={(v) => set(i, { period_key: v })} />
          <Input type="date" value={e.due_date} onChange={(x) => set(i, { due_date: x.target.value })} title="New due date" />
          <Input value={e.note ?? ""} placeholder="e.g. Notification 12/2026-CT" onChange={(x) => set(i, { note: x.target.value })} />
          <Button type="button" variant="ghost" className="!px-2 text-red-600" onClick={() => onChange(rows.filter((_, j) => j !== i))}><Trash2 size={15} /></Button>
        </div>
      ))}
      <Button type="button" variant="secondary" onClick={() => onChange([...rows, { code: "", period_key: "", due_date: "", note: "" }])}><Plus size={15} /> Add extension</Button>
    </div>
  );
}
