"use client";

import { ArrowLeft, Printer } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { DEFAULT_PRINT, InvoiceDocument } from "@/components/InvoiceDocument";
import { ThermalReceipt } from "@/components/ThermalReceipt";
import { Button, ErrorBox, Loading, Select } from "@/components/ui";
import { kindOf } from "@/lib/constants";
import { docFileName, useDocTitle } from "@/lib/docName";
import { useFetch } from "@/lib/useFetch";
import type { Business, VoucherDetail } from "@/lib/types";

type Format = "A4" | "A5" | "THERMAL_80" | "THERMAL_58";
type Copy = "ORIGINAL" | "DUPLICATE" | "TRIPLICATE";

function PrintView() {
  const { id } = useParams<{ id: string }>();
  const sp = useSearchParams();
  const router = useRouter();
  const { data: v, error } = useFetch<VoucherDetail>(`/vouchers/${id}`);
  const { data: business } = useFetch<Business>("/businesses/current");
  const [format, setFormat] = useState<Format | null>((sp.get("format") as Format) ?? null);
  const [copies, setCopies] = useState<Copy[] | null>(null);
  useDocTitle(v ? docFileName(v) : null);

  if (error) return <div className="p-6"><ErrorBox message={error} /></div>;
  if (!v || !business) return <Loading />;

  const ps = { ...DEFAULT_PRINT, ...(business.print_settings ?? {}) };
  const fmt: Format = format ?? ps.paper;
  const selected: Copy[] = copies ?? (v.type === "SALE" ? ps.copy_labels : ["ORIGINAL"]);
  const thermal = fmt.startsWith("THERMAL");
  const docBusiness = { ...business, print_settings: { ...ps, paper: fmt === "A5" ? "A5" : "A4" } } as Business;

  return (
    <div className="min-h-screen bg-gray-100 py-6 print:bg-white print:py-0">
      {(v.ewb_required || v.irn_required) && (
        <div className="no-print mx-auto mb-3 max-w-[210mm] rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
          {v.irn_required && <div><b>IRN not generated.</b> This B2B invoice needs an IRN (e-invoice) before it is printed or sent.</div>}
          {v.ewb_required && <div><b>E-way bill not generated.</b> The goods are worth more than the e-way bill limit — generate it before they move.</div>}
          <button className="mt-1 font-medium underline" onClick={() => router.push(`/v/${kindOf(v.type)}/${v.id}`)}>Open the invoice to generate it</button>
        </div>
      )}
      <div className="no-print mx-auto mb-4 flex max-w-[210mm] flex-wrap items-center justify-between gap-2 px-2">
        <Button variant="secondary" onClick={() => router.push(sp.get("back") ?? `/v/${kindOf(v.type)}/${v.id}`)}>
          <ArrowLeft size={16} /> Back
        </Button>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={fmt} onChange={(e) => setFormat(e.target.value as Format)} className="!w-auto">
            <option value="A4">A4</option><option value="A5">A5</option>
            <option value="THERMAL_80">Thermal 80 mm</option><option value="THERMAL_58">Thermal 58 mm</option>
          </Select>
          {!thermal && v.type === "SALE" && (["ORIGINAL", "DUPLICATE", "TRIPLICATE"] as Copy[]).map((c) => (
            <label key={c} className="flex items-center gap-1 text-xs text-gray-700">
              <input type="checkbox" checked={selected.includes(c)}
                onChange={(e) => setCopies(e.target.checked ? [...selected, c] : selected.filter((x) => x !== c))} />
              {c.charAt(0) + c.slice(1).toLowerCase()}
            </label>
          ))}
          {v.ewb_no && <Button variant="secondary" onClick={() => router.push(`/print/ewaybill/${v.id}`)}><Printer size={16} /> E-way bill</Button>}
          <Button onClick={() => window.print()}><Printer size={16} /> Print / Save PDF</Button>
        </div>
      </div>
      {thermal ? (
        <ThermalReceipt v={v} business={business} width={fmt === "THERMAL_58" ? 58 : 80} />
      ) : (
        (selected.length ? selected : (["ORIGINAL"] as Copy[])).map((c, i) => (
          <div key={c} style={i > 0 ? { breakBefore: "page" } : undefined} className={i > 0 ? "mt-6 print:mt-0" : ""}>
            {fmt === "A5" && <style>{"@media print { @page { size: A5; margin: 8mm } }"}</style>}
            <InvoiceDocument v={v} business={docBusiness} copy={c} />
          </div>
        ))
      )}
    </div>
  );
}

export default function PrintPage() {
  return (
    <Suspense fallback={<Loading />}>
      <PrintView />
    </Suspense>
  );
}
