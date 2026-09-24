"use client";

import { Field, Input, Select } from "@/components/ui";
import { fyRange, monthRange } from "@/lib/format";

export type Period = { from: string; to: string };

const PRESETS: Record<string, () => Period> = {
  "This month": () => monthRange(0),
  "Last month": () => monthRange(-1),
  "This financial year": () => fyRange(),
};

export function PeriodPicker({ value, onChange }: { value: Period; onChange: (p: Period) => void }) {
  const preset = Object.entries(PRESETS).find(([, f]) => {
    const p = f();
    return p.from === value.from && p.to === value.to;
  })?.[0] ?? "Custom";
  return (
    <div className="no-print mb-4 flex flex-wrap items-end gap-2">
      <Field label="Period">
        <Select value={preset} onChange={(e) => PRESETS[e.target.value] && onChange(PRESETS[e.target.value]())}>
          {Object.keys(PRESETS).map((k) => <option key={k}>{k}</option>)}
          <option disabled>Custom</option>
        </Select>
      </Field>
      <Field label="From"><Input type="date" value={value.from} onChange={(e) => onChange({ ...value, from: e.target.value })} /></Field>
      <Field label="To"><Input type="date" value={value.to} onChange={(e) => onChange({ ...value, to: e.target.value })} /></Field>
    </div>
  );
}
