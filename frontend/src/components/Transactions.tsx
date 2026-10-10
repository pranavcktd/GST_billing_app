"use client";

import Link from "next/link";
import { money } from "@/lib/format";

export interface Txn {
  id: string; created_at: string; paid_at: string | null; item: string; plan: string; cycle: string; amount: number; taxable: number; gst: number;
  gst_rate: number; status: "CREATED" | "PAID" | "FAILED" | "CANCELLED"; status_label: string; mode: string; method: string | null;
  order_id: string; payment_id: string | null; receipt_no: string | null; error_code: string | null; error_reason: string | null;
  account_id: string; owner_name: string | null; owner_email: string | null; owner_phone: string | null; business_id: string | null; business_name: string | null;
}

const STYLE: Record<string, string> = {
  PAID: "bg-emerald-50 text-emerald-700 ring-emerald-200", FAILED: "bg-red-50 text-red-700 ring-red-200",
  CANCELLED: "bg-gray-100 text-gray-600 ring-gray-200", CREATED: "bg-amber-50 text-amber-800 ring-amber-200",
};

export function TxnStatus({ t }: { t: Pick<Txn, "status" | "status_label" | "mode"> }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STYLE[t.status] ?? STYLE.CREATED}`}>{t.status_label}</span>
      {t.mode !== "LIVE" && <span className="rounded bg-amber-100 px-1 text-[10px] font-semibold text-amber-800">{t.mode}</span>}
    </span>
  );
}

export const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

/** The owner's own payments (Subscription page): every attempt, with the receipt for paid ones. */
export function MyTransactions({ rows }: { rows: Txn[] }) {
  if (!rows.length) return <p className="px-5 pb-4 text-sm text-gray-500">No payments yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="tbl">
        <thead><tr><th>Date</th><th>For</th><th className="num">Amount</th><th>Status</th><th>Details</th><th /></tr></thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id}>
              <td className="whitespace-nowrap">{when(t.created_at)}</td>
              <td>{t.item}</td>
              <td className="num">{money(t.amount)}</td>
              <td><TxnStatus t={t} /></td>
              <td className="text-xs text-gray-500">
                {t.status === "PAID" ? <>Receipt {t.receipt_no}{t.method ? ` · ${t.method.toUpperCase()}` : ""}</>
                  : t.error_reason ?? (t.status === "CREATED" ? "Payment not completed" : "")}
              </td>
              <td className="text-right whitespace-nowrap">
                <Link href={`/receipt/${t.id}`} className="text-sm text-brand-600 hover:underline">{t.status === "PAID" ? "Receipt" : "View"}</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

