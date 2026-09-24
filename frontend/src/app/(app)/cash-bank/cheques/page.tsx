"use client";

import Link from "next/link";
import { useState } from "react";
import { AccountSelect } from "@/components/AccountSelect";
import { Modal } from "@/components/Modal";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { fmtDate, money, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Payment } from "@/lib/types";

const TABS = [
  { key: "OPEN", label: "Open" },
  { key: "CLEARED", label: "Cleared" },
  { key: "BOUNCED", label: "Bounced" },
] as const;

export default function ChequesPage() {
  const [tab, setTab] = useState<"OPEN" | "CLEARED" | "BOUNCED">("OPEN");
  const { data, error, reload } = useFetch<Payment[]>(`/cheques${qs({ status: tab })}`);
  const [clearing, setClearing] = useState<Payment | null>(null);
  const [clearDate, setClearDate] = useState(today());
  const [clearAccount, setClearAccount] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  async function act(p: Payment, action: "clear" | "bounce" | "reopen", extra: Record<string, unknown> = {}) {
    setActionError(null);
    try {
      await api(`/cheques/${p.id}`, { body: { action, ...extra } });
      setClearing(null);
      reload();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  const received = data?.filter((p) => p.type === "IN").reduce((s, p) => s + p.amount, 0) ?? 0;
  const issued = data?.filter((p) => p.type === "OUT").reduce((s, p) => s + p.amount, 0) ?? 0;

  return (
    <>
      <PageHeader title="Cheques" sub="Cheques reduce what the party owes immediately, and reach your bank balance once cleared." />
      <div className="mb-4 flex gap-1 rounded-lg border border-gray-200 bg-white p-1 text-sm w-fit">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`rounded-md px-4 py-1.5 ${tab === t.key ? "bg-brand-600 text-white" : "text-gray-700"}`}>{t.label}</button>
        ))}
      </div>
      <ErrorBox message={error ?? actionError} />
      {tab === "OPEN" && data && (
        <p className="mb-3 text-sm text-gray-600">Received, not yet cleared: <b>{money(received)}</b> · Issued, not yet cleared: <b>{money(issued)}</b></p>
      )}
      <Card className="overflow-x-auto">
        {!data ? <Loading /> : data.length === 0 ? <Empty title={`No ${tab.toLowerCase()} cheques`} /> : (
          <table className="tbl">
            <thead><tr><th>Date</th><th>Cheque no.</th><th>Party</th><th>Direction</th><th>Account</th><th className="num">Amount</th><th>{tab === "CLEARED" ? "Cleared on" : ""}</th><th /></tr></thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}>
                  <td>{fmtDate(p.cheque_date ?? p.date)}</td>
                  <td className="font-medium">{p.reference ?? p.number}</td>
                  <td>{p.party_id ? <Link href={`/parties/${p.party_id}`} className="text-brand-600 hover:underline">{p.party_name}</Link> : ""}</td>
                  <td>{p.type === "IN" ? "Received" : "Issued"}</td>
                  <td>{p.account_name}</td>
                  <td className="num">{money(p.amount)}</td>
                  <td>{p.cleared_on ? fmtDate(p.cleared_on) : ""}</td>
                  <td className="whitespace-nowrap text-right">
                    {tab === "OPEN" && (
                      <>
                        <Button variant="secondary" className="!py-1" onClick={() => { setClearing(p); setClearAccount(p.account_id); setClearDate(today()); }}>Mark cleared</Button>{" "}
                        <Button variant="danger" className="!py-1" onClick={() => confirm("Mark this cheque as bounced? The bills it paid become due again.") && act(p, "bounce")}>Bounced</Button>
                      </>
                    )}
                    {tab === "CLEARED" && <Button variant="ghost" className="!py-1" onClick={() => act(p, "reopen")}>Undo</Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {clearing && (
        <Modal title={`Clear cheque ${clearing.reference ?? ""}`} onClose={() => setClearing(null)}>
          <div className="space-y-3">
            <Field label="Cleared on"><Input type="date" value={clearDate} onChange={(e) => setClearDate(e.target.value)} /></Field>
            <Field label={clearing.type === "IN" ? "Deposited in" : "Paid from"}><AccountSelect value={clearAccount} onChange={setClearAccount} /></Field>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setClearing(null)}>Cancel</Button>
              <Button onClick={() => act(clearing, "clear", { date: clearDate, account_id: clearAccount || null })}>Mark cleared</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
