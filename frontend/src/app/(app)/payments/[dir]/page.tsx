"use client";

import { Download, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { useState } from "react";
import { ImportButton } from "@/components/ImportDialog";
import { Button, Card, Empty, ErrorBox, Field, Input, LinkButton, Loading, PageHeader } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PAYMENT_MODES } from "@/lib/constants";
import { downloadCsv, fmtDate, fyRange, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Payment } from "@/lib/types";

export default function PaymentsPage() {
  const { dir } = useParams<{ dir: string }>();
  if (dir !== "in" && dir !== "out") notFound();
  const type = dir === "in" ? "IN" : "OUT";
  const { business } = useAuth();
  const [range, setRange] = useState(fyRange());
  const { data, error, loading, reload } = useFetch<Payment[]>(
    `/payments${qs({ type, date_from: range.from, date_to: range.to, limit: 1000 })}`,
  );
  const total = data?.reduce((s, p) => s + p.amount, 0) ?? 0;
  const canDelete = business?.role === "OWNER" || business?.role === "ADMIN";

  async function remove(p: Payment) {
    if (!confirm(`Delete payment ${p.number} of ${money(p.amount)}? Bills it settled will become unpaid again.`)) return;
    await api(`/payments/${p.id}`, { method: "DELETE" });
    reload();
  }

  return (
    <>
      <PageHeader
        title={type === "IN" ? "Payment In" : "Payment Out"}
        sub={`${data?.length ?? 0} payments · ${money(total)}`}
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => data && downloadCsv(`payments-${dir}.csv`, ["Date", "Number", "Party", "Mode", "Reference", "Amount", "Allocated"],
                data.map((p) => [p.date, p.number, p.party_name, p.mode, p.reference, p.amount, p.allocated]))}
            >
              <Download size={16} /> Export
            </Button>
            <ImportButton entity={`payments-${dir}`} title={type === "IN" ? "payments received" : "payments made"} onDone={reload} />
            <LinkButton href={`/payments/${dir}/new`}><Plus size={16} /> {type === "IN" ? "Receive payment" : "Make payment"}</LinkButton>
          </>
        }
      />
      <div className="mb-3 flex flex-wrap gap-2">
        <Field label="From"><Input type="date" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} /></Field>
        <Field label="To"><Input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} /></Field>
      </div>
      <ErrorBox message={error} />
      <Card className="overflow-x-auto">
        {loading && !data ? (
          <Loading />
        ) : !data?.length ? (
          <Empty title="No payments in this period" />
        ) : (
          <table className="tbl">
            <thead>
              <tr><th>Date</th><th>Number</th><th>Party</th><th>Mode</th><th>Settled bills</th><th className="num">Amount</th><th /></tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}>
                  <td>{fmtDate(p.date)}</td>
                  <td className="font-medium">{p.number}</td>
                  <td>{p.party_id ? <Link href={`/parties/${p.party_id}`} className="text-brand-600 hover:underline">{p.party_name}</Link> : "Cash"}</td>
                  <td>
                    {PAYMENT_MODES[p.mode]} · {p.account_name}
                    {p.reference && <div className="text-xs text-gray-500">{p.reference}</div>}
                    {p.cheque_status && (
                      <div className={`text-xs ${p.cheque_status === "BOUNCED" ? "text-red-700" : p.cheque_status === "OPEN" ? "text-amber-700" : "text-emerald-700"}`}>
                        Cheque {p.cheque_status.toLowerCase()}
                      </div>
                    )}
                    {p.tds_amount > 0 && <div className="text-xs text-gray-500">TDS {money(p.tds_amount)}</div>}
                  </td>
                  <td className="text-xs">
                    {p.allocations.map((a) => (
                      <Link key={a.voucher_id} href={`/doc/${a.voucher_id}`} className="mr-2 text-brand-600 hover:underline">
                        {a.voucher_number} ({money(a.amount)})
                      </Link>
                    ))}
                    {p.amount + p.tds_amount - p.allocated > 0.005 && p.cheque_status !== "BOUNCED" && <span className="text-amber-700">Advance {money(p.amount + p.tds_amount - p.allocated)}</span>}
                  </td>
                  <td className="num font-medium">{money(p.amount)}</td>
                  <td>
                    {canDelete && (
                      <button className="text-gray-400 hover:text-red-600" aria-label="Delete payment" onClick={() => remove(p)}>
                        <Trash2 size={16} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
