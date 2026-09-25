"use client";

import { BadgeCheck, Loader2, RefreshCw, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { gstinError } from "@/lib/gst";

export interface GstinInfo {
  gstin: string; legal_name: string | null; trade_name: string | null; status: string; active: boolean;
  taxpayer_type: string | null; constitution: string | null; registration_date: string | null;
  cancellation_date: string | null; state_code: string; state: string | null; address: string | null;
  pincode: string | null; city: string | null; pan: string; nature_of_business: string[];
  party_gst_type: "REGISTERED" | "COMPOSITION" | "SEZ"; business_gst_type: "REGULAR" | "COMPOSITION";
  source: "live" | "cache"; fetched_at: string;
}

let availability: Promise<boolean> | null = null;
const isAvailable = () => (availability ??= api<{ enabled: boolean }>("/gstin/available").then((r) => r.enabled).catch(() => false));

/**
 * "Verify & autofill" next to a GSTIN field. Nothing is called while typing — the paid lookup runs
 * only when the user clicks. Hidden when the platform has not enabled GSTIN verification.
 */
export function GstinVerify({ gstin, onResult, filled }: { gstin: string | null; onResult: (d: GstinInfo) => void; filled?: string[] }) {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<GstinInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { isAvailable().then(setEnabled); }, []);
  const g = (gstin ?? "").trim().toUpperCase();
  const valid = g.length === 15 && !gstinError(g);
  const stale = info && info.gstin !== g;

  if (!enabled) return null;

  async function run(refresh = false) {
    setBusy(true);
    setErr(null);
    try {
      const d = await api<GstinInfo>("/gstin/verify", { body: { gstin: g, refresh } });
      setInfo(d);
      onResult(d);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-1.5 space-y-1.5">
      {(!info || stale) && (
        <button type="button" disabled={!valid || busy} onClick={() => run()}
          title={valid ? "Fetch name, address and registration details from the GST portal" : "Enter a valid 15-character GSTIN first"}
          className="inline-flex items-center gap-1.5 rounded-md border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <BadgeCheck size={13} />} Verify & autofill
        </button>
      )}
      {err && <p className="text-xs text-red-700">{err}</p>}
      {info && !stale && (
        <div className={`rounded-lg border px-3 py-2 text-xs ${info.active ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-red-200 bg-red-50 text-red-900"}`}>
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-1.5 font-semibold">
              {info.active ? <BadgeCheck size={14} /> : <ShieldAlert size={14} />}
              {info.status || "Unknown status"} · {info.taxpayer_type ?? "—"}
            </div>
            <button type="button" className="inline-flex items-center gap-1 text-[11px] underline opacity-70 hover:opacity-100" disabled={busy}
              onClick={() => { if (confirm("Fetch fresh details from the GST portal? This uses one paid lookup.")) run(true); }}>
              <RefreshCw size={11} /> Refresh
            </button>
          </div>
          <div className="mt-0.5">{info.legal_name}{info.trade_name && info.trade_name !== info.legal_name ? ` (${info.trade_name})` : ""}</div>
          <div className="opacity-80">
            {[info.constitution, info.registration_date && `registered ${info.registration_date}`, info.cancellation_date && `cancelled ${info.cancellation_date}`].filter(Boolean).join(" · ")}
          </div>
          {!info.active && <div className="mt-1 font-medium">This GSTIN is not active — GST should not be charged to / claimed from it. Check with the party.</div>}
          {filled && filled.length > 0 && <div className="mt-1 opacity-80">Filled in: {filled.join(", ")}. Please check and complete the rest.</div>}
          {info.source === "cache" && <div className="opacity-60">Verified earlier on {new Date(info.fetched_at).toLocaleDateString("en-IN")}</div>}
        </div>
      )}
    </div>
  );
}
