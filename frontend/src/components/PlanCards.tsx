"use client";

import { Check } from "lucide-react";
import { money } from "@/lib/format";

export interface PlanOut {
  code: "FREE" | "STARTER" | "PROFESSIONAL" | "ENTERPRISE"; name: string; audience: string; highlights: string[];
  monthly: number; yearly: number; monthly_with_gst: number; yearly_with_gst: number;
  invoices_per_month: number | null; businesses: number | null; users: number | null;
  multi_year?: Record<string, { years: number; discount_pct: number; price: number; price_with_gst: number; per_year: number; saving: number }>;
}
export interface Cycle { code: string; label: string; years?: number; discount_pct?: number }

const rupees = (n: number) => money(n).replace(/\.\d+$/, "");

/** Monthly / Yearly / 2 years / 3 years … switch; multi-year options show their discount. */
export function CycleToggle({ cycles, value, onChange, dark = false }: { cycles?: Cycle[]; value: string; onChange: (c: string) => void; dark?: boolean }) {
  const list = cycles?.length ? cycles : [{ code: "MONTHLY", label: "Monthly" }, { code: "YEARLY", label: "Yearly" }];
  return (
    <div className={`inline-flex flex-wrap rounded-xl p-1 text-sm ${dark ? "bg-white/10" : "bg-gray-100"}`}>
      {list.map((c) => (
        <button key={c.code} type="button" onClick={() => onChange(c.code)}
          className={`rounded-lg px-3.5 py-1.5 font-medium whitespace-nowrap transition ${value === c.code ? "bg-white text-gray-900 shadow-sm" : dark ? "text-white/80" : "text-gray-600"}`}>
          {c.label}
          {c.discount_pct ? <span className="ml-1.5 rounded bg-emerald-100 px-1.5 py-0.5 text-[11px] text-emerald-700">−{c.discount_pct}%</span> : null}
        </button>
      ))}
    </div>
  );
}

/** Pricing cards shared by the landing page and the subscription page. */
export function PlanCards({ plans, cycle, current, onChoose, cta }: {
  plans: PlanOut[]; cycle: string; current?: string;
  onChoose?: (p: PlanOut) => void; cta?: (p: PlanOut) => React.ReactNode;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {plans.map((p) => {
        const popular = p.code === "PROFESSIONAL";
        const multi = cycle.startsWith("YEARS_") ? p.multi_year?.[cycle] : undefined;
        const price = multi ? multi.price : cycle === "MONTHLY" ? p.monthly : p.yearly;
        return (
          <div key={p.code} className={`relative flex flex-col rounded-2xl border bg-white p-5 shadow-sm ${popular ? "border-brand-500 ring-2 ring-brand-100" : "border-gray-200"}`}>
            {popular && <span className="absolute -top-3 left-5 rounded-full bg-brand-600 px-2.5 py-0.5 text-xs font-medium text-white">Most popular</span>}
            <div className="text-lg font-semibold text-gray-900">{p.name}</div>
            <div className="text-xs text-gray-500">{p.audience}</div>
            <div className="mt-4">
              {price === 0 ? (
                <span className="text-3xl font-bold text-gray-900">Free</span>
              ) : (
                multi ? (
                  <>
                    <span className="text-3xl font-bold text-gray-900">{rupees(multi.price)}</span>
                    <span className="text-sm text-gray-500"> for {multi.years} years</span>
                    <div className="text-xs text-gray-500">+ 18% GST · {rupees(multi.per_year)}/year · {rupees(multi.price / (multi.years * 12))}/month</div>
                    <div className="mt-1 inline-block rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">You save {rupees(multi.saving)} ({multi.discount_pct}% off)</div>
                  </>
                ) : (
                  <>
                    <span className="text-3xl font-bold text-gray-900">{money(price).replace(".00", "")}</span>
                    <span className="text-sm text-gray-500">/{cycle === "MONTHLY" ? "month" : "year"}</span>
                    <div className="text-xs text-gray-500">+ 18% GST{cycle === "YEARLY" ? ` · ${rupees(p.yearly / 12)}/month` : ""}</div>
                  </>
                )
              )}
            </div>
            <ul className="mt-4 flex-1 space-y-2 text-sm text-gray-700">
              {p.highlights.map((h) => (
                <li key={h} className="flex gap-2"><Check size={16} className="mt-0.5 shrink-0 text-emerald-600" aria-hidden />{h}</li>
              ))}
            </ul>
            <div className="mt-5">
              {cta ? cta(p) : current === p.code ? (
                <div className="rounded-lg bg-gray-100 py-2 text-center text-sm font-medium text-gray-600">Current plan</div>
              ) : onChoose && p.code !== "FREE" ? (
                <button onClick={() => onChoose(p)} className={`w-full rounded-lg py-2 text-sm font-medium ${popular ? "bg-brand-600 text-white hover:bg-brand-700" : "border border-gray-300 text-gray-800 hover:bg-gray-50"}`}>
                  Choose {p.name}
                </button>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
