"use client";

import { notFound, useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AccountSelect } from "@/components/AccountSelect";
import { Button, Card, Combobox, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { PAYMENT_MODES } from "@/lib/constants";
import { fmtDate, money, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Party, PaymentMode, Voucher } from "@/lib/types";

function PaymentForm({ type }: { type: "IN" | "OUT" }) {
  const sp = useSearchParams();
  const router = useRouter();
  const { data: parties } = useFetch<Party[]>("/parties");
  const [partyId, setPartyId] = useState<string | null>(sp.get("party"));
  const [voucherId, setVoucherId] = useState<string>(sp.get("voucher") ?? "");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const [mode, setMode] = useState<PaymentMode>(type === "IN" ? "CASH" : "BANK");
  const [reference, setReference] = useState("");
  const [tds, setTds] = useState("");
  const [accountId, setAccountId] = useState("");
  const [chequeDate, setChequeDate] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: bills } = useFetch<(Voucher & { due: number })[]>(
    partyId ? `/payments/open-bills${qs({ party_id: partyId, type })}` : null,
  );

  if (!parties) return <Loading />;
  const party = parties.find((p) => p.id === partyId);
  const totalDue = bills?.reduce((s, b) => s + b.due, 0) ?? 0;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!partyId) return setError("Select a party");
    setBusy(true);
    setError(null);
    try {
      await api("/payments", {
        body: {
          type, date, party_id: partyId, amount: Math.round(Number(amount || 0) * 100) / 100,
          tds_amount: Math.round(Number(tds || 0) * 100) / 100, account_id: accountId || null, mode,
          cheque_date: mode === "CHEQUE" && chequeDate ? chequeDate : null,
          reference: reference || null, notes: notes || null, voucher_id: voucherId || null, auto_allocate: true,
        },
      });
      router.push(`/parties/${partyId}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="grid gap-5 lg:grid-cols-5">
      <Card className="space-y-4 p-5 lg:col-span-3">
        <ErrorBox message={error} />
        <Field label="Party" required>
          <Combobox
            items={parties}
            value={party?.name ?? ""}
            placeholder="Search party"
            getKey={(p) => p.id}
            getLabel={(p) => `${p.name} ${p.phone ?? ""}`}
            renderOption={(p) => (
              <div className="flex justify-between"><span>{p.name}</span><span className="text-xs text-gray-500">{money(Math.abs(p.balance))} {p.balance > 0 ? "to collect" : p.balance < 0 ? "to pay" : ""}</span></div>
            )}
            onSelect={(p) => { setPartyId(p.id); setVoucherId(""); }}
          />
        </Field>
        {party && (
          <p className="text-sm text-gray-600">
            Balance: <b className={party.balance > 0 ? "text-emerald-700" : party.balance < 0 ? "text-red-700" : ""}>{money(Math.abs(party.balance))}</b>{" "}
            {party.balance > 0 ? "to collect" : party.balance < 0 ? "to pay" : ""}
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Amount (₹)" required hint="Money actually received / paid">
            <Input type="number" min="0" step="0.01" required value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
          </Field>
          <Field label="TDS deducted (₹)" hint={type === "IN" ? "Deducted by the customer" : "Deducted by you (payable to govt.)"}>
            <Input type="number" min="0" step="0.01" value={tds} onChange={(e) => setTds(e.target.value)} />
          </Field>
          <Field label="Date"><Input type="date" required value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          <Field label="Mode">
            <Select value={mode} onChange={(e) => setMode(e.target.value as PaymentMode)}>
              {Object.entries(PAYMENT_MODES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </Field>
          <Field label={type === "IN" ? "Deposit to" : "Paid from"}>
            <AccountSelect value={accountId} onChange={setAccountId} />
          </Field>
          <Field label={mode === "CHEQUE" ? "Cheque no." : "Reference"} hint={mode === "CHEQUE" ? undefined : "UTR / transaction id"}>
            <Input value={reference} onChange={(e) => setReference(e.target.value)} />
          </Field>
          {mode === "CHEQUE" && (
            <Field label="Cheque date" hint="Counts in the bank balance once you mark it cleared">
              <Input type="date" value={chequeDate} onChange={(e) => setChequeDate(e.target.value)} />
            </Field>
          )}
        </div>
        <Field label="Notes"><Input value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={() => router.back()}>Cancel</Button>
          <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save payment"}</Button>
        </div>
      </Card>
      <Card className="p-5 lg:col-span-2">
        <h2 className="mb-1 font-semibold text-gray-900">Open bills</h2>
        <p className="mb-3 text-xs text-gray-500">
          The payment settles the selected bill first, then the oldest unpaid bills. Any extra is kept as an advance.
        </p>
        {!partyId ? (
          <p className="text-sm text-gray-500">Select a party to see unpaid bills.</p>
        ) : !bills ? (
          <Loading />
        ) : bills.length === 0 ? (
          <p className="text-sm text-gray-500">No unpaid bills.</p>
        ) : (
          <>
            <ul className="divide-y divide-gray-100 text-sm">
              {bills.map((b) => (
                <li key={b.id}>
                  <label className="flex cursor-pointer items-center justify-between gap-2 py-2">
                    <span className="flex items-center gap-2">
                      <input type="radio" name="bill" checked={voucherId === b.id} onChange={() => { setVoucherId(b.id); if (!amount) setAmount(String(b.due)); }} />
                      <span>
                        <span className="font-medium">{b.number}</span>
                        <span className="ml-2 text-xs text-gray-500">{fmtDate(b.date)}</span>
                      </span>
                    </span>
                    <span className="tabular-nums">{money(b.due)}</span>
                  </label>
                </li>
              ))}
            </ul>
            <div className="mt-2 flex justify-between border-t border-gray-200 pt-2 text-sm font-semibold">
              <span>Total due</span>
              <button type="button" className="text-brand-600 hover:underline" onClick={() => setAmount(String(Math.round(totalDue * 100) / 100))}>{money(totalDue)}</button>
            </div>
          </>
        )}
      </Card>
    </form>
  );
}

export default function NewPaymentPage() {
  const { dir } = useParams<{ dir: string }>();
  if (dir !== "in" && dir !== "out") notFound();
  const type = dir === "in" ? "IN" : "OUT";
  return (
    <>
      <PageHeader title={type === "IN" ? "Receive payment" : "Make payment"} />
      <Suspense fallback={<Loading />}>
        <PaymentForm type={type} />
      </Suspense>
    </>
  );
}
