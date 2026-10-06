"use client";

import { AlertTriangle, CalendarClock } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import { hiddenHrefs, isHiddenHref } from "@/lib/modules";
import { useFetch } from "@/lib/useFetch";

interface Summary {
  summary: { OVERDUE: number; DUE_SOON: number } | null;
  next: { code: string; name: string; period: string; due_date: string; status: string; period_key: string }[];
}

/** Dashboard strip: overdue filings and those due in the next 15 days (links to the compliance calendar). */
export function ComplianceAlert() {
  const { business } = useAuth();
  const off = isHiddenHref("/compliance", hiddenHrefs(business));
  const { data } = useFetch<Summary>(off ? null : "/compliance/summary");
  if (off || !data?.summary || (!data.summary.OVERDUE && !data.summary.DUE_SOON)) return null;
  const overdue = data.summary.OVERDUE > 0;
  return (
    <Link href="/compliance" className={`mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border px-4 py-3 text-sm hover:opacity-95 ${overdue ? "border-red-200 bg-red-50 text-red-800" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
      <span className="flex items-center gap-2 font-medium">
        {overdue ? <AlertTriangle size={16} /> : <CalendarClock size={16} />}
        {overdue ? `${data.summary.OVERDUE} filing${data.summary.OVERDUE === 1 ? "" : "s"} overdue` : ""}
        {overdue && data.summary.DUE_SOON ? " · " : ""}
        {data.summary.DUE_SOON ? `${data.summary.DUE_SOON} due in the next 15 days` : ""}
      </span>
      <span className="text-xs opacity-90">
        {data.next.map((n) => `${n.name} (${n.period}) — ${fmtDate(n.due_date)}`).join(" · ")}
      </span>
      <span className="ml-auto text-xs font-medium underline">Open compliance calendar</span>
    </Link>
  );
}
