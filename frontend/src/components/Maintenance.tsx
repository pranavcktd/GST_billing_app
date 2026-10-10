"use client";

import { Wrench } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useConfig } from "@/lib/config";

export type MaintenanceState = { active: boolean; scheduled: boolean; starts_at: string | null; ends_at: string | null; message: string; auto_end: boolean };

/** The current maintenance window, checked every minute (it can be switched on while someone is working). */
export function useMaintenance(): MaintenanceState | undefined {
  const fromConfig = useConfig().maintenance;
  const [polled, setM] = useState<MaintenanceState | undefined>();
  useEffect(() => {
    let alive = true;
    const load = () => fetch(`${API_URL}/api/meta`).then((r) => (r.ok ? r.json() : null))
      .then((meta) => { if (alive && meta?.maintenance) setM(meta.maintenance); }).catch(() => {});
    const t = setInterval(load, 60000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  return polled ?? fromConfig;
}

/** Ticks every second: time left until `iso` as “1 h 05 m 09 s”. */
export function useCountdown(iso: string | null | undefined): string | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!iso) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [iso]);
  if (!iso) return null;
  let s = Math.max(0, Math.round((new Date(iso).getTime() - now) / 1000));
  const h = Math.floor(s / 3600); s -= h * 3600;
  const m = Math.floor(s / 60); s -= m * 60;
  return `${h ? `${h} h ` : ""}${String(m).padStart(h ? 2 : 1, "0")} m ${String(s).padStart(2, "0")} s`;
}

export const istTime = (iso: string | null) => iso
  ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" }) + " IST"
  : "";

/** Thin bar on every screen: maintenance coming up (save your work), or — for the super admin — maintenance is on. */
export function MaintenanceBanner() {
  const m = useMaintenance();
  const { me } = useAuth();
  const path = usePathname();
  const startsIn = useCountdown(m?.scheduled ? m.starts_at : null);
  if (!m || path.startsWith("/login") || path.startsWith("/print") || path.startsWith("/receipt")) return null;
  if (m.scheduled) {
    return (
      <div className="no-print sticky top-0 z-50 flex items-center justify-center gap-2 bg-amber-100 px-4 py-1.5 text-center text-xs text-amber-900">
        <Wrench size={13} className="shrink-0" />
        <span>Scheduled maintenance starts in <b className="tabular-nums">{startsIn}</b> ({istTime(m.starts_at)}{m.ends_at ? ` – ${istTime(m.ends_at)}` : ""}). Please save your work — you will be signed out.</span>
      </div>
    );
  }
  if (m.active && me?.platform_role === "SUPERADMIN") {
    return (
      <div className="no-print sticky top-0 z-50 flex items-center justify-center gap-2 bg-rose-100 px-4 py-1.5 text-xs text-rose-900">
        <Wrench size={13} /> Maintenance mode is ON — only super admins can use the platform. End it in Admin → Maintenance.
      </div>
    );
  }
  return null;
}
