"use client";

import { FileSpreadsheet, FileText, Loader2, Printer, Sheet } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui";
import { API_URL, ApiError, authHeaders, saveBlob } from "@/lib/api";
import type { ColType } from "@/lib/types";

export interface DocColumn { key: string; label: string; type: ColType }
export interface DocSection {
  title?: string | null; columns: DocColumn[]; rows: Record<string, unknown>[];
  total?: Record<string, unknown> | null; note?: string | null;
}
export interface TableDoc {
  title: string; subtitle?: string | null; filename?: string;
  summary?: { label: string; value: unknown; type: ColType }[]; sections: DocSection[];
}

const NUM_HINT = /qty|quantity|stock|count|nos|units/i;

/** Build a document from simple headers + rows (the shape pages already use for CSV). */
export function simpleDoc(title: string, headers: string[], rows: (string | number | null | undefined)[][],
  opts: { subtitle?: string; filename?: string; types?: ColType[] } = {}): TableDoc {
  const columns: DocColumn[] = headers.map((h, i) => {
    const vals = rows.map((r) => r[i]).filter((v) => v !== null && v !== undefined && v !== "");
    const auto: ColType = vals.length && vals.every((v) => typeof v === "number") ? (NUM_HINT.test(h) ? "qty" : "money")
      : vals.length && vals.every((v) => typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v)) ? "date" : "text";
    return { key: `c${i}`, label: h, type: opts.types?.[i] ?? auto };
  });
  return {
    title, subtitle: opts.subtitle, filename: opts.filename,
    sections: [{ columns, rows: rows.map((r) => Object.fromEntries(r.map((v, i) => [`c${i}`, v ?? null]))) }],
  };
}

async function fetchFile(doc: TableDoc, format: "pdf" | "xlsx") {
  const res = await fetch(`${API_URL}/api/export/table?format=${format}`, {
    method: "POST", headers: { ...authHeaders(), "Content-Type": "application/json" }, body: JSON.stringify(doc),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, (body?.detail?.message ?? body?.detail ?? `Export failed (${res.status})`) as string);
  }
  const cd = res.headers.get("Content-Disposition") ?? "";
  return { blob: await res.blob(), filename: /filename="?([^"]+)"?/.exec(cd)?.[1] ?? `export.${format}` };
}

function csv(doc: TableDoc) {
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines: unknown[][] = [[doc.title], ...(doc.subtitle ? [[doc.subtitle]] : [])];
  for (const s of doc.sections) {
    lines.push([]);
    if (s.title) lines.push([s.title]);
    lines.push(s.columns.map((c) => c.label));
    for (const r of s.rows) lines.push(s.columns.map((c) => r[c.key]));
    if (s.total) lines.push(s.columns.map((c, i) => (i === 0 ? "Total" : s.total![c.key])));
  }
  const blob = new Blob(["﻿" + lines.map((l) => l.map(esc).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
  saveBlob(blob, `${(doc.filename || doc.title).replace(/[^\w.-]+/g, "-")}.csv`);
}

/**
 * Print / PDF / Excel / CSV for whatever table a page shows. Exports always contain every row,
 * not just the page on screen. "Print" opens the PDF so the full table prints cleanly.
 */
export function ExportMenu({ build, disabled, compact }: { build: () => TableDoc | null; disabled?: boolean; compact?: boolean }) {
  const [busy, setBusy] = useState<string | null>(null);

  async function run(kind: "print" | "pdf" | "xlsx" | "csv") {
    const doc = build();
    if (!doc) return;
    if (kind === "csv") return csv(doc);
    const win = kind === "print" ? window.open("", "_blank") : null; // opened synchronously so pop-up blockers allow it
    setBusy(kind);
    try {
      const { blob, filename } = await fetchFile(doc, kind === "xlsx" ? "xlsx" : "pdf");
      if (win) {
        win.location.href = URL.createObjectURL(blob);
      } else {
        saveBlob(blob, filename);
      }
    } catch (e) {
      win?.close();
      alert((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const icon = (k: string, I: typeof Printer) => (busy === k ? <Loader2 size={15} className="animate-spin" /> : <I size={15} />);
  const cls = compact ? "!px-2.5 !py-1.5" : "";
  return (
    <div className="no-print inline-flex flex-wrap gap-1.5">
      <Button variant="secondary" className={cls} disabled={disabled || !!busy} onClick={() => run("print")} title="Print (opens a PDF)">{icon("print", Printer)} Print</Button>
      <Button variant="secondary" className={cls} disabled={disabled || !!busy} onClick={() => run("pdf")} title="Download PDF">{icon("pdf", FileText)} PDF</Button>
      <Button variant="secondary" className={cls} disabled={disabled || !!busy} onClick={() => run("xlsx")} title="Download Excel">{icon("xlsx", FileSpreadsheet)} Excel</Button>
      <Button variant="ghost" className={cls} disabled={disabled || !!busy} onClick={() => run("csv")} title="Download CSV">{icon("csv", Sheet)} CSV</Button>
    </div>
  );
}
