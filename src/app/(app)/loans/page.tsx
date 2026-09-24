"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { money, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Loan } from "@/lib/types";

export default function LoansPage() {
  const { data, error, reload } = useFetch<Loan[]>("/loans");
  const [f, setF] = useState<null | { name: string; lender: string; account_no: string; interest_rate: string; opening_balance: string; opening_date: string; notes: string }>(null);
  const [formError, setFormError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!f) return;
    setFormError(null);
    try {
      await api("/loans", { body: { name: f.name, lender: f.lender || null, account_no: f.account_no || null,
        interest_rate: f.interest_rate ? Number(f.interest_rate) : null, opening_balance: Number(f.opening_balance || 0),
        opening_date: f.opening_date || null, notes: f.notes || null } });
      setF(null);
      reload();
    } catch (err) {
      setFormError((err as Error).message);
    }
  }

  const total = data?.reduce((s, l) => s + l.outstanding, 0) ?? 0;
  return (
    <>
      <PageHeader title="Loan accounts" sub={`Total outstanding ${money(total)}`}
        actions={<Button onClick={() => setF({ name: "", lender: "", account_no: "", interest_rate: "", opening_balance: "", opening_date: today(), notes: "" })}><Plus size={16} /> Add loan</Button>} />
      <ErrorBox message={error} />
      <Card className="overflow-x-auto">
        {!data ? <Loading /> : data.length === 0 ? <Empty title="No loans recorded" /> : (
          <table className="tbl">
            <thead><tr><th>Loan</th><th>Lender</th><th className="num">Interest</th><th className="num">Outstanding</th></tr></thead>
            <tbody>
              {data.map((l) => (
                <tr key={l.id} className={l.is_active ? "" : "text-gray-400"}>
                  <td><Link href={`/loans/${l.id}`} className="font-medium text-brand-600 hover:underline">{l.name}</Link></td>
                  <td>{l.lender}</td>
                  <td className="num">{l.interest_rate !== null ? `${l.interest_rate}%` : ""}</td>
                  <td className="num">{money(l.outstanding)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {f && (
        <Modal title="Add loan account" onClose={() => setF(null)}>
          <form onSubmit={save} className="space-y-3">
            <ErrorBox message={formError} />
            <Field label="Loan name" required><Input required value={f.name} placeholder="SBI Term Loan" onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Lender"><Input value={f.lender} onChange={(e) => setF({ ...f, lender: e.target.value })} /></Field>
              <Field label="Loan a/c no."><Input value={f.account_no} onChange={(e) => setF({ ...f, account_no: e.target.value })} /></Field>
              <Field label="Interest rate % p.a."><Input type="number" step="0.01" value={f.interest_rate} onChange={(e) => setF({ ...f, interest_rate: e.target.value })} /></Field>
              <Field label="Outstanding as on" hint="Existing balance; add new disbursements separately">
                <Input type="date" value={f.opening_date} onChange={(e) => setF({ ...f, opening_date: e.target.value })} />
              </Field>
              <Field label="Opening outstanding" className="col-span-2"><Input type="number" step="0.01" value={f.opening_balance} onChange={(e) => setF({ ...f, opening_balance: e.target.value })} /></Field>
            </div>
            <Field label="Notes"><Textarea rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
            <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={() => setF(null)}>Cancel</Button><Button type="submit">Save</Button></div>
          </form>
        </Modal>
      )}
    </>
  );
}
