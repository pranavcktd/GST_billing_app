"use client";

import { Briefcase, GraduationCap, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { usePaged } from "@/components/Pager";
import { ClientForm } from "@/components/practice/ClientForm";
import type { PClient } from "@/components/practice/types";
import { Button, Card, Empty, ErrorBox, Input, Loading, PageHeader } from "@/components/ui";
import { qs } from "@/lib/api";
import { useConfig } from "@/lib/config";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

export default function PracticeHome() {
  const config = useConfig();
  const { data: status } = useFetch<{ enabled: boolean; limit: number; used: number }>("/practice/status");
  const [search, setSearch] = useState("");
  const { data, error, reload } = useFetch<PClient[]>(status?.enabled ? `/practice/clients${qs({ search })}` : null);
  const [adding, setAdding] = useState(false);
  const { rows, pager } = usePaged(data);

  if (!status) return <Loading />;
  if (!status.enabled) {
    return (
      <Card className="mx-auto mt-10 max-w-xl p-8 text-center">
        <Briefcase className="mx-auto text-brand-600" size={36} />
        <h1 className="mt-3 text-xl font-semibold text-gray-900">Practitioner workspace</h1>
        <p className="mt-2 text-sm text-gray-600">
          Prepare profit &amp; loss, balance sheet, capital accounts and depreciation for your clients — from a trial balance,
          their MyBillSync books, or annual figures — with an explanation behind every figure.
        </p>
        <p className="mt-4 text-sm text-gray-600">This add-on isn&apos;t active on your account yet. Contact us to enable it:
          <br /><a className="font-medium text-brand-600" href={`mailto:${config.company.email}`}>{config.company.email}</a></p>
      </Card>
    );
  }

  return (
    <>
      <PageHeader title="Clients" sub={`Final accounts workspace · ${status.used} of ${status.limit >= 100000 ? "unlimited" : status.limit} clients`}
        actions={<Button onClick={() => setAdding(true)} disabled={status.used >= status.limit}><Plus size={16} /> Add client</Button>} />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Input placeholder="Search name or PAN" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
        <span className="inline-flex items-center gap-1.5 text-xs text-gray-500"><GraduationCap size={14} /> Every figure in the statements explains where it comes from — open any line in the Statements tab.</span>
      </div>
      <ErrorBox message={error} />
      <Card className="overflow-x-auto">
        {!data ? <Loading /> : !data.length ? (
          <Empty title="No clients yet" action={<Button onClick={() => setAdding(true)}><Plus size={16} /> Add your first client</Button>} />
        ) : (
          <table className="tbl">
            <thead><tr><th>Client</th><th>Type</th><th>PAN</th><th>Years</th><th>Updated</th></tr></thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td><Link href={`/practice/clients/${c.id}`} className="font-medium text-brand-600 hover:underline">{c.name}</Link>
                    {c.nature_of_business && <div className="text-xs text-gray-500">{c.nature_of_business}</div>}</td>
                  <td className="text-sm">{c.entity_type === "PARTNERSHIP" ? "Partnership" : "Proprietorship"}</td>
                  <td className="font-mono text-xs">{c.pan ?? "—"}</td>
                  <td className="text-xs">
                    {(c.files ?? []).slice(0, 4).map((f) => (
                      <Link key={f.id} href={`/practice/files/${f.id}`}
                        className={`mr-1 inline-block rounded px-1.5 py-0.5 ${f.status === "FINAL" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"}`}>
                        {f.fy}{f.status === "FINAL" ? " ✓" : ""}
                      </Link>
                    ))}
                    {!c.files?.length && <span className="text-gray-400">none yet</span>}
                  </td>
                  <td className="text-xs text-gray-500">{fmtDate(c.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {pager}
      </Card>
      {adding && <ClientForm onClose={() => setAdding(false)} onSaved={() => { setAdding(false); reload(); }} />}
    </>
  );
}
