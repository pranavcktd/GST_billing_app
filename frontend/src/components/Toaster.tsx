"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { onToast, type Toast } from "@/lib/toast";

/** Shows toast() messages for a few seconds at the bottom of the screen. */
export function Toaster() {
  const [items, setItems] = useState<Toast[]>([]);
  useEffect(() => onToast((t) => {
    setItems((cur) => [...cur.slice(-2), t]);
    setTimeout(() => setItems((cur) => cur.filter((x) => x.id !== t.id)), 3000);
  }), []);
  if (!items.length) return null;
  return (
    <div className="no-print pointer-events-none fixed inset-x-0 bottom-5 z-[100] flex flex-col items-center gap-2 px-4" role="status" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} className={`pointer-events-auto flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white shadow-lg ${t.tone === "ok" ? "bg-emerald-600" : "bg-red-600"}`}>
          {t.tone === "ok" ? <CheckCircle2 size={16} /> : <XCircle size={16} />} {t.text}
        </div>
      ))}
    </div>
  );
}
