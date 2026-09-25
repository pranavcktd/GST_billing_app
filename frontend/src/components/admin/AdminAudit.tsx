"use client";

import { ExportMenu, simpleDoc } from "@/components/ExportMenu";
import { useState } from "react";
import { Button, Card, Empty, Field, Input, Loading, Select } from "@/components/ui";
import { qs } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Row { id: string; created_at: string; user: string | null; action: string; entity: string; summary: string; ip: string | null; business: string | null }
const PAGE = 100;
const TONE: Record<string, string> = {
  LOGIN: "text-emerald-700", LOGIN_FAIL: "text-amber-700", LOCKED: "text-red-700", CREATE: "text-emerald-700", UPDATE: "text-brand-700",
  DELETE: "text-red-700", CANCEL: "text-red-700", EXPORT: "text-gray-700", ACTION: "text-gray-700",
};

/** Platform events (sign-ins, admin actions, backups) and every business's audit trail. */
export function AdminAudit() {
  const [page, setPage] = useState(0);
  const [f, setF] = useState({ scope: "platform", action: "", search: "", date_from: "", date_to: "" });
  const { data } = useFetch<{ total: number; rows: Row[] }>(`/admin/audit${qs({ ...f, limit: PAGE, offset: page * PAGE })}`);
  const set = (p: Partial<typeof f>) => { setPage(0); setF({ ...f, ...p }); };

  return (
    <>
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <Field label="Scope">
          <Select value={f.scope} onChange={(e) => set({ scope: e.target.value })}>
            <option value="platform">Platform & sign-ins</option><option value="business">All businesses</option><option value="all">Everything</option>
          </Select>
        </Field>
        <Field label="Action">
          <Select value={f.action} onChange={(e) => set({ action: e.target.value })}>
            <option value="">Any</option>
            {["LOGIN", "LOGIN_FAIL", "LOCKED", "CREATE", "UPDATE", "DELETE", "CANCEL", "EXPORT", "ACTION"].map((a) => <option key={a}>{a}</option>)}
          </Select>
        </Field>
        <Field label="Search"><Input placeholder="email, invoice no…" value={f.search} onChange={(e) => set({ search: e.target.value })} /></Field>
        <Field label="From"><Input type="date" value={f.date_from} onChange={(e) => set({ date_from: e.target.value })} /></Field>
        <Field label="To"><Input type="date" value={f.date_to} onChange={(e) => set({ date_to: e.target.value })} /></Field>
        <div className="flex-1" />
        {data && <ExportMenu compact build={() => simpleDoc("Platform audit trail", ["When", "User", "Action", "Business", "What", "IP"],
          data.rows.map((r) => [new Date(r.created_at).toLocaleString("en-IN"), r.user, r.action, r.business, r.summary, r.ip]), { filename: "platform-audit" })} />}
      </div>
      <Card className="overflow-x-auto">
        {!data ? <Loading /> : !data.rows.length ? <Empty title="Nothing recorded for these filters" /> : (
          <table className="tbl">
            <thead><tr><th>When</th><th>User</th><th>Action</th>{f.scope !== "platform" && <th>Business</th>}<th>What</th><th>IP</th></tr></thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.id}>
                  <td className="whitespace-nowrap text-xs">{new Date(r.created_at).toLocaleString("en-IN")}</td>
                  <td>{r.user}</td>
                  <td className={`text-xs font-semibold ${TONE[r.action] ?? ""}`}>{r.action}</td>
                  {f.scope !== "platform" && <td className="text-xs">{r.business}</td>}
                  <td className="text-sm">{r.summary}</td>
                  <td className="font-mono text-xs text-gray-500">{r.ip}</td>
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
