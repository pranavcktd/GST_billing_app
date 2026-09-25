"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { PeriodPicker } from "@/components/PeriodPicker";
import { Button, Card, ErrorBox, PageHeader } from "@/components/ui";
import { downloadFile, qs } from "@/lib/api";
import { fyRange } from "@/lib/format";

export default function TallyExport() {
  const [period, setPeriod] = useState(fyRange());
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <PageHeader title="Export to Tally" sub="Send your books to your CA in Tally Prime / ERP 9 format" />
      <Card className="max-w-3xl space-y-4 p-5">
        <PeriodPicker value={period} onChange={setPeriod} />
        <ErrorBox message={err} />
        <ol className="list-decimal space-y-1 pl-5 text-sm text-gray-700">
          <li>Download the XML file for the period.</li>
          <li>In Tally, create (or open) the company with the same name as this business.</li>
          <li>Gateway of Tally → Import → Masters, choose the file (creates ledgers: parties, sales, purchase, GST, banks).</li>
          <li>Gateway of Tally → Import → Transactions, choose the same file (sales, purchases, notes, receipts, payments, contra).</li>
        </ol>
        <p className="text-xs text-gray-500">Exported in accounting-invoice mode. Cancelled documents and bounced cheques are skipped. Every voucher is balanced before export.</p>
        <Button disabled={busy} onClick={async () => {
          setBusy(true); setErr(null);
          try { await downloadFile(`/exports/tally${qs({ date_from: period.from, date_to: period.to })}`); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
        }}><Download size={16} /> {busy ? "Preparing…" : "Download Tally XML"}</Button>
      </Card>
    </>
  );
}
