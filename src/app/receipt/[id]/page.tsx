"use client";

import { ArrowLeft, Printer } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { type Txn, TxnStatus, when } from "@/components/Transactions";
import { Button, ErrorBox, Loading } from "@/components/ui";
import { useDocTitle } from "@/lib/docName";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Receipt extends Txn {
  seller: { name: string; email: string; phone: string; address: string; gstin?: string; website?: string; brand: string };
  buyer: { name: string | null; gstin: string | null; address: string | null };
  tax_split: "IGST" | "CGST_SGST";
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return v ? <div className="flex justify-between gap-4 py-1"><span className="text-gray-500">{k}</span><span className="text-right font-medium">{v}</span></div> : null;
}

/** Receipt for a subscription payment (or the details of a failed / unfinished one) — print or save as PDF.
 *  Open to the account owner and to the platform team with the Transactions area. */
export default function ReceiptPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: r, error } = useFetch<Receipt>(`/billing/payments/${id}`);
  useDocTitle(r ? (r.receipt_no ? `Receipt_${r.receipt_no}` : `Payment_${r.order_id}`) : null);

  if (error) return <div className="mx-auto max-w-2xl p-6"><ErrorBox message={error} /></div>;
  if (!r) return <Loading />;
  const paid = r.status === "PAID";
  const half = Math.round(r.gst * 50) / 100;

  return (
    <div className="min-h-screen bg-gray-100 py-6 print:bg-white print:py-0">
      <div className="no-print mx-auto mb-4 flex max-w-2xl justify-between px-4">
        <Button variant="secondary" onClick={() => router.back()}><ArrowLeft size={15} /> Back</Button>
        <Button onClick={() => window.print()}><Printer size={15} /> Print / save PDF</Button>
      </div>
      <div className="mx-auto max-w-2xl bg-white p-8 text-sm text-gray-800 shadow print:shadow-none">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-gray-200 pb-4">
          <div>
            <div className="text-lg font-bold text-gray-900">{r.seller.name}</div>
            <div className="text-xs text-gray-500">{r.seller.brand}</div>
            <div className="mt-1 text-xs whitespace-pre-line text-gray-600">{r.seller.address}</div>
            <div className="text-xs text-gray-600">{[r.seller.email, r.seller.phone].filter(Boolean).join(" · ")}</div>
            {r.seller.gstin && <div className="text-xs text-gray-600">GSTIN {r.seller.gstin}</div>}
          </div>
          <div className="text-right">
            <div className="text-xl font-semibold text-gray-900">{paid ? "Payment receipt" : "Payment details"}</div>
            {r.receipt_no && <div className="font-mono text-sm">{r.receipt_no}</div>}
            <div className="mt-1 text-xs text-gray-500">{when(r.paid_at ?? r.created_at)}</div>
            <div className="mt-1"><TxnStatus t={r} /></div>
          </div>
        </div>

        <div className="grid gap-4 border-b border-gray-200 py-4 sm:grid-cols-2">
          <div>
            <div className="text-xs font-semibold text-gray-500 uppercase">Billed to</div>
            <div className="mt-1 font-semibold">{r.buyer.name ?? r.owner_name}</div>
            {r.buyer.address && <div className="text-xs text-gray-600">{r.buyer.address}</div>}
            {r.buyer.gstin && <div className="text-xs text-gray-600">GSTIN {r.buyer.gstin}</div>}
            <div className="text-xs text-gray-600">{r.owner_name} · {r.owner_email}{r.owner_phone ? ` · ${r.owner_phone}` : ""}</div>
          </div>
          <div className="text-xs">
            <Row k="Order id" v={<span className="font-mono">{r.order_id}</span>} />
            <Row k="Payment id" v={r.payment_id && <span className="font-mono">{r.payment_id}</span>} />
            <Row k="Method" v={r.method?.toUpperCase()} />
            {r.mode !== "LIVE" && <Row k="Mode" v={r.mode === "TEST" ? "Razorpay test — no money charged" : "Simulated (development)"} />}
          </div>
        </div>

        <table className="mt-4 w-full">
          <thead><tr className="border-b border-gray-200 text-left text-xs text-gray-500"><th className="py-2">Description</th><th className="py-2 text-right">Amount</th></tr></thead>
          <tbody>
            <tr className="border-b border-gray-100"><td className="py-2">{r.item}<div className="text-xs text-gray-500">Software subscription ({r.seller.brand})</div></td><td className="py-2 text-right tabular-nums">{money(r.taxable)}</td></tr>
            {r.tax_split === "CGST_SGST" ? (
              <>
                <tr><td className="py-1 text-gray-600">CGST @ {r.gst_rate / 2}%</td><td className="py-1 text-right tabular-nums">{money(half)}</td></tr>
                <tr><td className="py-1 text-gray-600">SGST @ {r.gst_rate / 2}%</td><td className="py-1 text-right tabular-nums">{money(r.gst - half)}</td></tr>
              </>
            ) : <tr><td className="py-1 text-gray-600">IGST @ {r.gst_rate}%</td><td className="py-1 text-right tabular-nums">{money(r.gst)}</td></tr>}
            <tr className="border-t border-gray-300 font-semibold"><td className="py-2">{paid ? "Total paid" : "Amount"}</td><td className="py-2 text-right tabular-nums">{money(r.amount)}</td></tr>
          </tbody>
        </table>

        {!paid && (
          <p className={`mt-4 rounded-md px-3 py-2 text-xs ${r.status === "FAILED" ? "bg-red-50 text-red-800" : "bg-amber-50 text-amber-800"}`}>
            {r.status === "FAILED" ? `This payment failed${r.error_reason ? `: ${r.error_reason}` : ""}. ` : r.status === "CANCELLED" ? "The checkout was closed without paying. " : "This payment was not completed. "}
            No receipt is issued. If money was debited, your bank returns it automatically (usually within 5–7 working days).
          </p>
        )}
        <p className="mt-6 text-center text-[11px] text-gray-400">
          {paid ? "This is a computer-generated receipt and needs no signature." : "This is not a receipt."} Amounts in Indian Rupees, inclusive of GST.
        </p>
      </div>
    </div>
  );
}
