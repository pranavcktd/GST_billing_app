"use client";

import { ArrowLeftRight, Banknote, Landmark, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { downloadCsv, fmtDate, fyRange, money, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Account } from "@/lib/types";

interface Statement {
  opening: number; closing: number;
  entries: { date: string; kind: string; number: string; party: string | null; note: string | null; ref_type: string; ref_id: string;
    deposit: number; withdrawal: number; balance: number }[];
}

type Draft = { id?: string; type: "CASH" | "BANK"; name: string; bank_name: string; account_no: string; ifsc: string; opening_balance: string; opening_date: string };
const blank: Draft = { type: "BANK", name: "", bank_name: "", account_no: "", ifsc: "", opening_balance: "", opening_date: today() };

export default function CashBankPage() {
  const { data: accounts, error, reload } = useFetch<Account[]>("/accounts");
  const [selected, setSelected] = useState<string | null>(null);
  const [range, setRange] = useState(fyRange());
  const [draft, setDraft] = useState<Draft | null>(null);
  const [transfer, setTransfer] = useState<{ from: string; to: string; amount: string; date: string; note: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const current = accounts?.find((a) => a.id === (selected ?? accounts?.[0]?.id));
  const { data: st } = useFetch<Statement>(current ? `/accounts/${current.id}/statement${qs({ date_from: range.from, date_to: range.to })}` : null);

  if (!accounts) return error ? <ErrorBox message={error} /> : <Loading />;
  const active = accounts.filter((a) => a.is_active);
  const total = active.reduce((s, a) => s + a.balance, 0);

  async function saveAccount(e: React.FormEvent) {
    e.preventDefault();
    if (!draft) return;
    setFormError(null);
    try {
      const body = { ...draft, opening_balance: Number(draft.opening_balance || 0), opening_date: draft.opening_date || null,
        bank_name: draft.bank_name || null, account_no: draft.account_no || null, ifsc: draft.ifsc || null };
      await api(draft.id ? `/accounts/${draft.id}` : "/accounts", { method: draft.id ? "PUT" : "POST", body });
      setDraft(null);
      reload();
    } catch (err) {
      setFormError((err as Error).message);
    }
  }

  async function saveTransfer(e: React.FormEvent) {
    e.preventDefault();
    if (!transfer) return;
    setFormError(null);
    try {
      await api("/transfers", { body: { from_account_id: transfer.from, to_account_id: transfer.to, amount: Number(transfer.amount),
        date: transfer.date, note: transfer.note || null } });
      setTransfer(null);
      reload();
    } catch (err) {
      setFormError((err as Error).message);
    }
  }

  async function remove(a: Account) {
    if (!confirm(`Delete ${a.name}? Accounts with transactions are only deactivated.`)) return;
    await api(`/accounts/${a.id}`, { method: "DELETE" });
    setSelected(null);
    reload();
  }

  return (
    <>
      <PageHeader
        title="Cash & Bank"
        sub={`Total balance ${money(total)}`}
        actions={
          <>
            <Link href="/cash-bank/cheques" className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-3.5 py-2 text-sm font-medium hover:bg-gray-50">Cheques</Link>
            <Button variant="secondary" onClick={() => { setFormError(null); setTransfer({ from: active[0]?.id ?? "", to: active[1]?.id ?? "", amount: "", date: today(), note: "" }); }}>
              <ArrowLeftRight size={16} /> Transfer / deposit
            </Button>
            <Button onClick={() => { setFormError(null); setDraft(blank); }}><Plus size={16} /> Add bank account</Button>
          </>
        }
      />
      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {active.map((a) => (
          <button key={a.id} onClick={() => setSelected(a.id)} className="text-left">
            <Card className={`h-full p-4 ${current?.id === a.id ? "border-brand-500 ring-2 ring-brand-100" : ""}`}>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                {a.type === "CASH" ? <Banknote size={14} /> : <Landmark size={14} />}
                {a.type === "CASH" ? "Cash" : a.bank_name || "Bank"}{a.account_no ? ` · …${a.account_no.slice(-4)}` : ""}
              </div>
              <div className="mt-1 font-medium text-gray-900">{a.name}</div>
              <div className={`mt-1 text-lg font-semibold tabular-nums ${a.balance < 0 ? "text-red-700" : ""}`}>{money(a.balance)}</div>
            </Card>
          </button>
        ))}
      </div>

      {current && (
        <Card className="overflow-x-auto">
          <div className="flex flex-wrap items-end justify-between gap-3 px-5 pt-4 pb-3">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-gray-900">{current.name} — statement</h2>
              <button className="text-gray-400 hover:text-gray-700" aria-label="Edit account"
                onClick={() => setDraft({ id: current.id, type: current.type, name: current.name, bank_name: current.bank_name ?? "",
                  account_no: current.account_no ?? "", ifsc: current.ifsc ?? "", opening_balance: String(current.opening_balance),
                  opening_date: current.opening_date ?? "" })}>
                <Pencil size={15} />
              </button>
              {!current.is_default_cash && (
                <button className="text-gray-400 hover:text-red-600" aria-label="Delete account" onClick={() => remove(current)}><Trash2 size={15} /></button>
              )}
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <Field label="From"><Input type="date" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} /></Field>
              <Field label="To"><Input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} /></Field>
              {st && (
                <Button variant="secondary" onClick={() => downloadCsv(`${current.name}-statement.csv`, ["Date", "Type", "Ref", "Party / note", "In", "Out", "Balance"],
                  st.entries.map((e) => [e.date, e.kind, e.number, e.party ?? e.note, e.deposit || "", e.withdrawal || "", e.balance]))}>Export</Button>
              )}
            </div>
          </div>
          {!st ? <Loading /> : (
            <table className="tbl">
              <thead><tr><th>Date</th><th>Type</th><th>Ref</th><th>Party / note</th><th className="num">Money in</th><th className="num">Money out</th><th className="num">Balance</th></tr></thead>
              <tbody>
                <tr className="bg-gray-50"><td>{fmtDate(range.from)}</td><td colSpan={5} className="text-gray-600">Opening balance</td><td className="num">{money(st.opening)}</td></tr>
                {st.entries.map((e, i) => (
                  <tr key={i}>
                    <td>{fmtDate(e.date)}</td><td>{e.kind}</td><td>{e.number}</td><td>{e.party ?? e.note ?? ""}</td>
                    <td className="num text-emerald-700">{e.deposit ? money(e.deposit) : ""}</td>
                    <td className="num text-red-700">{e.withdrawal ? money(e.withdrawal) : ""}</td>
                    <td className="num">{money(e.balance)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot><tr><td colSpan={6}>Closing balance</td><td className="num">{money(st.closing)}</td></tr></tfoot>
            </table>
          )}
        </Card>
      )}

      {draft && (
        <Modal title={draft.id ? "Edit account" : "Add bank account"} onClose={() => setDraft(null)}>
          <form onSubmit={saveAccount} className="space-y-3">
            <ErrorBox message={formError} />
            {!draft.id && (
              <Field label="Type">
                <Select value={draft.type} onChange={(e) => setDraft({ ...draft, type: e.target.value as "CASH" | "BANK" })}>
                  <option value="BANK">Bank account</option>
                  <option value="CASH">Cash (e.g. petty cash, second counter)</option>
                </Select>
              </Field>
            )}
            <Field label="Display name" required><Input required value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="HDFC Current A/c" /></Field>
            {draft.type === "BANK" && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="Bank name"><Input value={draft.bank_name} onChange={(e) => setDraft({ ...draft, bank_name: e.target.value })} /></Field>
                <Field label="IFSC"><Input value={draft.ifsc} maxLength={11} className="uppercase" onChange={(e) => setDraft({ ...draft, ifsc: e.target.value.toUpperCase() })} /></Field>
                <Field label="Account no." className="col-span-2"><Input value={draft.account_no} onChange={(e) => setDraft({ ...draft, account_no: e.target.value })} /></Field>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Opening balance"><Input type="number" step="0.01" value={draft.opening_balance} onChange={(e) => setDraft({ ...draft, opening_balance: e.target.value })} /></Field>
              <Field label="As of"><Input type="date" value={draft.opening_date} onChange={(e) => setDraft({ ...draft, opening_date: e.target.value })} /></Field>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="secondary" onClick={() => setDraft(null)}>Cancel</Button>
              <Button type="submit">Save</Button>
            </div>
          </form>
        </Modal>
      )}

      {transfer && (
        <Modal title="Transfer money" onClose={() => setTransfer(null)}>
          <form onSubmit={saveTransfer} className="space-y-3">
            <ErrorBox message={formError} />
            <p className="text-xs text-gray-500">Cash deposit to bank, cash withdrawal, or bank-to-bank transfer.</p>
            <div className="grid grid-cols-2 gap-3">
              <Field label="From">
                <Select value={transfer.from} onChange={(e) => setTransfer({ ...transfer, from: e.target.value })}>
                  {active.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </Select>
              </Field>
              <Field label="To">
                <Select value={transfer.to} onChange={(e) => setTransfer({ ...transfer, to: e.target.value })}>
                  {active.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </Select>
              </Field>
              <Field label="Amount" required><Input type="number" min="0.01" step="0.01" required value={transfer.amount} onChange={(e) => setTransfer({ ...transfer, amount: e.target.value })} /></Field>
              <Field label="Date"><Input type="date" value={transfer.date} onChange={(e) => setTransfer({ ...transfer, date: e.target.value })} /></Field>
            </div>
            <Field label="Note"><Input value={transfer.note} onChange={(e) => setTransfer({ ...transfer, note: e.target.value })} /></Field>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="secondary" onClick={() => setTransfer(null)}>Cancel</Button>
              <Button type="submit">Transfer</Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
