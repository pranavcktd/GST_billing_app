"use client";

import { useState } from "react";
import { money } from "@/lib/format";

interface Point {
  month: string;
  sales: number;
  purchases: number;
  expenses: number;
}

const SERIES = [
  { key: "sales" as const, label: "Sales", color: "var(--color-series-1)" },
  { key: "purchases" as const, label: "Purchases", color: "var(--color-series-2)" },
  { key: "expenses" as const, label: "Expenses", color: "var(--color-series-3)" },
];

function niceMax(v: number): number {
  if (v <= 0) return 1000;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

const compact = (n: number) =>
  n >= 1e7 ? `${+(n / 1e7).toFixed(1)}Cr` : n >= 1e5 ? `${+(n / 1e5).toFixed(1)}L` : n >= 1e3 ? `${+(n / 1e3).toFixed(1)}K` : `${n}`;

/** Grouped bars: sales vs purchases for the last 6 months, with a hover tooltip per month. */
export function TrendChart({ data }: { data: Point[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const W = 640, H = 240, L = 48, R = 8, T = 12, B = 28;
  const max = niceMax(Math.max(...data.flatMap((d) => SERIES.map((s) => d[s.key] ?? 0)), 0));
  const plotW = W - L - R, plotH = H - T - B;
  const band = plotW / data.length;
  const barW = Math.min(18, (band - 16) / 3);
  const y = (v: number) => T + plotH - (Math.max(v, 0) / max) * plotH;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);

  return (
    <div className="relative">
      <div className="mb-2 flex flex-wrap items-center gap-4 text-xs text-gray-600">
        {SERIES.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
        <button className="ml-auto text-brand-600 hover:underline" onClick={() => setAsTable((t) => !t)}>
          {asTable ? "Show chart" : "Show table"}
        </button>
      </div>
      {asTable ? (
        <table className="tbl">
          <thead><tr><th>Month</th>{SERIES.map((s) => <th key={s.key} className="num">{s.label}</th>)}</tr></thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.month}><td>{d.month}</td>{SERIES.map((s) => <td key={s.key} className="num">{money(d[s.key] ?? 0)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      ) : (
      <>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Sales and purchases, last 6 months">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="#eef0f3" />
            <text x={L - 6} y={y(t) + 4} textAnchor="end" fontSize="10" fill="#6b7280">
              {compact(t)}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const cx = L + band * i + band / 2;
          return (
            <g key={d.month} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={L + band * i} y={T} width={band} height={plotH} fill={hover === i ? "#f3f5f8" : "transparent"} />
              {SERIES.map((s, si) => {
                const v = d[s.key] ?? 0;
                const top = y(v);
                const h = Math.max(T + plotH - top, v > 0 ? 1 : 0);
                const x = cx - (SERIES.length * barW + (SERIES.length - 1) * 2) / 2 + si * (barW + 2);
                const r = Math.min(4, h);
                // rounded data-end, square baseline
                const path = h
                  ? `M${x},${T + plotH} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${T + plotH} Z`
                  : "";
                return path ? <path key={s.key} d={path} fill={s.color} /> : null;
              })}
              <text x={cx} y={H - 8} textAnchor="middle" fontSize="10" fill="#6b7280">
                {d.month.split(" ")[0]}
              </text>
            </g>
          );
        })}
        <line x1={L} x2={W - R} y1={T + plotH} y2={T + plotH} stroke="#d5d9e0" />
      </svg>
      {hover !== null && (
        <div
          className="pointer-events-none absolute top-6 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs shadow-md"
          style={{ left: `${Math.min(((L + band * hover + band) / W) * 100, 70)}%` }}
        >
          <div className="mb-1 font-semibold text-gray-900">{data[hover].month}</div>
          {SERIES.map((s) => (
            <div key={s.key} className="flex items-center gap-2 text-gray-700">
              <span className="inline-block h-2 w-2 rounded-sm" style={{ background: s.color }} />
              {s.label}: <span className="font-medium text-gray-900">{money(data[hover][s.key] ?? 0)}</span>
            </div>
          ))}
        </div>
      )}
      </>
      )}
    </div>
  );
}
