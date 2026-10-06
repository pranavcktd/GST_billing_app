"use client";

import { Factory, Pencil, Plus, Trash2 } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { Modal } from "@/components/Modal";
import { usePaged } from "@/components/Pager";
import { Button, Card, Combobox, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select, Textarea } from "@/components/ui";
import { ApiError, api, qs } from "@/lib/api";
import { usePerms } from "@/lib/auth";
import { fmtDate, money, qty as fq, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Godown, Item } from "@/lib/types";

interface BomLine { item_id: string; item?: string | null; unit?: string | null; qty: number }
interface Bom { id: string; name: string; item_id: string; item: string | null; unit: string | null; output_qty: number; other_cost: number; notes: string | null; is_active: boolean; lines: BomLine[] }
interface Prod { id: string; number: string; date: string; item: string | null; qty: number; batch_no: string | null; material_cost: number; other_cost: number; unit_cost: number; total_cost: number; consumed: { name: string; unit: string; qty: number; rate: number; amount: number }[]; created_by: string | null }
interface Plan { lines: { item_id: string; name: string; unit: string; qty: number; rate: number; amount: number; in_stock: number | null; short: number }[]; material_cost: number; other_cost: number; total_cost: number; unit_cost: number }

export default function ManufacturingPage() {
  const { can } = usePerms();
  const [tab, setTab] = useState<"production" | "boms">("production");
  const { data: boms, reload: reloadBoms } = useFetch<Bom[]>("/boms");
  const { data: prods, reload: reloadProds } = useFetch<Prod[]>("/productions");
  const { data: items } = useFetch<Item[]>("/items");
  const [editBom, setEditBom] = useState<Partial<Bom> | null>(null);
  const [producing, setProducing] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const { rows, pager } = usePaged(prods);

  return (
    <>
      <PageHeader title="Manufacturing" sub="Bills of materials and production — raw materials go out of stock, finished goods come in at cost"
        actions={<>
          {can("items", "create") && <Button variant="secondary" onClick={() => setEditBom({ output_qty: 1, other_cost: 0, lines: [], is_active: true })}><Plus size={16} /> Bill of materials</Button>}
          {can("items", "create") && <Button disabled={!boms?.some((b) => b.is_active)} onClick={() => setProducing(true)}><Factory size={16} /> New production</Button>}
        </>} />
      <div className="mb-4 flex w-fit gap-1 rounded-lg border border-gray-200 bg-white p-1 text-sm">
        {(["production", "boms"] as const).map((t) => <button key={t} onClick={() => setTab(t)} className={`rounded-md px-4 py-1.5 ${tab === t ? "bg-brand-600 text-white" : "text-gray-700"}`}>{t === "production" ? "Production" : `Bills of materials (${boms?.length ?? 0})`}</button>)}
      </div>
      <ErrorBox message={err} />

      {tab === "boms" && (!boms ? <Loading /> : !boms.length ? (
        <Card><Empty title="No bills of materials yet. Create one: the finished item and the materials (with quantities) needed to make it." /></Card>
      ) : (
        <Card className="overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>Bill of materials</th><th>Makes</th><th>Materials</th><th className="num">Other cost / batch</th><th /></tr></thead>
            <tbody>
              {boms.map((b) => (
                <tr key={b.id} className={b.is_active ? "" : "text-gray-400"}>
                  <td className="font-medium">{b.name}{!b.is_active && " (inactive)"}</td>
                  <td>{fq(b.output_qty)} {b.unit} {b.item}</td>
                  <td className="text-xs">{b.lines.map((l) => `${fq(l.qty)} ${l.unit ?? ""} ${l.item}`).join(" · ")}</td>
                  <td className="num">{money(b.other_cost)}</td>
                  <td className="whitespace-nowrap text-right">
                    {can("items", "edit") && <Button variant="ghost" className="!px-2 !py-1" onClick={() => setEditBom(b)}><Pencil size={15} /></Button>}
                    {can("items", "delete") && <Button variant="ghost" className="!px-2 !py-1" onClick={async () => { if (confirm(`Delete “${b.name}”?`)) { await api(`/boms/${b.id}`, { method: "DELETE" }).catch((e) => setErr(e.message)); reloadBoms(); } }}><Trash2 size={15} /></Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}

      {tab === "production" && (!prods ? <Loading /> : !prods.length ? (
        <Card><Empty title={boms?.length ? "No production yet — click “New production”." : "Start by creating a bill of materials."} /></Card>
      ) : (
        <Card className="overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>Date</th><th>Number</th><th>Item produced</th><th className="num">Qty</th><th className="num">Material cost</th><th className="num">Other cost</th><th className="num">Cost / unit</th><th /></tr></thead>
            <tbody>
              {rows.map((p) => (
                <Fragment key={p.id}>
                  <tr>
                    <td>{fmtDate(p.date)}</td>
                    <td><button className="font-medium text-brand-600 hover:underline" onClick={() => setOpen(open === p.id ? null : p.id)}>{p.number}</button></td>
                    <td>{p.item}{p.batch_no && <span className="ml-1 text-xs text-gray-500">batch {p.batch_no}</span>}</td>
                    <td className="num">{fq(p.qty)}</td>
                    <td className="num">{money(p.material_cost)}</td>
                    <td className="num">{money(p.other_cost)}</td>
                    <td className="num font-medium">{money(p.unit_cost)}</td>
                    <td className="text-right">{can("items", "delete") && <Button variant="ghost" className="!px-2 !py-1" title="Undo this production" onClick={async () => { if (confirm(`Undo ${p.number}? Materials go back to stock and the produced goods are removed.`)) { await api(`/productions/${p.id}`, { method: "DELETE" }).catch((e) => setErr(e.message)); reloadProds(); } }}><Trash2 size={15} /></Button>}</td>
                  </tr>
                  {open === p.id && (
                    <tr className="bg-gray-50"><td /><td colSpan={7}>
                      <div className="py-1 text-xs">
                        <div className="mb-1 font-semibold text-gray-700">Materials used</div>
                        {p.consumed.map((c, i) => <div key={i}>{fq(c.qty)} {c.unit} {c.name} @ {money(c.rate)} = {money(c.amount)}</div>)}
                        {p.created_by && <div className="mt-1 text-gray-500">by {p.created_by}</div>}
                      </div>
                    </td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          {pager}
        </Card>
      ))}

      {editBom && items && <BomEditor bom={editBom} items={items} onClose={() => setEditBom(null)} onSaved={() => { setEditBom(null); reloadBoms(); setTab("boms"); }} />}
      {producing && boms && <ProduceForm boms={boms.filter((b) => b.is_active)} onClose={() => setProducing(false)} onDone={() => { setProducing(false); reloadProds(); setTab("production"); }} />}
    </>
  );
}

function BomEditor({ bom, items, onClose, onSaved }: { bom: Partial<Bom>; items: Item[]; onClose: () => void; onSaved: () => void }) {
  const goods = items.filter((i) => i.type === "GOODS");
  const [f, setF] = useState({ item_id: bom.item_id ?? "", name: bom.name ?? "", output_qty: String(bom.output_qty ?? 1), other_cost: String(bom.other_cost ?? 0), notes: bom.notes ?? "", is_active: bom.is_active ?? true });
  const [lines, setLines] = useState<BomLine[]>(bom.lines?.length ? bom.lines : [{ item_id: "", qty: 1 }]);
  const [err, setErr] = useState<string | null>(null);
  const byId = Object.fromEntries(items.map((i) => [i.id, i]));

  async function save() {
    setErr(null);
    try {
      const body = { ...f, name: f.name || null, output_qty: Number(f.output_qty) || 1, other_cost: Number(f.other_cost) || 0, notes: f.notes || null,
        lines: lines.filter((l) => l.item_id).map((l) => ({ item_id: l.item_id, qty: Number(l.qty) })) };
      await api(bom.id ? `/boms/${bom.id}` : "/boms", { method: bom.id ? "PUT" : "POST", body });
      onSaved();
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <Modal title={bom.id ? "Edit bill of materials" : "New bill of materials"} onClose={onClose} wide>
      <div className="space-y-3 text-sm">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Finished item" required className="sm:col-span-2">
            <Combobox items={goods} value={byId[f.item_id]?.name ?? ""} placeholder="Item you make" getKey={(i) => i.id} getLabel={(i) => i.name} onSelect={(i) => setF({ ...f, item_id: i.id })} />
          </Field>
          <Field label="Quantity made" hint={byId[f.item_id] ? `in ${byId[f.item_id].unit}` : "per batch"}><Input inputMode="decimal" value={f.output_qty} onChange={(e) => setF({ ...f, output_qty: e.target.value })} /></Field>
          <Field label="Name (optional)" className="sm:col-span-2"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="e.g. Almirah — 2 door" /></Field>
          <Field label="Labour / overheads per batch (₹)" hint="Added to the finished goods' cost"><Input inputMode="decimal" value={f.other_cost} onChange={(e) => setF({ ...f, other_cost: e.target.value })} /></Field>
        </div>
        <div className="rounded-lg border border-gray-200">
          <div className="border-b border-gray-100 px-3 py-2 font-medium text-gray-700">Materials for one batch</div>
          {lines.map((l, i) => (
            <div key={i} className="flex items-center gap-2 border-b border-gray-50 px-3 py-2">
              <div className="flex-1"><Combobox items={items.filter((x) => x.id !== f.item_id)} value={byId[l.item_id]?.name ?? ""} placeholder="Material / component"
                getKey={(x) => x.id} getLabel={(x) => x.name} onSelect={(x) => setLines(lines.map((y, j) => (j === i ? { ...y, item_id: x.id } : y)))} /></div>
              <Input className="!w-28 text-right" inputMode="decimal" value={String(l.qty)} onChange={(e) => setLines(lines.map((y, j) => (j === i ? { ...y, qty: e.target.value as unknown as number } : y)))} />
              <span className="w-12 text-xs text-gray-500">{byId[l.item_id]?.unit}</span>
              <button className="text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => setLines(lines.filter((_, j) => j !== i))}><Trash2 size={15} /></button>
            </div>
          ))}
          <div className="p-2"><Button variant="ghost" onClick={() => setLines([...lines, { item_id: "", qty: 1 }])}><Plus size={15} /> Add material</Button></div>
        </div>
        <Field label="Notes"><Textarea rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
        <label className="flex items-center gap-2"><input type="checkbox" checked={f.is_active} onChange={(e) => setF({ ...f, is_active: e.target.checked })} /> Active</label>
        <ErrorBox message={err} />
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!f.item_id || !lines.some((l) => l.item_id)} onClick={save}>Save</Button></div>
      </div>
    </Modal>
  );
}

function ProduceForm({ boms, onClose, onDone }: { boms: Bom[]; onClose: () => void; onDone: () => void }) {
  const { data: godowns } = useFetch<Godown[]>("/godowns");
  const [f, setF] = useState({ bom_id: boms[0]?.id ?? "", qty: String(boms[0]?.output_qty ?? 1), date: today(), godown_id: "", batch_no: "", other_cost: "", notes: "" });
  const [plan, setPlan] = useState<Plan | null>(null);
  const [allow, setAllow] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const bom = boms.find((b) => b.id === f.bom_id);
  const active = (godowns ?? []).filter((g) => g.is_active);

  useEffect(() => {
    if (!f.bom_id || !(Number(f.qty) > 0)) return;
    let alive = true;
    const t = setTimeout(() => api<Plan>(`/boms/${f.bom_id}/plan${qs({ qty: f.qty, date: f.date, godown_id: f.godown_id || null })}`).then((p) => alive && setPlan(p)).catch(() => {}), 250);
    return () => { alive = false; clearTimeout(t); };
  }, [f.bom_id, f.qty, f.date, f.godown_id]);

  const short = plan?.lines.some((l) => l.short > 0);
  const other = f.other_cost === "" ? plan?.other_cost ?? 0 : Number(f.other_cost) || 0;
  const total = (plan?.material_cost ?? 0) + other;

  async function save() {
    setBusy(true); setErr(null);
    try {
      await api("/productions", { body: { bom_id: f.bom_id, qty: Number(f.qty), date: f.date, godown_id: f.godown_id || null, batch_no: f.batch_no || null,
        other_cost: f.other_cost === "" ? null : Number(f.other_cost), notes: f.notes || null, allow_shortage: allow } });
      onDone();
    } catch (e) { setErr(e instanceof ApiError ? e.message : (e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal title="New production" onClose={onClose} wide>
      <div className="space-y-3 text-sm">
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Bill of materials" className="sm:col-span-2">
            <Select value={f.bom_id} onChange={(e) => setF({ ...f, bom_id: e.target.value })}>{boms.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</Select>
          </Field>
          <Field label={`Quantity to make${bom?.unit ? ` (${bom.unit})` : ""}`}><Input inputMode="decimal" value={f.qty} onChange={(e) => setF({ ...f, qty: e.target.value })} /></Field>
          <Field label="Date"><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></Field>
          {active.length > 1 && (
            <Field label="Godown">
              <Select value={f.godown_id || active.find((g) => g.is_default)?.id || ""} onChange={(e) => setF({ ...f, godown_id: e.target.value })}>
                {active.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
              </Select>
            </Field>
          )}
          <Field label="Batch no. (optional)"><Input value={f.batch_no} onChange={(e) => setF({ ...f, batch_no: e.target.value })} /></Field>
          <Field label="Labour / overheads (₹)" hint={plan ? `Default ${money(plan.other_cost)}` : undefined}><Input inputMode="decimal" value={f.other_cost} placeholder={plan ? String(plan.other_cost) : ""} onChange={(e) => setF({ ...f, other_cost: e.target.value })} /></Field>
        </div>
        {!plan ? <Loading /> : (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="tbl">
              <thead><tr><th>Material</th><th className="num">Needed</th><th className="num">In stock</th><th className="num">Avg cost</th><th className="num">Amount</th></tr></thead>
              <tbody>
                {plan.lines.map((l) => (
                  <tr key={l.item_id} className={l.short > 0 ? "bg-red-50" : ""}>
                    <td>{l.name}</td><td className="num">{fq(l.qty)} {l.unit}</td>
                    <td className={`num ${l.short > 0 ? "font-medium text-red-700" : ""}`}>{l.in_stock === null ? "—" : fq(l.in_stock)}{l.short > 0 ? ` (short ${fq(l.short)})` : ""}</td>
                    <td className="num">{money(l.rate)}</td><td className="num">{money(l.amount)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr><td colSpan={4}>Materials</td><td className="num">{money(plan.material_cost)}</td></tr>
                <tr><td colSpan={4}>Labour / overheads</td><td className="num">{money(other)}</td></tr>
                <tr><td colSpan={4} className="font-semibold">Cost of {f.qty} {bom?.unit} — {money(Number(f.qty) ? total / Number(f.qty) : 0)} each</td><td className="num font-semibold">{money(total)}</td></tr>
              </tfoot>
            </table>
          </div>
        )}
        {short && <label className="flex items-center gap-2 text-amber-800"><input type="checkbox" checked={allow} onChange={(e) => setAllow(e.target.checked)} /> Some materials are short — record anyway (stock goes negative)</label>}
        <Field label="Notes"><Textarea rows={1} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
        <ErrorBox message={err} />
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={busy || !plan || (short && !allow)} onClick={save}><Factory size={15} /> Record production</Button></div>
      </div>
    </Modal>
  );
}
