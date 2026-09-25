"use client";

import { BadgeCheck, Loader2, RefreshCw, ShieldAlert, ShieldQuestion } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { BrandName } from "@/lib/config";
import { gstinError } from "@/lib/gst";

export interface GstinInfo {
  gstin: string; legal_name: string | null; trade_name: string | null; status: string; active: boolean;
  taxpayer_type: string | null; constitution: string | null; registration_date: string | null;
  cancellation_date: string | null; state_code: string; state: string | null; address: string | null;
  pincode: string | null; city: string | null; pan: string; nature_of_business: string[];
  party_gst_type: "REGISTERED" | "COMPOSITION" | "SEZ"; business_gst_type: "REGULAR" | "COMPOSITION";
  source: "live" | "cache"; fetched_at: string;
}

/** Last verification of a GSTIN anywhere on the platform (from our own records — free). */
export interface GstinStatus {
  verified: boolean; verified_at?: string; status?: string | null; active?: boolean; legal_name?: string | null;
  trade_name?: string | null; taxpayer_type?: string | null; fresh?: boolean; days_ago?: number;
}

// re-checked at most once a minute, so switching it on in Admin → Integrations shows up without a reload
let availability: { at: number; value: Promise<boolean> } | null = null;
const isAvailable = () => {
  if (!availability || Date.now() - availability.at > 60_000) {
    availability = { at: Date.now(), value: api<{ enabled: boolean }>("/gstin/available").then((r) => r.enabled).catch(() => false) };
  }
  return availability.value;
};

const statusCache = new Map<string, GstinStatus>();
export async function gstinStatuses(gstins: string[]): Promise<Record<string, GstinStatus>> {
  const want = [...new Set(gstins.map((g) => g.trim().toUpperCase()).filter((g) => g.length === 15))];
  const missing = want.filter((g) => !statusCache.has(g));
  if (missing.length) {
    const r = await api<Record<string, GstinStatus>>("/gstin/status", { body: { gstins: missing } });
    for (const [g, s] of Object.entries(r)) statusCache.set(g, s);
  }
  return Object.fromEntries(want.map((g) => [g, statusCache.get(g) ?? { verified: false }]));
}

const fmt = (d?: string) => (d ? new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "");

/** Small badge with the last verification result (used in lists and next to GSTIN fields). */
export function GstinBadge({ s }: { s?: GstinStatus }) {
  if (!s) return null;
  if (!s.verified) return <span className="inline-flex items-center gap-0.5 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500" title="Not verified yet"><ShieldQuestion size={11} /> Not verified</span>;
  return (
    <span title={`Verified on ${fmt(s.verified_at)}: ${s.status ?? ""} · ${s.taxpayer_type ?? ""}`}
      className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium ${s.active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
      {s.active ? <BadgeCheck size={11} /> : <ShieldAlert size={11} />} {s.active ? "Verified" : s.status || "Inactive"}
    </span>
  );
}

/**
 * GSTIN verification next to a GSTIN field.
 * - Shows, for free, whether this GSTIN was already verified on the platform (by anyone) and the result.
 * - "Autofill (free)" when a recent verification exists; "Verify & autofill" otherwise (paid lookup).
 * Nothing is called while typing except the free status check.
 */
export function GstinVerify({ gstin, onResult, filled }: { gstin: string | null; onResult: (d: GstinInfo) => void; filled?: string[] }) {
  const { me } = useAuth();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<GstinInfo | null>(null);
  const [status, setStatus] = useState<GstinStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { isAvailable().then(setEnabled); }, []);
  const g = (gstin ?? "").trim().toUpperCase();
  const valid = g.length === 15 && !gstinError(g);
  const stale = info && info.gstin !== g;

  useEffect(() => {
    if (!enabled || !valid) return;
    let alive = true;
    const t = setTimeout(() => gstinStatuses([g]).then((r) => alive && setStatus(r[g])).catch(() => {}), 300);
    return () => { alive = false; clearTimeout(t); };
  }, [enabled, valid, g]);

  if (enabled === null) return null;
  if (!enabled) {
    // ordinary users never see a feature that is switched off; the super admin gets a pointer
    return me?.platform_role === "SUPERADMIN" ? (
      <p className="mt-1.5 text-xs text-amber-800">
        <BadgeCheck size={12} className="mr-1 inline" />
        &quot;Verify &amp; autofill&quot; is off — switch it on in <a href="/admin" className="underline">Admin → Integrations</a> (tick Enabled, Save).
      </p>
    ) : null;
  }

  async function run(refresh = false) {
    setBusy(true);
    setErr(null);
    try {
      const d = await api<GstinInfo>("/gstin/verify", { body: { gstin: g, refresh } });
      setInfo(d);
      const s: GstinStatus = { verified: true, verified_at: d.fetched_at, status: d.status, active: d.active, legal_name: d.legal_name,
        trade_name: d.trade_name, taxpayer_type: d.taxpayer_type, fresh: true, days_ago: 0 };
      statusCache.set(d.gstin, s);
      setStatus(s);
      onResult(d);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const known = valid && status?.verified && status.fresh;
  const st = valid && status && (!info || stale) ? status : null;

  return (
    <div className="mt-1.5 space-y-1.5">
      {st?.verified && (
        <div className={`rounded-md px-2.5 py-1.5 text-xs ${st.active ? "bg-emerald-50 text-emerald-900" : "bg-red-50 text-red-900"}`}>
          <span className="font-medium">{st.active ? <BadgeCheck size={12} className="mr-1 inline" /> : <ShieldAlert size={12} className="mr-1 inline" />}
            Already verified on <BrandName /></span> on {fmt(st.verified_at)}{st.days_ago ? ` (${st.days_ago} days ago)` : ""}: <b>{st.status || "—"}</b>
          {st.legal_name ? ` · ${st.legal_name}` : ""}
          {!st.active && <div className="mt-0.5 font-medium">At the last check this GSTIN was not active.</div>}
        </div>
      )}
      {(!info || stale) && (
        <button type="button" disabled={!valid || busy} onClick={() => run()}
          title={!valid ? "Type the full 15-character GSTIN to enable"
            : known ? "Fill the details from the earlier verification — no new lookup is made"
              : "Fetch name, address and registration details from the GST portal"}
          className="inline-flex items-center gap-1.5 rounded-md border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <BadgeCheck size={13} />}
          {known ? "Autofill from verified details (free)" : status?.verified ? "Verify again & autofill" : "Verify & autofill"}
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
          {!info.active && <div className="mt-1 font-medium">This GSTIN is not active as per the latest available data — please confirm with the party before charging or claiming GST.</div>}
          {filled && filled.length > 0 && <div className="mt-1 opacity-80">Filled in: {filled.join(", ")}. Please check and complete the rest.</div>}
          <div className="opacity-60">{info.source === "cache" ? `From the verification of ${fmt(info.fetched_at)} — no new lookup was made.` : "Verified just now."} Data as provided by the GST data source.</div>
        </div>
      )}
    </div>
  );
}
