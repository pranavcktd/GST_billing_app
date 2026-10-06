"use client";

import { Copy, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Field, Input, Select, Textarea } from "@/components/ui";
import { ENTITY_TYPES } from "@/lib/constants";

/**
 * Form editor for the compliance calendar rules (Admin → GST config → Compliance calendar). No JSON needed:
 * every filing is a row; "Edit" opens plain fields. Saving still goes through the effective-dated versions.
 */

type DueSpec = { day?: number; months_after?: number; state_day?: Record<string, number>; within_fy?: boolean; dates?: YearDate[] };
type YearDate = { month: number; day: number; label?: string };
export interface Rule {
  code: string; name: string; authority?: string; description?: string; penalty?: string; link?: string | null;
  frequency: "MONTHLY" | "QUARTERLY" | "YEARLY"; disabled?: boolean;
  applies?: { gst?: string[]; gst_filing?: string; entities?: string[]; requires?: string[]; excludes?: string[] };
  due: DueSpec; months_in_quarter?: number[];
  month_overrides?: Record<string, DueSpec>; quarter_overrides?: Record<string, DueSpec>;
  fee_per_day?: number | string | null; fee_cap?: number | null;
}

const LAWS: Record<string, string> = { GST: "GST", INCOME_TAX: "Income tax", TDS: "TDS", MCA: "Company law (MCA)", LLP: "LLP (MCA)", PAYROLL: "PF / ESI", OTHER: "Other" };
const GST_TYPES: Record<string, string> = { REGULAR: "GST regular", COMPOSITION: "GST composition", UNREGISTERED: "Not GST registered" };
const FLAGS: Record<string, string> = { tax_audit: "Tax audit applies", tds: "Deducts TDS (has TAN)", payroll: "Has PF / ESI employees" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const AFTER = ["the same month", "the next month", "the 2nd month after", "the 3rd month after"];
const ordinal = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
const dayText = (d?: number) => (d === 31 ? "last day" : ordinal(d ?? 1));

export function describeDue(r: Rule): string {
  if (r.frequency === "YEARLY") {
    const dates = (r.due.dates ?? []).map((d) => `${dayText(d.day)} ${MONTHS[d.month - 1]}${d.label ? ` (${d.label})` : ""}`).join(", ");
    return `Every year: ${dates || "no date set"}${r.due.within_fy ? " — within the financial year" : " — after the year ends"}`;
  }
  const base = `${r.frequency === "MONTHLY" ? "Every month" : "Every quarter"}, due on the ${dayText(r.due.day)} of ${AFTER[r.due.months_after ?? 1] ?? `${r.due.months_after} months after`}`;
  const ex = Object.keys(r.frequency === "MONTHLY" ? r.month_overrides ?? {} : r.quarter_overrides ?? {}).length;
  return base + (r.months_in_quarter?.length ? ` (only month ${r.months_in_quarter.join(" & ")} of each quarter)` : "") + (ex ? ` · ${ex} exception${ex > 1 ? "s" : ""}` : "")
    + (r.due.state_day && Object.keys(r.due.state_day).length ? " · state-specific days" : "");
}

function whoText(r: Rule): string {
  const a = r.applies ?? {};
  const parts = [
    a.gst?.length ? a.gst.map((g) => GST_TYPES[g] ?? g).join(" / ") : null,
    a.gst_filing ? (a.gst_filing === "MONTHLY" ? "monthly filers" : "quarterly (QRMP) filers") : null,
    a.entities?.length ? a.entities.map((e) => (ENTITY_TYPES[e] ?? e).split(" (")[0]).join(", ") : null,
    ...(a.requires ?? []).map((f) => FLAGS[f] ?? f),
    ...(a.excludes ?? []).map((f) => `not if: ${(FLAGS[f] ?? f).toLowerCase()}`),
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Every business";
}

export function ComplianceRulesEditor({ rules, onChange, links }: { rules: Rule[]; onChange: (r: Rule[]) => void; links: string[] }) {
  const [editing, setEditing] = useState<{ index: number; rule: Rule } | null>(null);
  const [law, setLaw] = useState("");
  const shown = rules.map((r, i) => ({ r, i })).filter(({ r }) => !law || r.authority === law);

  function save(rule: Rule) {
    if (!editing) return;
    const next = [...rules];
    if (editing.index < 0) next.push(rule); else next[editing.index] = rule;
    onChange(next);
    setEditing(null);
  }
  const blank: Rule = { code: "", name: "", authority: "GST", frequency: "MONTHLY", due: { day: 20, months_after: 1 }, applies: {}, description: "", penalty: "" };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Select className="!w-auto" value={law} onChange={(e) => setLaw(e.target.value)}>
          <option value="">All laws ({rules.length})</option>
          {Object.entries(LAWS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Button variant="secondary" onClick={() => setEditing({ index: -1, rule: blank })}><Plus size={15} /> Add filing</Button>
        <span className="text-xs text-gray-500">Changes are saved with the “Save change” bar below, effective from the date you choose.</span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="tbl">
          <thead><tr><th>Filing</th><th>Who</th><th>Due</th><th>On</th><th /></tr></thead>
          <tbody>
            {shown.map(({ r, i }) => (
              <tr key={r.code + i} className={r.disabled ? "opacity-50" : ""}>
                <td><div className="font-medium">{r.name}</div><div className="text-xs text-gray-500">{LAWS[r.authority ?? ""] ?? r.authority}</div></td>
                <td className="text-xs">{whoText(r)}</td>
                <td className="text-xs">{describeDue(r)}</td>
                <td>
                  <input type="checkbox" aria-label="Show this filing" checked={!r.disabled}
                    onChange={(e) => onChange(rules.map((x, j) => (j === i ? { ...x, disabled: !e.target.checked } : x)))} />
                </td>
                <td className="whitespace-nowrap text-right">
                  <button type="button" className="mr-2 text-gray-400 hover:text-gray-700" title="Edit" onClick={() => setEditing({ index: i, rule: structuredClone(r) })}><Pencil size={15} /></button>
                  <button type="button" className="mr-2 text-gray-400 hover:text-gray-700" title="Copy as a new filing"
                    onClick={() => setEditing({ index: -1, rule: { ...structuredClone(r), code: "", name: `${r.name} (copy)` } })}><Copy size={15} /></button>
                  <button type="button" className="text-gray-400 hover:text-red-600" title="Delete"
                    onClick={() => confirm(`Delete “${r.name}” from every business's calendar? (Switching it off keeps it for later.)`) && onChange(rules.filter((_, j) => j !== i))}><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && <RuleForm initial={editing.rule} codes={rules.filter((_, j) => j !== editing.index).map((r) => r.code)} links={links}
        onCancel={() => setEditing(null)} onSave={save} />}
    </div>
  );
}

function toggle(list: string[] | undefined, v: string, on: boolean): string[] {
  const s = new Set(list ?? []);
  if (on) s.add(v); else s.delete(v);
  return [...s];
}

function RuleForm({ initial, codes, links, onCancel, onSave }: {
  initial: Rule; codes: string[]; links: string[]; onCancel: () => void; onSave: (r: Rule) => void;
}) {
  const [r, setR] = useState<Rule>(initial);
  const [err, setErr] = useState<string | null>(null);
  const a = r.applies ?? {};
  const setA = (patch: Partial<NonNullable<Rule["applies"]>>) => setR({ ...r, applies: { ...a, ...patch } });
  const setDue = (patch: Partial<DueSpec>) => setR({ ...r, due: { ...r.due, ...patch } });
  const overridesKey = r.frequency === "MONTHLY" ? "month_overrides" : "quarter_overrides";
  const overrides = (r[overridesKey] ?? {}) as Record<string, DueSpec>;
  const initialStates = Object.entries(initial.due.state_day ?? {});
  const [sdDay, setSdDay] = useState(initialStates.length ? String(initialStates[0][1]) : "");
  const [sdCodes, setSdCodes] = useState(initialStates.map(([c]) => c).join(", "));
  function setStates(day: string, codesText: string) {
    setSdDay(day); setSdCodes(codesText);
    const d = Number(day);
    const list = codesText.split(/[,\s]+/).filter((c) => /^\d{1,2}$/.test(c)).map((c) => c.padStart(2, "0"));
    setDue({ state_day: d >= 1 && d <= 31 ? Object.fromEntries(list.map((c) => [c, d])) : {} });
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!r.name.trim()) return setErr("Give the filing a name");
    const code = r.code || r.name.toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 24) || "FILING";
    let unique = code, n = 2;
    while (codes.includes(unique)) unique = `${code}_${n++}`;
    if (r.frequency === "YEARLY" && !(r.due.dates ?? []).length) return setErr("Add at least one due date");
    const clean: Rule = { ...r, code: unique };
    if (r.frequency === "YEARLY") clean.due = { dates: r.due.dates, within_fy: !!r.due.within_fy };
    else clean.due = { day: r.due.day ?? 20, months_after: r.due.months_after ?? 1, ...(r.due.state_day && Object.keys(r.due.state_day).length ? { state_day: r.due.state_day } : {}) };
    if (r.frequency !== "MONTHLY") { delete clean.months_in_quarter; delete clean.month_overrides; }
    if (r.frequency !== "QUARTERLY") delete clean.quarter_overrides;
    onSave(clean);
  }

  const check = (label: string, checked: boolean, on: (v: boolean) => void) => (
    <label key={label} className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={checked} onChange={(e) => on(e.target.checked)} /> {label}</label>
  );

  return (
    <Modal title={initial.code ? `Edit — ${initial.name}` : "Add filing"} onClose={onCancel} wide>
      <form onSubmit={submit} className="max-h-[75vh] space-y-5 overflow-y-auto pr-1">
        <ErrorBox message={err} />
        <section className="grid gap-3 sm:grid-cols-3">
          <Field label="Name of the filing" className="sm:col-span-2"><Input value={r.name} onChange={(e) => setR({ ...r, name: e.target.value })} placeholder="e.g. GSTR-3B (monthly)" /></Field>
          <Field label="Law"><Select value={r.authority ?? "OTHER"} onChange={(e) => setR({ ...r, authority: e.target.value })}>{Object.entries(LAWS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
          <Field label="What it is (shown to businesses)" className="sm:col-span-3"><Input value={r.description ?? ""} onChange={(e) => setR({ ...r, description: e.target.value })} /></Field>
          <Field label="If filed late (penalty / consequence)" className="sm:col-span-3"
            hint="Write {late_fee_per_day} or {interest_rate} to show the current values from the GST rules section.">
            <Textarea rows={2} value={r.penalty ?? ""} onChange={(e) => setR({ ...r, penalty: e.target.value })} />
          </Field>
          <Field label="Portal button opens">
            <Select value={r.link ?? ""} onChange={(e) => setR({ ...r, link: e.target.value || null })}>
              <option value="">No button</option>{links.map((k) => <option key={k} value={k}>{k.replace(/_/g, " ")}</option>)}
            </Select>
          </Field>
        </section>

        <section className="space-y-2 rounded-lg border border-gray-200 p-3">
          <h3 className="text-sm font-semibold text-gray-900">Who must file <span className="font-normal text-gray-500">— leave a group empty to mean “everyone”</span></h3>
          <div className="flex flex-wrap gap-x-4 gap-y-1">{Object.entries(GST_TYPES).map(([k, v]) => check(v, !!a.gst?.includes(k), (on) => setA({ gst: toggle(a.gst, k, on) })))}</div>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            GST returns filed
            <Select className="!w-auto" value={a.gst_filing ?? ""} onChange={(e) => setA({ gst_filing: e.target.value || undefined })}>
              <option value="">monthly or quarterly</option><option value="MONTHLY">monthly only</option><option value="QUARTERLY">quarterly (QRMP) only</option>
            </Select>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1">{Object.entries(ENTITY_TYPES).map(([k, v]) => check(v.split(" (")[0], !!a.entities?.includes(k), (on) => setA({ entities: toggle(a.entities, k, on) })))}</div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div><div className="text-xs font-medium text-gray-600">Only if the business says</div>{Object.entries(FLAGS).map(([k, v]) => check(v, !!a.requires?.includes(k), (on) => setA({ requires: toggle(a.requires, k, on) })))}</div>
            <div><div className="text-xs font-medium text-gray-600">Not if the business says</div>{Object.entries(FLAGS).map(([k, v]) => check(v, !!a.excludes?.includes(k), (on) => setA({ excludes: toggle(a.excludes, k, on) })))}</div>
          </div>
        </section>

        <section className="space-y-3 rounded-lg border border-gray-200 p-3">
          <h3 className="text-sm font-semibold text-gray-900">When it is due</h3>
          <div className="flex flex-wrap gap-2">
            {(["MONTHLY", "QUARTERLY", "YEARLY"] as const).map((f) => (
              <button key={f} type="button" onClick={() => setR({ ...r, frequency: f, due: f === "YEARLY" ? { dates: r.due.dates?.length ? r.due.dates : [{ month: 7, day: 31 }] } : { day: r.due.day ?? 20, months_after: r.due.months_after ?? 1 } })}
                className={`rounded-md border px-3 py-1.5 text-sm ${r.frequency === f ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-200"}`}>
                {f === "MONTHLY" ? "Every month" : f === "QUARTERLY" ? "Every quarter" : "Every year"}
              </button>
            ))}
          </div>
          {r.frequency !== "YEARLY" ? (
            <>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                Due on the
                <Select className="!w-auto" value={r.due.day ?? 20} onChange={(e) => setDue({ day: Number(e.target.value) })}>
                  {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>{dayText(d)}</option>)}
                </Select>
                of
                <Select className="!w-auto" value={r.due.months_after ?? 1} onChange={(e) => setDue({ months_after: Number(e.target.value) })}>
                  {AFTER.map((t, i) => <option key={i} value={i}>{t}</option>)}
                </Select>
                {r.frequency === "QUARTERLY" ? "after the quarter ends" : "after the month"}
              </div>
              {r.frequency === "MONTHLY" && (
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  Only in these months of each quarter:
                  {[1, 2, 3].map((m) => check(`${ordinal(m)} month`, !r.months_in_quarter?.length || r.months_in_quarter.includes(m), (on) => {
                    const cur = new Set(r.months_in_quarter?.length ? r.months_in_quarter : [1, 2, 3]);
                    if (on) cur.add(m); else cur.delete(m);
                    const list = [...cur].sort();
                    setR({ ...r, months_in_quarter: list.length === 3 ? undefined : list });
                  }))}
                </div>
              )}
              <div className="flex flex-wrap items-center gap-2 text-sm">
                Different day for some states:
                <Input className="!w-20" inputMode="numeric" placeholder="day" value={sdDay} onChange={(e) => setStates(e.target.value, sdCodes)} />
                for state codes
                <Input className="!w-72" placeholder="e.g. 27, 29, 33" value={sdCodes} onChange={(e) => setStates(sdDay, e.target.value)} />
              </div>
              <div className="space-y-1 text-sm">
                <div className="font-medium text-gray-700">Exceptions (e.g. March TDS due 30 April)</div>
                {Object.entries(overrides).map(([k, o]) => (
                  <div key={k} className="flex flex-wrap items-center gap-2">
                    For {r.frequency === "MONTHLY" ? MONTHS[Number(k) - 1] : `Q${k}`}: due on the
                    <Select className="!w-auto" value={o.day ?? 1} onChange={(e) => setR({ ...r, [overridesKey]: { ...overrides, [k]: { ...o, day: Number(e.target.value) } } })}>
                      {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>{dayText(d)}</option>)}
                    </Select>
                    of
                    <Select className="!w-auto" value={o.months_after ?? 1} onChange={(e) => setR({ ...r, [overridesKey]: { ...overrides, [k]: { ...o, months_after: Number(e.target.value) } } })}>
                      {AFTER.map((t, i) => <option key={i} value={i}>{t}</option>)}
                    </Select>
                    <button type="button" className="text-gray-400 hover:text-red-600" onClick={() => { const n = { ...overrides }; delete n[k]; setR({ ...r, [overridesKey]: n }); }}><Trash2 size={14} /></button>
                  </div>
                ))}
                <Select className="!w-auto" value="" onChange={(e) => e.target.value && setR({ ...r, [overridesKey]: { ...overrides, [e.target.value]: { day: r.due.day, months_after: r.due.months_after ?? 1 } } })}>
                  <option value="">+ Add an exception for…</option>
                  {(r.frequency === "MONTHLY" ? MONTHS.map((m, i) => [String(i + 1), m]) : [["1", "Q1 (Apr–Jun)"], ["2", "Q2 (Jul–Sep)"], ["3", "Q3 (Oct–Dec)"], ["4", "Q4 (Jan–Mar)"]])
                    .filter(([k]) => !(k in overrides)).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </Select>
              </div>
            </>
          ) : (
            <div className="space-y-2 text-sm">
              {(r.due.dates ?? []).map((d, i) => (
                <div key={i} className="flex flex-wrap items-center gap-2">
                  <Select className="!w-auto" value={d.day} onChange={(e) => setDue({ dates: r.due.dates!.map((x, j) => (j === i ? { ...x, day: Number(e.target.value) } : x)) })}>
                    {Array.from({ length: 31 }, (_, k) => k + 1).map((n) => <option key={n} value={n}>{dayText(n)}</option>)}
                  </Select>
                  <Select className="!w-auto" value={d.month} onChange={(e) => setDue({ dates: r.due.dates!.map((x, j) => (j === i ? { ...x, month: Number(e.target.value) } : x)) })}>
                    {MONTHS.map((m, k) => <option key={m} value={k + 1}>{m}</option>)}
                  </Select>
                  <Input className="!w-56" placeholder="Label (optional), e.g. 1st instalment" value={d.label ?? ""}
                    onChange={(e) => setDue({ dates: r.due.dates!.map((x, j) => (j === i ? { ...x, label: e.target.value || undefined } : x)) })} />
                  <button type="button" className="text-gray-400 hover:text-red-600" onClick={() => setDue({ dates: r.due.dates!.filter((_, j) => j !== i) })}><Trash2 size={14} /></button>
                </div>
              ))}
              <Button type="button" variant="ghost" onClick={() => setDue({ dates: [...(r.due.dates ?? []), { month: 9, day: 30 }] })}><Plus size={14} /> Add date</Button>
              <label className="flex items-center gap-2"><input type="checkbox" checked={!!r.due.within_fy} onChange={(e) => setDue({ within_fy: e.target.checked })} />
                The dates fall <b>inside</b> the financial year (like advance tax). Unticked: in the year after it ends (like returns and annual filings).</label>
            </div>
          )}
          <p className="rounded bg-gray-50 px-2 py-1 text-xs text-gray-600">{describeDue(r)}</p>
        </section>

        <section className="grid gap-3 rounded-lg border border-gray-200 p-3 sm:grid-cols-3">
          <h3 className="text-sm font-semibold text-gray-900 sm:col-span-3">Late fee estimate shown when overdue <span className="font-normal text-gray-500">(optional)</span></h3>
          <Field label="Per day">
            <Select value={r.fee_per_day === "late_fee_per_day" ? "cfg" : r.fee_per_day == null ? "" : "num"}
              onChange={(e) => setR({ ...r, fee_per_day: e.target.value === "cfg" ? "late_fee_per_day" : e.target.value === "num" ? 100 : null })}>
              <option value="">No estimate</option><option value="cfg">GST late fee setting</option><option value="num">Fixed amount</option>
            </Select>
          </Field>
          {typeof r.fee_per_day === "number" && <Field label="Amount per day (₹)"><Input inputMode="decimal" value={r.fee_per_day} onChange={(e) => setR({ ...r, fee_per_day: Number(e.target.value) || 0 })} /></Field>}
          {r.fee_per_day != null && <Field label="Maximum (₹)" hint="Leave empty for no maximum"><Input inputMode="decimal" value={r.fee_cap ?? ""} onChange={(e) => setR({ ...r, fee_cap: e.target.value ? Number(e.target.value) : null })} /></Field>}
        </section>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button type="submit">{initial.code ? "Update filing" : "Add filing"}</Button>
        </div>
      </form>
    </Modal>
  );
}
