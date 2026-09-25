"use client";

import { Plus, Trash2, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AccountSelect } from "@/components/AccountSelect";
import { QuickPartyDialog } from "@/components/QuickPartyDialog";
import { TransportFields } from "@/components/TransportFields";
import { useConfig } from "@/lib/config";
import { Button, Card, Combobox, ErrorBox, Field, Input, Loading, Select, Textarea } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { GST_RATES, KINDS, type Kind, NON_LEDGER, PAYMENT_MODES, STATES, isOutward, stateLabel } from "@/lib/constants";
import { money, today } from "@/lib/format";
import { calcInvoice } from "@/lib/gst";
import { useFetch } from "@/lib/useFetch";
import type { Business, Godown, Item, Party, PaymentMode, Transport, Voucher, VoucherDetail } from "@/lib/types";

interface FormLine {
  key: number;
  item_id: string | null;
  name: string;
  description: string;
  hsn_sac: string;
  unit: string;
  qty: string;
  rate: string;
  discount_pct: string;
  gst_rate: number;
  cess_rate: number;
  tax_inclusive: boolean;
  batch_no: string;
  expiry_date: string;
  serial_nos: string;
}

let lineKey = 1;
const blankLine = (): FormLine => ({
  key: lineKey++, item_id: null, name: "", description: "", hsn_sac: "", unit: "NOS", qty: "1", rate: "",
  discount_pct: "", gst_rate: 18, cess_rate: 0, tax_inclusive: false, batch_no: "", expiry_date: "", serial_nos: "",
});

const fromLine = (l: VoucherDetail["lines"][number]): FormLine => ({
  key: lineKey++, item_id: l.item_id, name: l.name, description: l.description ?? "", hsn_sac: l.hsn_sac ?? "",
  unit: l.unit ?? "NOS", qty: String(l.qty), rate: String(l.rate), discount_pct: l.discount_pct ? String(l.discount_pct) : "",
  gst_rate: l.gst_rate, cess_rate: l.cess_rate, tax_inclusive: l.tax_inclusive, batch_no: l.batch_no ?? "",
  expiry_date: l.expiry_date ?? "", serial_nos: l.serial_nos ?? "",
});

const toNum = (s: string) => (s.trim() === "" ? 0 : Number(s) || 0);
const round2 = (n: number) => Math.round(n * 100) / 100;

export function VoucherForm({
  kind,
  existing,
  presetPartyId,
  sourceId,
  originalId,
}: {
  kind: Kind;
  existing?: VoucherDetail;
  presetPartyId?: string | null;
  sourceId?: string | null;
  originalId?: string | null;
}) {
  const meta = KINDS[kind];
  const vtype = meta.type;
  const outward = isOutward(vtype);
  const config = useConfig();
  const isReturn = vtype === "SALE_RETURN" || vtype === "PURCHASE_RETURN";
  const router = useRouter();

  const { data: business } = useFetch<Business>("/businesses/current");
  const { data: partiesData, setData: setParties } = useFetch<Party[]>(`/parties${qs({ type: meta.party })}`);
  const { data: items } = useFetch<Item[]>("/items");
  const { data: godowns } = useFetch<Godown[]>(vtype === "EXPENSE" ? null : "/godowns");
  const parties = useMemo(() => partiesData ?? [], [partiesData]);

  const [partyId, setPartyId] = useState<string | null>(existing?.party_id ?? presetPartyId ?? null);
  const [walkInName, setWalkInName] = useState(existing && !existing.party_id ? existing.party_name : "");
  const [walkInPhone, setWalkInPhone] = useState(existing?.party_phone ?? "");
  const [number, setNumber] = useState(existing?.number ?? "");
  const [nextNumber, setNextNumber] = useState("");
  const [date, setDate] = useState(existing?.date ?? today());
  const [dueDate, setDueDate] = useState(existing?.due_date ?? "");
  const [pos, setPos] = useState(existing?.place_of_supply ?? "");
  const [supplierCharged, setSupplierCharged] = useState<boolean | null>(existing ? existing.tax_applicable : null);
  const [reverseCharge, setReverseCharge] = useState(existing?.reverse_charge ?? false);
  const [supplierInvNo, setSupplierInvNo] = useState(existing?.supplier_invoice_no ?? "");
  const [supplierInvDate, setSupplierInvDate] = useState(existing?.supplier_invoice_date ?? "");
  const [original, setOriginal] = useState(existing?.original_voucher_id ?? originalId ?? "");
  const [reason, setReason] = useState(existing?.reason ?? "");
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [terms, setTerms] = useState<string | null>(existing ? existing.terms ?? "" : null);
  const [roundOff, setRoundOff] = useState(true);
  const [lines, setLines] = useState<FormLine[]>(() => (existing ? existing.lines.map(fromLine) : [blankLine()]));
  const [tcsRate, setTcsRate] = useState(existing?.tcs_rate ? String(existing.tcs_rate) : "");
  const [paid, setPaid] = useState("");
  const [fullyPaid, setFullyPaid] = useState(false);
  const [mode, setMode] = useState<PaymentMode>("CASH");
  const [accountId, setAccountId] = useState("");
  const [godownId, setGodownId] = useState(existing?.godown_id ?? "");
  const [extra, setExtra] = useState<Record<string, string>>(existing?.extra_fields ?? {});
  const [transport, setTransport] = useState<Transport>(existing?.transport ?? {});
  const [showTransport, setShowTransport] = useState(!!existing?.transport);
  const [exportPay, setExportPay] = useState<"" | "WP" | "WOP">(
    existing?.export_type?.endsWith("WOP") ? "WOP" : existing?.export_type?.endsWith("WP") ? "WP" : "");
  const [shipBill, setShipBill] = useState(existing?.shipping_bill_no ?? "");
  const [shipDate, setShipDate] = useState(existing?.shipping_bill_date ?? "");
  const [portCode, setPortCode] = useState(existing?.port_code ?? "");
  const [currency, setCurrency] = useState(existing?.currency_code ?? "");
  const [fxRate, setFxRate] = useState(existing?.exchange_rate ? String(existing.exchange_rate) : "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [quickParty, setQuickParty] = useState<string | null>(null);

  const party = parties.find((p) => p.id === partyId) ?? null;
  // untouched terms fall back to the business default
  const termsValue = terms ?? (outward ? business?.invoice_terms ?? "" : "");

  // next number preview
  useEffect(() => {
    if (existing) return;
    api<{ number: string }>(`/vouchers/next-number${qs({ type: vtype, date })}`).then((r) => setNextNumber(r.number)).catch(() => {});
  }, [vtype, date, existing]);

  // convert estimate / order / challan -> bill
  useEffect(() => {
    if (!sourceId) return;
    api<VoucherDetail>(`/vouchers/${sourceId}`).then((src) => {
      setPartyId(src.party_id);
      if (!src.party_id) setWalkInName(src.party_name);
      setNotes(src.notes ?? "");
      setLines(src.lines.map(fromLine));
    }).catch((e) => setError(e.message));
  }, [sourceId]);

  // bills this return can refer to
  const originalType = vtype === "SALE_RETURN" ? "SALE" : "PURCHASE";
  const { data: partyBills } = useFetch<Voucher[]>(
    isReturn && partyId ? `/vouchers${qs({ type: originalType, party_id: partyId, limit: 100 })}` : null,
  );

  if (!business || !partiesData || !items) return <Loading />;
  const customFields = business.print_settings?.custom_fields ?? [];
  const activeGodowns = (godowns ?? []).filter((g) => g.is_active);

  // ---- GST context (mirrors the backend) ----
  const taxApplicable = outward
    ? business.gst_type === "REGULAR"
    : supplierCharged ?? (party ? ["REGISTERED", "SEZ", "OVERSEAS"].includes(party.gst_type) : false);
  const exportKind = outward && party ? (party.gst_type === "OVERSEAS" ? "EXP" : party.gst_type === "SEZ" ? "SEZ" : null) : null;
  const isImport = !outward && party?.gst_type === "OVERSEAS";
  const lutOk = !!business.lut_number && (!business.lut_valid_till || business.lut_valid_till >= date);
  const zeroRated = !!exportKind && taxApplicable && (exportPay ? exportPay === "WOP" : lutOk);
  const placeOfSupply = outward ? pos || party?.state_code || business.state_code : pos || business.state_code;
  const supplierState = outward ? business.state_code : party?.state_code || business.state_code;
  const interState = !!exportKind || isImport || supplierState !== placeOfSupply;

  const calcLines = lines.map((l) => ({
    qty: toNum(l.qty), rate: toNum(l.rate), gst_rate: l.gst_rate, cess_rate: l.cess_rate,
    discount_pct: toNum(l.discount_pct), tax_inclusive: l.tax_inclusive,
  }));
  const totals = calcInvoice(calcLines, taxApplicable && !zeroRated, interState, roundOff, reverseCharge && !outward && taxApplicable, toNum(tcsRate));
  const canPay = !existing && !NON_LEDGER.includes(vtype);
  const isOrder = NON_LEDGER.includes(vtype);
  const tracked = (l: FormLine) => items?.find((i) => i.id === l.item_id);
  const paidAmount = fullyPaid ? totals.grand_total : toNum(paid);

  const updateLine = (key: number, patch: Partial<FormLine>) =>
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  const pickItem = (key: number, it: Item) => {
    const sale = meta.party === "CUSTOMER";
    updateLine(key, {
      item_id: it.id, name: it.name, hsn_sac: it.hsn_sac ?? "", unit: it.unit, gst_rate: it.gst_rate, cess_rate: it.cess_rate,
      rate: String(sale ? it.sale_price : it.purchase_price),
      tax_inclusive: sale ? it.sale_price_tax_inclusive : it.purchase_price_tax_inclusive,
    });
  };

  async function save(andPrint: boolean) {
    setError(null);
    const valid = lines.filter((l) => l.name.trim());
    if (!valid.length) return setError("Add at least one item");
    if (valid.some((l) => toNum(l.qty) <= 0)) return setError("Quantity must be more than zero");
    setBusy(true);
    try {
      const body = {
        type: vtype, number: number || null, date, due_date: dueDate || null,
        party_id: partyId, party_name: partyId ? null : walkInName || null, party_phone: partyId ? null : walkInPhone || null,
        place_of_supply: pos || null,
        tax_applicable: outward ? null : taxApplicable, reverse_charge: !outward && reverseCharge,
        supplier_invoice_no: supplierInvNo || null, supplier_invoice_date: supplierInvDate || null,
        original_voucher_id: isReturn ? original || null : null, reason: reason || null,
        notes: notes || null, terms: termsValue || null, round_off: roundOff,
        lines: valid.map((l) => ({
          item_id: l.item_id, name: l.name, description: l.description || null, hsn_sac: l.hsn_sac || null, unit: l.unit,
          qty: toNum(l.qty), rate: round2(toNum(l.rate)), discount_pct: toNum(l.discount_pct),
          gst_rate: l.gst_rate, cess_rate: l.cess_rate, tax_inclusive: l.tax_inclusive,
          batch_no: l.batch_no || null, expiry_date: l.expiry_date || null, serial_nos: l.serial_nos || null,
        })),
        tcs_rate: toNum(tcsRate),
        amount_paid: canPay && !fullyPaid ? round2(paidAmount) : 0,
        fully_paid: canPay && fullyPaid,
        payment_mode: mode,
        payment_account_id: accountId || null,
        godown_id: godownId || null,
        extra_fields: Object.keys(extra).length ? extra : null,
        transport: Object.values(transport).some((x) => x !== undefined && x !== "") ? transport : null,
        source_voucher_id: sourceId || null,
        export_with_payment: exportKind && exportPay ? exportPay === "WP" : null,
        shipping_bill_no: (exportKind || isImport) && shipBill ? shipBill : null,
        shipping_bill_date: (exportKind || isImport) && shipDate ? shipDate : null,
        port_code: (exportKind || isImport) && portCode ? portCode.toUpperCase() : null,
        currency_code: exportKind === "EXP" && currency ? currency.toUpperCase() : null,
        exchange_rate: exportKind === "EXP" && toNum(fxRate) > 0 ? toNum(fxRate) : null,
      };
      const saved = existing
        ? await api<VoucherDetail>(`/vouchers/${existing.id}`, { method: "PUT", body })
        : await api<VoucherDetail>("/vouchers", { body });
      router.push(andPrint ? `/print/${saved.id}` : `/v/${kind}/${saved.id}`);
    } catch (e) {
      setError((e as Error).message);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setBusy(false);
    }
  }

  const docLabel = meta.label;
  const walkInAllowed = vtype === "SALE" || vtype === "ESTIMATE";

  return (
    <div className="space-y-5">
      <ErrorBox message={error} />
      {!taxApplicable && outward && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Your business is {business.gst_type === "COMPOSITION" ? "under the Composition scheme" : "not GST registered"} — this will be issued as a{" "}
          <b>Bill of Supply</b> without GST.
        </div>
      )}

      <Card className="p-5">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="md:col-span-2">
            <Field label={meta.partyLabel} required={!walkInAllowed}>
              <div className="flex gap-2">
                <div className="flex-1">
                  <Combobox
                    items={parties}
                    value={party?.name ?? ""}
                    placeholder={walkInAllowed ? "Search party — or leave empty for a cash sale" : "Search party"}
                    getKey={(p) => p.id}
                    getLabel={(p) => `${p.name} ${p.phone ?? ""} ${p.gstin ?? ""}`}
                    renderOption={(p) => (
                      <div className="flex justify-between gap-3">
                        <span>
                          <span className="font-medium">{p.name}</span>
                          {p.gstin && <span className="ml-2 font-mono text-xs text-gray-500">{p.gstin}</span>}
                        </span>
                        <span className={`text-xs ${p.balance > 0 ? "text-emerald-700" : p.balance < 0 ? "text-red-700" : "text-gray-400"}`}>
                          {money(Math.abs(p.balance))}
                        </span>
                      </div>
                    )}
                    onSelect={(p) => {
                      setPartyId(p.id);
                      setPos("");
                      setOriginal("");
                      setSupplierCharged(null);
                    }}
                    footer={
                      <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => setQuickParty("")}
                        className="flex w-full items-center gap-2 rounded px-2 py-2 text-left text-sm font-medium text-brand-600 hover:bg-brand-50">
                        <UserPlus size={15} /> Add new {meta.partyLabel.toLowerCase()}
                      </button>
                    }
                  />
                </div>
                {partyId && (
                  <Button type="button" variant="ghost" onClick={() => setPartyId(null)} aria-label="Clear party">
                    <Trash2 size={16} />
                  </Button>
                )}
              </div>
            </Field>
            {party ? (
              <p className="mt-2 text-xs text-gray-600">
                {[party.gstin ? `GSTIN ${party.gstin}` : "Unregistered", stateLabel(party.state_code), party.phone].filter(Boolean).join(" · ")}
                {party.balance !== 0 && (
                  <span className={party.balance > 0 ? "ml-2 text-emerald-700" : "ml-2 text-red-700"}>
                    · Balance {money(Math.abs(party.balance))} {party.balance > 0 ? "to collect" : "to pay"}
                  </span>
                )}
              </p>
            ) : walkInAllowed ? (
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Input placeholder="Customer name (optional)" value={walkInName} onChange={(e) => setWalkInName(e.target.value)} />
                <Input placeholder="Phone (optional)" value={walkInPhone ?? ""} onChange={(e) => setWalkInPhone(e.target.value)} />
              </div>
            ) : null}
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-1">
            <Field label={`${docLabel} no.`} hint={existing ? undefined : "Leave blank for auto"}>
              <Input value={number} placeholder={nextNumber} maxLength={16} onChange={(e) => setNumber(e.target.value)} />
            </Field>
            <Field label="Date"><Input type="date" required value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          </div>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 md:grid-cols-4">
          {(vtype === "SALE" || vtype === "PURCHASE" || isOrder) && (
            <Field label={isOrder ? (vtype === "ESTIMATE" ? "Valid till" : "Delivery date") : "Due date"}>
              <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </Field>
          )}
          {(taxApplicable || outward) && exportKind !== "EXP" && !isImport && (
            <Field label="Place of supply" hint={interState ? "Inter-state → IGST" : "Intra-state → CGST + SGST"}>
              <Select value={placeOfSupply} onChange={(e) => setPos(e.target.value)}>
                {Object.entries(STATES).map(([c, n]) => <option key={c} value={c}>{c} - {n}</option>)}
              </Select>
            </Field>
          )}
          {!outward && (
            <>
              <Field label="Supplier bill no."><Input value={supplierInvNo} onChange={(e) => setSupplierInvNo(e.target.value)} /></Field>
              <Field label="Supplier bill date"><Input type="date" value={supplierInvDate} onChange={(e) => setSupplierInvDate(e.target.value)} /></Field>
            </>
          )}
          {isReturn && (
            <>
              <Field label={`Against ${vtype === "SALE_RETURN" ? "invoice" : "bill"}`}>
                <Select value={original} onChange={(e) => setOriginal(e.target.value)} disabled={!partyId}>
                  <option value="">{partyId ? "Select (optional)" : "Select a party first"}</option>
                  {partyBills?.filter((b) => !b.cancelled).map((b) => (
                    <option key={b.id} value={b.id}>{b.number} · {money(b.grand_total)}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Reason">
                <Select value={reason} onChange={(e) => setReason(e.target.value)}>
                  <option value="">Select</option>
                  {config.credit_note_reasons.map((r) => (
                    <option key={r}>{r}</option>
                  ))}
                </Select>
              </Field>
            </>
          )}
        </div>
        {(exportKind || isImport) && (
          <div className="mt-4 rounded-lg border border-sky-100 bg-sky-50/50 p-3">
            <p className="mb-3 text-xs text-sky-800">
              {isImport
                ? "Import — IGST paid at customs (goods) or under reverse charge (services). Enter the bill of entry for ITC on imports (GSTR-3B 4A)."
                : exportKind === "EXP"
                  ? "Export of goods / services — zero rated, place of supply outside India (96)."
                  : "Supply to an SEZ unit / developer — zero rated, treated as inter-state."}
            </p>
            <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
              {exportKind && taxApplicable && (
                <Field label="IGST" hint={lutOk ? `LUT ${business.lut_number}` : "No valid LUT in Settings"}>
                  <Select value={exportPay || (lutOk ? "WOP" : "WP")} onChange={(e) => setExportPay(e.target.value as "WP" | "WOP")}>
                    <option value="WOP" disabled={!lutOk}>Without payment (under LUT)</option>
                    <option value="WP">With payment of IGST</option>
                  </Select>
                </Field>
              )}
              {vtype !== "ESTIMATE" && vtype !== "SALE_ORDER" && vtype !== "PURCHASE_ORDER" && (exportKind === "EXP" || isImport) && (
                <>
                  <Field label={isImport ? "Bill of entry no." : "Shipping bill no."}><Input maxLength={20} value={shipBill} onChange={(e) => setShipBill(e.target.value)} /></Field>
                  <Field label={isImport ? "Bill of entry date" : "Shipping bill date"}><Input type="date" value={shipDate} onChange={(e) => setShipDate(e.target.value)} /></Field>
                  <Field label="Port code" hint="6 characters, e.g. INNSA1"><Input maxLength={6} className="uppercase" value={portCode} onChange={(e) => setPortCode(e.target.value)} /></Field>
                </>
              )}
              {exportKind === "EXP" && (
                <>
                  <Field label="Foreign currency" hint="e.g. USD"><Input maxLength={3} className="uppercase" value={currency} onChange={(e) => setCurrency(e.target.value)} /></Field>
                  <Field label="Exchange rate (₹)"><Input inputMode="decimal" value={fxRate} onChange={(e) => setFxRate(e.target.value)} /></Field>
                </>
              )}
            </div>
          </div>
        )}
        {!outward && (
          <div className="mt-4 flex flex-wrap gap-5 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={taxApplicable} onChange={(e) => setSupplierCharged(e.target.checked)} />
              Supplier charged GST on this bill
            </label>
            {taxApplicable && (
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={reverseCharge} onChange={(e) => setReverseCharge(e.target.checked)} />
                Reverse charge (RCM) — you pay the GST
              </label>
            )}
          </div>
        )}
        {(customFields.length > 0 || activeGodowns.length > 1) && (
          <div className="mt-4 grid gap-4 sm:grid-cols-2 md:grid-cols-4">
            {activeGodowns.length > 1 && ["SALE", "SALE_RETURN", "PURCHASE", "PURCHASE_RETURN"].includes(vtype) && (
              <Field label="Godown / location">
                <Select value={godownId || activeGodowns.find((g) => g.is_default)?.id || ""} onChange={(e) => setGodownId(e.target.value)}>
                  {activeGodowns.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                </Select>
              </Field>
            )}
            {customFields.map((f) => (
              <Field key={f.key} label={f.label}>
                <Input value={extra[f.key] ?? ""} onChange={(e) => setExtra({ ...extra, [f.key]: e.target.value })} />
              </Field>
            ))}
          </div>
        )}
        {vtype !== "EXPENSE" && (
          <div className="mt-4 border-t border-gray-100 pt-3">
            <button type="button" className="text-sm font-medium text-brand-600 hover:underline" onClick={() => setShowTransport((x) => !x)}>
              {showTransport ? "− Hide" : "+ Add"} transport & shipping details
            </button>
            {showTransport && <div className="mt-3"><TransportFields value={transport} onChange={setTransport} /></div>}
          </div>
        )}
      </Card>

      <Card className="overflow-x-auto">
        <table className="tbl min-w-[900px]">
          <thead>
            <tr>
              <th className="w-8">#</th>
              <th className="min-w-64">Item</th>
              <th className="w-24">HSN/SAC</th>
              <th className="w-24 text-right">Qty</th>
              <th className="w-32 text-right">Rate (₹)</th>
              <th className="w-20 text-right">Disc %</th>
              <th className="w-24">GST</th>
              <th className="w-32 text-right">Amount</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={l.key}>
                <td className="pt-4 text-gray-500">{i + 1}</td>
                <td>
                  <Combobox
                    items={items}
                    value={l.name}
                    placeholder="Search or type item name"
                    getKey={(it) => it.id}
                    getLabel={(it) => `${it.name} ${it.code ?? ""} ${it.hsn_sac ?? ""}`}
                    renderOption={(it) => (
                      <div className="flex justify-between gap-3">
                        <span className="font-medium">{it.name}</span>
                        <span className="text-xs text-gray-500">
                          {money(meta.party === "CUSTOMER" ? it.sale_price : it.purchase_price)}
                          {it.type === "GOODS" && ` · ${it.stock} ${it.unit}`}
                        </span>
                      </div>
                    )}
                    onSelect={(it) => pickItem(l.key, it)}
                  />
                  {!l.item_id && (
                    <input
                      className="mt-1 w-full border-0 border-b border-dashed border-gray-200 px-1 py-0.5 text-xs outline-none"
                      placeholder="…or type a custom item name"
                      value={l.name}
                      onChange={(e) => updateLine(l.key, { name: e.target.value })}
                    />
                  )}
                  <input
                    className="mt-1 w-full border-0 px-1 py-0.5 text-xs text-gray-600 outline-none"
                    placeholder="Description (optional)"
                    value={l.description}
                    onChange={(e) => updateLine(l.key, { description: e.target.value })}
                  />
                  {(tracked(l)?.track_batch || l.batch_no) && (
                    <div className="mt-1 flex gap-1">
                      <input className="input !py-1 text-xs" placeholder="Batch no." value={l.batch_no}
                        onChange={(e) => updateLine(l.key, { batch_no: e.target.value })} />
                      <input className="input !py-1 text-xs" type="date" title="Expiry date" value={l.expiry_date}
                        onChange={(e) => updateLine(l.key, { expiry_date: e.target.value })} />
                    </div>
                  )}
                  {(tracked(l)?.track_serial || l.serial_nos) && (
                    <input className="input mt-1 !py-1 text-xs" placeholder="Serial nos. (comma separated)" value={l.serial_nos}
                      onChange={(e) => updateLine(l.key, { serial_nos: e.target.value })} />
                  )}
                </td>
                <td><Input value={l.hsn_sac} maxLength={8} onChange={(e) => updateLine(l.key, { hsn_sac: e.target.value })} /></td>
                <td>
                  <Input className="text-right" inputMode="decimal" value={l.qty} onChange={(e) => updateLine(l.key, { qty: e.target.value })} />
                  <div className="mt-1 text-right text-xs text-gray-500">{l.unit}</div>
                </td>
                <td>
                  <Input className="text-right" inputMode="decimal" value={l.rate} onChange={(e) => updateLine(l.key, { rate: e.target.value })} />
                  {taxApplicable && (
                    <button type="button" className="mt-1 block w-full text-right text-xs text-brand-600" onClick={() => updateLine(l.key, { tax_inclusive: !l.tax_inclusive })}>
                      {l.tax_inclusive ? "incl. tax" : "excl. tax"}
                    </button>
                  )}
                </td>
                <td><Input className="text-right" inputMode="decimal" value={l.discount_pct} placeholder="0" onChange={(e) => updateLine(l.key, { discount_pct: e.target.value })} /></td>
                <td>
                  <Select value={l.gst_rate} onChange={(e) => updateLine(l.key, { gst_rate: Number(e.target.value) })} disabled={!taxApplicable}>
                    {GST_RATES.map((r) => <option key={r} value={r}>{r}%</option>)}
                  </Select>
                </td>
                <td className="num pt-4 font-medium">{money(totals.lines[i]?.total)}</td>
                <td className="pt-3">
                  {lines.length > 1 && (
                    <button type="button" className="text-gray-400 hover:text-red-600" aria-label="Remove line" onClick={() => setLines((ls) => ls.filter((x) => x.key !== l.key))}>
                      <Trash2 size={16} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="p-3">
          <Button type="button" variant="secondary" onClick={() => setLines((ls) => [...ls, blankLine()])}>
            <Plus size={16} /> Add line
          </Button>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="space-y-4 p-5 lg:col-span-3">
          <Field label="Notes"><Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
          {outward && <Field label="Terms & conditions"><Textarea rows={3} value={termsValue} onChange={(e) => setTerms(e.target.value)} /></Field>}
        </Card>
        <Card className="p-5 lg:col-span-2">
          <dl className="space-y-1.5 text-sm">
            <Row label="Sub total" value={totals.sub_total} />
            {totals.discount > 0 && <Row label="Discount" value={-totals.discount} />}
            <Row label="Taxable value" value={totals.taxable} />
            {taxApplicable && (interState ? (
              <Row label="IGST" value={totals.igst} />
            ) : (
              <>
                <Row label="CGST" value={totals.cgst} />
                <Row label="SGST" value={totals.sgst} />
              </>
            ))}
            {totals.cess > 0 && <Row label="Cess" value={totals.cess} />}
            {!isOrder && vtype !== "EXPENSE" && (
              <div className="flex items-center justify-between text-gray-600">
                <label className="flex items-center gap-2">
                  TCS %
                  <input className="input !w-16 !py-0.5 text-right" inputMode="decimal" value={tcsRate} placeholder="0"
                    onChange={(e) => setTcsRate(e.target.value)} />
                </label>
                <span className="tabular-nums">{money(totals.tcs)}</span>
              </div>
            )}
            {reverseCharge && !outward && <p className="text-xs text-amber-800">GST under reverse charge is payable by you, not to the supplier.</p>}
            <div className="flex items-center justify-between text-gray-600">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={roundOff} onChange={(e) => setRoundOff(e.target.checked)} /> Round off
              </label>
              <span className="tabular-nums">{money(totals.round_off)}</span>
            </div>
            <div className="flex justify-between border-t border-gray-200 pt-2 text-base font-semibold text-gray-900">
              <span>Total</span>
              <span className="tabular-nums">{money(totals.grand_total)}</span>
            </div>
          </dl>
          {canPay && (
            <div className="mt-4 space-y-3 border-t border-gray-100 pt-4">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={fullyPaid} onChange={(e) => setFullyPaid(e.target.checked)} />
                {meta.party === "CUSTOMER" ? "Fully received" : "Fully paid"}
              </label>
              <div className="grid grid-cols-2 gap-2">
                <Field label={meta.party === "CUSTOMER" ? (isReturn ? "Refunded now" : "Received now") : isReturn ? "Refund received" : "Paid now"}>
                  <Input inputMode="decimal" disabled={fullyPaid} value={fullyPaid ? String(totals.grand_total) : paid} placeholder="0" onChange={(e) => setPaid(e.target.value)} />
                </Field>
                <Field label="Mode">
                  <Select value={mode} onChange={(e) => setMode(e.target.value as PaymentMode)}>
                    {Object.entries(PAYMENT_MODES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </Select>
                </Field>
              </div>
              <Field label={meta.party === "CUSTOMER" && !isReturn ? "Deposit to" : "Paid from"}>
                <AccountSelect value={accountId} onChange={setAccountId} />
              </Field>
              <div className="flex justify-between text-sm text-gray-600">
                <span>Balance due</span>
                <span className="font-medium tabular-nums">{money(Math.max(totals.grand_total - paidAmount, 0))}</span>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="sticky bottom-0 -mx-4 flex justify-end gap-2 border-t border-gray-200 bg-white/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <Button type="button" variant="secondary" onClick={() => router.back()}>Cancel</Button>
        <Button type="button" variant="secondary" disabled={busy} onClick={() => save(false)}>Save</Button>
        <Button type="button" disabled={busy} onClick={() => save(true)}>{busy ? "Saving…" : "Save & Print"}</Button>
      </div>

      {quickParty !== null && (
        <QuickPartyDialog
          type={meta.party}
          initialName={quickParty}
          onClose={() => setQuickParty(null)}
          onCreated={(p) => {
            setParties([...parties, p].sort((a, b) => a.name.localeCompare(b.name)));
            setPartyId(p.id);
            setQuickParty(null);
          }}
        />
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between text-gray-600">
      <dt>{label}</dt>
      <dd className="tabular-nums">{money(value)}</dd>
    </div>
  );
}
