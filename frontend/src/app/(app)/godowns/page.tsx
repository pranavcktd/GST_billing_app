"use client";

import { ArrowLeftRight, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, Combobox, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { usePerms } from "@/lib/auth";
import { fmtDate, money, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Godown, Item } from "@/lib/types";

interface Transfer { id: string; number: string; date: string; from_godown: string; to_godown: string; note: string | null; lines: { item: string; qty: number; batch_no: string | null }[] }
interface Line { key: number; item_id: string; name: string; qty: string; batch_no: string }
let k = 1;

export default function GodownsPage() {
  const { can } = usePerms();
  const { data: godowns, error, reload } = useFetch<Godown[]>("/godowns");
  const { data: transfers, reload: reloadT } = useFetch<Transfer[]>("/stock-transfers");
  const { data: items } = useFetch<Item[]>("/items");
  const [edit, setEdit] = useState<{ id?: string; name: string; address: string } | null>(null);
  const [tf, setTf] = useState<{ from: string; to: string; date: string; note: string; lines: Line[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (!godowns) return error ? <ErrorBox message={error} /> : <Loading />;
  const active = godowns.filter((g) => g.is_active);
  const goods = (items ?? []).filter((i) => i.type === "GOODS");

  const run = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try { await fn(); reload(); reloadT(); return true; } catch (e) { setErr((e as Error).message); return false; }
  };

  return (
    <>
      <PageHeader title="Godowns & stock transfers" sub="Keep stock by location and move it between shops and warehouses"
        actions={
          <>
            {can("items", "create") && active.length > 1 && (
              <Button variant="secondary" onClick={() => setTf({ from: active[0].id, to: active[1].id, date: today(), note: "", lines: [{ key: k++, item_id: "", name: "", qty: "", batch_no: "" }] })}>
                <ArrowLeftRight size={16} /> Transfer stock
              </Button>
            )}
            {can("items", "create") && <Button onClick={() => setEdit({ name: "", address: "" })}><Plus size={16} /> Add godown</Button>}
          </>
        } />
      <ErrorBox message={err} />
      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {godowns.map((g) => (
          <Card key={g.id} className={`p-4 ${g.is_active ? "" : "opacity-50"}`}>
            <div className="flex items-start justify-between">
              <div>
                <div className="font-medium text-gray-900">{g.name} {g.is_default && <span className="ml-1 rounded bg-gray-100 px-1.5 text-xs text-gray-600">main</span>}</div>
                <div className="text-xs text-gray-500">{g.address}</div>
              </div>
              {can("items", "edit") && (
                <div className="flex gap-1">
                  <button className="text-gray-400 hover:text-gray-700" aria-label="Edit" onClick={() => setEdit({ id: g.id, name: g.name, address: g.address ?? "" })}><Pencil size={14} /></button>
                  {!g.is_default && <button className="text-gray-400 hover:text-red-600" aria-label="Delete" onClick={() => confirm(`Delete ${g.name}?`) && run(() => api(`/godowns/${g.id}`, { method: "DELETE" }))}><Trash2 size={14} /></button>}
                </div>
              )}
            </div>
            <div className="mt-2 text-lg font-semibold tabular-nums">{money(g.stock_value)}</div>
            <div className="text-xs text-gray-500">stock value at purchase price</div>
          </Card>
        ))}
      </div>

      <Card className="overflow-x-auto">
        <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Transfers</h2>
        {!transfers ? <Loading /> : transfers.length === 0 ? <Empty title="No stock transfers yet" /> : (
          <table className="tbl">
            <thead><tr><th>Date</th><th>No.</th><th>From</th><th>To</th><th>Items</th><th /></tr></thead>
            <tbody>
              {transfers.map((t) => (
                <tr key={t.id}>
                  <td>{fmtDate(t.date)}</td><td className="font-medium">{t.number}</td><td>{t.from_godown}</td><td>{t.to_godown}</td>
                  <td className="text-xs">{t.lines.map((l) => `${l.item} × ${l.qty}${l.batch_no ? ` (${l.batch_no})` : ""}`).join(", ")}{t.note && <div className="text-gray-500">{t.note}</div>}</td>
                  <td>{can("items", "delete") && <button className="text-gray-400 hover:text-red-600" aria-label="Delete" onClick={() => confirm("Delete this transfer? Stock moves back.") && run(() => api(`/stock-transfers/${t.id}`, { method: "DELETE" }))}><Trash2 size={15} /></button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {edit && (
        <Modal title={edit.id ? "Edit godown" : "Add godown"} onClose={() => setEdit(null)}>
          <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); if (await run(() => api(edit.id ? `/godowns/${edit.id}` : "/godowns", { method: edit.id ? "PUT" : "POST", body: { name: edit.name, address: edit.address || null } }))) setEdit(null); }}>
            <Field label="Name" required><Input required value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} placeholder="City shop / Warehouse 2" /></Field>
            <Field label="Address"><Input value={edit.address} onChange={(e) => setEdit({ ...edit, address: e.target.value })} /></Field>
            <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={() => setEdit(null)}>Cancel</Button><Button type="submit">Save</Button></div>
          </form>
        </Modal>
      )}

      {tf && (
        <Modal title="Transfer stock" onClose={() => setTf(null)} wide>
          <form className="space-y-3" onSubmit={async (e) => {
            e.preventDefault();
            const lines = tf.lines.filter((l) => l.item_id && Number(l.qty) > 0).map((l) => ({ item_id: l.item_id, qty: Number(l.qty), batch_no: l.batch_no || null }));
            if (await run(() => api("/stock-transfers", { body: { from_godown_id: tf.from, to_godown_id: tf.to, date: tf.date, note: tf.note || null, lines } }))) setTf(null);
          }}>
            <ErrorBox message={err} />
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="From"><Select value={tf.from} onChange={(e) => setTf({ ...tf, from: e.target.value })}>{active.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</Select></Field>
              <Field label="To"><Select value={tf.to} onChange={(e) => setTf({ ...tf, to: e.target.value })}>{active.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</Select></Field>
              <Field label="Date"><Input type="date" value={tf.date} onChange={(e) => setTf({ ...tf, date: e.target.value })} /></Field>
            </div>
            {tf.lines.map((l, i) => (
              <div key={l.key} className="grid grid-cols-[1fr_7rem_8rem_2rem] items-end gap-2">
                <Field label={i === 0 ? "Item" : ""}>
                  <Combobox items={goods} value={l.name} placeholder="Search item" getKey={(x) => x.id} getLabel={(x) => `${x.name} ${x.code ?? ""}`}
                    onSelect={(x) => setTf({ ...tf, lines: tf.lines.map((y) => y.key === l.key ? { ...y, item_id: x.id, name: x.name } : y) })} />
                </Field>
                <Field label={i === 0 ? "Qty" : ""}><Input inputMode="decimal" value={l.qty} onChange={(e) => setTf({ ...tf, lines: tf.lines.map((y) => y.key === l.key ? { ...y, qty: e.target.value } : y) })} /></Field>
                <Field label={i === 0 ? "Batch" : ""}><Input value={l.batch_no} onChange={(e) => setTf({ ...tf, lines: tf.lines.map((y) => y.key === l.key ? { ...y, batch_no: e.target.value } : y) })} /></Field>
                <button type="button" className="pb-2 text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => setTf({ ...tf, lines: tf.lines.filter((y) => y.key !== l.key) })}><Trash2 size={15} /></button>
              </div>
            ))}
            <Button type="button" variant="secondary" onClick={() => setTf({ ...tf, lines: [...tf.lines, { key: k++, item_id: "", name: "", qty: "", batch_no: "" }] })}><Plus size={15} /> Add item</Button>
            <Field label="Note"><Input value={tf.note} onChange={(e) => setTf({ ...tf, note: e.target.value })} /></Field>
            <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={() => setTf(null)}>Cancel</Button><Button type="submit">Transfer</Button></div>
          </form>
        </Modal>
      )}
    </>
  );
}
