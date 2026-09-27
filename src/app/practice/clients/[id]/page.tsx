"use client";

import { ArrowLeft, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ClientForm } from "@/components/practice/ClientForm";
import { fyOptions, type PClient } from "@/components/practice/types";
import { Button, Card, ErrorBox, Field, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

export default function ClientPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: c, error, reload } = useFetch<PClient>(`/practice/clients/${id}`);
  const [editing, setEditing] = useState(false);
  const [fy, setFy] = useState(fyOptions()[1]);
  const [err, setErr] = useState<string | null>(null);

  if (error) return <ErrorBox message={error} />;
  if (!c) return <Loading />;
  const existing = new Set((c.files ?? []).map((f) => f.fy));

  async function start() {
    setErr(null);
    try {
      const f = await api<{ id: string }>(`/practice/clients/${id}/files`, { body: { fy, carry_forward: true } });
      router.push(`/practice/files/${f.id}`);
    } catch (e) { setErr((e as Error).message); }
  }

  async function remove() {
    if (!confirm(`Delete ${c!.name} and all their years? This cannot be undone.`)) return;
    await api(`/practice/clients/${id}`, { method: "DELETE" });
    router.push("/practice");
  }

  return (
    <>
      <Link href="/practice" className="mb-3 inline-flex items-center gap-1 text-sm text-gray-600 hover:underline"><ArrowLeft size={14} /> All clients</Link>
      <PageHeader title={c.name} sub={[c.entity_type === "PARTNERSHIP" ? "Partnership firm" : "Proprietorship", c.pan && `PAN ${c.pan}`, c.gstin && `GSTIN ${c.gstin}`].filter(Boolean).join(" · ")}
        actions={<>
          <Button variant="secondary" onClick={() => setEditing(true)}><Pencil size={15} /> Edit</Button>
          <Button variant="ghost" onClick={remove}><Trash2 size={15} /></Button>
        </>} />
      <ErrorBox message={err} />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <h2 className="mb-3 font-semibold text-gray-900">Financial years</h2>
          {!(c.files ?? []).length ? <p className="text-sm text-gray-500">No years yet — start one on the right.</p> : (
            <table className="tbl">
              <thead><tr><th>Year</th><th>Status</th><th>Version</th><th>Last updated</th><th /></tr></thead>
              <tbody>
                {(c.files ?? []).map((f) => (
                  <tr key={f.id}>
                    <td className="font-medium">FY {f.fy}</td>
                    <td><span className={`rounded px-2 py-0.5 text-xs ${f.status === "FINAL" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"}`}>{f.status === "FINAL" ? "Finalised" : "Draft"}</span></td>
                    <td>v{f.version}</td>
                    <td className="text-xs text-gray-500">{fmtDate(f.updated_at)}</td>
                    <td className="text-right"><Link href={`/practice/files/${f.id}`} className="font-medium text-brand-600 hover:underline">Open</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card className="space-y-3 p-5">
          <h2 className="font-semibold text-gray-900">Start a year</h2>
          <Field label="Financial year">
            <Select value={fy} onChange={(e) => setFy(e.target.value)}>
              {fyOptions().map((y) => <option key={y} value={y} disabled={existing.has(y)}>FY {y}{existing.has(y) ? " (exists)" : ""}</option>)}
            </Select>
          </Field>
          <p className="text-xs text-gray-500">If the previous year exists here, its closing figures become this year&apos;s comparatives and openings (stock, fixed assets, depreciation).</p>
          <Button onClick={start} disabled={existing.has(fy)} className="w-full"><Plus size={15} /> Start FY {fy}</Button>
          {c.address && <p className="border-t border-gray-100 pt-3 text-xs text-gray-500">{c.address}</p>}
        </Card>
      </div>
      {editing && <ClientForm initial={c} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); reload(); }} />}
    </>
  );
}
