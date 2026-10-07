"use client";

import { ArrowLeft, Printer } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { Button, ErrorBox, Loading } from "@/components/ui";
import { BrandName } from "@/lib/config";
import { useDocTitle } from "@/lib/docName";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Business } from "@/lib/types";

interface Line {
  id: string; name: string; bonus: number; other_additions: number; advance_recovery: number; other_deductions: number;
  gross: number; deductions: number; net: number; note: string | null;
  data: Record<string, number | string | null>;
}
interface Run { month: string; status: string; paid_on: string | null; lines: Line[] }

function Info({ k, v }: { k: string; v: React.ReactNode }) {
  return v ? <div><span className="text-gray-500">{k}: </span><b>{v}</b></div> : null;
}

/** Payslip for one employee and month — print or save as PDF. */
export default function Payslip() {
  const { run: runId, line: lineId } = useParams<{ run: string; line: string }>();
  const router = useRouter();
  const { data: run, error } = useFetch<Run>(`/payroll/runs/${runId}`);
  const { data: biz } = useFetch<Business>("/businesses/current");
  const line = run?.lines.find((l) => l.id === lineId);
  useDocTitle(line && run ? `Payslip_${line.name.replace(/[^A-Za-z0-9]+/g, "-")}_${run.month}` : null);

  if (error) return <div className="p-6"><ErrorBox message={error} /></div>;
  if (!run || !biz) return <Loading />;
  if (!line) return <div className="p-6"><ErrorBox message="Payslip not found" /></div>;
  const d = line.data;
  const n = (k: string) => Number(d[k] ?? 0);
  const month = new Date(`${run.month}-01`).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
  const earnings: [string, number][] = [
    [d.salary_type === "DAILY" ? `Wages (${n("paid_days")} days × ${money(n("rate"))})` : `Salary (${n("paid_days")} of ${n("days_in_month")} days)`, n("earned")],
    [`Overtime (${n("ot_hours")} h)`, n("ot_pay")], ["Bonus / incentive", line.bonus], ["Other additions", line.other_additions],
  ];
  const deductions: [string, number][] = [
    ["Provident fund (EPF)", n("pf_employee")], ["ESI", n("esi_employee")], ["Professional tax", n("pt")], ["TDS (income tax)", n("tds")],
    ["Advance recovery", line.advance_recovery], ["Other deductions", line.other_deductions],
  ];

  return (
    <div className="min-h-screen bg-gray-100 py-6 print:bg-white print:py-0">
      <div className="no-print mx-auto mb-4 flex max-w-[210mm] justify-between px-2">
        <Button variant="secondary" onClick={() => router.push("/staff/payroll")}><ArrowLeft size={16} /> Back</Button>
        <Button onClick={() => window.print()}><Printer size={16} /> Print / Save PDF</Button>
      </div>
      <div className="print-sheet mx-auto max-w-[210mm] bg-white p-8 text-[12px] text-gray-900 shadow-sm print:shadow-none">
        <div className="flex items-start justify-between border-b-2 border-gray-800 pb-3">
          <div>
            <div className="text-lg font-bold">{biz.name}</div>
            <div className="text-gray-600">{[biz.address, biz.city, biz.pincode].filter(Boolean).join(", ")}</div>
            {biz.gstin && <div className="text-gray-600">GSTIN {biz.gstin}</div>}
          </div>
          <div className="text-right"><div className="text-base font-bold">PAYSLIP</div><div>{month}</div>{run.status !== "PAID" && <div className="text-xs text-amber-700">{run.status === "DRAFT" ? "Draft" : "Not yet paid"}</div>}</div>
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 py-3">
          <Info k="Employee" v={line.name} /><Info k="Code" v={d.code as string} />
          <Info k="Designation" v={d.designation as string} /><Info k="UAN" v={d.uan as string} />
          <Info k="ESIC no." v={d.esic_no as string} /><Info k="Bank" v={d.bank as string} />
          <Info k="Paid on" v={run.paid_on ? new Date(run.paid_on).toLocaleDateString("en-IN") : ""} />
        </div>
        <div className="mb-3 grid grid-cols-4 gap-2 rounded border border-gray-200 p-2 text-center sm:grid-cols-8">
          {([["Days", "days_in_month"], ["Paid days", "paid_days"], ["Present", "present"], ["Absent", "absent"], ["Half days", "half_days"],
            ["Leave", "leave"], ["Weekly off", "weekly_off"], ["Holidays", "holidays"]] as [string, string][]).map(([k, f]) => (
            <div key={k}><div className="text-[10px] text-gray-500">{k}</div><div className="font-semibold">{n(f)}</div></div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-4">
          {([["Earnings", earnings, line.gross], ["Deductions", deductions, line.deductions]] as [string, [string, number][], number][]).map(([title, rows, total]) => (
            <table key={title} className="w-full border-collapse self-start">
              <thead><tr className="border-y border-gray-400"><th className="py-1 text-left">{title}</th><th className="text-right">Amount</th></tr></thead>
              <tbody>{rows.filter(([, v]) => v).map(([k, v]) => <tr key={k} className="border-b border-gray-100"><td className="py-1">{k}</td><td className="text-right">{money(v)}</td></tr>)}</tbody>
              <tfoot><tr className="border-t border-gray-400 font-semibold"><td className="py-1">Total {title.toLowerCase()}</td><td className="text-right">{money(total)}</td></tr></tfoot>
            </table>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between rounded bg-gray-100 px-4 py-3 text-base font-bold print:bg-gray-100" style={{ printColorAdjust: "exact" }}>
          <span>Net pay</span><span>{money(line.net)}</span>
        </div>
        {line.note && <p className="mt-2 text-gray-600">Note: {line.note}</p>}
        <div className="mt-10 grid grid-cols-2 gap-6 text-center text-gray-600">
          <div className="border-t border-gray-300 pt-1">Employee signature</div>
          <div className="border-t border-gray-300 pt-1">For {biz.name}</div>
        </div>
        <p className="mt-6 text-center text-[10px] text-gray-400">This is a computer-generated payslip. Made with <BrandName />.</p>
      </div>
    </div>
  );
}
