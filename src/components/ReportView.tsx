"use client";

import Link from "next/link";
import { Card } from "@/components/ui";
import { fmtDate, money, qty } from "@/lib/format";
import type { ColType, ReportResult, ReportRow, ReportSection } from "@/lib/types";

export function fmtCell(v: unknown, type: ColType): string {
  if (v === null || v === undefined || v === "") return "";
  switch (type) {
    case "money":
      return money(Number(v));
    case "qty":
      return qty(Number(v));
    case "pct":
      return `${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}%`;
    case "int":
      return String(v);
    case "date":
      return fmtDate(String(v));
    default:
      return String(v);
  }
}

const numeric = (t: ColType) => t !== "text" && t !== "date";

function Row({ row, section }: { row: ReportRow; section: ReportSection }) {
  const style = row._style;
  const cls = style === "bold" ? "font-semibold bg-gray-50" : style === "head" ? "font-semibold text-gray-900" : style === "sub" ? "text-gray-400" : "";
  return (
    <tr className={cls}>
      {section.columns.map((c, i) => {
        const text = fmtCell(row[c.key], c.type);
        const neg = c.type === "money" && Number(row[c.key]) < 0;
        return (
          <td key={c.key} className={`${numeric(c.type) ? "num" : ""} ${neg ? "text-red-700" : ""} whitespace-pre`}>
            {i === 0 && row._link ? <Link href={row._link} className="text-brand-600 hover:underline">{text}</Link> : text}
          </td>
        );
      })}
    </tr>
  );
}

export function ReportSections({ data }: { data: ReportResult }) {
  return (
    <>
      {data.summary.length > 0 && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {data.summary.map((s) => (
            <Card key={s.label} className="p-4">
              <div className="text-xs text-gray-500">{s.label}</div>
              <div className={`mt-1 text-lg font-semibold tabular-nums ${s.type === "money" && s.value < 0 ? "text-red-700" : "text-gray-900"}`}>
                {fmtCell(s.value, s.type)}
              </div>
            </Card>
          ))}
        </div>
      )}
      {data.sections.map((sec, si) => (
        <Card key={si} className="mb-5 overflow-x-auto print:border-0 print:shadow-none">
          {sec.title && <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">{sec.title}</h2>}
          {sec.rows.length === 0 ? (
            <p className="px-5 py-6 text-sm text-gray-500">No records for the selected filters.</p>
          ) : (
            <table className="tbl">
              <thead>
                <tr>{sec.columns.map((c) => <th key={c.key} className={numeric(c.type) ? "num" : ""}>{c.label}</th>)}</tr>
              </thead>
              <tbody>
                {sec.rows.map((r, i) => <Row key={i} row={r} section={sec} />)}
              </tbody>
              {sec.total && (
                <tfoot>
                  <tr>
                    {sec.columns.map((c, i) => (
                      <td key={c.key} className={numeric(c.type) ? "num" : ""}>
                        {i === 0 ? "Total" : c.key in sec.total! ? fmtCell(sec.total![c.key], c.type) : ""}
                      </td>
                    ))}
                  </tr>
                </tfoot>
              )}
            </table>
          )}
          {sec.note && <p className="px-5 py-3 text-xs text-gray-500">{sec.note}</p>}
        </Card>
      ))}
    </>
  );
}

/** CSV of every section, one after another. */
export function reportCsvRows(data: ReportResult): { headers: string[]; rows: (string | number | null)[][] } {
  const rows: (string | number | null)[][] = [];
  data.sections.forEach((sec, i) => {
    if (i > 0) rows.push([]);
    if (sec.title) rows.push([sec.title]);
    rows.push(sec.columns.map((c) => c.label));
    for (const r of sec.rows) rows.push(sec.columns.map((c) => (r[c.key] ?? null) as string | number | null));
    if (sec.total) rows.push(sec.columns.map((c, j) => (j === 0 ? "Total" : ((sec.total![c.key] ?? null) as string | number | null))));
  });
  return { headers: [data.title], rows };
}
