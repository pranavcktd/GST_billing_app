"use client";

import { Printer } from "lucide-react";
import { useParams } from "next/navigation";
import { InvoiceDocument } from "@/components/InvoiceDocument";
import { Button, Loading } from "@/components/ui";
import { useFetch } from "@/lib/useFetch";
import type { Business, VoucherDetail } from "@/lib/types";

/** Public, read-only document view for customers who received a link (no login needed). */
export default function PublicInvoice() {
  const { token } = useParams<{ token: string }>();
  const { data, error } = useFetch<{ voucher: VoucherDetail; business: Business }>(`/public/invoice/${token}`);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6 text-center">
        <div><h1 className="text-lg font-semibold text-gray-900">Link not available</h1><p className="mt-1 text-sm text-gray-600">{error}</p></div>
      </div>
    );
  }
  if (!data) return <Loading />;
  return (
    <div className="min-h-screen bg-gray-100 py-6 print:bg-white print:py-0">
      <div className="no-print mx-auto mb-4 flex max-w-[210mm] items-center justify-between px-2">
        <div className="text-sm text-gray-600">{data.voucher.title} from <b>{data.business.name}</b></div>
        <Button onClick={() => window.print()}><Printer size={16} /> Print / Save PDF</Button>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[760px]">
          <InvoiceDocument v={data.voucher} business={data.business} />
        </div>
      </div>
    </div>
  );
}
