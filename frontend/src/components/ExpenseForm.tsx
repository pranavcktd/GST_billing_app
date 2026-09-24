"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AccountSelect } from "@/components/AccountSelect";
import { Button, Card, Combobox, ErrorBox, Field, Input, Loading, Select, Textarea } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { GST_RATES, PAYMENT_MODES } from "@/lib/constants";
import { money, today } from "@/lib/format";
import { calcInvoice } from "@/lib/gst";
import { useFetch } from "@/lib/useFetch";
import type { Business, ExpenseCategory, ExpenseItem, Party, PaymentMode, VoucherDetail } from "@/lib/types";

interface Line { key: number; expense_item_id: string | null; name: string; qty: string; rate: string; gst_rate: number; hsn_sac: string }
let k = 1;
const blank = (): Line => ({ key: k++, expense_item_id: null, name: "", qty: "1", rate: "", gst_rate: 0, hsn_sac: "" });
const num = (s: string) => (s.trim() === "" ? 0 : Number(s) || 0);

export function ExpenseForm({ existing }: { existing?: VoucherDetail }) {
  const router = useRouter();
  const { data: business } = useFetch<Business>("/businesses/current");
  const { data: cats, setData: setCats } = useFetch<ExpenseCategory[]>("/expenses/categories");
  const { data: expItems, setData: setExpItems } = useFetch<ExpenseItem[]>("/expenses/items");
  const { data: parties } = useFetch<Party[]>(`/parties${qs({ type: "SUPPLIER" })}`);

  const [categoryId, setCategoryId] = useState(existing?.expense_category_id ?? "");
  const [newCat, setNewCat] = useState("");
  const [date, setDate] = useState(existing?.date ?? today());
  const [number, setNumber] = useState(existing?.number ?? "");
  const [nextNumber, setNextNumber] = useState("");
  const [partyId, setPartyId] = useState<string | null>(existing?.party_id ?? null);
  const [gstBill, setGstBill] = useState(existing?.tax_applicable ?? false);
  const [lines, setLines] = useState<Line[]>(() =>
    existing ? existing.lines.map((l) => ({ key: k++, expense_item_id: l.expense_item_id ?? null, name: l.name, qty: String(l.qty),
      rate: String(l.rate), gst_rate: l.gst_rate, hsn_sac: l.hsn_sac ?? "" })) : [blank()]);
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [paidNow, setPaidNow] = useState(!existing);
  const [mode, setMode] = useState<PaymentMode>("CASH");
  const [accountId, setAccountId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (existing) return;
    api<{ number: string }>(`/vouchers/next-number${qs({ type: "EXPENSE", date })}`).then((r) => setNextNumber(r.number)).catch(() => {});
  }, [date, existing]);

  if (!business || !cats || !expItems || !parties) return <Loading />;

  const party = parties.find((p) => p.id === partyId);
  const interState = !!party?.state_code && party.state_code !== business.state_code;
  const totals = calcInvoice(
    lines.map((l) => ({ qty: num(l.qty), rate: num(l.rate), gst_rate: l.gst_rate, cess_rate: 0, discount_pct: 0, tax_inclusive: false })),
    gstBill, interState,
  );
  const update = (key: number, patch: Partial<Line>) => setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  const catItems = expItems.filter((i) => i.is_active && (!categoryId || !i.category_id || i.category_id === categoryId));

  async function addCategory() {
    if (!newCat.trim()) return;
    try {
      const c = await api<ExpenseCategory>("/expenses/categories", { body: { name: newCat.trim(), kind: "INDIRECT" } });
      setCats([...cats!, c].sort((a, b) => a.name.localeCompare(b.name)));
      setCategoryId(c.id);
      setNewCat("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function ensureItem(l: Line): Promise<string | null> {
    if (l.expense_item_id) return l.expense_item_id;
    const found = expItems!.find((i) => i.name.toLowerCase() === l.name.trim().toLowerCase());
    if (found) return found.id;
    const created = await api<ExpenseItem>("/expenses/items", {
      body: { name: l.name.trim(), category_id: categoryId || null, gst_rate: l.gst_rate, hsn_sac: l.hsn_sac || null },
    });
    setExpItems([...expItems!, created]);
    return created.id;
  }

  async function save() {
    setError(null);
    if (!categoryId) return setError("Choose an expense category");
    const valid = lines.filter((l) => l.name.trim() && num(l.rate) > 0);
    if (!valid.length) return setError("Enter at least one expense line with an amount");
    if (!partyId && !paidNow) return setError("Expenses without a party must be paid now");
    setBusy(true);
    try {
      const ids: (string | null)[] = [];
      for (const l of valid) ids.push(await ensureItem(l));
      const body = {
        type: "EXPENSE", number: number || null, date, party_id: partyId, expense_category_id: categoryId,
        tax_applicable: gstBill, notes: notes || null,
        lines: valid.map((l, i) => ({ expense_item_id: ids[i], name: l.name.trim(), qty: num(l.qty) || 1,
          rate: Math.round(num(l.rate) * 100) / 100, gst_rate: gstBill ? l.gst_rate : 0, hsn_sac: l.hsn_sac || null })),
        fully_paid: !existing && paidNow, payment_mode: mode, payment_account_id: accountId || null,
      };
      const saved = existing
        ? await api<VoucherDetail>(`/vouchers/${existing.id}`, { method: "PUT", body })
        : await api<VoucherDetail>("/vouchers", { body });
      router.push(`/v/expenses/${saved.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <ErrorBox message={error} />
      <Card className="p-5">
        <div className="grid gap-4 md:grid-cols-4">
          <Field label="Category" required className="md:col-span-2">
            <div className="flex gap-2">
              <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                <option value="">Select category</option>
                {cats.filter((c) => c.is_active || c.id === categoryId).map((c) => (
                  <option key={c.id} value={c.id}>{c.name}{c.kind === "DIRECT" ? " (direct)" : ""}</option>
                ))}
              </Select>
            </div>
            <div className="mt-2 flex gap-2">
              <Input placeholder="…or add a new category" value={newCat} onChange={(e) => setNewCat(e.target.value)} />
              <Button type="button" variant="secondary" onClick={addCategory} disabled={!newCat.trim()}>Add</Button>
            </div>
          </Field>
          <Field label="Expense no." hint={existing ? undefined : "Leave blank for auto"}>
            <Input value={number} placeholder={nextNumber} maxLength={16} onChange={(e) => setNumber(e.target.value)} />
          </Field>
          <Field label="Date"><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          <Field label="Paid to (optional supplier)" className="md:col-span-2">
            <Combobox items={parties} value={party?.name ?? ""} placeholder="Search supplier — or leave empty"
              getKey={(p) => p.id} getLabel={(p) => `${p.name} ${p.gstin ?? ""}`} onSelect={(p) => { setPartyId(p.id); if (p.gstin) setGstBill(true); }} />
            {partyId && <button className="mt-1 text-xs text-gray-500 hover:underline" onClick={() => setPartyId(null)}>Clear</button>}
          </Field>
          <label className="flex items-center gap-2 self-end pb-2 text-sm md:col-span-2">
            <input type="checkbox" checked={gstBill} onChange={(e) => setGstBill(e.target.checked)} />
            GST bill {business.gst_type === "REGULAR" ? "(claim input tax credit)" : ""}
          </label>
        </div>
      </Card>

      <Card className="overflow-x-auto">
        <table className="tbl min-w-[700px]">
          <thead>
            <tr><th className="w-8">#</th><th>Expense item</th><th className="w-24">Qty</th><th className="w-36 text-right">Amount (₹)</th>
              {gstBill && <th className="w-24">GST</th>}<th className="w-32 text-right">Total</th><th className="w-10" /></tr>
          </thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={l.key}>
                <td className="pt-4 text-gray-500">{i + 1}</td>
                <td>
                  <Combobox items={catItems} value={l.name} placeholder="Search or type (e.g. Petrol, Tea)"
                    getKey={(x) => x.id} getLabel={(x) => x.name}
                    onSelect={(x) => update(l.key, { expense_item_id: x.id, name: x.name, gst_rate: x.gst_rate, hsn_sac: x.hsn_sac ?? "", rate: x.rate ? String(x.rate) : l.rate })} />
                  {!l.expense_item_id && (
                    <input className="mt-1 w-full border-0 border-b border-dashed border-gray-200 px-1 py-0.5 text-xs outline-none"
                      placeholder="…or type a new expense item (saved automatically)" value={l.name}
                      onChange={(e) => update(l.key, { name: e.target.value })} />
                  )}
                </td>
                <td><Input inputMode="decimal" className="text-right" value={l.qty} onChange={(e) => update(l.key, { qty: e.target.value })} /></td>
                <td><Input inputMode="decimal" className="text-right" value={l.rate} onChange={(e) => update(l.key, { rate: e.target.value })} /></td>
                {gstBill && (
                  <td>
                    <Select value={l.gst_rate} onChange={(e) => update(l.key, { gst_rate: Number(e.target.value) })}>
                      {GST_RATES.map((r) => <option key={r} value={r}>{r}%</option>)}
                    </Select>
                  </td>
                )}
                <td className="num pt-4 font-medium">{money(totals.lines[i]?.total)}</td>
                <td className="pt-3">
                  {lines.length > 1 && (
                    <button className="text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => setLines((ls) => ls.filter((x) => x.key !== l.key))}>
                      <Trash2 size={16} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="p-3">
          <Button variant="secondary" onClick={() => setLines((ls) => [...ls, blank()])}><Plus size={16} /> Add line</Button>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="p-5 lg:col-span-3">
          <Field label="Notes"><Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        </Card>
        <Card className="space-y-3 p-5 lg:col-span-2">
          <div className="flex justify-between text-sm text-gray-600"><span>Amount</span><span>{money(totals.taxable)}</span></div>
          {gstBill && <div className="flex justify-between text-sm text-gray-600"><span>GST</span><span>{money(totals.cgst + totals.sgst + totals.igst)}</span></div>}
          <div className="flex justify-between border-t border-gray-200 pt-2 font-semibold"><span>Total</span><span>{money(totals.grand_total)}</span></div>
          {!existing && (
            <>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={paidNow} onChange={(e) => setPaidNow(e.target.checked)} /> Paid now
              </label>
              {paidNow && (
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Mode">
                    <Select value={mode} onChange={(e) => setMode(e.target.value as PaymentMode)}>
                      {Object.entries(PAYMENT_MODES).map(([key, v]) => <option key={key} value={key}>{v}</option>)}
                    </Select>
                  </Field>
                  <Field label="Paid from"><AccountSelect value={accountId} onChange={setAccountId} /></Field>
                </div>
              )}
            </>
          )}
        </Card>
      </div>

      <div className="sticky bottom-0 -mx-4 flex justify-end gap-2 border-t border-gray-200 bg-white/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <Button variant="secondary" onClick={() => router.back()}>Cancel</Button>
        <Button disabled={busy} onClick={save}>{busy ? "Saving…" : "Save expense"}</Button>
      </div>
    </div>
  );
}
