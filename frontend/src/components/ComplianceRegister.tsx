"use client";

import { CheckCircle2, RefreshCw, Undo2 } from "lucide-react";
import { useState } from "react";
import { PortalLink } from "@/components/PortalLink";
import { Button, Card, ErrorBox, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

/** One law, one financial year: month-by-month / quarter-by-quarter table of filings (compliance page tabs). */

export interface Markable { code: string; name: string; period_key: string; period: string }
type St = "DONE" | "OVERDUE" | "DUE_SOON" | "UPCOMING" | "NOT_TRACKED";
interface Done { id: string; done_on: string; reference: string | null; note: string | null; by: string | null; source?: string }
interface Row extends Markable {
  frequency: "MONTHLY" | "QUARTERLY" | "YEARLY"; period_start: string; due_date: string; status: St; days_overdue: number;
  days_left: number; done: Done | null; penalty: string | null; late_fee_so_far: number | null; link: string | null;
}
interface PortalRow { return_type: string; return_period: string; status: string | null; filed: boolean; filed_on: string | null; arn: string | null; mode: string | null }
interface Register {
  fy: number; fy_label: string; law: string; columns: { code: string; name: string; frequency: Row["frequency"] }[]; rows: Row[];
  track_from: string; portal?: PortalRow[]; portal_fetched_at?: string | null;
}

export const LAW_LABEL: Record<string, string> = { GST: "GST", INCOME_TAX: "Income tax", TDS: "TDS", MCA: "Company (MCA)", LLP: "LLP", PAYROLL: "EPF / ESI" };
const MONTHS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"];
const RET_NAME: Record<string, string> = { GSTR1: "GSTR-1", GSTR3B: "GSTR-3B", GSTR9: "GSTR-9", GSTR9C: "GSTR-9C", GSTR4: "GSTR-4", CMP08: "CMP-08", IFF: "IFF", GSTR2X: "GSTR-2X" };

export function currentFy(): number {
  const d = new Date();
  return d.getMonth() >= 3 ? d.getFullYear() : d.getFullYear() - 1;
}

/** Where a "filed" record came from: fetched from the GST portal, or entered by a person. */
export function SourceBadge({ source }: { source?: string }) {
  return source === "SYNC"
    ? <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold text-sky-800" title="Fetched from the GST portal (GSTN)">GST portal</span>
    : <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold text-gray-600" title="Marked as filed by a user">Manual</span>;
}

function Cell({ r, onMark, onUndo }: { r?: Row; onMark: (r: Row) => void; onUndo: (r: Row) => void }) {
  if (!r) return <span className="text-xs text-gray-300">—</span>;
  if (r.done) {
    return (
      <div className="text-xs leading-5">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-medium text-emerald-700">Filed {fmtDate(r.done.done_on)}</span>
          <SourceBadge source={r.done.source} />
          <button className="text-gray-300 hover:text-gray-600" title="Mark as not filed" onClick={() => onUndo(r)}><Undo2 size={12} /></button>
        </div>
        {r.done.reference && <div className="font-mono text-[11px] text-gray-600">ARN {r.done.reference}</div>}
        <div className="text-[11px] text-gray-400">due {fmtDate(r.due_date)}{r.done.done_on > r.due_date ? " · filed late" : ""}</div>
      </div>
    );
  }
  const tone = r.status === "OVERDUE" ? "text-red-700" : r.status === "DUE_SOON" ? "text-amber-700" : "text-gray-500";
  return (
    <div className="text-xs leading-5">
      <div className={tone}>
        {r.status === "OVERDUE" ? `Overdue · ${r.days_overdue} day${r.days_overdue === 1 ? "" : "s"}` : r.status === "NOT_TRACKED" ? "Not recorded" : `Due ${fmtDate(r.due_date)}`}
      </div>
      {(r.status === "OVERDUE" || r.status === "NOT_TRACKED") && <div className="text-[11px] text-gray-400">due {fmtDate(r.due_date)}</div>}
      {r.late_fee_so_far !== null && <div className="text-[11px] text-red-600" title={r.penalty ?? ""}>late fee ≈ {money(r.late_fee_so_far)}</div>}
      {r.status !== "UPCOMING" && <button className="text-[11px] font-medium text-brand-600 hover:underline" onClick={() => onMark(r)}>Mark filed</button>}
    </div>
  );
}

export function ComplianceRegister({ law, version, syncAvailable, onMark, onChanged }: {
  law: string; version: number; syncAvailable: boolean; onMark: (r: Markable) => void; onChanged: () => void;
}) {
  const [fy, setFy] = useState(currentFy());
  const [syncing, setSyncing] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const { data, error, reload } = useFetch<Register>(`/compliance/register?law=${law}&fy=${fy}&v=${version}`);
  const years = Array.from({ length: currentFy() - 2016 }, (_, i) => currentFy() - i);

  async function undo(r: Row) {
    if (!r.done || !confirm(`Mark ${r.name} (${r.period}) as not filed?`)) return;
    try { await api(`/compliance/tasks/${r.done.id}`, { method: "DELETE" }); reload(); onChanged(); } catch (e) { alert((e as Error).message); }
  }
  async function syncYear() {
    setSyncing(true); setMsg(null);
    try {
      const r = await api<{ message: string }>(`/compliance/sync?fy=${fy}`, { body: {} });
      setMsg(r.message);
      reload(); onChanged();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setSyncing(false);
    }
  }

  const byKey = new Map((data?.rows ?? []).map((r) => [`${r.code}|${r.period_key}`, r]));
  const monthly = data?.columns.filter((c) => c.frequency === "MONTHLY") ?? [];
  const quarterly = data?.columns.filter((c) => c.frequency === "QUARTERLY") ?? [];
  const yearly = data?.rows.filter((r) => r.frequency === "YEARLY") ?? [];
  const monthKey = (i: number) => { const y = i < 9 ? fy : fy + 1; return `${y}-${String(((i + 3) % 12) + 1).padStart(2, "0")}`; };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Select className="!w-auto" value={fy} onChange={(e) => setFy(Number(e.target.value))}>
          {years.map((y) => <option key={y} value={y}>FY {y}-{String(y + 1).slice(-2)}</option>)}
        </Select>
        {law === "GST" && syncAvailable && (
          <Button variant="secondary" onClick={syncYear} disabled={syncing} title="Fetch this year's GST filing status from the GST portal">
            <RefreshCw size={15} className={syncing ? "animate-spin" : ""} /> {syncing ? "Fetching…" : `Fetch FY ${fy}-${String(fy + 1).slice(-2)} from GST portal`}
          </Button>
        )}
        <span className="ml-auto flex items-center gap-2 text-xs text-gray-500"><SourceBadge source="SYNC" /> fetched from the GST portal <SourceBadge source="MANUAL" /> entered by a user</span>
      </div>
      {msg && <p className="text-sm font-medium text-gray-800">{msg}</p>}
      <ErrorBox message={error} />
      {!data ? <Loading /> : data.rows.length === 0 ? (
        <Card className="p-6 text-sm text-gray-500">No {LAW_LABEL[law] ?? law} filings apply to this business for FY {data.fy_label} (based on your compliance profile).</Card>
      ) : (
        <>
          {monthly.length > 0 && (
            <Card className="overflow-x-auto">
              <h3 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Monthly — FY {data.fy_label}</h3>
              <table className="tbl">
                <thead><tr><th className="w-28">Month</th>{monthly.map((c) => <th key={c.code}>{c.name}</th>)}</tr></thead>
                <tbody>
                  {MONTHS.map((m, i) => (
                    <tr key={m}>
                      <td className="font-medium whitespace-nowrap">{m} {i < 9 ? fy : fy + 1}</td>
                      {monthly.map((c) => <td key={c.code}><Cell r={byKey.get(`${c.code}|${monthKey(i)}`)} onMark={onMark} onUndo={undo} /></td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
          {quarterly.length > 0 && (
            <Card className="overflow-x-auto">
              <h3 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Quarterly — FY {data.fy_label}</h3>
              <table className="tbl">
                <thead><tr><th className="w-40">Quarter</th>{quarterly.map((c) => <th key={c.code}>{c.name}</th>)}</tr></thead>
                <tbody>
                  {[1, 2, 3, 4].map((q) => (
                    <tr key={q}>
                      <td className="font-medium whitespace-nowrap">Q{q} <span className="font-normal text-gray-500">{["Apr–Jun", "Jul–Sep", "Oct–Dec", "Jan–Mar"][q - 1]}</span></td>
                      {quarterly.map((c) => <td key={c.code}><Cell r={byKey.get(`${c.code}|FY${fy}-Q${q}`)} onMark={onMark} onUndo={undo} /></td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
          {yearly.length > 0 && (
            <Card className="overflow-x-auto">
              <h3 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Yearly — FY {data.fy_label}</h3>
              <table className="tbl">
                <thead><tr><th>Filing</th><th>Due date</th><th>Status</th><th /></tr></thead>
                <tbody>
                  {yearly.map((r) => (
                    <tr key={r.code + r.period_key}>
                      <td className="font-medium">{r.name}{r.period.includes("·") && <span className="font-normal text-gray-500"> — {r.period.split("·")[1]}</span>}</td>
                      <td className="whitespace-nowrap">{fmtDate(r.due_date)}</td>
                      <td><Cell r={r} onMark={onMark} onUndo={undo} /></td>
                      <td className="text-right">{r.link && !r.done && <PortalLink to={r.link}>Portal</PortalLink>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
          {data.rows.some((r) => r.status === "NOT_TRACKED") && (
            <p className="text-xs text-gray-500">“Not recorded” = due before {fmtDate(data.track_from)}, the date tracking starts (change it in Your compliance profile). Mark them filed, or fetch from the GST portal.</p>
          )}
        </>
      )}

      {law === "GST" && data && (
        <Card className="overflow-x-auto">
          <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pt-4 pb-2">
            <h3 className="flex items-center gap-2 font-semibold text-gray-900"><CheckCircle2 size={16} className="text-sky-600" /> As received from the GST portal — FY {data.fy_label}</h3>
            <span className="text-xs text-gray-500">{data.portal_fetched_at ? `Fetched ${new Date(data.portal_fetched_at).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}` : "Not fetched yet"}</span>
          </div>
          {!data.portal?.length ? (
            <p className="px-5 pb-5 text-sm text-gray-500">{syncAvailable ? "Click “Fetch … from GST portal” above to see every return the portal has for this year." : "Fetching from the GST portal is not switched on for this platform."}</p>
          ) : (
            <table className="tbl">
              <thead><tr><th>Return</th><th>Period</th><th>Status</th><th>Filed on</th><th>ARN</th><th>Mode</th></tr></thead>
              <tbody>
                {data.portal.map((p, i) => {
                  const [y, m] = p.return_period.split("-").map(Number);
                  return (
                    <tr key={i}>
                      <td className="font-medium">{RET_NAME[p.return_type] ?? p.return_type}</td>
                      <td className="whitespace-nowrap">{new Date(y, m - 1, 1).toLocaleDateString("en-IN", { month: "short", year: "numeric" })}</td>
                      <td className={p.filed ? "text-emerald-700" : "text-red-700"}>{p.status ?? (p.filed ? "Filed" : "Not filed")}</td>
                      <td className="whitespace-nowrap">{p.filed_on ? fmtDate(p.filed_on) : "—"}</td>
                      <td className="font-mono text-xs">{p.arn ?? "—"}</td>
                      <td className="text-xs">{p.mode ?? ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  );
}
