"use client";

import { Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, LinkButton, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, money, qty, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Item } from "@/lib/types";

interface Move { id: string; date: string; type: string; qty: number; rate: number | null; voucher_id: string | null; note: string | null }

const MOVE_LABEL: Record<string, string> = {
  OPENING: "Opening stock", SALE: "Sale", SALE_RETURN: "Sale return", PURCHASE: "Purchase",
  PURCHASE_RETURN: "Purchase return", ADJUSTMENT: "Adjustment",
};

export default function ItemDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: item, error, setData } = useFetch<Item>(`/items/${id}`);
  const { data: moves, reload } = useFetch<Move[]>(`/items/${id}/movements`);
  const [adj, setAdj] = useState({ qty: "", direction: "ADD", date: today(), note: "" });
  const [adjError, setAdjError] = useState<string | null>(null);

  if (error) return <ErrorBox message={error} />;
  if (!item) return <Loading />;

  async function adjust(e: React.FormEvent) {
    e.preventDefault();
    setAdjError(null);
    try {
      setData(await api<Item>(`/items/${id}/adjust`, { body: { ...adj, qty: Number(adj.qty) } }));
      setAdj({ ...adj, qty: "", note: "" });
      reload();
    } catch (err) {
      setAdjError((err as Error).message);
    }
  }

  const remove = async () => {
    if (!confirm("Delete this item? Items used in bills are only deactivated.")) return;
    await api(`/items/${id}`, { method: "DELETE" });
    router.push("/items");
  };

  return (
    <>
      <PageHeader
        title={item.name}
        sub={[item.hsn_sac && `HSN/SAC ${item.hsn_sac}`, `GST ${item.gst_rate}%`, item.code].filter(Boolean).join(" · ")}
        actions={
          <>
            <LinkButton href={`/items/${id}/edit`} variant="secondary"><Pencil size={16} /> Edit</LinkButton>
            <Button variant="danger" onClick={remove}><Trash2 size={16} /></Button>
          </>
        }
      />
      <div className="mb-5 grid gap-3 sm:grid-cols-4">
        <Card className="p-4"><div className="text-xs text-gray-500">Sale price</div><div className="mt-1 font-semibold">{money(item.sale_price)} <span className="text-xs font-normal text-gray-500">{item.sale_price_tax_inclusive ? "incl. tax" : "+ tax"}</span></div></Card>
        <Card className="p-4"><div className="text-xs text-gray-500">Purchase price</div><div className="mt-1 font-semibold">{money(item.purchase_price)}</div></Card>
        {item.type === "GOODS" && (
          <>
            <Card className="p-4"><div className="text-xs text-gray-500">In stock</div><div className="mt-1 font-semibold">{qty(item.stock)} {item.unit}</div></Card>
            <Card className="p-4"><div className="text-xs text-gray-500">Stock value</div><div className="mt-1 font-semibold">{money(Math.max(item.stock, 0) * item.purchase_price)}</div></Card>
          </>
        )}
      </div>

      {item.type === "GOODS" && (
        <div className="grid gap-5 lg:grid-cols-3">
          <Card className="p-5">
            <h2 className="mb-3 font-semibold text-gray-900">Adjust stock</h2>
            <form onSubmit={adjust} className="space-y-3">
              <ErrorBox message={adjError} />
              <div className="grid grid-cols-2 gap-3">
                <Field label="Action">
                  <Select value={adj.direction} onChange={(e) => setAdj({ ...adj, direction: e.target.value })}>
                    <option value="ADD">Add stock</option>
                    <option value="REDUCE">Reduce stock</option>
                  </Select>
                </Field>
                <Field label={`Quantity (${item.unit})`}>
                  <Input type="number" min="0.001" step="0.001" required value={adj.qty} onChange={(e) => setAdj({ ...adj, qty: e.target.value })} />
                </Field>
              </div>
              <Field label="Date"><Input type="date" value={adj.date} onChange={(e) => setAdj({ ...adj, date: e.target.value })} /></Field>
              <Field label="Reason"><Input placeholder="Damaged, count correction…" value={adj.note} onChange={(e) => setAdj({ ...adj, note: e.target.value })} /></Field>
              <Button type="submit" className="w-full">Save adjustment</Button>
            </form>
          </Card>
          <Card className="overflow-x-auto lg:col-span-2">
            <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Stock history</h2>
            <table className="tbl">
              <thead><tr><th>Date</th><th>Type</th><th>Note</th><th className="num">Qty</th></tr></thead>
              <tbody>
                {moves?.map((m) => (
                  <tr key={m.id}>
                    <td>{fmtDate(m.date)}</td>
                    <td>{m.voucher_id ? <Link href={`/doc/${m.voucher_id}`} className="text-brand-600 hover:underline">{MOVE_LABEL[m.type]}</Link> : MOVE_LABEL[m.type]}</td>
                    <td className="text-gray-600">{m.note ?? ""}</td>
                    <td className={`num ${m.qty < 0 ? "text-red-700" : "text-emerald-700"}`}>{m.qty > 0 ? "+" : ""}{qty(m.qty)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}
    </>
  );
}
