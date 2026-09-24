"use client";

import { useState } from "react";
import { Card, Field, Input, PageHeader, Select } from "@/components/ui";
import { GST_RATES } from "@/lib/constants";
import { money } from "@/lib/format";

const r2 = (n: number) => Math.round(n * 100) / 100;

export default function GstCalculator() {
  const [amount, setAmount] = useState("1000");
  const [rate, setRate] = useState(18);
  const [mode, setMode] = useState<"add" | "remove">("add");
  const [inter, setInter] = useState(false);

  const a = Number(amount) || 0;
  const base = mode === "add" ? a : r2((a * 100) / (100 + rate));
  const tax = mode === "add" ? r2((a * rate) / 100) : r2(a - base);
  const total = mode === "add" ? r2(a + tax) : a;
  const half = r2(tax / 2);

  return (
    <>
      <PageHeader title="GST calculator" />
      <div className="grid max-w-4xl gap-5 md:grid-cols-2">
        <Card className="space-y-4 p-5">
          <Field label="Amount (₹)"><Input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus /></Field>
          <Field label="GST rate">
            <div className="flex flex-wrap gap-1.5">
              {GST_RATES.map((r) => (
                <button key={r} onClick={() => setRate(r)} className={`rounded-lg border px-3 py-1.5 text-sm ${rate === r ? "border-brand-500 bg-brand-50 font-medium text-brand-700" : "border-gray-200"}`}>{r}%</button>
              ))}
            </div>
          </Field>
          <Field label="Calculation">
            <Select value={mode} onChange={(e) => setMode(e.target.value as "add" | "remove")}>
              <option value="add">Add GST (amount is before tax)</option>
              <option value="remove">Remove GST (amount includes tax)</option>
            </Select>
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={inter} onChange={(e) => setInter(e.target.checked)} /> Inter-state supply (IGST)
          </label>
        </Card>
        <Card className="p-5">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-600">Taxable value</dt><dd className="tabular-nums">{money(base)}</dd></div>
            {inter ? (
              <div className="flex justify-between"><dt className="text-gray-600">IGST @ {rate}%</dt><dd className="tabular-nums">{money(tax)}</dd></div>
            ) : (
              <>
                <div className="flex justify-between"><dt className="text-gray-600">CGST @ {rate / 2}%</dt><dd className="tabular-nums">{money(half)}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-600">SGST @ {rate / 2}%</dt><dd className="tabular-nums">{money(r2(tax - half))}</dd></div>
              </>
            )}
            <div className="flex justify-between"><dt className="text-gray-600">Total GST</dt><dd className="tabular-nums">{money(tax)}</dd></div>
            <div className="flex justify-between border-t border-gray-200 pt-2 text-lg font-semibold"><dt>Total</dt><dd className="tabular-nums">{money(total)}</dd></div>
          </dl>
        </Card>
      </div>
    </>
  );
}
