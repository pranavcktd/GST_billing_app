"use client";

import { Minus, Plus, ScanLine, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button, Card, Combobox, ErrorBox, Field, Input, Loading } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { money, today } from "@/lib/format";
import { calcInvoice } from "@/lib/gst";
import { useFetch } from "@/lib/useFetch";
import type { Business, Item, Party, PaymentMode, VoucherDetail } from "@/lib/types";

interface CartLine { item: Item; qty: number; rate: number }

/** Counter billing: scan barcodes (item code), collect payment, print a thermal receipt. */
export default function PosPage() {
  const router = useRouter();
  const { data: business } = useFetch<Business>("/businesses/current");
  const { data: items } = useFetch<Item[]>("/items");
  const { data: parties } = useFetch<Party[]>(`/parties${qs({ type: "CUSTOMER" })}`);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [scan, setScan] = useState("");
  const [partyId, setPartyId] = useState<string | null>(null);
  const [walkIn, setWalkIn] = useState({ name: "", phone: "" });
  const [mode, setMode] = useState<PaymentMode>("CASH");
  const [tendered, setTendered] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const scanRef = useRef<HTMLInputElement>(null);

  const add = (it: Item) => {
    setErr(null);
    setCart((c) => {
      const i = c.findIndex((l) => l.item.id === it.id);
      if (i >= 0) return c.map((l, j) => (j === i ? { ...l, qty: l.qty + 1 } : l));
      return [...c, { item: it, qty: 1, rate: it.sale_price }];
    });
  };

  const onScan = () => {
    const code = scan.trim();
    if (!code || !items) return;
    const hit = items.find((i) => i.code === code) ?? items.find((i) => i.name.toLowerCase() === code.toLowerCase())
      ?? items.find((i) => i.name.toLowerCase().includes(code.toLowerCase()));
    if (hit) add(hit);
    else setErr(`No item with code “${code}”`);
    setScan("");
  };

  const taxApplicable = business?.gst_type === "REGULAR";
  const party = parties?.find((p) => p.id === partyId) ?? null;
  const interState = !!party?.state_code && party.state_code !== business?.state_code;
  const totals = calcInvoice(cart.map((l) => ({
    qty: l.qty, rate: l.rate, gst_rate: l.item.gst_rate, cess_rate: l.item.cess_rate, discount_pct: 0,
    tax_inclusive: l.item.sale_price_tax_inclusive,
  })), taxApplicable, interState);
  const change = Math.max(0, (Number(tendered) || 0) - totals.grand_total);

  async function save() {
    if (!cart.length || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const v = await api<VoucherDetail>("/vouchers", { body: {
        type: "SALE", date: today(), party_id: partyId, party_name: partyId ? null : walkIn.name || null,
        party_phone: partyId ? null : walkIn.phone || null, fully_paid: true, payment_mode: mode,
        lines: cart.map((l) => ({ item_id: l.item.id, name: l.item.name, hsn_sac: l.item.hsn_sac, unit: l.item.unit,
          qty: l.qty, rate: l.rate, gst_rate: l.item.gst_rate, cess_rate: l.item.cess_rate,
          tax_inclusive: l.item.sale_price_tax_inclusive })),
      } });
      setCart([]); setTendered(""); setPartyId(null); setWalkIn({ name: "", phone: "" });
      router.push(`/print/${v.id}?format=${business?.print_settings?.paper?.startsWith("THERMAL") ? business.print_settings.paper : "THERMAL_80"}&back=/pos`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // keyboard: F2 = scan box, F9 = save & print
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "F2") { e.preventDefault(); scanRef.current?.focus(); }
      if (e.key === "F9") { e.preventDefault(); save(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!business || !items || !parties) return <Loading />;

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Card className="p-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <ScanLine size={18} className="pointer-events-none absolute top-2.5 left-3 text-gray-400" />
              <input ref={scanRef} autoFocus className="input pl-10 text-base" placeholder="Scan barcode or type item code, then Enter  (F2)"
                value={scan} onChange={(e) => setScan(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); onScan(); } }} />
            </div>
            <div className="w-72">
              <Combobox items={items} value="" placeholder="…or search item" getKey={(i) => i.id} getLabel={(i) => `${i.name} ${i.code ?? ""}`}
                renderOption={(i) => <div className="flex justify-between"><span>{i.name}</span><span className="text-xs text-gray-500">{money(i.sale_price)}</span></div>}
                onSelect={add} />
            </div>
          </div>
          {err && <div className="mt-3"><ErrorBox message={err} /></div>}
        </Card>
        <Card className="overflow-x-auto">
          {cart.length === 0 ? (
            <p className="py-16 text-center text-sm text-gray-500">Scan an item to start the bill</p>
          ) : (
            <table className="tbl">
              <thead><tr><th>Item</th><th className="w-40 text-center">Qty</th><th className="w-32 text-right">Rate</th><th className="num">Amount</th><th className="w-8" /></tr></thead>
              <tbody>
                {cart.map((l, i) => (
                  <tr key={l.item.id}>
                    <td><div className="font-medium">{l.item.name}</div><div className="text-xs text-gray-500">{l.item.code} · GST {l.item.gst_rate}%</div></td>
                    <td>
                      <div className="flex items-center justify-center gap-1">
                        <button className="rounded border border-gray-300 p-1" aria-label="Less" onClick={() => setCart((c) => c.map((x, j) => j === i ? { ...x, qty: Math.max(1, x.qty - 1) } : x))}><Minus size={14} /></button>
                        <input className="input !w-16 text-center" inputMode="decimal" value={l.qty} onChange={(e) => setCart((c) => c.map((x, j) => j === i ? { ...x, qty: Number(e.target.value) || 0 } : x))} />
                        <button className="rounded border border-gray-300 p-1" aria-label="More" onClick={() => setCart((c) => c.map((x, j) => j === i ? { ...x, qty: x.qty + 1 } : x))}><Plus size={14} /></button>
                      </div>
                    </td>
                    <td><input className="input text-right" inputMode="decimal" value={l.rate} onChange={(e) => setCart((c) => c.map((x, j) => j === i ? { ...x, rate: Number(e.target.value) || 0 } : x))} /></td>
                    <td className="num font-medium">{money(totals.lines[i]?.total)}</td>
                    <td><button className="text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => setCart((c) => c.filter((_, j) => j !== i))}><Trash2 size={16} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <Card className="h-fit space-y-4 p-5 lg:sticky lg:top-20">
        <Field label="Customer">
          <Combobox items={parties} value={party?.name ?? ""} placeholder="Walk-in customer" getKey={(p) => p.id} getLabel={(p) => `${p.name} ${p.phone ?? ""}`} onSelect={(p) => setPartyId(p.id)} />
          {partyId && <button className="mt-1 text-xs text-gray-500 hover:underline" onClick={() => setPartyId(null)}>Walk-in instead</button>}
        </Field>
        {!partyId && (
          <div className="grid grid-cols-2 gap-2">
            <Input placeholder="Name (optional)" value={walkIn.name} onChange={(e) => setWalkIn({ ...walkIn, name: e.target.value })} />
            <Input placeholder="Mobile (optional)" value={walkIn.phone} onChange={(e) => setWalkIn({ ...walkIn, phone: e.target.value })} />
          </div>
        )}
        <dl className="space-y-1 text-sm">
          <div className="flex justify-between text-gray-600"><dt>Items</dt><dd>{cart.reduce((s, l) => s + l.qty, 0)}</dd></div>
          <div className="flex justify-between text-gray-600"><dt>Taxable</dt><dd>{money(totals.taxable)}</dd></div>
          {taxApplicable && <div className="flex justify-between text-gray-600"><dt>GST</dt><dd>{money(totals.cgst + totals.sgst + totals.igst + totals.cess)}</dd></div>}
          <div className="flex justify-between border-t border-gray-200 pt-2 text-2xl font-bold text-gray-900"><dt>Total</dt><dd className="tabular-nums">{money(totals.grand_total)}</dd></div>
        </dl>
        <div className="grid grid-cols-3 gap-2">
          {(["CASH", "UPI", "CARD"] as PaymentMode[]).map((m) => (
            <button key={m} onClick={() => setMode(m)} className={`rounded-lg border py-2 text-sm font-medium ${mode === m ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-200"}`}>{m === "CASH" ? "Cash" : m === "UPI" ? "UPI" : "Card"}</button>
          ))}
        </div>
        {mode === "CASH" && (
          <div className="grid grid-cols-2 items-end gap-2">
            <Field label="Cash received"><Input inputMode="decimal" value={tendered} onChange={(e) => setTendered(e.target.value)} /></Field>
            <div className="pb-2 text-right text-sm">Return <b className="tabular-nums">{money(change)}</b></div>
          </div>
        )}
        <Button className="w-full !py-3 text-base" disabled={!cart.length || busy} onClick={save}>{busy ? "Saving…" : "Save & print (F9)"}</Button>
      </Card>
    </div>
  );
}
