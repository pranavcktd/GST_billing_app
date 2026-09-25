"use client";

import Link from "next/link";
import { useState } from "react";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader } from "@/components/ui";
import { qs } from "@/lib/api";
import { downloadCsv } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Row { id: string; created_at: string; user: string | null; action: string; entity: string; entity_id: string | null; summary: string; ip: string | null }
const PAGE = 100;
const TONE: Record<string, string> = { CREATE: "text-emerald-700", UPDATE: "text-brand-700", DELETE: "text-red-700", CANCEL: "text-red-700", ACTION: "text-gray-700" };

export default function AuditPage() {
  const [page, setPage] = useState(0);
  const [f, setF] = useState({ entity: "", date_from: "", date_to: "" });
  const { data, error, loading } = useFetch<{ total: number; rows: Row[] }>(`/audit${qs({ ...f, limit: PAGE, offset: page * PAGE })}`);

  return (
    <>
      <PageHeader title="Audit trail" sub="Every change — who made it and when. Entries cannot be edited or deleted (MCA audit-trail requirement)."
        actions={data && <Button variant="secondary" onClick={() => downloadCsv("audit-trail.csv", ["When", "User", "Action", "What", "IP"], data.rows.map((r) => [new Date(r.created_at).toLocaleString("en-IN"), r.user, r.action, r.summary, r.ip]))}>Export</Button>} />
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <Field label="Search type"><Input placeholder="invoice, payment, party…" value={f.entity} onChange={(e) => { setPage(0); setF({ ...f, entity: e.target.value }); }} /></Field>
        <Field label="From"><Input type="date" value={f.date_from} onChange={(e) => { setPage(0); setF({ ...f, date_from: e.target.value }); }} /></Field>
        <Field label="To"><Input type="date" value={f.date_to} onChange={(e) => { setPage(0); setF({ ...f, date_to: e.target.value }); }} /></Field>
      </div>
      <ErrorBox message={error} />
      <Card className="overflow-x-auto">
        {loading && !data ? <Loading /> : !data?.rows.length ? <Empty title="No activity recorded yet" /> : (
          <table className="tbl">
            <thead><tr><th>When</th><th>User</th><th>Action</th><th>What</th></tr></thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.id}>
                  <td className="whitespace-nowrap">{new Date(r.created_at).toLocaleString("en-IN")}</td>
                  <td>{r.user}</td>
                  <td className={`text-xs font-semibold ${TONE[r.action] ?? ""}`}>{r.action}</td>
                  <td>{r.entity_id && ["document", "Tax Invoice", "Bill of Supply"].some((x) => r.entity.includes(x)) ? <Link href={`/doc/${r.entity_id}`} className="text-brand-600 hover:underline">{r.summary}</Link> : r.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {data && data.total > PAGE && (
        <div className="mt-3 flex items-center justify-end gap-2 text-sm">
          <Button variant="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
          <span>Page {page + 1} of {Math.ceil(data.total / PAGE)}</span>
          <Button variant="secondary" disabled={(page + 1) * PAGE >= data.total} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      )}
    </>
  );
}
