"use client";

import { Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AccountSelect } from "@/components/AccountSelect";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, money, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Entry { id: string; date: string; type: "INTRODUCED" | "DRAWINGS"; amount: number; account_id: string; note: string | null }

export default function CapitalPage() {
  const { data, error, reload } = useFetch<Entry[]>("/capital");
  const [f, setF] = useState({ type: "INTRODUCED", amount: "", date: today(), account_id: "", note: "" });
  const [formError, setFormError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      await api("/capital", { body: { ...f, amount: Number(f.amount), account_id: f.account_id || null, note: f.note || null } });
      setF({ ...f, amount: "", note: "" });
      reload();
    } catch (err) {
      setFormError((err as Error).message);
    }
  }

  const introduced = data?.filter((x) => x.type === "INTRODUCED").reduce((s, x) => s + x.amount, 0) ?? 0;
  const drawings = data?.filter((x) => x.type === "DRAWINGS").reduce((s, x) => s + x.amount, 0) ?? 0;

  return (
    <>
      <PageHeader title="Capital & drawings" sub={`Introduced ${money(introduced)} · Drawings ${money(drawings)}`}
        actions={<Link href="/reports/r/capital" className="text-sm text-brand-600 hover:underline">Capital account report →</Link>} />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-5">
          <h2 className="mb-3 font-semibold text-gray-900">New entry</h2>
          <form onSubmit={save} className="space-y-3">
            <ErrorBox message={formError} />
            <Field label="Type">
              <Select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>
                <option value="INTRODUCED">Capital introduced (owner puts money in)</option>
                <option value="DRAWINGS">Drawings (owner takes money out)</option>
              </Select>
            </Field>
            <Field label="Amount" required><Input type="number" min="0.01" step="0.01" required value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></Field>
            <Field label="Date"><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></Field>
            <Field label="Account"><AccountSelect value={f.account_id} onChange={(v) => setF({ ...f, account_id: v })} /></Field>
            <Field label="Note"><Input value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
            <Button type="submit" className="w-full">Save</Button>
          </form>
        </Card>
        <Card className="overflow-x-auto lg:col-span-2">
          <ErrorBox message={error} />
          {!data ? <Loading /> : data.length === 0 ? <Empty title="No capital entries yet" /> : (
            <table className="tbl">
              <thead><tr><th>Date</th><th>Type</th><th>Note</th><th className="num">Amount</th><th /></tr></thead>
              <tbody>
                {data.map((x) => (
                  <tr key={x.id}>
                    <td>{fmtDate(x.date)}</td>
                    <td>{x.type === "INTRODUCED" ? "Capital introduced" : "Drawings"}</td>
                    <td className="text-gray-600">{x.note}</td>
                    <td className={`num ${x.type === "DRAWINGS" ? "text-red-700" : "text-emerald-700"}`}>{money(x.amount)}</td>
                    <td><button className="text-gray-400 hover:text-red-600" aria-label="Delete" onClick={async () => { if (confirm("Delete entry?")) { await api(`/capital/${x.id}`, { method: "DELETE" }); reload(); } }}><Trash2 size={15} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </>
  );
}
