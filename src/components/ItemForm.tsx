"use client";

import { useState } from "react";
import { ImageUpload } from "@/components/ImageUpload";
import { Button, Card, ErrorBox, Field, Input, Select, Textarea } from "@/components/ui";
import { GST_RATES, UNITS } from "@/lib/constants";
import { api } from "@/lib/api";
import { today } from "@/lib/format";
import type { Item, ItemType } from "@/lib/types";

export type ItemDraft = Omit<Item, "id" | "stock" | "is_active"> & { opening_stock?: number; opening_stock_date?: string };

export const emptyItem: ItemDraft = {
  type: "GOODS", name: "", code: "", hsn_sac: "", unit: "NOS", category: "", description: "", image_url: null,
  sale_price: 0, sale_price_tax_inclusive: false, purchase_price: 0, purchase_price_tax_inclusive: false, mrp: null,
  gst_rate: 18, cess_rate: 0, low_stock_level: null, opening_stock: 0, opening_stock_date: today(),
  track_batch: false, track_serial: false,
};

export function ItemForm({
  initial,
  isNew,
  onSubmit,
}: {
  initial: ItemDraft;
  isNew: boolean;
  onSubmit: (i: ItemDraft) => Promise<void>;
}) {
  const [it, setIt] = useState<ItemDraft>(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof ItemDraft>(k: K, v: ItemDraft[K]) => setIt((prev) => ({ ...prev, [k]: v }));
  const text = (k: keyof ItemDraft) => ({
    value: (it[k] as string | null) ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => set(k, e.target.value as never),
  });
  const numField = (k: keyof ItemDraft, nullable = false) => ({
    type: "number" as const,
    min: 0,
    step: "0.01",
    value: (it[k] as number | null) ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      set(k, (e.target.value === "" ? (nullable ? null : 0) : Number(e.target.value)) as never),
  });
  const goods = it.type === "GOODS";
  const [hsnHint, setHsnHint] = useState<string | null>(null);

  /** Look the code up in the HSN/SAC master and apply its current GST rate. */
  async function lookupHsn(code: string) {
    setHsnHint(null);
    if (!/^\d{4,8}$/.test(code)) return;
    try {
      const hits = await api<{ code: string; description: string | null; gst_rate: number; cess_rate: number }[]>(`/hsn?search=${code}`);
      const hit = hits.find((h) => h.code === code);
      if (hit) {
        setIt((prev) => ({ ...prev, gst_rate: hit.gst_rate, cess_rate: hit.cess_rate }));
        setHsnHint(`From HSN master: ${hit.gst_rate}% GST${hit.description ? ` — ${hit.description}` : ""}`);
      }
    } catch {
      /* master lookup is optional */
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(it);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <ErrorBox message={error} />
      <Card className="p-5">
        <div className="mb-4 inline-flex rounded-lg border border-gray-200 p-0.5">
          {(["GOODS", "SERVICE"] as ItemType[]).map((t) => (
            <button
              type="button"
              key={t}
              onClick={() => set("type", t)}
              className={`rounded-md px-4 py-1.5 text-sm ${it.type === t ? "bg-brand-600 text-white" : "text-gray-700"}`}
            >
              {t === "GOODS" ? "Product" : "Service"}
            </button>
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Item name" required className="sm:col-span-2"><Input required autoFocus {...text("name")} /></Field>
          <Field label="Item code / SKU"><Input {...text("code")} /></Field>
          <Field label={goods ? "HSN code" : "SAC code"} hint="4–8 digits; mandatory for most GST filers">
            <Input inputMode="numeric" maxLength={8} pattern="\d{4,8}" {...text("hsn_sac")} onBlur={(e) => lookupHsn(e.target.value)} />
            {hsnHint && <span className="mt-1 block text-xs text-emerald-700">{hsnHint}</span>}
          </Field>
          <Field label="Unit">
            <Select value={it.unit} onChange={(e) => set("unit", e.target.value)}>
              {Object.entries(UNITS).map(([c, n]) => <option key={c} value={c}>{c} - {n}</option>)}
            </Select>
          </Field>
          <Field label="Category"><Input {...text("category")} /></Field>
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="mb-4 font-semibold text-gray-900">Pricing & tax</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Sale price (₹)">
            <div className="flex gap-2">
              <Input {...numField("sale_price")} />
              <Select className="max-w-32" value={it.sale_price_tax_inclusive ? "1" : "0"} onChange={(e) => set("sale_price_tax_inclusive", e.target.value === "1")}>
                <option value="0">Without tax</option>
                <option value="1">With tax</option>
              </Select>
            </div>
          </Field>
          <Field label="Purchase price (₹)">
            <div className="flex gap-2">
              <Input {...numField("purchase_price")} />
              <Select className="max-w-32" value={it.purchase_price_tax_inclusive ? "1" : "0"} onChange={(e) => set("purchase_price_tax_inclusive", e.target.value === "1")}>
                <option value="0">Without tax</option>
                <option value="1">With tax</option>
              </Select>
            </div>
          </Field>
          <Field label="MRP (₹)"><Input {...numField("mrp", true)} /></Field>
          <Field label="GST rate">
            <Select value={it.gst_rate} onChange={(e) => set("gst_rate", Number(e.target.value))}>
              {GST_RATES.map((r) => <option key={r} value={r}>{r === 0 ? "0% / Exempt / Nil" : `${r}%`}</option>)}
            </Select>
          </Field>
          <Field label="Cess %"><Input {...numField("cess_rate")} /></Field>
        </div>
      </Card>

      {goods && (
        <Card className="p-5">
          <h2 className="mb-4 font-semibold text-gray-900">Stock</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {isNew && (
              <>
                <Field label="Opening stock"><Input type="number" step="0.001" value={it.opening_stock ?? 0} onChange={(e) => set("opening_stock", Number(e.target.value))} /></Field>
                <Field label="As of date"><Input type="date" value={it.opening_stock_date ?? today()} onChange={(e) => set("opening_stock_date", e.target.value)} /></Field>
              </>
            )}
            <Field label="Low stock alert at"><Input {...numField("low_stock_level", true)} step="0.001" /></Field>
          </div>
          <div className="mt-4 flex flex-wrap gap-6 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={it.track_batch} onChange={(e) => set("track_batch", e.target.checked)} />
              Track batch no. & expiry
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={it.track_serial} onChange={(e) => set("track_serial", e.target.checked)} />
              Track serial numbers / IMEI
            </label>
          </div>
        </Card>
      )}

      <Card className="p-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Description" className="sm:col-span-2"><Textarea rows={2} {...text("description")} /></Field>
          <ImageUpload kind="item" label="Image" value={it.image_url} onChange={(u) => set("image_url", u)} />
        </div>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save item"}</Button>
      </div>
    </form>
  );
}
