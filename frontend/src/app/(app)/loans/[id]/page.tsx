"use client";

import { Trash2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { AccountSelect } from "@/components/AccountSelect";
import { Button, Card, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, money, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Loan } from "@/lib/types";

interface LoanDetail {
  loan: Loan; opening: number; closing: number;
  entries: { id: string; date: string; type: string; principal: number; interest: number; paid: number; received: number; balance: number; note: string | null }[];
}

const LABEL: Record<string, string> = { DISBURSEMENT: "Loan received", EMI: "EMI / repayment", CHARGES: "Charges" };

export default function LoanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, reload } = useFetch<LoanDetail>(`/loans/${id}`);
  const [f, setF] = useState({ type: "EMI", principal: "", interest: "", date: today(), account_id: "", note: "" });
  const [formError, setFormError] = useState<string | null>(null);

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      await api(`/loans/${id}/txns`, { body: { type: f.type, principal: Number(f.principal || 0), interest: Number(f.interest || 0),
        date: f.date, account_id: f.account_id || null, note: f.note || null } });
      setF({ ...f, principal: "", interest: "", note: "" });
      reload();
    } catch (err) {
      setFormError((err as Error).message);
    }
  }

  return (
    <>
      <PageHeader title={data.loan.name} sub={[data.loan.lender, data.loan.interest_rate !== null ? `${data.loan.interest_rate}% p.a.` : null, `Outstanding ${money(data.loan.outstanding)}`].filter(Boolean).join(" · ")} />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-5">
          <h2 className="mb-3 font-semibold text-gray-900">Add entry</h2>
          <form onSubmit={save} className="space-y-3">
            <ErrorBox message={formError} />
            <Field label="Type">
              <Select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>
                <option value="EMI">EMI / repayment</option>
                <option value="DISBURSEMENT">Loan amount received</option>
                <option value="CHARGES">Processing fee / charges</option>
              </Select>
            </Field>
            {f.type !== "CHARGES" && (
              <Field label={f.type === "EMI" ? "Principal part" : "Amount received"}>
                <Input type="number" step="0.01" min="0" value={f.principal} onChange={(e) => setF({ ...f, principal: e.target.value })} />
              </Field>
            )}
            {f.type !== "DISBURSEMENT" && (
              <Field label={f.type === "EMI" ? "Interest part" : "Charges"}>
                <Input type="number" step="0.01" min="0" value={f.interest} onChange={(e) => setF({ ...f, interest: e.target.value })} />
              </Field>
            )}
            <Field label="Date"><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></Field>
            <Field label={f.type === "DISBURSEMENT" ? "Received in" : "Paid from"}><AccountSelect value={f.account_id} onChange={(v) => setF({ ...f, account_id: v })} /></Field>
            <Field label="Note"><Input value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
            <Button type="submit" className="w-full">Save</Button>
          </form>
        </Card>
        <Card className="overflow-x-auto lg:col-span-2">
          <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Loan statement</h2>
          <table className="tbl">
            <thead><tr><th>Date</th><th>Type</th><th className="num">Received</th><th className="num">Principal</th><th className="num">Interest</th><th className="num">Outstanding</th><th /></tr></thead>
            <tbody>
              <tr className="bg-gray-50"><td>{fmtDate(data.loan.opening_date)}</td><td colSpan={4} className="text-gray-600">Opening outstanding</td><td className="num">{money(data.opening)}</td><td /></tr>
              {data.entries.map((e) => (
                <tr key={e.id}>
                  <td>{fmtDate(e.date)}</td>
                  <td>{LABEL[e.type]}{e.note && <div className="text-xs text-gray-500">{e.note}</div>}</td>
                  <td className="num">{e.received ? money(e.received) : ""}</td>
                  <td className="num">{e.type === "EMI" && e.principal ? money(e.principal) : ""}</td>
                  <td className="num">{e.interest ? money(e.interest) : ""}</td>
                  <td className="num">{money(e.balance)}</td>
                  <td><button className="text-gray-400 hover:text-red-600" aria-label="Delete" onClick={async () => { if (confirm("Delete entry?")) { await api(`/loans/${id}/txns/${e.id}`, { method: "DELETE" }); reload(); } }}><Trash2 size={15} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  );
}
