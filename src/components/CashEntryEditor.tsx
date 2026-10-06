"use client";

import { useState } from "react";
import { AccountSelect } from "@/components/AccountSelect";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Account } from "@/lib/types";

/**
 * Edit or delete a money entry entered by mistake: a transfer, a capital / drawings entry, a tax challan or a
 * loan entry. Used from the Cash & Bank statement and from each entry's own page.
 */
export type CashEntryKind = "transfer" | "capital" | "tax" | "loan";

type Rec = Record<string, string | number | null>;
const SOURCE: Record<CashEntryKind, (loanId?: string) => string> = {
  transfer: () => "/transfers", capital: () => "/capital", tax: () => "/tax-payments", loan: (l) => `/loans/${l}`,
};
const PATH: Record<CashEntryKind, (id: string, loanId?: string) => string> = {
  transfer: (id) => `/transfers/${id}`, capital: (id) => `/capital/${id}`, tax: (id) => `/tax-payments/${id}`,
  loan: (id, l) => `/loans/${l}/txns/${id}`,
};
const TITLE: Record<CashEntryKind, string> = { transfer: "transfer", capital: "capital entry", tax: "tax payment", loan: "loan entry" };

export function CashEntryEditor({ kind, id, loanId, onClose, onSaved }: {
  kind: CashEntryKind; id: string; loanId?: string; onClose: () => void; onSaved: () => void;
}) {
  const { data, error } = useFetch<Rec[] | { entries: Rec[] }>(SOURCE[kind](loanId));
  const list = Array.isArray(data) ? data : data?.entries;
  const rec = list?.find((r) => r.id === id);
  return (
    <Modal title={`Edit ${TITLE[kind]}`} onClose={onClose}>
      {error ? <ErrorBox message={error} /> : !list ? <Loading /> : !rec ? <ErrorBox message="This entry no longer exists." /> : (
        <EntryForm kind={kind} rec={rec} path={PATH[kind](id, loanId)} onClose={onClose} onSaved={onSaved} />
      )}
    </Modal>
  );
}

const str = (v: unknown) => (v === null || v === undefined ? "" : String(v));

function EntryForm({ kind, rec, path, onClose, onSaved }: { kind: CashEntryKind; rec: Rec; path: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState<Record<string, string>>(() => Object.fromEntries(Object.entries(rec).map(([k, v]) => [k, str(v)])));
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: accounts } = useFetch<Account[]>(kind === "transfer" ? "/accounts" : null);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const num = (k: string) => Number(f[k] || 0);
  const opt = (k: string) => f[k] || null;

  function body() {
    if (kind === "transfer") return { date: f.date, from_account_id: f.from_account_id, to_account_id: f.to_account_id, amount: num("amount"), note: opt("note") };
    if (kind === "capital") return { date: f.date, type: f.type, amount: num("amount"), account_id: opt("account_id"), note: opt("note") };
    if (kind === "tax") return { date: f.date, type: f.type, amount: num("amount"), account_id: opt("account_id"), reference: opt("reference"), period: opt("period"), note: opt("note") };
    return { date: f.date, type: f.type, principal: num("principal"), interest: num("interest"), account_id: opt("account_id"), note: opt("note") };
  }

  async function run(method: "PUT" | "DELETE") {
    if (method === "DELETE" && !confirm("Delete this entry? Balances will be recalculated.")) return;
    setBusy(true); setErr(null);
    try {
      await api(path, method === "PUT" ? { method, body: body() } : { method });
      onSaved();
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const active = accounts?.filter((a) => a.is_active) ?? [];
  return (
    <form onSubmit={(e) => { e.preventDefault(); run("PUT"); }} className="space-y-3">
      <ErrorBox message={err} />
      {kind === "transfer" && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="From"><Select value={f.from_account_id} onChange={set("from_account_id")}>{active.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</Select></Field>
          <Field label="To"><Select value={f.to_account_id} onChange={set("to_account_id")}>{active.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</Select></Field>
        </div>
      )}
      {kind === "capital" && (
        <Field label="Type">
          <Select value={f.type} onChange={set("type")}>
            <option value="INTRODUCED">Capital introduced</option><option value="DRAWINGS">Drawings</option>
          </Select>
        </Field>
      )}
      {kind === "tax" && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Tax"><Select value={f.type} onChange={set("type")}><option>GST</option><option>TDS</option><option>TCS</option></Select></Field>
          <Field label="Period"><Input value={f.period} onChange={set("period")} /></Field>
        </div>
      )}
      {kind === "loan" && (
        <Field label="Type">
          <Select value={f.type} onChange={set("type")}>
            <option value="EMI">EMI / repayment</option><option value="DISBURSEMENT">Loan amount received</option><option value="CHARGES">Processing fee / charges</option>
          </Select>
        </Field>
      )}
      <div className="grid grid-cols-2 gap-3">
        {kind === "loan" ? (
          <>
            {f.type !== "CHARGES" && <Field label={f.type === "EMI" ? "Principal part" : "Amount received"}><Input type="number" step="0.01" min="0" value={f.principal} onChange={set("principal")} /></Field>}
            {f.type !== "DISBURSEMENT" && <Field label={f.type === "EMI" ? "Interest part" : "Charges"}><Input type="number" step="0.01" min="0" value={f.interest} onChange={set("interest")} /></Field>}
          </>
        ) : (
          <Field label="Amount" required><Input type="number" min="0.01" step="0.01" required value={f.amount} onChange={set("amount")} /></Field>
        )}
        <Field label="Date"><Input type="date" required value={f.date} onChange={set("date")} /></Field>
      </div>
      {kind !== "transfer" && <Field label="Account"><AccountSelect value={f.account_id} onChange={(v) => setF({ ...f, account_id: v })} /></Field>}
      {kind === "tax" && <Field label="CIN / challan no."><Input value={f.reference} onChange={set("reference")} /></Field>}
      <Field label="Note"><Input value={f.note} onChange={set("note")} /></Field>
      <div className="flex justify-between gap-2 pt-2">
        <Button type="button" variant="danger" disabled={busy} onClick={() => run("DELETE")}>Delete</Button>
        <div className="flex gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Update"}</Button>
        </div>
      </div>
    </form>
  );
}
