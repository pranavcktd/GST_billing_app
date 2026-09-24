"use client";

import { Download, Printer } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { PeriodPicker } from "@/components/PeriodPicker";
import { ReportSections, reportCsvRows } from "@/components/ReportView";
import { Button, Combobox, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { qs } from "@/lib/api";
import { downloadCsv, fyRange, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Account, ExpenseCategory, Item, Loan, Party, ReportMeta, ReportResult } from "@/lib/types";

export default function ReportRunner() {
  const { slug } = useParams<{ slug: string }>();
  const { data: catalog } = useFetch<ReportMeta[]>("/reports/catalog");
  const meta = catalog?.find((r) => r.slug === slug);
  const f = new Set((meta?.filters ?? []).map((x) => x.replace("*", "")));
  const required = new Set((meta?.filters ?? []).filter((x) => x.endsWith("*")).map((x) => x.replace("*", "")));

  const [period, setPeriod] = useState(fyRange());
  const [asOf, setAsOf] = useState(today());
  const [partyId, setPartyId] = useState("");
  const [itemId, setItemId] = useState("");
  const [accountId, setAccountId] = useState("");
  const [loanId, setLoanId] = useState("");
  const [categoryId, setCategoryId] = useState("");

  const { data: parties } = useFetch<Party[]>(f.has("party") ? "/parties?include_inactive=true" : null);
  const { data: items } = useFetch<Item[]>(f.has("item") ? "/items?include_inactive=true" : null);
  const { data: accounts } = useFetch<Account[]>(f.has("account") ? "/accounts" : null);
  const { data: loans } = useFetch<Loan[]>(f.has("loan") ? "/loans" : null);
  const { data: cats } = useFetch<ExpenseCategory[]>(f.has("expense_category") ? "/expenses/categories" : null);

  const missing = (required.has("party") && !partyId) || (required.has("item") && !itemId) || (required.has("loan") && !loanId);
  const params = qs({
    date_from: f.has("period") ? period.from : null, date_to: f.has("period") ? period.to : null,
    as_of: f.has("as_of") ? asOf : null, party_id: partyId || null, item_id: itemId || null,
    account_id: accountId || null, loan_id: loanId || null, category_id: categoryId || null,
  });
  const { data, error, loading } = useFetch<ReportResult>(meta && !missing ? `/reports/run/${slug}${params}` : null);

  if (!catalog) return <Loading />;
  if (!meta) return <ErrorBox message="Report not found" />;

  const exportCsv = () => {
    if (!data) return;
    const { headers, rows } = reportCsvRows(data);
    downloadCsv(`${slug}-${f.has("period") ? `${period.from}_${period.to}` : asOf}.csv`, headers, rows);
  };

  return (
    <>
      <PageHeader
        title={data?.title ?? meta.title}
        sub={data?.subtitle ?? meta.description}
        actions={
          <div className="no-print flex gap-2">
            <Button variant="secondary" onClick={() => window.print()} disabled={!data}><Printer size={16} /> Print / PDF</Button>
            <Button variant="secondary" onClick={exportCsv} disabled={!data}><Download size={16} /> Export</Button>
          </div>
        }
      />
      <div className="no-print flex flex-wrap items-end gap-2">
        {f.has("period") && <PeriodPicker value={period} onChange={setPeriod} />}
        {f.has("as_of") && (
          <Field label="As of" className="mb-4"><Input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></Field>
        )}
        {f.has("party") && parties && (
          <Field label={`Party${required.has("party") ? " *" : ""}`} className="mb-4 w-64">
            <Combobox items={parties} value={parties.find((p) => p.id === partyId)?.name ?? ""} placeholder={required.has("party") ? "Select party" : "All parties"}
              getKey={(p) => p.id} getLabel={(p) => p.name} onSelect={(p) => setPartyId(p.id)} />
            {partyId && !required.has("party") && <button className="mt-1 text-xs text-gray-500 hover:underline" onClick={() => setPartyId("")}>Clear</button>}
          </Field>
        )}
        {f.has("item") && items && (
          <Field label="Item *" className="mb-4 w-64">
            <Combobox items={items} value={items.find((i) => i.id === itemId)?.name ?? ""} placeholder="Select item"
              getKey={(i) => i.id} getLabel={(i) => `${i.name} ${i.code ?? ""}`} onSelect={(i) => setItemId(i.id)} />
          </Field>
        )}
        {f.has("account") && accounts && (
          <Field label="Account" className="mb-4">
            <Select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value="">Cash in Hand</option>
              {accounts.filter((a) => !a.is_default_cash).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </Select>
          </Field>
        )}
        {f.has("loan") && loans && (
          <Field label="Loan *" className="mb-4">
            <Select value={loanId} onChange={(e) => setLoanId(e.target.value)}>
              <option value="">Select loan</option>
              {loans.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </Select>
          </Field>
        )}
        {f.has("expense_category") && cats && (
          <Field label="Expense category" className="mb-4">
            <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
              <option value="">All categories</option>
              {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
        )}
      </div>
      <ErrorBox message={error} />
      {missing ? (
        <p className="py-10 text-center text-sm text-gray-500">Choose the {required.has("party") ? "party" : required.has("item") ? "item" : "loan"} to see this report.</p>
      ) : loading && !data ? (
        <Loading />
      ) : data ? (
        <ReportSections data={data} />
      ) : null}
    </>
  );
}
