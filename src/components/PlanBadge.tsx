"use client";

import { Crown } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useFetch } from "@/lib/useFetch";

interface PlanStatus { plan: { code: string; name: string }; status: "TRIAL" | "ACTIVE" | "EXPIRED"; valid_until: string | null }

const short = (d: string) => new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

/** Top bar: current plan and when it ends — amber in the last 7 days, red once expired. Opens Plan & billing. */
export function PlanBadge() {
  const { data } = useFetch<PlanStatus>("/billing/status");
  const [now] = useState(() => Date.now());
  if (!data) return null;
  const days = data.valid_until ? Math.ceil((new Date(data.valid_until).getTime() - now) / 86400000) : null;
  const trial = data.status === "TRIAL";
  const expired = data.status === "EXPIRED" || (days !== null && days < 0);
  const soon = !expired && days !== null && days <= 7;
  const label = trial ? `${data.plan.name} trial` : data.plan.name;
  const until = expired ? "expired" : data.valid_until
    ? (trial || soon ? `${days} day${days === 1 ? "" : "s"} left` : `till ${short(data.valid_until)}`)
    : data.plan.code === "FREE" ? "free forever" : "";
  const tone = expired ? "border-red-200 bg-red-50 text-red-700" : soon || trial ? "border-amber-200 bg-amber-50 text-amber-800" : "border-gray-200 bg-white text-gray-700";
  return (
    <Link href="/billing" title={`Plan: ${label}${data.valid_until ? ` · ends ${short(data.valid_until)}` : ""} — open Plan & billing`}
      className={`hidden items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs whitespace-nowrap hover:opacity-90 lg:inline-flex ${tone}`}>
      <Crown size={13} className={expired ? "" : "text-amber-500"} />
      <span className="font-medium">{label}</span>{until && <span className="opacity-80">· {until}</span>}
    </Link>
  );
}
