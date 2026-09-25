"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { GstinBadge, gstinStatuses, type GstinStatus } from "@/components/GstinVerify";
import { ImportButton } from "@/components/ImportDialog";
import { Card, Empty, ErrorBox, Input, LinkButton, Loading, PageHeader, Select } from "@/components/ui";
import { qs } from "@/lib/api";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Party } from "@/lib/types";

export default function PartiesPage() {
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const { data, error, loading, reload } = useFetch<Party[]>(`/parties${qs({ search, type })}`);

  const [verified, setVerified] = useState<Record<string, GstinStatus>>({});
  useEffect(() => {
    const gstins = (data ?? []).map((p) => p.gstin).filter((g): g is string => !!g);
    if (gstins.length) gstinStatuses(gstins).then(setVerified).catch(() => {});
  }, [data]);

  const receivable = data?.filter((p) => p.balance > 0).reduce((s, p) => s + p.balance, 0) ?? 0;
  const payable = data?.filter((p) => p.balance < 0).reduce((s, p) => s - p.balance, 0) ?? 0;

  return (
    <>
      <PageHeader
        title="Parties"
        sub={`To collect ${money(receivable)} · To pay ${money(payable)}`}
        actions={
          <>
            <ImportButton entity="parties" title="parties" onDone={reload} />
            <LinkButton href="/parties/new"><Plus size={16} /> Add party</LinkButton>
          </>
        }
      />
      <div className="mb-3 flex flex-wrap gap-2">
        <Input placeholder="Search name, phone or GSTIN" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
        <Select value={type} onChange={(e) => setType(e.target.value)} className="max-w-44">
          <option value="">All parties</option>
          <option value="CUSTOMER">Customers</option>
          <option value="SUPPLIER">Suppliers</option>
        </Select>
      </div>
      <ErrorBox message={error} />
      <Card className="overflow-x-auto">
        {loading && !data ? (
          <Loading />
        ) : !data?.length ? (
          <Empty title="No parties yet" action={<LinkButton href="/parties/new">Add your first party</LinkButton>} />
        ) : (
          <table className="tbl">
            <thead>
              <tr><th>Name</th><th>GSTIN</th><th>Phone</th><th>Type</th><th className="num">Balance</th></tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}>
                  <td><Link href={`/parties/${p.id}`} className="font-medium text-brand-600 hover:underline">{p.name}</Link></td>
                  <td className="font-mono text-xs">{p.gstin ?? "—"}{p.gstin && <div><GstinBadge s={verified[p.gstin]} /></div>}</td>
                  <td>{p.phone ?? "—"}</td>
                  <td className="text-gray-600">{p.type === "BOTH" ? "Customer & Supplier" : p.type.charAt(0) + p.type.slice(1).toLowerCase()}</td>
                  <td className={`num ${p.balance > 0 ? "text-emerald-700" : p.balance < 0 ? "text-red-700" : ""}`}>
                    {money(Math.abs(p.balance))}
                    <span className="ml-1 text-xs text-gray-500">{p.balance > 0 ? "to collect" : p.balance < 0 ? "to pay" : ""}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
