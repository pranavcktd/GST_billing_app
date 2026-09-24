"use client";

import { RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { ImportButton } from "@/components/ImportDialog";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { GST_RATES } from "@/lib/constants";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Hsn { id: string; code: string; description: string | null; gst_rate: number; cess_rate: number; effective_from: string | null }

export default function HsnPage() {
  const [search, setSearch] = useState("");
  const { data, error, reload } = useFetch<Hsn[]>(`/hsn${qs({ search })}`);
  const [f, setF] = useState({ code: "", description: "", gst_rate: 18, cess_rate: "", effective_from: "" });
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await api("/hsn", { body: { ...f, cess_rate: Number(f.cess_rate || 0), description: f.description || null, effective_from: f.effective_from || null } });
      setF({ code: "", description: "", gst_rate: 18, cess_rate: "", effective_from: "" });
      reload();
    } catch (x) { setErr((x as Error).message); }
  }

  async function apply() {
    if (!confirm("Update the GST rate of all items from this HSN/SAC master? Existing bills keep their original rates.")) return;
    try {
      const r = await api<{ updated: number }>("/hsn/apply-to-items", { body: {} });
      setMsg(`${r.updated} item(s) updated to the master rates.`);
    } catch (x) { setErr((x as Error).message); }
  }

  return (
    <>
      <PageHeader title="HSN / SAC master" sub="Keep codes with their current GST rates. Items pick up the rate when you type the code, and you can push rate changes to all items."
        actions={
          <>
            <ImportButton entity="hsn" title="HSN / SAC codes (add or update)" onDone={reload} />
            <Button variant="secondary" onClick={apply}><RefreshCw size={16} /> Apply rates to items</Button>
          </>
        } />
      <ErrorBox message={err ?? error} />
      {msg && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      <Card className="mb-5 p-4">
        <form onSubmit={save} className="grid gap-2 sm:grid-cols-6">
          <Field label="HSN/SAC code"><Input required pattern="\d{4,8}" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} /></Field>
          <Field label="Description" className="sm:col-span-2"><Input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
          <Field label="GST">
            <Select value={f.gst_rate} onChange={(e) => setF({ ...f, gst_rate: Number(e.target.value) })}>{GST_RATES.map((r) => <option key={r} value={r}>{r}%</option>)}</Select>
          </Field>
          <Field label="Effective from"><Input type="date" value={f.effective_from} onChange={(e) => setF({ ...f, effective_from: e.target.value })} /></Field>
          <div className="flex items-end"><Button type="submit" className="w-full">Add / update</Button></div>
        </form>
      </Card>
      <Input placeholder="Search code or description" value={search} onChange={(e) => setSearch(e.target.value)} className="mb-3 max-w-xs" />
      <Card className="overflow-x-auto">
        {!data ? <Loading /> : data.length === 0 ? <Empty title="No codes yet — import the list your CA or the GST portal provides" /> : (
          <table className="tbl">
            <thead><tr><th>Code</th><th>Description</th><th className="num">GST</th><th className="num">Cess</th><th>Effective from</th><th /></tr></thead>
            <tbody>
              {data.map((h) => (
                <tr key={h.id}>
                  <td className="font-mono">{h.code}</td><td>{h.description}</td>
                  <td className="num">{h.gst_rate}%</td><td className="num">{h.cess_rate ? `${h.cess_rate}%` : ""}</td>
                  <td>{fmtDate(h.effective_from)}</td>
                  <td className="text-right whitespace-nowrap">
                    <button className="mr-3 text-xs text-brand-600 hover:underline" onClick={() => setF({ code: h.code, description: h.description ?? "", gst_rate: h.gst_rate, cess_rate: String(h.cess_rate || ""), effective_from: h.effective_from ?? "" })}>Edit</button>
                    <button className="text-gray-400 hover:text-red-600" aria-label="Delete" onClick={async () => { if (confirm(`Delete ${h.code}?`)) { await api(`/hsn/${h.id}`, { method: "DELETE" }); reload(); } }}><Trash2 size={15} /></button>
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
