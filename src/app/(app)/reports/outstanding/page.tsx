"use client";

import Link from "next/link";
import { Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

type Row = { id: string; name: string; phone: string | null; gstin: string | null; amount: number };
interface Outstanding { receivable: Row[]; payable: Row[]; total_receivable: number; total_payable: number }

function List({ title, rows, total, tone }: { title: string; rows: Row[]; total: number; tone: string }) {
  return (
    <Card className="overflow-x-auto">
      <div className="flex items-baseline justify-between px-5 pt-4 pb-2">
        <h2 className="font-semibold text-gray-900">{title}</h2>
        <span className={`font-semibold ${tone}`}>{money(total)}</span>
      </div>
      {rows.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">Nothing outstanding.</p> : (
        <table className="tbl">
          <thead><tr><th>Party</th><th>Phone</th><th className="num">Amount</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><Link href={`/parties/${r.id}`} className="text-brand-600 hover:underline">{r.name}</Link></td>
                <td>{r.phone ?? "—"}</td>
                <td className="num">{money(r.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export default function OutstandingPage() {
  const { data, error, loading } = useFetch<Outstanding>("/reports/outstanding");
  return (
    <>
      <PageHeader title="Outstanding" sub="Who owes you, and whom you owe" />
      <ErrorBox message={error} />
      {loading || !data ? <Loading /> : (
        <div className="grid gap-5 lg:grid-cols-2">
          <List title="Receivables (to collect)" rows={data.receivable} total={data.total_receivable} tone="text-emerald-700" />
          <List title="Payables (to pay)" rows={data.payable} total={data.total_payable} tone="text-red-700" />
        </div>
      )}
    </>
  );
}
