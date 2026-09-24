"use client";

import { CheckCircle2, Download, FileSpreadsheet, Upload } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox } from "@/components/ui";
import { api, downloadFile } from "@/lib/api";

interface ImportResult {
  title: string; rows: number; ok: boolean; dry_run: boolean; saved: boolean; summary: string;
  created: Record<string, number>; errors: { row: number; message: string }[];
}

/** Bulk import: download template -> fill -> validate (dry run) -> import. All-or-nothing. */
export function ImportDialog({ entity, title, onClose, onDone }: {
  entity: string; title: string; onClose: () => void; onDone?: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("dry_run", String(dryRun));
      const r = await api<ImportResult>(`/import/${entity}`, { form });
      setResult(r);
      if (r.saved) onDone?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const created = result && Object.entries(result.created).filter(([, n]) => n > 0);

  return (
    <Modal title={`Import ${title}`} onClose={onClose} wide>
      <ol className="mb-5 space-y-3 text-sm text-gray-700">
        <li className="flex items-start gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">1</span>
          <div className="flex-1">
            Download the Excel template, fill your data in the <b>Data</b> sheet (see the <b>Instructions</b> sheet).
            <div className="mt-2">
              <Button variant="secondary" onClick={() => downloadFile(`/import/${entity}/template`).catch((e) => setError(e.message))}>
                <Download size={15} /> Download template
              </Button>
            </div>
          </div>
        </li>
        <li className="flex items-start gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">2</span>
          <div className="flex-1">
            Upload the filled file (.xlsx or .csv).
            <label className="mt-2 flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-gray-300 px-4 py-3 hover:bg-gray-50">
              <FileSpreadsheet size={20} className="text-gray-500" />
              <span className="flex-1 truncate">{file ? file.name : "Choose file…"}</span>
              <input type="file" accept=".xlsx,.csv" className="hidden" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); }} />
            </label>
          </div>
        </li>
        <li className="flex items-start gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">3</span>
          <div className="flex-1">Check it first — nothing is saved until every row is valid.</div>
        </li>
      </ol>

      <ErrorBox message={error} />

      {result && (
        <div className={`mb-4 rounded-lg border px-4 py-3 text-sm ${result.ok ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}>
          {result.saved ? (
            <p className="flex items-center gap-2 font-medium text-emerald-800">
              <CheckCircle2 size={16} /> Imported: {result.summary}
            </p>
          ) : result.ok ? (
            <p className="font-medium text-emerald-800">All {result.rows} rows are valid ({result.summary}). Click Import to save.</p>
          ) : (
            <p className="font-medium text-red-800">{result.errors.length} problem(s) found — fix them in the file and upload again. Nothing was saved.</p>
          )}
          {created && created.length > 0 && (
            <p className="mt-1 text-gray-700">
              {result.saved ? "Also created" : "Will also create"}: {created.map(([k, n]) => `${n} ${k.replace("_", " ")}`).join(", ")}
            </p>
          )}
          {result.errors.length > 0 && (
            <div className="mt-2 max-h-60 overflow-auto rounded border border-red-100 bg-white">
              <table className="tbl">
                <thead><tr><th className="w-16">Row</th><th>Problem</th></tr></thead>
                <tbody>
                  {result.errors.map((e, i) => (
                    <tr key={i}><td>{e.row}</td><td className="text-red-800">{e.message}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>{result?.saved ? "Close" : "Cancel"}</Button>
        {!result?.saved && (
          <>
            <Button variant="secondary" disabled={!file || busy} onClick={() => send(true)}>Check file</Button>
            <Button disabled={!file || busy || !result?.ok} onClick={() => send(false)}>
              <Upload size={15} /> {busy ? "Working…" : "Import"}
            </Button>
          </>
        )}
      </div>
    </Modal>
  );
}

/** Button that opens the import dialog. */
export function ImportButton({ entity, title, onDone }: { entity: string; title: string; onDone?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <Upload size={16} /> Import
      </Button>
      {open && <ImportDialog entity={entity} title={title} onClose={() => setOpen(false)} onDone={onDone} />}
    </>
  );
}
