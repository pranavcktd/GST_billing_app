"use client";

import { Check, Download, FileSpreadsheet, Pencil, Trash2, Upload, X } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api, downloadFile, qs } from "@/lib/api";
import { useConfig } from "@/lib/config";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Hsn { code: string; kind: "HSN" | "SAC"; description: string | null; gst_rate: number | null; cess_rate: number; effective_from: string | null }
interface Listing { total: number; hsn: number; sac: number; without_rate: number; matches: number; pending_requests: number; rows: Hsn[] }
interface ImportResult {
  dry_run: boolean; format: string; rows: number; hsn: number; sac: number; with_rate: number; created: number; updated: number;
  unchanged: number; rate_changes: number; error_count: number; errors: { row: string | number; error: string }[];
  sample: { code: string; kind: string; description: string | null; gst_rate: number | null }[];
}
interface Req { id: string; code: string; kind: string; description: string; gst_rate: number | null; note: string | null; status: string; admin_note: string | null; requested_by: string | null; created_at: string; business: string | null }

const PAGE = 100;
const blank = { code: "", description: "", gst_rate: "", cess_rate: "0", effective_from: "" };

export function AdminHsnMaster() {
  const [view, setView] = useState<"codes" | "requests">("codes");
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("");
  const [missing, setMissing] = useState(false);
  const [page, setPage] = useState(0);
  const { data, reload } = useFetch<Listing>(`/admin/hsn${qs({ search, kind: kind || undefined, missing_rate: missing || undefined, limit: PAGE, offset: page * PAGE })}`);
  const [form, setForm] = useState<typeof blank | null>(null);
  const [importing, setImporting] = useState(false);
  const [bulk, setBulk] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const filter = (fn: () => void) => { fn(); setPage(0); };

  return (
    <div className="space-y-5">
      <Card className="p-4 text-sm text-gray-600">
        The official HSN (goods) and SAC (services) list for every business on the platform. Only super admins can change it;
        businesses search it when creating items and can request missing codes. Upload the GST portal&apos;s HSN/SAC Excel as it is,
        our template, a CSV, or a PDF (codes and descriptions only). Set suggested GST rates per chapter with <b>Bulk rate</b>, or per code.
      </Card>

      {data && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {([["Codes", data.total], ["HSN (goods)", data.hsn], ["SAC (services)", data.sac], ["Without a rate", data.without_rate], ["Pending requests", data.pending_requests]] as const).map(([l, v]) => (
            <Card key={l} className="p-4"><div className="text-xs text-gray-500">{l}</div><div className="mt-1 text-2xl font-semibold">{v.toLocaleString("en-IN")}</div></Card>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <div className="flex rounded-lg border border-gray-200 bg-white p-0.5 text-sm">
          <button onClick={() => setView("codes")} className={`rounded-md px-3 py-1.5 ${view === "codes" ? "bg-brand-600 text-white" : ""}`}>Codes</button>
          <button onClick={() => setView("requests")} className={`rounded-md px-3 py-1.5 ${view === "requests" ? "bg-brand-600 text-white" : ""}`}>
            Requests{data?.pending_requests ? ` (${data.pending_requests})` : ""}
          </button>
        </div>
        <div className="flex-1" />
        <Button variant="secondary" onClick={() => downloadFile("/admin/hsn/template").catch((e) => setErr(e.message))}><FileSpreadsheet size={15} /> Template</Button>
        <Button variant="secondary" onClick={() => downloadFile("/admin/hsn/export").catch((e) => setErr(e.message))}><Download size={15} /> Export all</Button>
        <Button variant="secondary" onClick={() => setBulk(true)}>Bulk rate</Button>
        <Button variant="secondary" onClick={() => setForm(blank)}>Add code</Button>
        <Button onClick={() => setImporting(true)}><Upload size={15} /> Import</Button>
      </div>
      <ErrorBox message={err} />

      {view === "requests" ? <Requests onChange={reload} /> : (
        <Card className="overflow-x-auto">
          <div className="flex flex-wrap items-end gap-2 border-b border-gray-100 p-4">
            <Field label="Search code or description" className="min-w-64 flex-1"><Input value={search} onChange={(e) => filter(() => setSearch(e.target.value))} /></Field>
            <Field label="Type">
              <Select value={kind} onChange={(e) => filter(() => setKind(e.target.value))}><option value="">HSN & SAC</option><option value="HSN">HSN (goods)</option><option value="SAC">SAC (services)</option></Select>
            </Field>
            <label className="flex items-center gap-1.5 pb-2 text-sm"><input type="checkbox" checked={missing} onChange={(e) => filter(() => setMissing(e.target.checked))} /> Without a rate</label>
          </div>
          {!data ? <Loading /> : data.rows.length === 0 ? (
            <p className="p-5 text-sm text-gray-500">{data.total ? "No codes match." : "The master is empty — download the template or the GST portal's HSN/SAC Excel and import it."}</p>
          ) : (
            <>
              <table className="tbl">
                <thead><tr><th>Code</th><th>Type</th><th>Description</th><th className="num">GST %</th><th className="num">Cess %</th><th>Effective from</th><th /></tr></thead>
                <tbody>
                  {data.rows.map((h) => (
                    <tr key={h.code}>
                      <td className={`font-mono ${h.code.length <= 2 ? "font-bold" : h.code.length <= 4 ? "font-semibold" : ""}`}>{h.code}</td>
                      <td className="text-xs">{h.kind}</td>
                      <td className="max-w-xl text-xs">{h.description}</td>
                      <td className="num">{h.gst_rate ?? <span className="text-amber-700">—</span>}</td>
                      <td className="num">{h.cess_rate || ""}</td>
                      <td className="whitespace-nowrap">{h.effective_from ? fmtDate(h.effective_from) : ""}</td>
                      <td className="whitespace-nowrap text-right">
                        <button className="mr-2 text-gray-400 hover:text-gray-700" aria-label="Edit" onClick={() => setForm({ code: h.code, description: h.description ?? "", gst_rate: h.gst_rate === null ? "" : String(h.gst_rate), cess_rate: String(h.cess_rate), effective_from: h.effective_from ?? "" })}><Pencil size={15} /></button>
                        <button className="text-gray-400 hover:text-red-600" aria-label="Delete" onClick={async () => { if (confirm(`Delete ${h.code} from the master?`)) { await api(`/admin/hsn/${h.code}`, { method: "DELETE" }).catch((e) => setErr(e.message)); reload(); } }}><Trash2 size={15} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex items-center justify-between px-5 py-3 text-sm text-gray-600">
                <span>{page * PAGE + 1}–{page * PAGE + data.rows.length} of {data.matches.toLocaleString("en-IN")}</span>
                <div className="flex gap-2">
                  <Button variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
                  <Button variant="ghost" disabled={(page + 1) * PAGE >= data.matches} onClick={() => setPage(page + 1)}>Next</Button>
                </div>
              </div>
            </>
          )}
        </Card>
      )}

      {form && <CodeForm initial={form} onClose={() => setForm(null)} onSaved={() => { setForm(null); reload(); }} />}
      {importing && <ImportDialog onClose={() => setImporting(false)} onDone={reload} />}
      {bulk && <BulkRate onClose={() => setBulk(false)} onDone={reload} />}
    </div>
  );
}

function RateSelect({ value, onChange, blankLabel = "No rate" }: { value: string; onChange: (v: string) => void; blankLabel?: string }) {
  const config = useConfig();
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{blankLabel}</option>
      {config.gst_rates.map((r) => <option key={r} value={r}>{r}%</option>)}
    </Select>
  );
}

function CodeForm({ initial, onClose, onSaved }: { initial: typeof blank; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState(initial);
  const [err, setErr] = useState<string | null>(null);
  async function save() {
    try {
      await api("/admin/hsn", { body: { code: f.code, description: f.description || null, gst_rate: f.gst_rate === "" ? null : Number(f.gst_rate),
        cess_rate: Number(f.cess_rate || 0), effective_from: f.effective_from || null } });
      onSaved();
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <Modal title={initial.code ? `Edit ${initial.code}` : "Add HSN / SAC code"} onClose={onClose}>
      <div className="space-y-3">
        <Field label="Code" hint="2–8 digits; SAC codes start with 99"><Input value={f.code} disabled={!!initial.code} onChange={(e) => setF({ ...f, code: e.target.value.replace(/\D/g, "") })} /></Field>
        <Field label="Description"><Input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="GST %"><RateSelect value={f.gst_rate} onChange={(v) => setF({ ...f, gst_rate: v })} /></Field>
          <Field label="Cess %"><Input inputMode="decimal" value={f.cess_rate} onChange={(e) => setF({ ...f, cess_rate: e.target.value })} /></Field>
          <Field label="Effective from"><Input type="date" value={f.effective_from} onChange={(e) => setF({ ...f, effective_from: e.target.value })} /></Field>
        </div>
        <ErrorBox message={err} />
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save}>Save</Button></div>
      </div>
    </Modal>
  );
}

function ImportDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run(dryRun: boolean, f = file) {
    if (!f) return;
    setBusy(true);
    setErr(null);
    const form = new FormData();
    form.append("file", f);
    form.append("dry_run", String(dryRun));
    try {
      setResult(await api<ImportResult>("/admin/hsn/import", { form }));
      if (!dryRun) onDone();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal title="Import HSN / SAC codes" onClose={onClose} wide>
      <div className="space-y-4 text-sm">
        <p className="text-gray-600">
          Excel (.xlsx), CSV or PDF, up to 40 MB. The GST portal&apos;s HSN/SAC Excel (sheets HSN_MSTR and SAC_MSTR) works as it is.
          Nothing is saved until you confirm after the preview. Existing codes are updated; blank cells never erase stored values.
          Rates are never read from PDFs.
        </p>
        <label className="flex cursor-pointer items-center gap-3 rounded-lg border-2 border-dashed border-gray-300 p-4 hover:border-brand-400">
          <Upload size={20} className="text-gray-400" />
          <span>{file ? <b>{file.name}</b> : "Choose a file…"}</span>
          <input type="file" accept=".xlsx,.csv,.pdf" className="hidden" onChange={(e) => { const f = e.target.files?.[0] ?? null; e.target.value = ""; setFile(f); setResult(null); if (f) run(true, f); }} />
        </label>
        {busy && <Loading label="Reading the file…" />}
        <ErrorBox message={err} />
        {result && (
          <>
            <div className={`rounded-lg px-4 py-3 ${result.dry_run ? "bg-sky-50 text-sky-900" : "bg-emerald-50 text-emerald-900"}`}>
              <b>{result.dry_run ? "Preview" : "Imported"}</b> ({result.format}): {result.rows.toLocaleString("en-IN")} codes read — {result.hsn.toLocaleString("en-IN")} HSN, {result.sac.toLocaleString("en-IN")} SAC,{" "}
              {result.with_rate.toLocaleString("en-IN")} with a rate.{" "}
              {result.dry_run ? "Will add" : "Added"} <b>{result.created.toLocaleString("en-IN")}</b>, update <b>{result.updated.toLocaleString("en-IN")}</b> ({result.rate_changes} rate changes), {result.unchanged.toLocaleString("en-IN")} unchanged.
              {result.error_count > 0 && <> <b>{result.error_count}</b> rows skipped.</>}
            </div>
            {result.errors.length > 0 && (
              <details className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                <summary className="cursor-pointer font-medium">Skipped rows ({result.error_count})</summary>
                <ul className="mt-2 max-h-40 list-disc overflow-y-auto pl-5">{result.errors.map((e, i) => <li key={i}>Row {e.row}: {e.error}</li>)}</ul>
              </details>
            )}
            {result.sample.length > 0 && (
              <div className="max-h-64 overflow-y-auto rounded-lg border border-gray-100">
                <table className="tbl">
                  <thead><tr><th>Code</th><th>Type</th><th>Description</th><th className="num">GST %</th></tr></thead>
                  <tbody>{result.sample.map((r) => <tr key={r.code}><td className="font-mono">{r.code}</td><td className="text-xs">{r.kind}</td><td className="text-xs">{r.description}</td><td className="num">{r.gst_rate ?? "—"}</td></tr>)}</tbody>
                </table>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={onClose}>{result.dry_run ? "Cancel" : "Close"}</Button>
              {result.dry_run && <Button disabled={busy || result.rows === 0} onClick={() => run(false)}>Import {result.rows.toLocaleString("en-IN")} codes</Button>}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

function BulkRate({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ prefix: "", gst_rate: "", cess_rate: "", effective_from: "", only_missing: true });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function run() {
    setErr(null);
    try {
      const r = await api<{ updated: number }>("/admin/hsn/bulk-rate", { body: { prefix: f.prefix, gst_rate: f.gst_rate === "" ? null : Number(f.gst_rate),
        cess_rate: f.cess_rate === "" ? null : Number(f.cess_rate), effective_from: f.effective_from || null, only_missing: f.only_missing } });
      setMsg(`${r.updated} codes updated.`);
      onDone();
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <Modal title="Set a rate for a chapter / heading" onClose={onClose}>
      <div className="space-y-3 text-sm">
        <p className="text-gray-600">Applies to every code of 4+ digits starting with the prefix — e.g. <b>61</b> for all knitted apparel, <b>9954</b> for construction services.
          Use it for the common rate, then correct the exceptions code by code.</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Code starts with"><Input value={f.prefix} onChange={(e) => setF({ ...f, prefix: e.target.value.replace(/\D/g, "") })} /></Field>
          <Field label="GST %"><RateSelect value={f.gst_rate} onChange={(v) => setF({ ...f, gst_rate: v })} blankLabel="Clear the rate" /></Field>
          <Field label="Cess % (optional)"><Input inputMode="decimal" value={f.cess_rate} onChange={(e) => setF({ ...f, cess_rate: e.target.value })} /></Field>
          <Field label="Effective from (optional)"><Input type="date" value={f.effective_from} onChange={(e) => setF({ ...f, effective_from: e.target.value })} /></Field>
        </div>
        <label className="flex items-center gap-2"><input type="checkbox" checked={f.only_missing} onChange={(e) => setF({ ...f, only_missing: e.target.checked })} /> Only codes that have no rate yet</label>
        <ErrorBox message={err} />
        {msg && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-800">{msg}</div>}
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Close</Button><Button disabled={f.prefix.length < 2} onClick={run}>Apply</Button></div>
      </div>
    </Modal>
  );
}

function Requests({ onChange }: { onChange: () => void }) {
  const [status, setStatus] = useState("PENDING");
  const { data, reload } = useFetch<Req[]>(`/admin/hsn-requests${qs({ status })}`);
  const [edit, setEdit] = useState<(Req & { approve: boolean; rate: string; desc: string; adminNote: string }) | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function resolve() {
    if (!edit) return;
    try {
      await api(`/admin/hsn-requests/${edit.id}`, { body: { approve: edit.approve, description: edit.desc || null,
        gst_rate: edit.rate === "" ? null : Number(edit.rate), admin_note: edit.adminNote || null } });
      setEdit(null);
      reload();
      onChange();
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <Card className="overflow-x-auto">
      <div className="flex items-end gap-2 border-b border-gray-100 p-4">
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="PENDING">Pending</option><option value="APPROVED">Approved</option><option value="REJECTED">Rejected</option><option value="ALL">All</option>
          </Select>
        </Field>
      </div>
      {!data ? <Loading /> : data.length === 0 ? <p className="p-5 text-sm text-gray-500">No requests.</p> : (
        <table className="tbl">
          <thead><tr><th>Code</th><th>Description</th><th className="num">Rate</th><th>Business / by</th><th>Note</th><th>Status</th><th /></tr></thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.id}>
                <td className="font-mono">{r.code}<div className="text-[10px] text-gray-400">{r.kind}</div></td>
                <td className="text-xs">{r.description}</td>
                <td className="num">{r.gst_rate ?? "—"}</td>
                <td className="text-xs">{r.business}<div className="text-gray-400">{r.requested_by} · {fmtDate(r.created_at)}</div></td>
                <td className="text-xs">{r.note}{r.admin_note && <div className="text-gray-500">Reply: {r.admin_note}</div>}</td>
                <td className="text-xs">{r.status}</td>
                <td className="whitespace-nowrap text-right">
                  {r.status === "PENDING" && (
                    <>
                      <Button variant="ghost" className="!px-2 !py-1 text-emerald-700" onClick={() => setEdit({ ...r, approve: true, rate: r.gst_rate === null ? "" : String(r.gst_rate), desc: r.description, adminNote: "" })}><Check size={15} /> Approve</Button>
                      <Button variant="ghost" className="!px-2 !py-1 text-red-700" onClick={() => setEdit({ ...r, approve: false, rate: "", desc: "", adminNote: "" })}><X size={15} /> Reject</Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {edit && (
        <Modal title={`${edit.approve ? "Approve" : "Reject"} ${edit.code}`} onClose={() => setEdit(null)}>
          <div className="space-y-3">
            {edit.approve && (
              <>
                <p className="text-sm text-gray-600">Verify the code against the official tariff / notification before approving — it becomes available to every business.</p>
                <Field label="Official description"><Input value={edit.desc} onChange={(e) => setEdit({ ...edit, desc: e.target.value })} /></Field>
                <Field label="Suggested GST %"><RateSelect value={edit.rate} onChange={(v) => setEdit({ ...edit, rate: v })} /></Field>
              </>
            )}
            <Field label={edit.approve ? "Note to the business (optional)" : "Reason"}><Input value={edit.adminNote} onChange={(e) => setEdit({ ...edit, adminNote: e.target.value })} /></Field>
            <ErrorBox message={err} />
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setEdit(null)}>Cancel</Button><Button onClick={resolve}>{edit.approve ? "Approve & add" : "Reject"}</Button></div>
          </div>
        </Modal>
      )}
    </Card>
  );
}
