"use client";

import { Download, Upload } from "lucide-react";
import { PortalLink } from "@/components/PortalLink";
import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { usePaged } from "@/components/Pager";
import { PeriodPicker } from "@/components/PeriodPicker";
import { Button, Card, Empty, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { api, qs, saveBlob } from "@/lib/api";
import { useConfig } from "@/lib/config";
import { fmtDate, monthRange, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Row {
  id: string; type: string; number: string; date: string; party: string; value: number; status: "PENDING" | "ACTIVE" | "EXPIRING" | "EXPIRED";
  ewb_no: string | null; ewb_date: string | null; valid_till: string | null; vehicle: string | null; distance: number | null; ready: boolean; problems: string[];
}
const TABS = [["PENDING", "Needed"], ["EXPIRING", "Expiring soon"], ["ACTIVE", "Active"], ["EXPIRED", "Expired"], ["", "All"]] as const;
const TONE: Record<Row["status"], string> = { PENDING: "bg-amber-50 text-amber-800", EXPIRING: "bg-red-50 text-red-700", ACTIVE: "bg-emerald-50 text-emerald-700", EXPIRED: "bg-gray-100 text-gray-600" };
const LABEL: Record<Row["status"], string> = { PENDING: "Needed", EXPIRING: "Expiring", ACTIVE: "Active", EXPIRED: "Expired" };
const KIND: Record<string, string> = { SALE: "sales", DELIVERY_CHALLAN: "delivery-challans", PURCHASE: "purchases" };
const dtm = (s: string | null) => (s ? new Date(s).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");

/** E-way bills without an API: which bills need one, one JSON for the portal's bulk upload, and importing the numbers back. */
export default function EwayBillsPage() {
  const config = useConfig();
  const [period, setPeriod] = useState(monthRange(0));
  const [tab, setTab] = useState<string>("PENDING");
  const { data, error, reload } = useFetch<Row[]>(`/ewaybills${qs({ date_from: period.from, date_to: period.to })}`);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const shown = (data ?? []).filter((r) => !tab || r.status === tab);
  const { rows, pager } = usePaged(shown);
  const count = (s: string) => (data ?? []).filter((r) => !s || r.status === s).length;

  async function bulk() {
    setErr(null); setMsg(null);
    try {
      const r = await api<{ json: unknown; count: number; skipped: { number: string; problems: string[] }[] }>("/ewaybills/bulk-json", { body: { voucher_ids: [...sel] } });
      if (r.count) saveBlob(new Blob([JSON.stringify(r.json, null, 1)], { type: "application/json" }), `ewaybill-bulk-${period.from}-${r.count}.json`);
      setMsg(`${r.count} bill(s) in the file.${r.skipped.length ? ` Skipped (details missing): ${r.skipped.map((s) => s.number).join(", ")}` : ""}`
        + (r.count ? " Upload it on the e-way bill portal → e-Waybill → Generate Bulk, then import the generated list here." : ""));
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <>
      <PageHeader title="E-way bills" sub={`Goods worth more than ${money(config.ewb_threshold)} need an e-way bill before they move`}
        actions={<>
          <PortalLink to="ewaybill_portal" button>E-way bill portal</PortalLink>
          <Button variant="secondary" onClick={() => setImporting(true)}><Upload size={15} /> Import generated list</Button>
        </>} />
      <PeriodPicker value={period} onChange={(p) => { setPeriod(p); setSel(new Set()); }} />
      <ErrorBox message={err ?? error} />
      {msg && <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1 rounded-lg border border-gray-200 bg-white p-1 text-sm">
          {TABS.map(([k, l]) => <button key={k} onClick={() => setTab(k)} className={`rounded-md px-3 py-1.5 ${tab === k ? "bg-brand-600 text-white" : "text-gray-700"}`}>{l} ({count(k)})</button>)}
        </div>
        <div className="flex-1" />
        {tab === "PENDING" && (
          <>
            <Button variant="secondary" onClick={() => setSel(new Set(shown.filter((r) => r.ready).map((r) => r.id)))}>Select all ready</Button>
            <Button disabled={!sel.size} onClick={bulk}><Download size={15} /> Bulk JSON ({sel.size})</Button>
          </>
        )}
      </div>
      <Card className="overflow-x-auto">
        {!data ? <Loading /> : !shown.length ? <Empty title={tab === "PENDING" ? "No bills need an e-way bill in this period." : "Nothing here."} /> : (
          <table className="tbl">
            <thead><tr>{tab === "PENDING" && <th />}<th>Bill</th><th>Party</th><th className="num">Value</th><th>Transport</th><th>E-way bill</th><th>Status</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  {tab === "PENDING" && <td><input type="checkbox" disabled={!r.ready} checked={sel.has(r.id)} onChange={(e) => { const s = new Set(sel); if (e.target.checked) s.add(r.id); else s.delete(r.id); setSel(s); }} /></td>}
                  <td><Link href={`/v/${KIND[r.type]}/${r.id}`} className="font-medium text-brand-600 hover:underline">{r.number}</Link><div className="text-xs text-gray-500">{fmtDate(r.date)}{r.type === "DELIVERY_CHALLAN" ? " · challan" : r.type === "PURCHASE" ? " · purchase" : ""}</div></td>
                  <td>{r.party}</td>
                  <td className="num">{money(r.value)}</td>
                  <td className="text-xs">{[r.vehicle, r.distance ? `${r.distance} km` : null].filter(Boolean).join(" · ") || "—"}</td>
                  <td className="text-xs">
                    {r.ewb_no ? <><span className="font-mono">{r.ewb_no}</span><div className="text-gray-500">{dtm(r.ewb_date)}{r.valid_till ? ` → ${dtm(r.valid_till)}` : ""}</div></>
                      : r.problems.length ? <span className="text-amber-700" title={r.problems.join("\n")}>Missing: {r.problems.map((p) => p.split(" (")[0]).join("; ")}</span>
                        : <span className="text-gray-500">Ready for the bulk file</span>}
                  </td>
                  <td><span className={`rounded px-2 py-0.5 text-xs ${TONE[r.status]}`}>{LABEL[r.status]}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {pager}
      </Card>
      <p className="mt-3 text-xs text-gray-500">
        Without an API connection: select the ready bills → <b>Bulk JSON</b> → upload it on the portal (e-Waybill → Generate Bulk) → download the list of generated
        e-way bills → <b>Import generated list</b> here. Numbers and validity are filled on the matching bills (validity: 1 day per {config.ewb_km_per_day ?? 200} km).
        Vehicle changes (Part B) and extensions are done on the portal; record the new details on the bill.
      </p>
      {importing && <ImportList onClose={() => setImporting(false)} onDone={(m) => { setImporting(false); setMsg(m); reload(); }} />}
    </>
  );
}

function ImportList({ onClose, onDone }: { onClose: () => void; onDone: (msg: string) => void }) {
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function upload(f: File) {
    setBusy(true); setErr(null);
    const form = new FormData();
    form.append("file", f);
    try {
      const r = await api<{ updated: { number: string }[]; unmatched: string[]; unchanged: number }>("/ewaybills/import", { form });
      onDone(`${r.updated.length} bill(s) updated with e-way bill numbers.${r.unchanged ? ` ${r.unchanged} already up to date.` : ""}${r.unmatched.length ? ` Not found here: ${r.unmatched.slice(0, 10).join(", ")}` : ""}`);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <Modal title="Import generated e-way bills" onClose={onClose}>
      <div className="space-y-3 text-sm">
        <p className="text-gray-600">On the e-way bill portal, open the list of e-way bills you generated (or the bulk upload result) and download it as Excel / CSV.
          Upload it here — bills are matched by document number.</p>
        <label className="flex cursor-pointer items-center gap-3 rounded-lg border-2 border-dashed border-gray-300 p-4 hover:border-brand-400">
          <Upload size={20} className="text-gray-400" /> {busy ? "Reading…" : "Choose the file (.xlsx or .csv)…"}
          <input type="file" accept=".xlsx,.csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} />
        </label>
        <ErrorBox message={err} />
      </div>
    </Modal>
  );
}
