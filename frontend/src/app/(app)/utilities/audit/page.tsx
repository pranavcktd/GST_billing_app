"use client";

import Link from "next/link";
import { useState } from "react";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader } from "@/components/ui";
import { qs } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { ExportMenu, simpleDoc } from "@/components/ExportMenu";

interface Row { id: string; created_at: string; user: string | null; action: string; entity: string; entity_id: string | null; summary: string; ip: string | null }
interface Change { id: string; at: string; user: string | null; op: "INSERT" | "UPDATE" | "DELETE"; entity: string; row_id: string | null;
  before: Record<string, unknown> | null; after: Record<string, unknown> | null; ip: string | null }
const PAGE = 100;
const TONE: Record<string, string> = { CREATE: "text-emerald-700", UPDATE: "text-brand-700", DELETE: "text-red-700", CANCEL: "text-red-700", ACTION: "text-gray-700",
  INSERT: "text-emerald-700" };
const OP: Record<string, string> = { INSERT: "Added", UPDATE: "Changed", DELETE: "Deleted" };
const HIDE = new Set(["id", "business_id", "created_at", "created_by_id", "sort_order"]);
const show = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));

function Diff({ c }: { c: Change }) {
  const keys = [...new Set([...Object.keys(c.before ?? {}), ...Object.keys(c.after ?? {})])].filter((k) => !HIDE.has(k));
  const shown = c.op === "UPDATE" ? keys : keys.filter((k) => (c.after ?? c.before ?? {})[k] !== null).slice(0, 8);
  return (
    <div className="space-y-0.5 text-xs">
      {shown.map((k) => (
        <div key={k} className="flex flex-wrap gap-1">
          <span className="text-gray-500">{k.replace(/_/g, " ")}:</span>
          {c.op === "UPDATE" ? <><span className="text-red-700 line-through">{show(c.before?.[k])}</span><span>→</span><span className="text-emerald-700">{show(c.after?.[k])}</span></>
            : <span>{show((c.after ?? c.before)?.[k])}</span>}
        </div>
      ))}
    </div>
  );
}

export default function AuditPage() {
  const [view, setView] = useState<"activity" | "changes">("activity");
  const [page, setPage] = useState(0);
  const [f, setF] = useState({ entity: "", date_from: "", date_to: "" });
  const base = view === "activity" ? "/audit" : "/audit/changes";
  const { data, error, loading } = useFetch<{ total: number; rows: (Row | Change)[] }>(`${base}${qs({ ...f, limit: PAGE, offset: page * PAGE })}`);
  const rows = data?.rows ?? [];

  return (
    <>
      <PageHeader title="Audit trail" sub="Every change — who made it, when, and (in Detailed changes) the values before and after. It cannot be edited, deleted or switched off (Companies (Accounts) Rules 3(1))."
        actions={data && <ExportMenu compact build={() => view === "activity"
          ? simpleDoc("Audit trail", ["When", "User", "Action", "What", "IP"], (rows as Row[]).map((r) => [new Date(r.created_at).toLocaleString("en-IN"), r.user, r.action, r.summary, r.ip]), { filename: "audit-trail" })
          : simpleDoc("Edit log", ["When", "User", "Change", "Record", "Before", "After", "IP"], (rows as Change[]).map((c) => [new Date(c.at).toLocaleString("en-IN"), c.user, OP[c.op], c.entity,
            JSON.stringify(c.before ?? {}), JSON.stringify(c.after ?? {}), c.ip]), { filename: "edit-log" })} />} />
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <div className="inline-flex rounded-lg bg-gray-100 p-1 text-sm">
          {(["activity", "changes"] as const).map((v) => (
            <button key={v} onClick={() => { setView(v); setPage(0); }} className={`rounded-md px-3 py-1.5 font-medium ${view === v ? "bg-white text-gray-900 shadow-sm" : "text-gray-600"}`}>
              {v === "activity" ? "Activity" : "Detailed changes (before / after)"}
            </button>
          ))}
        </div>
        <Field label="Search type"><Input placeholder="invoice, payment, party…" value={f.entity} onChange={(e) => { setPage(0); setF({ ...f, entity: e.target.value }); }} /></Field>
        <Field label="From"><Input type="date" value={f.date_from} onChange={(e) => { setPage(0); setF({ ...f, date_from: e.target.value }); }} /></Field>
        <Field label="To"><Input type="date" value={f.date_to} onChange={(e) => { setPage(0); setF({ ...f, date_to: e.target.value }); }} /></Field>
      </div>
      <ErrorBox message={error} />
      <Card className="overflow-x-auto">
        {loading && !data ? <Loading /> : !rows.length ? <Empty title="No activity recorded yet" /> : view === "activity" ? (
          <table className="tbl">
            <thead><tr><th>When</th><th>User</th><th>Action</th><th>What</th></tr></thead>
            <tbody>
              {(rows as Row[]).map((r) => (
                <tr key={r.id}>
                  <td className="whitespace-nowrap">{new Date(r.created_at).toLocaleString("en-IN")}</td>
                  <td>{r.user}</td>
                  <td className={`text-xs font-semibold ${TONE[r.action] ?? ""}`}>{r.action}</td>
                  <td>{r.entity_id && ["document", "Tax Invoice", "Bill of Supply"].some((x) => r.entity.includes(x)) ? <Link href={`/doc/${r.entity_id}`} className="text-brand-600 hover:underline">{r.summary}</Link> : r.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="tbl">
            <thead><tr><th>When</th><th>User</th><th>Change</th><th>Record</th><th>Values</th></tr></thead>
            <tbody>
              {(rows as Change[]).map((c) => (
                <tr key={c.id}>
                  <td className="whitespace-nowrap align-top">{new Date(c.at).toLocaleString("en-IN")}<div className="text-[11px] text-gray-400">{c.ip}</div></td>
                  <td className="align-top">{c.user ?? "system"}</td>
                  <td className={`align-top text-xs font-semibold ${TONE[c.op]}`}>{OP[c.op]}</td>
                  <td className="align-top">{c.entity}</td>
                  <td><Diff c={c} /></td>
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
