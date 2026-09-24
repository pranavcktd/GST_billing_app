"use client";

import { MessageCircle, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, LinkButton, Loading, PageHeader } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { stateLabel } from "@/lib/constants";
import { downloadCsv, fmtDate, fyRange, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Party } from "@/lib/types";

interface Ledger {
  party: Party;
  opening: number;
  closing: number;
  entries: { date: string; kind: string; number: string; ref_id: string; ref_type: string; debit: number; credit: number; balance: number }[];
}

const balText = (n: number) => `${money(Math.abs(n))} ${n > 0 ? "Dr" : n < 0 ? "Cr" : ""}`;

export default function PartyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [range, setRange] = useState(fyRange());
  const { data: party, error } = useFetch<Party>(`/parties/${id}`);
  const { data: ledger } = useFetch<Ledger>(`/parties/${id}/ledger${qs({ date_from: range.from, date_to: range.to })}`);

  if (error) return <ErrorBox message={error} />;
  if (!party) return <Loading />;

  const reminder = () => {
    const phone = (party.phone ?? "").replace(/\D/g, "").slice(-10);
    const text = `Dear ${party.name}, a payment of ${money(party.balance)} is pending. Kindly clear it at the earliest. Thank you.`;
    window.open(`https://wa.me/${phone ? "91" + phone : ""}?text=${encodeURIComponent(text)}`, "_blank");
  };

  const remove = async () => {
    if (!confirm("Delete this party? Parties with transactions are only deactivated.")) return;
    await api(`/parties/${id}`, { method: "DELETE" });
    router.push("/parties");
  };

  return (
    <>
      <PageHeader
        title={party.name}
        sub={[party.gstin && `GSTIN ${party.gstin}`, stateLabel(party.state_code), party.phone].filter(Boolean).join(" · ")}
        actions={
          <>
            {party.balance > 0 && (
              <Button variant="secondary" onClick={reminder}><MessageCircle size={16} /> Payment reminder</Button>
            )}
            <LinkButton href={`/parties/${id}/edit`} variant="secondary"><Pencil size={16} /> Edit</LinkButton>
            <Button variant="danger" onClick={remove}><Trash2 size={16} /></Button>
          </>
        }
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Card className="p-4">
          <div className="text-xs text-gray-500">Current balance</div>
          <div className={`mt-1 text-xl font-semibold ${party.balance > 0 ? "text-emerald-700" : party.balance < 0 ? "text-red-700" : "text-gray-900"}`}>
            {money(Math.abs(party.balance))}
          </div>
          <div className="text-xs text-gray-500">{party.balance > 0 ? "To collect" : party.balance < 0 ? "To pay" : "Settled"}</div>
        </Card>
        <Card className="flex flex-wrap items-center gap-2 p-4 sm:col-span-2">
          <LinkButton href={`/v/sales/new?party=${id}`} variant="secondary">New sale</LinkButton>
          <LinkButton href={`/v/purchases/new?party=${id}`} variant="secondary">New purchase</LinkButton>
          <LinkButton href={`/payments/in/new?party=${id}`} variant="secondary">Receive payment</LinkButton>
          <LinkButton href={`/payments/out/new?party=${id}`} variant="secondary">Make payment</LinkButton>
        </Card>
      </div>

      <Card className="overflow-x-auto">
        <div className="flex flex-wrap items-end justify-between gap-3 px-5 pt-4 pb-3">
          <h2 className="font-semibold text-gray-900">Ledger statement</h2>
          <div className="flex flex-wrap items-end gap-2">
            <Field label="From"><Input type="date" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} /></Field>
            <Field label="To"><Input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} /></Field>
            {ledger && (
              <Button
                variant="secondary"
                onClick={() =>
                  downloadCsv(`ledger-${party.name}.csv`, ["Date", "Type", "Number", "Debit", "Credit", "Balance"], [
                    [range.from, "Opening balance", "", "", "", ledger.opening],
                    ...ledger.entries.map((e) => [e.date, e.kind, e.number, e.debit || "", e.credit || "", e.balance]),
                  ])
                }
              >
                Export
              </Button>
            )}
          </div>
        </div>
        {!ledger ? (
          <Loading />
        ) : (
          <table className="tbl">
            <thead>
              <tr><th>Date</th><th>Type</th><th>Number</th><th className="num">Debit</th><th className="num">Credit</th><th className="num">Balance</th></tr>
            </thead>
            <tbody>
              <tr className="bg-gray-50">
                <td>{fmtDate(range.from)}</td><td colSpan={4} className="text-gray-600">Opening balance</td>
                <td className="num">{balText(ledger.opening)}</td>
              </tr>
              {ledger.entries.map((e, i) => (
                <tr key={i}>
                  <td>{fmtDate(e.date)}</td>
                  <td>{e.kind}</td>
                  <td>
                    {e.ref_type === "voucher" ? (
                      <Link href={`/doc/${e.ref_id}`} className="text-brand-600 hover:underline">{e.number}</Link>
                    ) : (
                      e.number
                    )}
                  </td>
                  <td className="num">{e.debit ? money(e.debit) : ""}</td>
                  <td className="num">{e.credit ? money(e.credit) : ""}</td>
                  <td className="num">{balText(e.balance)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr><td colSpan={5}>Closing balance</td><td className="num">{balText(ledger.closing)}</td></tr>
            </tfoot>
          </table>
        )}
      </Card>
    </>
  );
}
