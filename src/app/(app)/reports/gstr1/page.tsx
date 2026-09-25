"use client";

import { Download } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { type DocColumn, type DocSection, ExportMenu, type TableDoc } from "@/components/ExportMenu";
import { PeriodPicker } from "@/components/PeriodPicker";
import { Button, Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { downloadFile, qs } from "@/lib/api";
import { downloadCsv, fmtDate, monthRange, money, qty } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import { ReviewNote } from "@/components/ReviewNote";

type Tax = { taxable: number; igst: number; cgst: number; sgst: number; cess: number };
type RateRow = Tax & { rate: number };
interface Doc { id: string; number: string; date: string; party_name: string; gstin: string | null; pos: string; reverse_charge: boolean; value: number; rates: RateRow[]; original_number?: string | null; type?: string; shipping_bill?: string | null; shipping_date?: string | null; port?: string | null }
interface Gstr1 {
  applicable: boolean;
  b2b: Doc[]; b2b_total: Tax; b2cl: Doc[]; b2cl_total: Tax; b2cs: (Tax & { pos: string; rate: number })[]; b2cs_total: Tax;
  cdnr: Doc[]; cdnr_total: Tax; exp: Doc[]; exp_total: Tax; cdnur: Doc[]; cdnur_total: Tax; nil: Record<string, number>;
  hsn: (Tax & { section: string; hsn: string; uqc: string; rate: number; qty: number; value: number })[];
  docs: { nature: string; from_number: string; to_number: string; total: number; cancelled: number; net_issued: number }[];
}

const TAX_COLS = ["Taxable", "IGST", "CGST", "SGST", "Cess"];
const taxCells = (t: Tax) => [t.taxable, t.igst, t.cgst, t.sgst, t.cess];

function Section({ title, sub, onExport, children }: { title: string; sub?: string; onExport?: () => void; children: React.ReactNode }) {
  return (
    <Card className="mb-5 overflow-x-auto">
      <div className="flex items-center justify-between px-5 pt-4 pb-2">
        <div>
          <h2 className="font-semibold text-gray-900">{title}</h2>
          {sub && <p className="text-xs text-gray-500">{sub}</p>}
        </div>
        {onExport && <Button variant="ghost" onClick={onExport}><Download size={15} /> CSV</Button>}
      </div>
      {children}
    </Card>
  );
}

const TYPE_LABEL: Record<string, string> = { SEWP: "SEZ with payment", SEWOP: "SEZ without payment", EXPWP: "With IGST", EXPWOP: "Under LUT" };

function DocTable({ docs, total, showOriginal, showShipping }: { docs: Doc[]; total: Tax; showOriginal?: boolean; showShipping?: boolean }) {
  if (!docs.length) return <p className="px-5 pb-4 text-sm text-gray-500">None in this period.</p>;
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>GSTIN</th><th>Party</th><th>Number</th><th>Date</th>{showOriginal && <th>Against</th>}{showShipping ? <th>Shipping bill / port</th> : <th>POS</th>}
          <th className="num">Value</th><th className="num">Rate</th>{TAX_COLS.map((c) => <th key={c} className="num">{c}</th>)}
        </tr>
      </thead>
      <tbody>
        {docs.flatMap((d) =>
          d.rates.map((r, i) => (
            <tr key={d.id + r.rate}>
              {i === 0 ? (
                <>
                  <td rowSpan={d.rates.length} className="font-mono text-xs">{d.gstin ?? "—"}</td>
                  <td rowSpan={d.rates.length}>
                    {d.party_name}
                    {d.type && TYPE_LABEL[d.type] && <span className="ml-1 rounded bg-sky-50 px-1.5 py-0.5 text-[10px] text-sky-700">{TYPE_LABEL[d.type]}</span>}
                  </td>
                  <td rowSpan={d.rates.length}><Link href={`/doc/${d.id}`} className="text-brand-600 hover:underline">{d.number}</Link></td>
                  <td rowSpan={d.rates.length}>{fmtDate(d.date)}</td>
                  {showOriginal && <td rowSpan={d.rates.length}>{d.original_number ?? "—"}</td>}
                  <td rowSpan={d.rates.length}>
                    {showShipping ? [d.shipping_bill, d.shipping_date && fmtDate(d.shipping_date), d.port].filter(Boolean).join(" · ") || "—" : d.pos}
                  </td>
                  <td rowSpan={d.rates.length} className="num">{money(d.value)}</td>
                </>
              ) : null}
              <td className="num">{r.rate}%</td>
              {taxCells(r).map((v, j) => <td key={j} className="num">{money(v)}</td>)}
            </tr>
          )),
        )}
      </tbody>
      <tfoot>
        <tr><td colSpan={showOriginal ? 8 : 7}>Total</td>{taxCells(total).map((v, j) => <td key={j} className="num">{money(v)}</td>)}</tr>
      </tfoot>
    </table>
  );
}

const docRows = (docs: Doc[]) =>
  docs.flatMap((d) => d.rates.map((r) => [d.gstin, d.party_name, d.number, d.date, d.original_number ?? "", d.pos, d.reverse_charge ? "Y" : "N", d.value, r.rate, ...taxCells(r)]));
const DOC_HEAD = ["GSTIN", "Party", "Number", "Date", "Against", "Place of supply", "Reverse charge", "Invoice value", "Rate", ...TAX_COLS];

const TAXC: DocColumn[] = [
  { key: "taxable", label: "Taxable", type: "money" }, { key: "igst", label: "IGST", type: "money" }, { key: "cgst", label: "CGST", type: "money" },
  { key: "sgst", label: "SGST", type: "money" }, { key: "cess", label: "Cess", type: "money" },
];
const docSection = (title: string, docs: Doc[], total: Tax): DocSection => ({
  title,
  columns: [{ key: "gstin", label: "GSTIN", type: "text" }, { key: "party_name", label: "Party", type: "text" }, { key: "number", label: "Number", type: "text" },
    { key: "date", label: "Date", type: "date" }, { key: "pos", label: "POS", type: "text" }, { key: "value", label: "Value", type: "money" },
    { key: "rate", label: "Rate %", type: "pct" }, ...TAXC],
  rows: docs.flatMap((d) => d.rates.map((r, i) => ({
    ...(i === 0 ? { gstin: d.gstin, party_name: d.party_name, number: d.number, date: d.date, pos: d.pos, value: d.value } : {}),
    rate: r.rate, taxable: r.taxable, igst: r.igst, cgst: r.cgst, sgst: r.sgst, cess: r.cess,
  }))),
  total: { ...total },
});

function gstr1Doc(d: Gstr1, from: string, to: string): TableDoc {
  return {
    title: "GSTR-1 — outward supplies", subtitle: `${fmtDate(from)} to ${fmtDate(to)} · prepared from your books for review`, filename: `GSTR1-${from}-to-${to}`,
    sections: [
      docSection("4A — B2B invoices", d.b2b, d.b2b_total),
      docSection("5 — B2C Large", d.b2cl, d.b2cl_total),
      { title: "7 — B2C Others", columns: [{ key: "pos", label: "Place of supply", type: "text" }, { key: "rate", label: "Rate %", type: "pct" }, ...TAXC], rows: d.b2cs, total: { ...d.b2cs_total } },
      docSection("6A — Exports", d.exp, d.exp_total),
      docSection("9B — Credit / debit notes (registered)", d.cdnr, d.cdnr_total),
      docSection("9B — Credit / debit notes (unregistered)", d.cdnur, d.cdnur_total),
      { title: "8 — Nil rated / exempt", columns: [{ key: "k", label: "Description", type: "text" }, { key: "v", label: "Value", type: "money" }],
        rows: Object.entries(d.nil).map(([k, v]) => ({ k: k.replace("_", " "), v })) },
      { title: "12 — HSN summary", columns: [{ key: "section", label: "Section", type: "text" }, { key: "hsn", label: "HSN", type: "text" }, { key: "uqc", label: "UQC", type: "text" },
        { key: "qty", label: "Qty", type: "qty" }, { key: "rate", label: "Rate %", type: "pct" }, { key: "value", label: "Value", type: "money" }, ...TAXC], rows: d.hsn },
      { title: "13 — Documents issued", columns: [{ key: "nature", label: "Nature", type: "text" }, { key: "from_number", label: "From", type: "text" },
        { key: "to_number", label: "To", type: "text" }, { key: "total", label: "Total", type: "int" }, { key: "cancelled", label: "Cancelled", type: "int" },
        { key: "net_issued", label: "Net issued", type: "int" }], rows: d.docs },
    ],
  };
}

export default function Gstr1Page() {
  const [period, setPeriod] = useState(monthRange(0));
  const { data, error, loading } = useFetch<Gstr1>(`/reports/gstr1${qs({ date_from: period.from, date_to: period.to })}`);
  const tag = `${period.from}_${period.to}`;

  return (
    <>
      <PageHeader title="GSTR-1" sub="Details of outward supplies" actions={
        <>
          <ExportMenu compact build={() => (data ? gstr1Doc(data, period.from, period.to) : null)} disabled={!data?.applicable} />
          <Button variant="secondary" onClick={() => downloadFile(`/einvoice/bulk-json${qs({ date_from: period.from, date_to: period.to })}`).catch((e) => alert(e.message))}>
            <Download size={16} /> e-Invoice bulk JSON
          </Button>
          <Button onClick={() => downloadFile(`/exports/gstr1-json${qs({ date_from: period.from, date_to: period.to })}`).catch((e) => alert(e.message))}>
            <Download size={16} /> GSTR-1 JSON for portal
          </Button>
        </>
      } />
      <PeriodPicker value={period} onChange={setPeriod} />
      <ReviewNote />
      <ErrorBox message={error} />
      {loading || !data ? (
        <Loading />
      ) : !data.applicable ? (
        <Card className="p-5 text-sm text-gray-600">GSTR-1 applies to regular GST registered businesses. Your business is set up as composition or unregistered.</Card>
      ) : (
        <>
          <Section title="4A — B2B invoices" sub="Supplies to registered persons" onExport={() => downloadCsv(`gstr1-b2b-${tag}.csv`, DOC_HEAD, docRows(data.b2b))}>
            <DocTable docs={data.b2b} total={data.b2b_total} />
          </Section>
          <Section title="5 — B2C Large" sub="Inter-state supplies to unregistered persons above ₹1,00,000" onExport={() => downloadCsv(`gstr1-b2cl-${tag}.csv`, DOC_HEAD, docRows(data.b2cl))}>
            <DocTable docs={data.b2cl} total={data.b2cl_total} />
          </Section>
          <Section title="7 — B2C Others" sub="Summary by place of supply and rate (net of credit notes)"
            onExport={() => downloadCsv(`gstr1-b2cs-${tag}.csv`, ["Place of supply", "Rate", ...TAX_COLS], data.b2cs.map((r) => [r.pos, r.rate, ...taxCells(r)]))}>
            {data.b2cs.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">None in this period.</p> : (
              <table className="tbl">
                <thead><tr><th>Place of supply</th><th className="num">Rate</th>{TAX_COLS.map((c) => <th key={c} className="num">{c}</th>)}</tr></thead>
                <tbody>{data.b2cs.map((r) => (<tr key={r.pos + r.rate}><td>{r.pos}</td><td className="num">{r.rate}%</td>{taxCells(r).map((v, j) => <td key={j} className="num">{money(v)}</td>)}</tr>))}</tbody>
                <tfoot><tr><td colSpan={2}>Total</td>{taxCells(data.b2cs_total).map((v, j) => <td key={j} className="num">{money(v)}</td>)}</tr></tfoot>
              </table>
            )}
          </Section>
          <Section title="9B — Credit / debit notes (registered)" onExport={() => downloadCsv(`gstr1-cdnr-${tag}.csv`, DOC_HEAD, docRows(data.cdnr))}>
            <DocTable docs={data.cdnr} total={data.cdnr_total} showOriginal />
          </Section>
          <Section title="6A — Exports" sub="With payment of IGST or under LUT (zero rated)" onExport={() => downloadCsv(`gstr1-exp-${tag}.csv`, DOC_HEAD, docRows(data.exp))}>
            <DocTable docs={data.exp} total={data.exp_total} showShipping />
          </Section>
          <Section title="9B — Credit / debit notes (unregistered)" sub="Against B2C Large invoices and exports" onExport={() => downloadCsv(`gstr1-cdnur-${tag}.csv`, DOC_HEAD, docRows(data.cdnur))}>
            <DocTable docs={data.cdnur} total={data.cdnur_total} />
          </Section>
          <Section title="8 — Nil rated / exempt supplies">
            <table className="tbl">
              <thead><tr><th>Description</th><th className="num">Value</th></tr></thead>
              <tbody>
                <tr><td>Inter-state to registered persons</td><td className="num">{money(data.nil.inter_registered)}</td></tr>
                <tr><td>Intra-state to registered persons</td><td className="num">{money(data.nil.intra_registered)}</td></tr>
                <tr><td>Inter-state to unregistered persons</td><td className="num">{money(data.nil.inter_unregistered)}</td></tr>
                <tr><td>Intra-state to unregistered persons</td><td className="num">{money(data.nil.intra_unregistered)}</td></tr>
              </tbody>
            </table>
          </Section>
          <Section title="12 — HSN-wise summary" sub="Reported separately for B2B and B2C supplies"
            onExport={() => downloadCsv(`gstr1-hsn-${tag}.csv`, ["Section", "HSN", "UQC", "Quantity", "Rate", "Total value", ...TAX_COLS], data.hsn.map((h) => [h.section, h.hsn, h.uqc, h.qty, h.rate, h.value, ...taxCells(h)]))}>
            {data.hsn.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">None in this period.</p> : (
              <table className="tbl">
                <thead><tr><th>Section</th><th>HSN</th><th>UQC</th><th className="num">Qty</th><th className="num">Rate</th><th className="num">Value</th>{TAX_COLS.map((c) => <th key={c} className="num">{c}</th>)}</tr></thead>
                <tbody>
                  {data.hsn.map((h, i) => (
                    <tr key={i} className={!h.hsn ? "bg-amber-50" : ""}>
                      <td>{h.section}</td><td className="font-mono">{h.hsn || <span className="text-amber-800">missing</span>}</td><td>{h.uqc}</td>
                      <td className="num">{qty(h.qty)}</td><td className="num">{h.rate}%</td><td className="num">{money(h.value)}</td>
                      {taxCells(h).map((v, j) => <td key={j} className="num">{money(v)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>
          <Section title="13 — Documents issued">
            {data.docs.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">None in this period.</p> : (
              <table className="tbl">
                <thead><tr><th>Nature of document</th><th>From</th><th>To</th><th className="num">Total</th><th className="num">Cancelled</th><th className="num">Net issued</th></tr></thead>
                <tbody>{data.docs.map((d) => (<tr key={d.nature}><td>{d.nature}</td><td>{d.from_number}</td><td>{d.to_number}</td><td className="num">{d.total}</td><td className="num">{d.cancelled}</td><td className="num">{d.net_issued}</td></tr>))}</tbody>
              </table>
            )}
          </Section>
        </>
      )}
    </>
  );
}
