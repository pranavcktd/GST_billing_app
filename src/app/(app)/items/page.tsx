"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ImportButton } from "@/components/ImportDialog";
import { Card, Empty, ErrorBox, Input, LinkButton, Loading, PageHeader } from "@/components/ui";
import { qs } from "@/lib/api";
import { money, qty } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Item } from "@/lib/types";
import { ExportMenu, simpleDoc } from "@/components/ExportMenu";
import { usePaged } from "@/components/Pager";

export default function ItemsPage() {
  const [search, setSearch] = useState("");
  const { data, error, loading, reload } = useFetch<Item[]>(`/items${qs({ search })}`);
  const { rows, pager } = usePaged(data);
  const buildDoc = () => data && simpleDoc("Items & stock",
    ["Item", "Code", "Type", "HSN/SAC", "Unit", "GST %", "Sale price", "Purchase price", "Stock", "Stock value"],
    data.map((i) => [i.name, i.code, i.type === "SERVICE" ? "Service" : "Goods", i.hsn_sac, i.unit, i.gst_rate, i.sale_price, i.purchase_price,
      i.type === "GOODS" ? i.stock : null, i.type === "GOODS" ? Math.round(i.stock * i.purchase_price * 100) / 100 : null]),
    { filename: "items", types: ["text", "text", "text", "text", "text", "pct", "money", "money", "qty", "money"] });
  const stockValue = data?.reduce((s, i) => s + (i.type === "GOODS" && i.stock > 0 ? i.stock * i.purchase_price : 0), 0) ?? 0;

  return (
    <>
      <PageHeader
        title="Items & Stock"
        sub={`Stock value (at purchase price): ${money(stockValue)}`}
        actions={
          <>
            <ExportMenu build={buildDoc} disabled={!data?.length} compact />
            <ImportButton entity="items" title="items (add or update)" onDone={reload} />
            <ImportButton entity="stock" title="stock adjustments" onDone={reload} />
            <LinkButton href="/items/new"><Plus size={16} /> Add item</LinkButton>
          </>
        }
      />
      <Input placeholder="Search name, code or HSN" value={search} onChange={(e) => setSearch(e.target.value)} className="mb-3 max-w-xs" />
      <ErrorBox message={error} />
      <Card className="overflow-x-auto">
        {loading && !data ? (
          <Loading />
        ) : !data?.length ? (
          <Empty title="No items yet" action={<LinkButton href="/items/new">Add your first item</LinkButton>} />
        ) : (
          <table className="tbl">
            <thead>
              <tr><th>Item</th><th>HSN/SAC</th><th className="num">GST</th><th className="num">Sale price</th><th className="num">Purchase price</th><th className="num">Stock</th></tr>
            </thead>
            <tbody>
              {rows.map((i) => {
                const low = i.type === "GOODS" && i.low_stock_level !== null && i.stock <= i.low_stock_level;
                return (
                  <tr key={i.id}>
                    <td>
                      <Link href={`/items/${i.id}`} className="font-medium text-brand-600 hover:underline">{i.name}</Link>
                      {i.code && <span className="ml-2 text-xs text-gray-500">{i.code}</span>}
                      {i.type === "SERVICE" && <span className="ml-2 rounded bg-gray-100 px-1.5 text-xs text-gray-600">Service</span>}
                    </td>
                    <td className="font-mono text-xs">{i.hsn_sac ?? "—"}</td>
                    <td className="num">{i.gst_rate}%</td>
                    <td className="num">{money(i.sale_price)}</td>
                    <td className="num">{money(i.purchase_price)}</td>
                    <td className={`num ${low ? "font-semibold text-red-700" : ""}`}>
                      {i.type === "GOODS" ? `${qty(i.stock)} ${i.unit}` : "—"}
                      {low && <span className="ml-1 text-xs">(low)</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {pager}
      </Card>
    </>
  );
}
