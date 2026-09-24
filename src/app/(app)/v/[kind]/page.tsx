"use client";

import { Download, Plus } from "lucide-react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { useState } from "react";
import { ImportButton } from "@/components/ImportDialog";
import { Button, Card, Empty, ErrorBox, Field, Input, LinkButton, Loading, PageHeader, Select, StatusBadge } from "@/components/ui";
import { qs } from "@/lib/api";
import { IMPORT_ENTITY, KINDS, type Kind, NON_LEDGER } from "@/lib/constants";
import { downloadCsv, fmtDate, fyRange, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Voucher } from "@/lib/types";

export default function VoucherListPage() {
  const { kind } = useParams<{ kind: string }>();
  if (!(kind in KINDS)) notFound();
  const meta = KINDS[kind as Kind];
  const isEstimate = NON_LEDGER.includes(meta.type);

  const [range, setRange] = useState(fyRange());
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useFetch<Voucher[]>(
    `/vouchers${qs({ type: meta.type, date_from: range.from, date_to: range.to, search, status, limit: 1000 })}`,
  );

  const live = data?.filter((v) => !v.cancelled) ?? [];
  const total = live.reduce((s, v) => s + v.grand_total, 0);
  const balance = live.reduce((s, v) => s + v.balance, 0);

  const exportCsv = () =>
    data &&
    downloadCsv(`${kind}-${range.from}-to-${range.to}.csv`,
      ["Date", "Number", "Party", "GSTIN", "Taxable", "CGST", "SGST", "IGST", "Cess", "Total", "Paid", "Balance", "Status"],
      data.map((v) => [v.date, v.number, v.party_name, v.party_gstin, v.taxable, v.cgst, v.sgst, v.igst, v.cess, v.grand_total, v.paid, v.balance, v.status]));

  return (
    <>
      <PageHeader
        title={meta.plural}
        sub={`${live.length} documents · Total ${money(total)}${isEstimate ? "" : ` · Unpaid ${money(balance)}`}`}
        actions={
          <>
            <ImportButton entity={IMPORT_ENTITY[kind as Kind]} title={meta.plural} onDone={reload} />
            <Button variant="secondary" onClick={exportCsv}><Download size={16} /> Export</Button>
            <LinkButton href={`/v/${kind}/new`}><Plus size={16} /> New {meta.label}</LinkButton>
          </>
        }
      />
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <Field label="From"><Input type="date" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} /></Field>
        <Field label="To"><Input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} /></Field>
        <Field label="Search"><Input placeholder="Number or party" value={search} onChange={(e) => setSearch(e.target.value)} /></Field>
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            {(isEstimate ? ["OPEN", "CONVERTED", "CANCELLED"] : ["UNPAID", "PARTIAL", "OVERDUE", "PAID", "CANCELLED"]).map((s) => (
              <option key={s} value={s}>{s.charAt(0) + s.slice(1).toLowerCase()}</option>
            ))}
          </Select>
        </Field>
      </div>
      <ErrorBox message={error} />
      <Card className="overflow-x-auto">
        {loading && !data ? (
          <Loading />
        ) : !data?.length ? (
          <Empty title={`No ${meta.plural.toLowerCase()} in this period`} action={<LinkButton href={`/v/${kind}/new`}>Create {meta.label.toLowerCase()}</LinkButton>} />
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>Date</th><th>Number</th><th>Party</th>
                <th className="num">Total</th>{!isEstimate && <th className="num">Balance</th>}<th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((v) => (
                <tr key={v.id} className={v.cancelled ? "text-gray-400" : ""}>
                  <td className="whitespace-nowrap">{fmtDate(v.date)}</td>
                  <td><Link href={`/v/${kind}/${v.id}`} className="font-medium text-brand-600 hover:underline">{v.number}</Link></td>
                  <td>
                    {v.party_name}
                    {v.party_gstin && <div className="font-mono text-xs text-gray-500">{v.party_gstin}</div>}
                  </td>
                  <td className="num">{money(v.grand_total)}</td>
                  {!isEstimate && <td className="num">{money(v.balance)}</td>}
                  <td><StatusBadge status={v.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
