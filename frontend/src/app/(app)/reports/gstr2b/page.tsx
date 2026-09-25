"use client";

import { FileJson, Upload } from "lucide-react";
import { useState } from "react";
import { PeriodPicker } from "@/components/PeriodPicker";
import { ReportSections } from "@/components/ReportView";
import { Button, Card, ErrorBox, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { monthRange } from "@/lib/format";
import type { ReportResult } from "@/lib/types";

export default function Gstr2bPage() {
  const [period, setPeriod] = useState(monthRange(-1));
  const [file, setFile] = useState<File | null>(null);
  const [data, setData] = useState<ReportResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    if (!file) return;
    setBusy(true); setErr(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("date_from", period.from);
      form.append("date_to", period.to);
      setData(await api<ReportResult>("/reconcile/gstr2b", { form }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="GSTR-2B reconciliation" sub="Match what suppliers reported on the GST portal with your purchase bills before claiming ITC" />
      <Card className="mb-5 space-y-3 p-5">
        <p className="text-sm text-gray-600">GST portal → Returns Dashboard → GSTR-2B → <b>Download JSON</b>. Choose the purchase period to compare (usually the same month).</p>
        <PeriodPicker value={period} onChange={setPeriod} />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-gray-300 px-4 py-2 text-sm hover:bg-gray-50">
            <FileJson size={18} className="text-gray-500" /> {file ? file.name : "Choose GSTR-2B JSON"}
            <input type="file" accept=".json,application/json" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <Button disabled={!file || busy} onClick={run}><Upload size={16} /> {busy ? "Matching…" : "Reconcile"}</Button>
        </div>
        <ErrorBox message={err} />
      </Card>
      {data && <ReportSections data={data} />}
    </>
  );
}
