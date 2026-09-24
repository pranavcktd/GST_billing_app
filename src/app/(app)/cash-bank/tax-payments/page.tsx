"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";
import { AccountSelect } from "@/components/AccountSelect";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, money, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface TaxPayment { id: string; date: string; type: "GST" | "TDS" | "TCS"; amount: number; reference: string | null; period: string | null; note: string | null }

export default function TaxPaymentsPage() {
  const { data, error, reload } = useFetch<TaxPayment[]>("/tax-payments");
  const [f, setF] = useState({ type: "GST", amount: "", date: today(), account_id: "", reference: "", period: "" });
  const [formError, setFormError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      await api("/tax-payments", { body: { ...f, amount: Number(f.amount), account_id: f.account_id || null,
        reference: f.reference || null, period: f.period || null } });
      setF({ ...f, amount: "", reference: "" });
      reload();
    } catch (err) {
      setFormError((err as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Tax payments" sub="GST, TDS and TCS deposited with the government (challans). These reduce the tax payable shown in the balance sheet." />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-5">
          <h2 className="mb-3 font-semibold text-gray-900">Record challan</h2>
          <form onSubmit={save} className="space-y-3">
            <ErrorBox message={formError} />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Tax">
                <Select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>
                  <option>GST</option><option>TDS</option><option>TCS</option>
                </Select>
              </Field>
              <Field label="Period" hint="e.g. Aug-2026 / Q2"><Input value={f.period} onChange={(e) => setF({ ...f, period: e.target.value })} /></Field>
            </div>
            <Field label="Amount" required><Input type="number" min="0.01" step="0.01" required value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></Field>
            <Field label="Date"><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></Field>
            <Field label="CIN / challan no."><Input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} /></Field>
            <Field label="Paid from"><AccountSelect value={f.account_id} onChange={(v) => setF({ ...f, account_id: v })} /></Field>
            <Button type="submit" className="w-full">Save</Button>
          </form>
        </Card>
        <Card className="overflow-x-auto lg:col-span-2">
          <ErrorBox message={error} />
          {!data ? <Loading /> : data.length === 0 ? <Empty title="No tax payments yet" /> : (
            <table className="tbl">
              <thead><tr><th>Date</th><th>Tax</th><th>Period</th><th>Challan</th><th className="num">Amount</th><th /></tr></thead>
              <tbody>
                {data.map((x) => (
                  <tr key={x.id}>
                    <td>{fmtDate(x.date)}</td><td>{x.type}</td><td>{x.period}</td><td>{x.reference}</td>
                    <td className="num">{money(x.amount)}</td>
                    <td><button className="text-gray-400 hover:text-red-600" aria-label="Delete" onClick={async () => { if (confirm("Delete?")) { await api(`/tax-payments/${x.id}`, { method: "DELETE" }); reload(); } }}><Trash2 size={15} /></button></td>
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
