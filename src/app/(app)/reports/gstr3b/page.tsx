"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { PeriodPicker } from "@/components/PeriodPicker";
import { Button, Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { downloadFile, qs } from "@/lib/api";
import { monthRange, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import { ReviewNote } from "@/components/ReviewNote";

type Tax = { taxable?: number; igst: number; cgst: number; sgst: number; cess: number };
interface Gstr3b {
  applicable: boolean;
  outward_taxable: Tax; zero_rated: Tax; nil_exempt: number; inward_rcm: Tax;
  inter_state_unregistered: { pos: string; taxable: number; igst: number }[];
  inter_state_composition: { pos: string; taxable: number; igst: number }[];
  itc_import_goods: Tax; itc_import_services: Tax; itc_rcm: Tax; itc_other: Tax; itc_total: Tax; itc_blocked: Tax;
  inward_exempt: { inter: number; intra: number };
  liability: Tax; net_payable: Tax;
}

const Cell = ({ v }: { v?: number }) => <td className="num">{v === undefined ? "—" : money(v)}</td>;

function Row({ label, t, bold }: { label: string; t: Tax; bold?: boolean }) {
  return (
    <tr className={bold ? "font-semibold" : ""}>
      <td>{label}</td><Cell v={t.taxable} /><Cell v={t.igst} /><Cell v={t.cgst} /><Cell v={t.sgst} /><Cell v={t.cess} />
    </tr>
  );
}

const Head = () => (
  <thead><tr><th>Nature</th><th className="num">Taxable value</th><th className="num">IGST</th><th className="num">CGST</th><th className="num">SGST/UTGST</th><th className="num">Cess</th></tr></thead>
);

export default function Gstr3bPage() {
  const [period, setPeriod] = useState(monthRange(0));
  const { data, error, loading } = useFetch<Gstr3b>(`/reports/gstr3b${qs({ date_from: period.from, date_to: period.to })}`);

  return (
    <>
      <PageHeader title="GSTR-3B" sub="Summary return — tax liability and input tax credit" actions={
        <Button onClick={() => downloadFile(`/exports/gstr3b-json${qs({ date_from: period.from, date_to: period.to })}`).catch((e) => alert(e.message))}>
          <Download size={16} /> GSTR-3B JSON for portal
        </Button>
      } />
      <PeriodPicker value={period} onChange={setPeriod} />
      <ReviewNote />
      <ErrorBox message={error} />
      {loading || !data ? <Loading /> : !data.applicable ? (
        <Card className="p-5 text-sm text-gray-600">GSTR-3B applies to regular GST registered businesses.</Card>
      ) : (
        <>
          <Card className="mb-5 overflow-x-auto">
            <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">3.1 — Outward supplies and inward supplies liable to reverse charge</h2>
            <table className="tbl">
              <Head />
              <tbody>
                <Row label="(a) Outward taxable supplies (other than zero rated, nil rated and exempted)" t={data.outward_taxable} />
                <Row label="(b) Outward taxable supplies (zero rated — exports & SEZ)" t={data.zero_rated} />
                <Row label="(c) Other outward supplies (nil rated, exempted)" t={{ taxable: data.nil_exempt, igst: 0, cgst: 0, sgst: 0, cess: 0 }} />
                <Row label="(d) Inward supplies (liable to reverse charge)" t={data.inward_rcm} />
              </tbody>
            </table>
          </Card>

          <Card className="mb-5 overflow-x-auto">
            <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">3.2 — Inter-state supplies to unregistered persons and composition dealers</h2>
            {data.inter_state_unregistered.length + data.inter_state_composition.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">None.</p> : (
              <table className="tbl">
                <thead><tr><th>Supplies to</th><th>Place of supply</th><th className="num">Taxable value</th><th className="num">IGST</th></tr></thead>
                <tbody>
                  {data.inter_state_unregistered.map((r) => (<tr key={"u" + r.pos}><td>Unregistered persons</td><td>{r.pos}</td><Cell v={r.taxable} /><Cell v={r.igst} /></tr>))}
                  {data.inter_state_composition.map((r) => (<tr key={"c" + r.pos}><td>Composition taxable persons</td><td>{r.pos}</td><Cell v={r.taxable} /><Cell v={r.igst} /></tr>))}
                </tbody>
              </table>
            )}
          </Card>

          <Card className="mb-5 overflow-x-auto">
            <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">4 — Eligible input tax credit</h2>
            <table className="tbl">
              <Head />
              <tbody>
                <Row label="(A)(1) Import of goods" t={{ ...data.itc_import_goods, taxable: undefined }} />
                <Row label="(A)(2) Import of services" t={{ ...data.itc_import_services, taxable: undefined }} />
                <Row label="(A)(3) Inward supplies liable to reverse charge (other than imports)" t={{ ...data.itc_rcm, taxable: undefined }} />
                <Row label="(A)(5) All other ITC (net of debit notes)" t={{ ...data.itc_other, taxable: undefined }} />
                <Row label="(C) Net ITC available" t={{ ...data.itc_total, taxable: undefined }} bold />
                <Row label="(D)(1) Ineligible ITC — blocked u/s 17(5)" t={{ ...data.itc_blocked, taxable: undefined }} />
              </tbody>
            </table>
          </Card>

          <Card className="mb-5 overflow-x-auto">
            <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">5 — Exempt, nil rated and non-GST inward supplies</h2>
            <table className="tbl">
              <thead><tr><th>Nature</th><th className="num">Inter-state</th><th className="num">Intra-state</th></tr></thead>
              <tbody><tr><td>From composition, exempt and nil rated suppliers</td><Cell v={data.inward_exempt.inter} /><Cell v={data.inward_exempt.intra} /></tr></tbody>
            </table>
          </Card>

          <Card className="overflow-x-auto">
            <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Tax payable (indicative)</h2>
            <table className="tbl">
              <Head />
              <tbody>
                <Row label="Total tax liability" t={data.liability} />
                <Row label="Less: ITC" t={data.itc_total} />
                <Row label="Net (negative = credit carried forward)" t={data.net_payable} bold />
              </tbody>
            </table>
            <p className="px-5 py-3 text-xs text-gray-500">
              Cross-utilisation of IGST/CGST/SGST credit (Sec. 49) is applied on the GST portal when you offset liability; figures here are head-wise.
            </p>
          </Card>
        </>
      )}
    </>
  );
}
