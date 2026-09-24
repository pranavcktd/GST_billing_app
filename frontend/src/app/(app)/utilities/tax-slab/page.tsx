"use client";

import { useState } from "react";
import { Button, Card, Empty, ErrorBox, Field, Input, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { GST_RATES } from "@/lib/constants";

interface Result { count: number; applied: boolean; items: { id: string; name: string; hsn: string | null; old: number; new: number }[] }

export default function TaxSlabPage() {
  const [f, setF] = useState({ from_rate: "12", hsn_prefix: "", category: "", new_rate: "5" });
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function send(preview: boolean) {
    setErr(null);
    try {
      setRes(await api<Result>("/tax-slab/update", { body: {
        new_rate: Number(f.new_rate), from_rate: f.from_rate === "" ? null : Number(f.from_rate),
        hsn_prefix: f.hsn_prefix || null, category: f.category || null, preview,
      } }));
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <>
      <PageHeader title="Update tax slab" sub="Change the GST rate on many items together — e.g. after the GST Council moves goods from 12% to 5%. Old bills keep the rate they were issued with." />
      <Card className="mb-5 p-5">
        <div className="grid gap-3 sm:grid-cols-5">
          <Field label="Items currently at">
            <Select value={f.from_rate} onChange={(e) => setF({ ...f, from_rate: e.target.value })}>
              <option value="">Any rate</option>{GST_RATES.map((r) => <option key={r} value={r}>{r}%</option>)}
            </Select>
          </Field>
          <Field label="HSN starts with" hint="optional"><Input value={f.hsn_prefix} onChange={(e) => setF({ ...f, hsn_prefix: e.target.value })} /></Field>
          <Field label="Item category" hint="optional"><Input value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} /></Field>
          <Field label="New GST rate">
            <Select value={f.new_rate} onChange={(e) => setF({ ...f, new_rate: e.target.value })}>{GST_RATES.map((r) => <option key={r} value={r}>{r}%</option>)}</Select>
          </Field>
          <div className="flex items-end"><Button variant="secondary" className="w-full" onClick={() => send(true)}>Preview items</Button></div>
        </div>
      </Card>
      <ErrorBox message={err} />
      {res && (
        <Card className="overflow-x-auto">
          <div className="flex items-center justify-between px-5 pt-4 pb-2">
            <h2 className="font-semibold text-gray-900">{res.applied ? `Updated ${res.count} item(s)` : `${res.count} item(s) will change`}</h2>
            {!res.applied && res.count > 0 && <Button onClick={() => confirm(`Change GST on ${res.count} items to ${f.new_rate}%?`) && send(false)}>Apply change</Button>}
          </div>
          {res.count === 0 ? <Empty title="No items match" /> : (
            <table className="tbl">
              <thead><tr><th>Item</th><th>HSN</th><th className="num">Old rate</th><th className="num">New rate</th></tr></thead>
              <tbody>{res.items.map((i) => <tr key={i.id}><td>{i.name}</td><td className="font-mono">{i.hsn}</td><td className="num">{i.old}%</td><td className="num font-medium">{i.new}%</td></tr>)}</tbody>
            </table>
          )}
        </Card>
      )}
    </>
  );
}
