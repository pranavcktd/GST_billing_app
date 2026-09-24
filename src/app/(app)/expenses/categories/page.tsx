"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { ImportButton } from "@/components/ImportDialog";
import { Button, Card, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { GST_RATES } from "@/lib/constants";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { ExpenseCategory, ExpenseItem } from "@/lib/types";

export default function ExpenseSetupPage() {
  const { data: cats, reload: reloadCats } = useFetch<ExpenseCategory[]>("/expenses/categories");
  const { data: items, reload: reloadItems } = useFetch<ExpenseItem[]>("/expenses/items");
  const [cat, setCat] = useState<{ id?: string; name: string; kind: "DIRECT" | "INDIRECT" }>({ name: "", kind: "INDIRECT" });
  const [item, setItem] = useState<{ id?: string; name: string; category_id: string; rate: string; gst_rate: number; hsn_sac: string }>(
    { name: "", category_id: "", rate: "", gst_rate: 0, hsn_sac: "" });
  const [error, setError] = useState<string | null>(null);

  if (!cats || !items) return <Loading />;
  const catName = (id: string | null) => cats.find((c) => c.id === id)?.name ?? "—";

  async function saveCat(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api(cat.id ? `/expenses/categories/${cat.id}` : "/expenses/categories", { method: cat.id ? "PUT" : "POST", body: { name: cat.name, kind: cat.kind } });
      setCat({ name: "", kind: "INDIRECT" });
      reloadCats();
    } catch (err) { setError((err as Error).message); }
  }

  async function saveItem(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api(item.id ? `/expenses/items/${item.id}` : "/expenses/items", { method: item.id ? "PUT" : "POST",
        body: { name: item.name, category_id: item.category_id || null, rate: Number(item.rate || 0), gst_rate: item.gst_rate, hsn_sac: item.hsn_sac || null } });
      setItem({ name: "", category_id: "", rate: "", gst_rate: 0, hsn_sac: "" });
      reloadItems();
    } catch (err) { setError((err as Error).message); }
  }

  const del = async (url: string, reload: () => void) => {
    if (!confirm("Delete? Entries already used in expenses are only deactivated.")) return;
    await api(url, { method: "DELETE" });
    reload();
  };

  return (
    <>
      <PageHeader title="Expense categories & items"
        sub="Direct expenses (manufacturing, freight inward, wages) go into cost of goods; indirect ones (rent, salary, petrol, tea) into operating expenses in P&L."
        actions={<ImportButton entity="expense-items" title="expense items" onDone={() => { reloadItems(); reloadCats(); }} />} />
      <ErrorBox message={error} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="overflow-x-auto">
          <form onSubmit={saveCat} className="flex flex-wrap items-end gap-2 border-b border-gray-100 p-4">
            <Field label={cat.id ? "Edit category" : "New category"} className="flex-1"><Input required value={cat.name} onChange={(e) => setCat({ ...cat, name: e.target.value })} placeholder="e.g. Diesel" /></Field>
            <Field label="Type">
              <Select value={cat.kind} onChange={(e) => setCat({ ...cat, kind: e.target.value as "DIRECT" | "INDIRECT" })}>
                <option value="INDIRECT">Indirect</option><option value="DIRECT">Direct</option>
              </Select>
            </Field>
            <Button type="submit">{cat.id ? "Update" : "Add"}</Button>
          </form>
          <table className="tbl">
            <thead><tr><th>Category</th><th>Type</th><th className="num">Total spent</th><th /></tr></thead>
            <tbody>
              {cats.map((c) => (
                <tr key={c.id} className={c.is_active ? "" : "text-gray-400"}>
                  <td>{c.name}</td><td>{c.kind === "DIRECT" ? "Direct" : "Indirect"}</td><td className="num">{money(c.total)}</td>
                  <td className="whitespace-nowrap text-right">
                    <button className="mr-2 text-gray-400 hover:text-gray-700" aria-label="Edit" onClick={() => setCat({ id: c.id, name: c.name, kind: c.kind })}><Pencil size={15} /></button>
                    <button className="text-gray-400 hover:text-red-600" aria-label="Delete" onClick={() => del(`/expenses/categories/${c.id}`, reloadCats)}><Trash2 size={15} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card className="overflow-x-auto">
          <form onSubmit={saveItem} className="grid grid-cols-2 gap-2 border-b border-gray-100 p-4 sm:grid-cols-4">
            <Field label={item.id ? "Edit item" : "New expense item"} className="col-span-2"><Input required value={item.name} onChange={(e) => setItem({ ...item, name: e.target.value })} placeholder="e.g. Petrol" /></Field>
            <Field label="Category" className="col-span-2">
              <Select value={item.category_id} onChange={(e) => setItem({ ...item, category_id: e.target.value })}>
                <option value="">Any</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </Field>
            <Field label="Default amount"><Input type="number" step="0.01" value={item.rate} onChange={(e) => setItem({ ...item, rate: e.target.value })} /></Field>
            <Field label="GST">
              <Select value={item.gst_rate} onChange={(e) => setItem({ ...item, gst_rate: Number(e.target.value) })}>
                {GST_RATES.map((r) => <option key={r} value={r}>{r}%</option>)}
              </Select>
            </Field>
            <Field label="HSN/SAC"><Input value={item.hsn_sac} onChange={(e) => setItem({ ...item, hsn_sac: e.target.value })} /></Field>
            <div className="flex items-end"><Button type="submit" className="w-full">{item.id ? "Update" : "Add"}</Button></div>
          </form>
          <table className="tbl">
            <thead><tr><th>Expense item</th><th>Category</th><th className="num">GST</th><th /></tr></thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} className={i.is_active ? "" : "text-gray-400"}>
                  <td>{i.name}</td><td>{catName(i.category_id)}</td><td className="num">{i.gst_rate}%</td>
                  <td className="whitespace-nowrap text-right">
                    <button className="mr-2 text-gray-400 hover:text-gray-700" aria-label="Edit" onClick={() => setItem({ id: i.id, name: i.name, category_id: i.category_id ?? "", rate: String(i.rate || ""), gst_rate: i.gst_rate, hsn_sac: i.hsn_sac ?? "" })}><Pencil size={15} /></button>
                    <button className="text-gray-400 hover:text-red-600" aria-label="Delete" onClick={() => del(`/expenses/items/${i.id}`, reloadItems)}><Trash2 size={15} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  );
}
