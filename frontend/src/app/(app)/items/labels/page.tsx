"use client";

import JsBarcode from "jsbarcode";
import { Printer, Wand2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Button, Card, ErrorBox, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Business, Item } from "@/lib/types";

function Barcode({ value }: { value: string }) {
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    try {
      const ean = /^\d{13}$/.test(value);
      JsBarcode(ref.current, value, { format: ean ? "EAN13" : "CODE128", height: 34, width: 1.4, fontSize: 11, margin: 0, displayValue: true });
    } catch {
      /* invalid code for the symbology */
    }
  }, [value]);
  return <svg ref={ref} className="max-w-full" />;
}

const SIZES = { "50x25": "grid-cols-4", "38x25": "grid-cols-5", "100x50": "grid-cols-2" } as const;

/** Print barcode labels (A4 sticker sheets) for items. */
export default function LabelsPage() {
  const { business: mine } = useAuth();
  const { data: items, reload } = useFetch<Item[]>("/items");
  const { data: business } = useFetch<Business>("/businesses/current");
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [size, setSize] = useState<keyof typeof SIZES>("50x25");
  const [showPrice, setShowPrice] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  if (!items || !business) return <Loading />;
  const allowed = business.plan?.barcode;
  const goods = items.filter((i) => i.type === "GOODS");
  const labels = goods.flatMap((i) => Array.from({ length: counts[i.id] ?? 0 }, () => i)).filter((i) => i.code);
  const missing = goods.filter((i) => !i.code).length;

  return (
    <>
      <div className="no-print">
        <PageHeader title="Barcode labels" sub="Print sticker sheets for your products; scan them at the POS counter"
          actions={
            <>
              {missing > 0 && mine?.role !== "BILLING" && (
                <Button variant="secondary" disabled={!allowed} onClick={async () => {
                  try { const r = await api<{ assigned: number }>("/items/assign-codes", { body: {} }); setErr(null); reload(); alert(`${r.assigned} item(s) got a barcode`); }
                  catch (e) { setErr((e as Error).message); }
                }}><Wand2 size={16} /> Create codes for {missing} item(s)</Button>
              )}
              <Button disabled={!allowed || !labels.length} onClick={() => window.print()}><Printer size={16} /> Print {labels.length} label(s)</Button>
            </>
          } />
        {!allowed && (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            Barcode label printing is part of the Enterprise plan. <Link href="/billing?plan=ENTERPRISE" className="font-medium underline">Upgrade</Link>
          </div>
        )}
        <ErrorBox message={err} />
        <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2">Label size
            <Select value={size} onChange={(e) => setSize(e.target.value as keyof typeof SIZES)} className="!w-auto">
              <option value="50x25">50 × 25 mm (4 per row)</option><option value="38x25">38 × 25 mm (5 per row)</option><option value="100x50">100 × 50 mm (2 per row)</option>
            </Select>
          </label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={showPrice} onChange={(e) => setShowPrice(e.target.checked)} /> Show price</label>
        </div>
        <Card className="mb-6 overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>Item</th><th>Code</th><th className="num">Sale price</th><th className="w-32">Labels</th></tr></thead>
            <tbody>
              {goods.map((i) => (
                <tr key={i.id}>
                  <td>{i.name}</td>
                  <td className="font-mono text-xs">{i.code ?? <span className="text-amber-700">no code</span>}</td>
                  <td className="num">{money(i.sale_price)}</td>
                  <td><Input type="number" min={0} max={500} disabled={!i.code} value={counts[i.id] ?? ""} onChange={(e) => setCounts({ ...counts, [i.id]: Math.max(0, Number(e.target.value) || 0) })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
      {allowed && labels.length > 0 && (
        <div className={`print-sheet grid gap-1 bg-white ${SIZES[size]}`}>
          {labels.map((i, n) => (
            <div key={n} className="flex flex-col items-center justify-center overflow-hidden border border-dashed border-gray-300 p-1 text-center print:border-gray-200">
              <div className="w-full truncate text-[10px] font-semibold">{business.name}</div>
              <div className="w-full truncate text-[11px]">{i.name}</div>
              <Barcode value={i.code!} />
              {showPrice && <div className="text-[11px] font-bold">{i.mrp ? `MRP ${money(i.mrp)}` : money(i.sale_price)}</div>}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
