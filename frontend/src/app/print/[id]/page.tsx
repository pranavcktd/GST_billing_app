"use client";

import { ArrowLeft, Printer } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { InvoiceDocument } from "@/components/InvoiceDocument";
import { Button, ErrorBox, Loading } from "@/components/ui";
import { kindOf } from "@/lib/constants";
import { useFetch } from "@/lib/useFetch";
import type { Business, VoucherDetail } from "@/lib/types";

export default function PrintPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: v, error } = useFetch<VoucherDetail>(`/vouchers/${id}`);
  const { data: business } = useFetch<Business>("/businesses/current");

  if (error) return <div className="p-6"><ErrorBox message={error} /></div>;
  if (!v || !business) return <Loading />;

  return (
    <div className="min-h-screen bg-gray-100 py-6 print:bg-white print:py-0">
      <div className="no-print mx-auto mb-4 flex max-w-[210mm] items-center justify-between px-2">
        <Button variant="secondary" onClick={() => router.push(`/v/${kindOf(v.type)}/${v.id}`)}>
          <ArrowLeft size={16} /> Back
        </Button>
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-gray-500 sm:inline">Choose “Save as PDF” in the print dialog to download</span>
          <Button onClick={() => window.print()}><Printer size={16} /> Print / Save PDF</Button>
        </div>
      </div>
      <InvoiceDocument v={v} business={business} />
    </div>
  );
}
