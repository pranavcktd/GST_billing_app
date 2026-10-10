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
  whatsapp?: { login: boolean; signup_verify: boolean; send: boolean; sandbox?: boolean };
  signup?: { verify: string[]; google_client_id: string | null };
  legal?: Record<string, string>;
  gst_rates: number[]; b2cl_limit: number; invoice_number_max_len: number; ewb_threshold: number; ewb_km_per_day?: number;
  einvoice_turnover_limit: number; composition_rates: Record<string, number>; hsn_digits_small: number;
  hsn_digits_large: number; late_fee_per_day: number; interest_rate: number; gstr1_due_day: number;
  gstr3b_due_day: number; gstr1_json_version: string; einvoice_schema_version: string;
  uqc: Record<string, string>; states: Record<string, string>; credit_note_reasons: string[];
  blocked_itc_categories: string[]; subscription_gst_rate: number; trial_days: number;
  company: { name: string; email: string; address: string; phone: string; gstin?: string; website?: string };
  it_depreciation_rates?: Record<string, number>; ca_residual_value_pct?: number;
  brand: { app_name: string; by_line: string; tagline: string };
  links: Record<string, string>;
}

/** Built-in portal addresses; the super admin can change any of them (Admin → GST config → Portals & links). */
export const DEFAULT_LINKS: Record<string, string> = {
  gst_portal: "https://www.gst.gov.in",
  gst_returns: "https://return.gst.gov.in/returns/auth/dashboard",
  gst_payment: "https://payment.gst.gov.in/payment/",
  gstin_search: "https://services.gst.gov.in/services/searchtp",
  hsn_search: "https://services.gst.gov.in/services/searchhsnsac",
  gst_offline_tool: "https://tutorial.gst.gov.in/offlineutilities/returns/",
  ewaybill_portal: "https://ewaybillgst.gov.in",
  einvoice_portal: "https://einvoice1.gst.gov.in",
  income_tax_portal: "https://www.incometax.gov.in/iec/foportal/",
  tds_traces: "https://www.tdscpc.gov.in",
  mca_portal: "https://www.mca.gov.in",
  epfo_portal: "https://unifiedportal-emp.epfindia.gov.in",
  esic_portal: "https://www.esic.gov.in",
  whatsapp_send: "https://wa.me/",
};

export const DEFAULT_CONFIG: AppConfig = {
  gst_rates: [...GST_RATES], b2cl_limit: 100000, invoice_number_max_len: 16, ewb_threshold: 50000,
  einvoice_turnover_limit: 50000000, composition_rates: { TRADER: 1, MANUFACTURER: 1, RESTAURANT: 5, SERVICE: 6 },
  hsn_digits_small: 4, hsn_digits_large: 6, late_fee_per_day: 50, interest_rate: 18, gstr1_due_day: 11,
  gstr3b_due_day: 20, gstr1_json_version: "GST3.2", einvoice_schema_version: "1.1", uqc: { ...UNITS },
  states: { ...STATES },
  credit_note_reasons: ["Sales return", "Post-sale discount", "Deficiency in services", "Correction in invoice",
    "Change in POS", "Finalization of provisional assessment", "Others"],
  blocked_itc_categories: ["Tea & Refreshments"], subscription_gst_rate: 18, trial_days: 14,
  brand: { app_name: APP_NAME, by_line: BY_LINE, tagline: TAGLINE }, links: { ...DEFAULT_LINKS },
  company: { name: COMPANY_NAME, email: "corenexgenaipvtltd@gmail.com",
    address: "Registered office address — to be filled in", phone: "+91 96032 43575" },
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
        const next: AppConfig = { ...DEFAULT_CONFIG, ...meta.config, whatsapp: meta.whatsapp, signup: meta.signup };
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

/** Address of an external portal as configured by the super admin. */
export function useLink(key: string): string {
  return useConfig().links?.[key] || DEFAULT_LINKS[key] || "#";
}

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

/** A value from Admin → GST config → Legal & privacy (grievance officer, jurisdiction, data location …). */
export function Legal({ field, fallback = "" }: { field: string; fallback?: string }) {
  return <>{useConfig().legal?.[field] || fallback}</>;
}

/** Renders children only when the Legal & privacy value is filled in (e.g. the hosting location). */
export function IfLegal({ field, children }: { field: string; children: React.ReactNode }) {
  return useConfig().legal?.[field] ? <>{children}</> : null;
}
