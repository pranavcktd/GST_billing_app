"use client";

import { Clock } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Me { linked: boolean; name?: string; status?: string | null; check_in?: string | null; check_out?: string | null }

/** Top bar: staff linked to an employee record check in / out themselves (marks today's attendance). */
export function CheckInButton() {
  const { data, setData } = useFetch<Me>("/attendance/me");
  const [busy, setBusy] = useState(false);
  if (!data?.linked) return null;
  if (data.check_out) return <span className="hidden items-center gap-1 text-xs text-gray-500 md:inline-flex" title="Today's attendance"><Clock size={13} /> {data.check_in}–{data.check_out}</span>;
  const action = data.check_in ? "check-out" : "check-in";
  async function go() {
    setBusy(true);
    try {
      const r = await api<Me>(`/attendance/me/${action}`, { body: {} });
      setData({ ...data!, ...r });
    } catch (e) { alert((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <button onClick={go} disabled={busy} title={data.check_in ? `Checked in at ${data.check_in}` : "Mark today's attendance"}
      className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium ${data.check_in ? "bg-gray-100 text-gray-700 hover:bg-gray-200" : "bg-emerald-600 text-white hover:bg-emerald-700"}`}>
      <Clock size={14} /> {data.check_in ? `Check out (in ${data.check_in})` : "Check in"}
    </button>
  );
}
