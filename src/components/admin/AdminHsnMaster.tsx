"use client";

import { Download, Pencil, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api, downloadFile, qs } from "@/lib/api";
import { useConfig } from "@/lib/config";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Hsn { code: string; description: string | null; gst_rate: number; cess_rate: number; effective_from: string | null }
const blank = { code: "", description: "", gst_rate: "18", cess_rate: "0", effective_from: "" };

export function AdminHsnMaster() {
  const config = useConfig();
  const [search, setSearch] = useState("");
  const { data, reload } = useFetch<{ total: number; rows: Hsn[] }>(`/admin/hsn${qs({ search, limit: 300 })}`);
  const [form, setForm] = useState(blank);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await api("/admin/hsn", { body: { code: form.code, description: form.description || null, gst_rate: Number(form.gst_rate),
        cess_rate: Number(form.cess_rate || 0), effective_from: form.effective_from || null } });
      setForm(blank);
      reload();
    } catch (e) { setErr((e as Error).message); }
  }

  async function upload(file: File) {
    setErr(null); setMsg(null);
    const f = new FormData();
    f.append("file", file);
    try {
      const r = await api<{ created: number; updated: number; errors: { row: number; error: string }[] }>("/admin/hsn/import", { form: f });
      setMsg(`${r.created} added, ${r.updated} updated` + (r.errors.length ? `, ${r.errors.length} rows skipped: ` + r.errors.slice(0, 5).map((x) => `row ${x.row}: ${x.error}`).join("; ") : ""));
      reload();
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <div className="space-y-5">
      <Card className="p-4 text-sm text-gray-600">
        The platform HSN/SAC master. Businesses search it from their item forms and HSN utility, and copy codes with current rates.
        Import the official list (Excel/CSV: HSN/SAC Code, Description, GST %, Cess %, Effective From); re-importing updates existing codes.
      </Card>
      <ErrorBox message={err} />
      {msg && <div className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{msg}</div>}
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Search code or description" className="min-w-64 flex-1"><Input value={search} onChange={(e) => setSearch(e.target.value)} /></Field>
        <Button variant="secondary" onClick={() => downloadFile("/admin/hsn/export").catch((e) => setErr(e.message))}><Download size={15} /> Export / template</Button>
        <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-brand-700">
          <Upload size={15} /> Import
          <input type="file" accept=".xlsx,.csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} />
        </label>
      </div>
      <Card className="overflow-x-auto">
        <form onSubmit={save} className="flex flex-wrap items-end gap-2 border-b border-gray-100 p-4">
          <Field label="Code"><Input required pattern="\d{4,8}" className="!w-28" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
          <Field label="Description" className="min-w-48 flex-1"><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="GST %">
            <Select value={form.gst_rate} onChange={(e) => setForm({ ...form, gst_rate: e.target.value })}>
              {config.gst_rates.map((r) => <option key={r} value={r}>{r}%</option>)}
            </Select>
          </Field>
          <Field label="Cess %"><Input className="!w-20" inputMode="decimal" value={form.cess_rate} onChange={(e) => setForm({ ...form, cess_rate: e.target.value })} /></Field>
          <Field label="Effective from"><Input type="date" value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} /></Field>
          <Button type="submit">Save code</Button>
        </form>
        {!data ? <Loading /> : (
          <>
            <p className="px-5 pt-3 text-xs text-gray-500">{data.total} codes in the master{search ? ` · showing ${data.rows.length} matches` : ""}</p>
            <table className="tbl">
              <thead><tr><th>Code</th><th>Description</th><th className="num">GST %</th><th className="num">Cess %</th><th>Effective from</th><th /></tr></thead>
              <tbody>
                {data.rows.map((h) => (
                  <tr key={h.code}>
                    <td className="font-mono">{h.code}</td><td className="text-xs">{h.description}</td>
                    <td className="num">{h.gst_rate}</td><td className="num">{h.cess_rate}</td>
                    <td>{h.effective_from ? fmtDate(h.effective_from) : "—"}</td>
                    <td className="whitespace-nowrap text-right">
                      <button className="mr-2 text-gray-400 hover:text-gray-700" aria-label="Edit" onClick={() => setForm({ code: h.code, description: h.description ?? "", gst_rate: String(h.gst_rate), cess_rate: String(h.cess_rate), effective_from: h.effective_from ?? "" })}><Pencil size={15} /></button>
                      <button className="text-gray-400 hover:text-red-600" aria-label="Delete" onClick={async () => { if (confirm(`Delete ${h.code}?`)) { await api(`/admin/hsn/${h.code}`, { method: "DELETE" }).catch((e) => setErr(e.message)); reload(); } }}><Trash2 size={15} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Card>
    </div>
  );
}
