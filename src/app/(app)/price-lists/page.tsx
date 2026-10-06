"use client";

import { Pencil, Plus, Save, Tags, Trash2 } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { usePaged } from "@/components/Pager";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { usePerms } from "@/lib/auth";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface PList { id: string; name: string; based_on: "SALE_PRICE" | "MRP"; adjust_pct: number; note: string | null; is_active: boolean; special_rates: number; parties: number }
interface Row { item_id: string; name: string; code: string | null; unit: string; sale_price: number; mrp: number | null; tax_inclusive: boolean; default_rate: number; special_rate: number | null }

const rule = (l: PList) => `${l.based_on === "MRP" ? "MRP" : "Sale price"}${l.adjust_pct ? ` ${l.adjust_pct > 0 ? "+" : "−"} ${Math.abs(l.adjust_pct)}%` : ""}`;

/** Party-wise price lists: a rule (e.g. sale price − 5%) plus special rates for chosen items. */
export default function PriceListsPage() {
  const { can } = usePerms();
  const editable = can("items", "edit");
  const { data, error, reload } = useFetch<PList[]>("/price-lists");
  const [form, setForm] = useState<Partial<PList> | null>(null);
  const [rates, setRates] = useState<PList | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function saveList() {
    if (!form) return;
    setErr(null);
    try {
      const body = { name: form.name, based_on: form.based_on ?? "SALE_PRICE", adjust_pct: Number(form.adjust_pct) || 0, note: form.note || null, is_active: form.is_active ?? true };
      await api(form.id ? `/price-lists/${form.id}` : "/price-lists", { method: form.id ? "PUT" : "POST", body });
      setForm(null);
      reload();
    } catch (e) { setErr((e as Error).message); }
  }

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;
  return (
    <>
      <PageHeader title="Price lists" sub="Special selling rates for dealers, wholesale buyers or regular customers — assign a list to a customer in their party details"
        actions={editable && <Button onClick={() => setForm({ name: "", based_on: "SALE_PRICE", adjust_pct: 0, is_active: true })}><Plus size={16} /> New price list</Button>} />
      {!data.length ? (
        <Card><Empty title="No price lists yet. Create one (e.g. “Dealer — 10% off”), set special rates if needed, then pick it on the customer." /></Card>
      ) : (
        <Card className="overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>Price list</th><th>Rule for other items</th><th className="num">Special rates</th><th className="num">Customers</th><th /></tr></thead>
            <tbody>
              {data.map((l) => (
                <tr key={l.id} className={l.is_active ? "" : "text-gray-400"}>
                  <td><div className="flex items-center gap-1.5 font-medium"><Tags size={14} className="text-brand-600" /> {l.name}{!l.is_active && " (inactive)"}</div>{l.note && <div className="text-xs text-gray-500">{l.note}</div>}</td>
                  <td>{rule(l)}</td>
                  <td className="num"><button className="text-brand-600 hover:underline" onClick={() => setRates(l)}>{l.special_rates} item{l.special_rates === 1 ? "" : "s"}</button></td>
                  <td className="num">{l.parties}</td>
                  <td className="whitespace-nowrap text-right">
                    <Button variant="ghost" className="!px-2 !py-1" onClick={() => setRates(l)}>Rates</Button>
                    {editable && <Button variant="ghost" className="!px-2 !py-1" onClick={() => setForm(l)}><Pencil size={15} /></Button>}
                    {editable && <Button variant="ghost" className="!px-2 !py-1" onClick={async () => { if (confirm(`Delete “${l.name}”? Customers using it go back to normal prices.`)) { await api(`/price-lists/${l.id}`, { method: "DELETE" }); reload(); } }}><Trash2 size={15} /></Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      <p className="mt-3 text-xs text-gray-500">On a sale invoice, picking an item for a customer with a price list fills their rate automatically. The rate last charged to that customer is shown under the rate box too.</p>

      {form && (
        <Modal title={form.id ? "Edit price list" : "New price list"} onClose={() => setForm(null)}>
          <div className="space-y-3 text-sm">
            <Field label="Name" required><Input value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Dealer" /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Start from">
                <Select value={form.based_on ?? "SALE_PRICE"} onChange={(e) => setForm({ ...form, based_on: e.target.value as PList["based_on"] })}>
                  <option value="SALE_PRICE">Item sale price</option><option value="MRP">Item MRP</option>
                </Select>
              </Field>
              <Field label="Adjust by %" hint="−10 = 10% lower, 5 = 5% higher"><Input inputMode="decimal" value={String(form.adjust_pct ?? 0)} onChange={(e) => setForm({ ...form, adjust_pct: e.target.value as unknown as number })} /></Field>
            </div>
            <Field label="Note"><Input value={form.note ?? ""} onChange={(e) => setForm({ ...form, note: e.target.value })} /></Field>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.is_active ?? true} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active</label>
            <ErrorBox message={err} />
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setForm(null)}>Cancel</Button><Button disabled={!form.name} onClick={saveList}>Save</Button></div>
          </div>
        </Modal>
      )}
      {rates && <RatesEditor list={rates} editable={editable} onClose={() => { setRates(null); reload(); }} />}
    </>
  );
}

function RatesEditor({ list, editable, onClose }: { list: PList; editable: boolean; onClose: () => void }) {
  const { data } = useFetch<Row[]>(`/price-lists/${list.id}/items`);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const [onlySpecial, setOnlySpecial] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const shown = (data ?? []).filter((r) => (!search || r.name.toLowerCase().includes(search.toLowerCase()) || (r.code ?? "").toLowerCase().includes(search.toLowerCase()))
    && (!onlySpecial || r.special_rate !== null || edits[r.item_id]));
  const { rows, pager } = usePaged(shown, 50);

  async function save() {
    setBusy(true); setErr(null);
    try {
      const body = Object.fromEntries(Object.entries(edits).map(([k, v]) => [k, v.trim() === "" ? null : Number(v)]));
      await api(`/price-lists/${list.id}/items`, { method: "PUT", body: { rates: body } });
      onClose();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal title={`Rates — ${list.name}`} onClose={onClose} wide>
      <div className="space-y-3 text-sm">
        <p className="text-gray-600">Items without a special rate use the rule: <b>{rule(list)}</b>. Type a special rate to override it; clear the box to go back to the rule.</p>
        <div className="flex flex-wrap items-center gap-3">
          <Input placeholder="Search item" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={onlySpecial} onChange={(e) => setOnlySpecial(e.target.checked)} /> Only special rates</label>
        </div>
        {!data ? <Loading /> : (
          <div className="max-h-[55vh] overflow-y-auto rounded-lg border border-gray-100">
            <table className="tbl">
              <thead><tr><th>Item</th><th className="num">Sale price</th><th className="num">MRP</th><th className="num">By rule</th><th className="num">Special rate</th></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const val = edits[r.item_id] ?? (r.special_rate !== null ? String(r.special_rate) : "");
                  return (
                    <tr key={r.item_id}>
                      <td>{r.name}{r.code && <span className="ml-1 text-xs text-gray-400">{r.code}</span>}<div className="text-[10px] text-gray-400">{r.tax_inclusive ? "incl. tax" : "excl. tax"} · per {r.unit}</div></td>
                      <td className="num">{money(r.sale_price)}</td>
                      <td className="num">{r.mrp ? money(r.mrp) : "—"}</td>
                      <td className="num text-gray-500">{money(r.default_rate)}</td>
                      <td className="num"><input className="input !w-28 !py-1 text-right" inputMode="decimal" disabled={!editable} placeholder="—" value={val}
                        onChange={(e) => setEdits({ ...edits, [r.item_id]: e.target.value })} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {pager}
          </div>
        )}
        <ErrorBox message={err} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Close</Button>
          {editable && <Button disabled={busy || !Object.keys(edits).length} onClick={save}><Save size={15} /> Save {Object.keys(edits).length || ""} change{Object.keys(edits).length === 1 ? "" : "s"}</Button>}
        </div>
      </div>
    </Modal>
  );
}
