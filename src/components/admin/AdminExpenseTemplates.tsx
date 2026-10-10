"use client";

import { Plus, RotateCcw, Trash2, X } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Item { name: string; gst_rate: number; hsn_sac: string | null }
interface Cat { name: string; kind: "DIRECT" | "INDIRECT"; itc_blocked: boolean; items: Item[] }
interface Data { categories: Cat[]; built_in: boolean; gst_rates: number[] }

/** Admin → Masters → Expense categories: the standard list new businesses are offered on their first visit. */
export function AdminExpenseTemplates() {
  const { data, setData } = useFetch<Data>("/admin/expense-templates");
  if (!data) return <Loading />;
  return <Editor key={JSON.stringify(data.categories)} data={data} onSaved={setData} />;
}

function Editor({ data, onSaved }: { data: Data; onSaved: (d: Data) => void }) {
  const [cats, setCats] = useState<Cat[]>(data.categories);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const set = (i: number, c: Partial<Cat>) => setCats(cats.map((x, j) => (j === i ? { ...x, ...c } : x)));
  const setItem = (i: number, k: number, it: Partial<Item>) => set(i, { items: cats[i].items.map((x, j) => (j === k ? { ...x, ...it } : x)) });

  async function save() {
    setErr(null); setMsg(null);
    try { onSaved(await api<Data>("/admin/expense-templates", { method: "PUT", body: { categories: cats } })); setMsg("Saved. New businesses will be offered this list."); }
    catch (e) { setErr((e as Error).message); }
  }
  async function reset() {
    if (!confirm("Go back to the built-in list? Your changes to the standard list are lost (businesses keep what they imported).")) return;
    onSaved(await api<Data>("/admin/expense-templates", { method: "DELETE" }));
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Standard expense categories</h2>
          <p className="max-w-2xl text-sm text-gray-500">
            Offered to every new business the first time it opens Expenses → Categories & Items. What a business imports becomes its own copy —
            changing this list never changes businesses that already imported. {data.built_in && <b>Currently the built-in list.</b>}
          </p>
        </div>
        <div className="flex gap-2">
          {!data.built_in && <Button variant="ghost" onClick={reset}><RotateCcw size={15} /> Built-in list</Button>}
          <Button variant="secondary" onClick={() => setCats([...cats, { name: "", kind: "INDIRECT", itc_blocked: false, items: [] }])}><Plus size={15} /> Category</Button>
          <Button onClick={save}>Save list</Button>
        </div>
      </div>
      <ErrorBox message={err} />
      {msg && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</p>}
      <div className="grid gap-3 lg:grid-cols-2">
        {cats.map((c, i) => (
          <Card key={i} className="space-y-2 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Input className="min-w-40 flex-1 font-medium" placeholder="Category name" value={c.name} onChange={(e) => set(i, { name: e.target.value })} />
              <Select value={c.kind} onChange={(e) => set(i, { kind: e.target.value as Cat["kind"] })} aria-label="Kind">
                <option value="INDIRECT">Indirect</option><option value="DIRECT">Direct (cost of goods)</option>
              </Select>
              <Button variant="ghost" className="!px-2 text-red-600" title="Remove category" onClick={() => setCats(cats.filter((_, j) => j !== i))}><Trash2 size={15} /></Button>
            </div>
            <label className="flex items-center gap-2 text-xs text-gray-600"><input type="checkbox" checked={c.itc_blocked} onChange={(e) => set(i, { itc_blocked: e.target.checked })} /> GST input credit blocked (Sec 17(5))</label>
            <div className="space-y-1.5">
              {c.items.map((it, k) => (
                <div key={k} className="flex items-center gap-1.5">
                  <Input className="flex-1 !py-1 text-sm" placeholder="Item" value={it.name} onChange={(e) => setItem(i, k, { name: e.target.value })} />
                  <Select className="!w-24 !py-1 text-sm" value={it.gst_rate} onChange={(e) => setItem(i, k, { gst_rate: Number(e.target.value) })} aria-label="GST %">
                    {data.gst_rates.map((r) => <option key={r} value={r}>{r}%</option>)}
                  </Select>
                  <Input className="!w-24 !py-1 text-sm" placeholder="HSN/SAC" value={it.hsn_sac ?? ""} onChange={(e) => setItem(i, k, { hsn_sac: e.target.value || null })} />
                  <button className="text-gray-400 hover:text-red-600" aria-label="Remove item" onClick={() => set(i, { items: c.items.filter((_, j) => j !== k) })}><X size={15} /></button>
                </div>
              ))}
              <button className="text-xs text-brand-600 hover:underline" onClick={() => set(i, { items: [...c.items, { name: "", gst_rate: 18, hsn_sac: null }] })}>+ Add item</button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
