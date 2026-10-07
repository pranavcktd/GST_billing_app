"use client";

import { Truck } from "lucide-react";
import Link from "next/link";
import { usePerms } from "@/lib/auth";
import { kindOf } from "@/lib/constants";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Pending {
  count: number; ewb: number; irn: number;
  items: { id: string; type: string; number: string; date: string; party_name: string; total: number; ewb: boolean; irn: boolean }[];
}

/** Dashboard: recent bills that still need an e-way bill or an IRN, so none slip through. */
export function EinvoiceAlert() {
  const { can } = usePerms();
  const { data } = useFetch<Pending>(can("sales") ? "/einvoice/pending" : null);
  if (!data?.count) return null;
  const what = [data.ewb && `${data.ewb} need an e-way bill`, data.irn && `${data.irn} need an IRN`].filter(Boolean).join(" · ");
  return (
    <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <div className="flex flex-wrap items-center gap-2 font-medium">
        <Truck size={16} /> {what}
        <Link href="/ewaybills" className="ml-auto text-xs underline">E-way bill register</Link>
      </div>
      <ul className="mt-1.5 space-y-0.5 text-xs">
        {data.items.slice(0, 5).map((x) => (
          <li key={x.id}>
            <Link href={`/v/${kindOf(x.type as never)}/${x.id}`} className="hover:underline">
              {x.number} · {fmtDate(x.date)} · {x.party_name} · {money(x.total)} — {[x.ewb && "e-way bill", x.irn && "IRN"].filter(Boolean).join(" + ")} pending
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
