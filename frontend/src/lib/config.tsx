"use client";

/**
 * Runtime configuration managed by the super admin (Admin → GST config).
 *
 * The built-in constants (STATES, UNITS, GST_RATES) are updated in place from /api/meta, so every
 * screen that imports them follows the admin's settings without a new release. The last copy is
 * kept in localStorage so pages render with current values immediately on the next visit.
 */

import { createContext, useContext, useEffect, useState } from "react";
import { APP_NAME, BY_LINE, COMPANY_NAME, TAGLINE } from "@/lib/brand";
import { GST_RATES, STATES, UNITS } from "@/lib/constants";

export interface AppConfig {
  gst_rates: number[]; b2cl_limit: number; invoice_number_max_len: number; ewb_threshold: number;
  einvoice_turnover_limit: number; composition_rates: Record<string, number>; hsn_digits_small: number;
  hsn_digits_large: number; late_fee_per_day: number; interest_rate: number; gstr1_due_day: number;
  gstr3b_due_day: number; gstr1_json_version: string; einvoice_schema_version: string;
  uqc: Record<string, string>; states: Record<string, string>; credit_note_reasons: string[];
  blocked_itc_categories: string[]; subscription_gst_rate: number; trial_days: number;
  company: { name: string; email: string; address: string; phone: string; gstin?: string; website?: string };
  brand: { app_name: string; by_line: string; tagline: string };
}

export const DEFAULT_CONFIG: AppConfig = {
  gst_rates: [...GST_RATES], b2cl_limit: 100000, invoice_number_max_len: 16, ewb_threshold: 50000,
  einvoice_turnover_limit: 50000000, composition_rates: { TRADER: 1, MANUFACTURER: 1, RESTAURANT: 5, SERVICE: 6 },
  hsn_digits_small: 4, hsn_digits_large: 6, late_fee_per_day: 50, interest_rate: 18, gstr1_due_day: 11,
  gstr3b_due_day: 20, gstr1_json_version: "GST3.2", einvoice_schema_version: "1.1", uqc: { ...UNITS },
  states: { ...STATES },
  credit_note_reasons: ["Sales return", "Post-sale discount", "Deficiency in services", "Correction in invoice",
    "Change in POS", "Finalization of provisional assessment", "Others"],
  blocked_itc_categories: ["Tea & Refreshments"], subscription_gst_rate: 18, trial_days: 14,
  brand: { app_name: APP_NAME, by_line: BY_LINE, tagline: TAGLINE },
  company: { name: COMPANY_NAME, email: "corenexgenaipvtltd@gmail.com",
    address: "Registered office address — to be filled in", phone: "Phone — to be filled in" },
};

const KEY = "app-config";
const ConfigContext = createContext<AppConfig>(DEFAULT_CONFIG);

function replace<T extends object>(target: T, values: T) {
  for (const k of Object.keys(target)) delete (target as Record<string, unknown>)[k];
  Object.assign(target, values);
}

/** Push values into the shared constants used across the app. */
function applyGlobals(c: AppConfig) {
  if (c.states && Object.keys(c.states).length) replace(STATES, c.states);
  if (c.uqc && Object.keys(c.uqc).length) replace(UNITS, c.uqc);
  if (c.gst_rates?.length) GST_RATES.splice(0, GST_RATES.length, ...c.gst_rates);
}

function readCached(): AppConfig | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULT_CONFIG, ...JSON.parse(raw) } : null;
  } catch {
    return null;
  }
}

// Apply the last known values before the first render in the browser.
const initial: AppConfig = (typeof window !== "undefined" && readCached()) || DEFAULT_CONFIG;
if (initial !== DEFAULT_CONFIG) applyGlobals(initial);

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(initial);
  const [rev, setRev] = useState(0);

  useEffect(() => {
    let alive = true;
    fetch(`${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/meta`)
      .then((r) => (r.ok ? r.json() : null))
      .then((meta) => {
        if (!alive || !meta?.config) return;
        const next: AppConfig = { ...DEFAULT_CONFIG, ...meta.config };
        const text = JSON.stringify(next);
        try { localStorage.setItem(KEY, text); } catch { /* private mode */ }
        if (text === JSON.stringify(initial)) return;
        applyGlobals(next);
        setConfig(next);
        setRev((r) => r + 1);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  // remount the tree only when the admin changed something since the last visit
  return <ConfigContext.Provider value={config}><div key={rev} className="contents">{children}</div></ConfigContext.Provider>;
}

export const useConfig = () => useContext(ConfigContext);

/** Company details for legal pages and footers (server pages can embed this client component). */
export function Company({ field, link }: { field: keyof AppConfig["company"]; link?: boolean }) {
  const value = useConfig().company[field] ?? "";
  if (link && field === "email") return <a className="text-brand-600 hover:underline" href={`mailto:${value}`}>{value}</a>;
  return <>{value}</>;
}

/** The product name as configured by the super admin (defaults to SmartHisab). */
export function BrandName() {
  return <>{useConfig().brand?.app_name || APP_NAME}</>;
}
