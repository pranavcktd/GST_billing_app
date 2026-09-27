"use client";

import { AlertTriangle, CheckCircle2, GraduationCap, Info, X, XCircle } from "lucide-react";
import { useState } from "react";
import { ExportMenu, type TableDoc } from "@/components/ExportMenu";
import { fmtCell } from "@/components/ReportView";
import { Card, Loading } from "@/components/ui";
import { money } from "@/lib/format";
import type { ColType } from "@/lib/types";
import type { Statements } from "./types";

const ICON = { error: XCircle, warn: AlertTriangle, info: Info, ok: CheckCircle2 };
const TONE = { error: "border-red-200 bg-red-50 text-red-800", warn: "border-amber-200 bg-amber-50 text-amber-900", info: "border-sky-200 bg-sky-50 text-sky-900", ok: "border-emerald-200 bg-emerald-50 text-emerald-800" };
const numeric = (t: ColType) => t !== "text" && t !== "date";

/** Statements with checks and "learn mode": click any line to see what it contains and how it is worked out. */
export function StatementsTab({ st, loading }: { st: Statements | null; loading: boolean }) {
  const [learn, setLearn] = useState(true);
  const [open, setOpen] = useState<string | null>(null);
  if (!st) return <Loading />;
  const ex = open ? st.explain[open] : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm">
          <input type="checkbox" checked={learn} onChange={(e) => setLearn(e.target.checked)} />
          <GraduationCap size={16} className="text-brand-600" /> Learn mode — explain the figures
        </label>
        {loading && <span className="text-xs text-gray-500">Updating…</span>}
        <div className="flex-1" />
        <ExportMenu build={() => st.doc as unknown as TableDoc} />
      </div>

      <div className="space-y-1.5">
        {st.checks.map((c, i) => {
          const I = ICON[c.level];
          return <div key={i} className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${TONE[c.level]}`}><I size={16} className="mt-0.5 shrink-0" /> {c.text}</div>;
        })}
      </div>

      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_22rem] lg:gap-5">
        <div className="min-w-0 space-y-5">
          <Card className="p-4 text-center">
            <div className="text-lg font-semibold text-gray-900">{st.doc.title}</div>
            <div className="text-sm text-gray-500">{st.doc.subtitle}</div>
          </Card>
          {st.doc.sections.map((sec, si) => (
            <Card key={si} className="overflow-x-auto">
              <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">{sec.title}</h2>
              <table className="tbl">
                <thead><tr>{sec.columns.map((c) => <th key={c.key} className={numeric(c.type) ? "num" : ""}>{c.label}</th>)}</tr></thead>
                <tbody>
                  {sec.rows.map((r, ri) => {
                    const key = typeof r._key === "string" && st.explain[r._key] ? r._key : null;
                    const style = r._style;
                    return (
                      <tr key={ri} onClick={() => key && setOpen(key)}
                        className={`${style === "bold" ? "bg-gray-50 font-semibold" : style === "head" ? "font-semibold text-gray-900" : style === "sub" ? "text-gray-500" : ""} ${key ? "cursor-pointer hover:bg-brand-50/60" : ""} ${open === key && key ? "bg-brand-50" : ""}`}>
                        {sec.columns.map((c, ci) => (
                          <td key={c.key} className={`${numeric(c.type) ? "num" : ""} whitespace-pre-wrap`}>
                            {fmtCell(r[c.key], c.type)}
                            {ci === 0 && key && learn && <Info size={12} className="ml-1.5 inline text-brand-500" />}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
                {sec.total && (
                  <tfoot><tr>{sec.columns.map((c, i) => <td key={c.key} className={numeric(c.type) ? "num" : ""}>{i === 0 ? "Total" : fmtCell(sec.total![c.key], c.type)}</td>)}</tr></tfoot>
                )}
              </table>
            </Card>
          ))}
        </div>
        {learn && (
          <aside className="mt-5 lg:mt-0">
            <Card className="p-4 lg:sticky lg:top-20">
              {!ex ? (
                <div className="text-sm text-gray-600">
                  <div className="mb-2 flex items-center gap-2 font-semibold text-gray-900"><GraduationCap size={18} className="text-brand-600" /> Learn mode</div>
                  Click any line with an <Info size={12} className="inline text-brand-500" /> to see what it means, which ledgers make it up and how it is calculated.
                  <p className="mt-3 text-xs text-gray-500">Tip: the balance sheet balances because every rupee is either owned (capital), owed (liabilities) or held (assets). Profit increases capital; drawings reduce it.</p>
                </div>
              ) : (
                <div className="text-sm">
                  <div className="mb-2 flex items-start justify-between gap-2">
                    <div className="font-semibold text-gray-900">{ex.title}</div>
                    <button onClick={() => setOpen(null)} className="text-gray-400 hover:text-gray-700" aria-label="Close"><X size={16} /></button>
                  </div>
                  <p className="text-gray-700">{ex.text}</p>
                  {ex.items.length > 0 && (
                    <table className="mt-3 w-full text-xs">
                      <thead><tr className="text-gray-500"><th className="text-left font-medium">Ledger</th><th className="text-right font-medium">Balance</th></tr></thead>
                      <tbody>
                        {ex.items.map((it, i) => <tr key={i} className="border-t border-gray-100"><td className="py-1">{it.name}</td><td className="py-1 text-right tabular-nums">{money(Math.abs(it.amount))} {it.amount >= 0 ? "Dr" : "Cr"}</td></tr>)}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </Card>
          </aside>
        )}
      </div>
    </div>
  );
}
