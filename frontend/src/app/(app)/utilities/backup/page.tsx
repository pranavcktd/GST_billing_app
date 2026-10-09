"use client";

import { DatabaseBackup, Download, FileSpreadsheet, Mail, RotateCcw, SearchCheck, Share2, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading, PageHeader } from "@/components/ui";
import { ApiError, api, apiBlob, saveBlob } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";
import type { Business } from "@/lib/types";

interface BackupRow { id: string; kind: "AUTO" | "MANUAL"; size: number; created_at: string; emailed_to: string | null; filename: string; excel_filename: string }
interface RestoreErr { file?: string; row: number | null; message: string }
interface RestoreOut { id: string | null; name: string | null; method: "exact" | "excel"; ok: boolean; edited?: string[]; skipped?: string[];
  summary?: Record<string, string>; errors?: RestoreErr[] }

const size = (n: number) => (n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
const when = (iso: string) => new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleString("en-IN");

export default function BackupPage() {
  const { refresh, switchBusiness } = useAuth();
  const { data: backups, error, reload } = useFetch<BackupRow[]>("/backups");
  const { data: biz, setData: setBiz } = useFetch<Business>("/businesses/current");
  const { data: opts } = useFetch<{ excel: boolean }>("/backups/settings");
  const excel = !!opts?.excel;
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [check, setCheck] = useState<RestoreOut | null>(null);
  const isZip = excel && !!file?.name.toLowerCase().endsWith(".zip");

  const restoreFile = (dryRun: boolean) => run(async () => {
    setCheck(null);
    const form = new FormData();
    form.append("file", file!);
    if (dryRun) form.append("dry_run", "true");
    try {
      const r = await api<RestoreOut>("/backups/restore", { form });
      if (dryRun) { setCheck(r); return; }
      await refresh();
      if (r.id && confirm(`Restored as “${r.name}”${r.method === "excel" ? " (rebuilt from the Excel files)" : ""}. Open it now?`)) switchBusiness(r.id);
    } catch (e) {
      const d = e instanceof ApiError ? (e.detail as { errors?: RestoreErr[]; summary?: Record<string, string> } | undefined) : undefined;
      if (d?.errors) { setCheck({ id: null, name: null, method: "excel", ok: false, errors: d.errors, summary: d.summary }); return; }
      throw e;
    }
  });

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setErr(null); setMsg(null);
    try { await fn(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  const download = (b: BackupRow) => run(async () => {
    const { blob, filename } = await apiBlob(`/backups/${b.id}/download`);
    saveBlob(blob, filename);
  });
  const downloadExcel = (b: BackupRow) => run(async () => {
    const { blob, filename } = await apiBlob(`/backups/${b.id}/excel`);
    saveBlob(blob, filename || b.excel_filename);
  });

  /** On phones this opens the share sheet (save to Files / Drive / WhatsApp). */
  const share = (b: BackupRow) => run(async () => {
    const { blob, filename } = await apiBlob(`/backups/${b.id}/download`);
    const f = new File([blob], filename, { type: "application/octet-stream" });
    if (navigator.canShare?.({ files: [f] })) await navigator.share({ files: [f], title: filename });
    else saveBlob(blob, filename);
  });

  async function saveSettings(auto: boolean, email: string) {
    if (!biz) return;
    await run(async () => {
      const updated = await api<Business>("/businesses/current", { method: "PUT", body: { ...biz, auto_backup: auto, backup_email: email || null } });
      setBiz(updated);
      setMsg("Backup settings saved");
    });
  }

  if (!backups || !biz) return error ? <ErrorBox message={error} /> : <Loading />;

  return (
    <>
      <PageHeader title="Backup & restore" sub={`Backups are complete snapshots of this company${excel ? " — also downloadable as Excel files anyone can open (green button)" : ""}. Restoring always creates a new company, so your current data is never overwritten.`} />
      <ErrorBox message={err} />
      {msg && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      <div className="mb-5 grid gap-5 lg:grid-cols-3">
        <Card className="space-y-3 p-5">
          <h2 className="font-semibold text-gray-900">Back up now</h2>
          <Button className="w-full" disabled={busy} onClick={() => run(async () => { await api("/backups", { body: {} }); setMsg("Backup created"); reload(); })}>
            <DatabaseBackup size={16} /> Create backup
          </Button>
          <Button variant="secondary" className="w-full" disabled={busy} onClick={() => run(async () => { await api("/backups?email=true", { body: {} }); setMsg(`Backup emailed to ${biz.backup_email || "your login email"}`); reload(); })}>
            <Mail size={16} /> Create & email backup
          </Button>
        </Card>
        <Card className="space-y-3 p-5">
          <h2 className="font-semibold text-gray-900">Automatic backup</h2>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={biz.auto_backup} onChange={(e) => saveSettings(e.target.checked, biz.backup_email ?? "")} />
            Back up automatically every day (last 7 kept)
          </label>
          <Field label="Backup email" hint="Used by “Create & email backup”">
            <Input type="email" defaultValue={biz.backup_email ?? ""} onBlur={(e) => e.target.value !== (biz.backup_email ?? "") && saveSettings(biz.auto_backup, e.target.value)} />
          </Field>
        </Card>
        <Card className="space-y-3 p-5">
          <h2 className="font-semibold text-gray-900">Restore from file</h2>
          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-gray-300 px-3 py-2 text-sm hover:bg-gray-50">
            <Upload size={16} className="text-gray-500" />
            <span className="truncate">{file ? file.name : excel ? "Choose backup (.gstbak) or Excel backup (.zip)" : "Choose .gstbak file"}</span>
            <input type="file" accept={excel ? ".gstbak,.zip,application/zip,application/octet-stream" : ".gstbak,application/octet-stream"} className="hidden"
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setCheck(null); }} />
          </label>
          {isZip && <p className="text-xs text-gray-500">Unchanged Excel files restore the exact backup inside the zip. Edited files rebuild the company from the Excel sheets — check them first.</p>}
          <div className="flex gap-2">
            {isZip && <Button variant="secondary" className="flex-1" disabled={busy} onClick={() => restoreFile(true)}><SearchCheck size={16} /> Check files</Button>}
            <Button variant="secondary" className="flex-1" disabled={!file || busy} onClick={() => restoreFile(false)}>
              <RotateCcw size={16} /> Restore as new company
            </Button>
          </div>
          {check && (
            <div className={`rounded-lg px-3 py-2 text-xs ${check.ok ? "bg-emerald-50 text-emerald-900" : "bg-red-50 text-red-900"}`}>
              <div className="font-medium">
                {check.ok ? (check.method === "exact" ? "Files unchanged — the exact backup will be restored." : "All Excel files are fine — ready to restore.")
                  : `${check.errors?.length ?? 0} problem(s) — nothing was restored. Fix these in the Excel files and try again:`}
              </div>
              {!!check.edited?.length && check.method === "excel" && <div className="mt-1">Changed files: {check.edited.join(", ")}</div>}
              {check.summary && <ul className="mt-1 list-disc pl-4">{Object.entries(check.summary).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul>}
              {!!check.errors?.length && (
                <ul className="mt-1 max-h-48 list-disc overflow-y-auto pl-4">
                  {check.errors.map((x, i) => <li key={i}>{x.file}{x.row ? `, row ${x.row}` : ""}: {x.message}</li>)}
                </ul>
              )}
              {!!check.skipped?.length && <div className="mt-1 text-gray-600">For reading only (not imported): {check.skipped.join(", ")}</div>}
            </div>
          )}
        </Card>
      </div>
      <Card className="overflow-x-auto">
        <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Saved backups</h2>
        {backups.length === 0 ? <p className="px-5 pb-5 text-sm text-gray-500">No backups yet.</p> : (
          <table className="tbl">
            <thead><tr><th>Created</th><th>Type</th><th>Size</th><th>Emailed to</th><th /></tr></thead>
            <tbody>
              {backups.map((b) => (
                <tr key={b.id}>
                  <td>{when(b.created_at)}</td>
                  <td>{b.kind === "AUTO" ? "Automatic" : "Manual"}</td>
                  <td>{size(b.size)}</td>
                  <td>{b.emailed_to ?? ""}</td>
                  <td className="whitespace-nowrap text-right">
                    <Button variant="ghost" className="!px-2 !py-1" title="Download backup" onClick={() => download(b)}><Download size={15} /></Button>
                    {excel && <Button variant="ghost" className="!px-2 !py-1 text-emerald-700" title="Download as Excel files (.zip)" onClick={() => downloadExcel(b)}><FileSpreadsheet size={15} /></Button>}
                    <Button variant="ghost" className="!px-2 !py-1" title="Save to phone / share" onClick={() => share(b)}><Share2 size={15} /></Button>
                    <Button variant="ghost" className="!px-2 !py-1" title="Restore as new company" onClick={() => run(async () => {
                      if (!confirm("Restore this backup as a new company?")) return;
                      const r = await api<{ id: string; name: string }>(`/backups/${b.id}/restore`, { body: {} });
                      await refresh();
                      setMsg(`Restored as “${r.name}” — switch to it from the company menu.`);
                    })}><RotateCcw size={15} /></Button>
                    <Button variant="ghost" className="!px-2 !py-1 text-red-600" title="Delete" onClick={() => run(async () => {
                      if (!confirm("Delete this backup?")) return;
                      await api(`/backups/${b.id}`, { method: "DELETE" });
                      reload();
                    })}><Trash2 size={15} /></Button>
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
