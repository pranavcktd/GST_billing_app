"use client";

import { Download, Phone, Receipt, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { type Txn, TxnStatus, when } from "@/components/Transactions";
import { Button, Card, Input, Loading, Select } from "@/components/ui";
import { qs } from "@/lib/api";
import { downloadCsv, fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface List { total: number; summary: Record<string, { count: number; amount: number }>; rows: Txn[] }
interface Lead extends Txn { attempts: number; current_plan: string | null; current_status: string | null; valid_until: string | null; signed_up: string; last_login_at: string | null }
interface Detail extends Txn { account_history: Txn[] }

const CARDS: [string, string, string][] = [
  ["PAID", "Successful", "text-emerald-700"], ["FAILED", "Failed", "text-red-700"],
  ["CANCELLED", "Closed without paying", "text-gray-700"], ["CREATED", "Not completed", "text-amber-700"],
];

/** Admin → Transactions: every subscription checkout with receipts, plus leads (tried to pay, have not). */
export function AdminTransactions({ initialId }: { initialId?: string | null }) {
  const [view, setView] = useState<"all" | "leads">("all");
  const [f, setF] = useState({ status: "", mode: "LIVE", q: "", start: "", end: "" });
  const [openId, setOpenId] = useState<string | null>(initialId ?? null);
  const { data } = useFetch<List>(view === "all" ? `/admin/payments${qs({ ...f, limit: 200 })}` : null);
  const { data: leads } = useFetch<Lead[]>(view === "leads" ? "/admin/payments/leads?days=90" : null);

  const exportCsv = () => data && downloadCsv("transactions.csv",
    ["Date", "Status", "Mode", "Customer", "E-mail", "Phone", "Business", "For", "Amount", "Receipt", "Order id", "Payment id", "Method", "Reason"],
    data.rows.map((t) => [when(t.created_at), t.status_label, t.mode, t.owner_name, t.owner_email, t.owner_phone, t.business_name, t.item, t.amount,
      t.receipt_no, t.order_id, t.payment_id, t.method, t.error_reason]));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Transactions</h2>
          <p className="text-sm text-gray-500">Every subscription payment — successful, failed, closed or unfinished. You get an alert (bell + e-mail) for each success and failure.</p>
        </div>
        <div className="flex rounded-lg border border-gray-200 bg-white p-0.5 text-sm">
          {(["all", "leads"] as const).map((v) => (
            <button key={v} onClick={() => setView(v)} className={`rounded-md px-3 py-1.5 ${view === v ? "bg-brand-600 text-white" : "text-gray-700"}`}>
              {v === "all" ? "All transactions" : "Leads"}
            </button>
          ))}
        </div>
      </div>

      {view === "all" && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {CARDS.map(([k, label, color]) => (
              <button key={k} onClick={() => setF({ ...f, status: f.status === k ? "" : k })} className="text-left">
                <Card className={`p-4 ${f.status === k ? "ring-2 ring-brand-300" : ""}`}>
                  <div className="text-xs text-gray-500">{label}</div>
                  <div className={`mt-1 text-xl font-semibold ${color}`}>{data?.summary[k]?.count ?? "–"}</div>
                  <div className="text-xs text-gray-500">{data ? money(data.summary[k]?.amount ?? 0) : ""}</div>
                </Card>
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <div className="relative"><Search size={15} className="absolute top-2.5 left-2.5 text-gray-400" />
              <Input className="!pl-8" placeholder="Name, e-mail, phone, business, order / receipt no." value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} /></div>
            <Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
              <option value="">All statuses</option>{CARDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </Select>
            <Select value={f.mode} onChange={(e) => setF({ ...f, mode: e.target.value })}>
              <option value="LIVE">Live payments</option><option value="TEST">Razorpay test</option><option value="DEV">Simulated (dev)</option><option value="">All modes</option>
            </Select>
            <Input type="date" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} title="From" />
            <Input type="date" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} title="To" />
            <Button variant="secondary" onClick={exportCsv} disabled={!data?.rows.length}><Download size={15} /> CSV</Button>
          </div>
          <Card className="overflow-x-auto">
            {!data ? <Loading /> : data.rows.length === 0 ? <p className="p-5 text-sm text-gray-500">No transactions match.</p> : (
              <table className="tbl">
                <thead><tr><th>When</th><th>Customer</th><th>For</th><th className="num">Amount</th><th>Status</th><th>Reference</th><th /></tr></thead>
                <tbody>
                  {data.rows.map((t) => (
                    <tr key={t.id} className="cursor-pointer hover:bg-gray-50" onClick={() => setOpenId(t.id)}>
                      <td className="whitespace-nowrap">{when(t.created_at)}</td>
                      <td>{t.owner_name}<div className="text-xs text-gray-500">{t.owner_email}{t.business_name ? ` · ${t.business_name}` : ""}</div></td>
                      <td>{t.item}</td>
                      <td className="num">{money(t.amount)}</td>
                      <td><TxnStatus t={t} />{t.error_reason && <div className="max-w-56 truncate text-xs text-red-700" title={t.error_reason}>{t.error_reason}</div>}</td>
                      <td className="font-mono text-xs">{t.receipt_no ?? t.payment_id ?? t.order_id}</td>
                      <td className="text-right"><Button variant="ghost" className="!py-1">Details</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {data && data.total > data.rows.length && <p className="px-5 py-3 text-xs text-gray-500">Showing the latest {data.rows.length} of {data.total} — narrow the dates or search.</p>}
          </Card>
        </>
      )}

      {view === "leads" && (
        <Card className="overflow-x-auto">
          <p className="px-5 pt-4 pb-2 text-sm text-gray-500">People whose last checkout (past 90 days) failed, was closed or never finished — and who have not paid since. Worth a call.</p>
          {!leads ? <Loading /> : leads.length === 0 ? <p className="p-5 text-sm text-gray-500">No open leads.</p> : (
            <table className="tbl">
              <thead><tr><th>Customer</th><th>Contact</th><th>Tried to buy</th><th>Last attempt</th><th className="num">Tries</th><th>Now on</th><th /></tr></thead>
              <tbody>
                {leads.map((l) => (
                  <tr key={l.id}>
                    <td>{l.owner_name}<div className="text-xs text-gray-500">{l.business_name ?? "—"} · joined {fmtDate(l.signed_up)}</div></td>
                    <td className="text-xs">
                      <a href={`mailto:${l.owner_email}`} className="text-brand-600 hover:underline">{l.owner_email}</a>
                      {l.owner_phone && <div><a href={`tel:+${l.owner_phone.replace(/\D/g, "")}`} className="inline-flex items-center gap-1 text-brand-600 hover:underline"><Phone size={11} /> {l.owner_phone}</a></div>}
                    </td>
                    <td>{l.item}<div className="text-xs text-gray-500">{money(l.amount)}</div></td>
                    <td className="whitespace-nowrap"><TxnStatus t={l} /><div className="text-xs text-gray-500">{when(l.created_at)}</div>
                      {l.error_reason && <div className="max-w-56 truncate text-xs text-red-700" title={l.error_reason}>{l.error_reason}</div>}</td>
                    <td className="num">{l.attempts}</td>
                    <td className="text-xs">{l.current_plan} · {l.current_status}{l.valid_until ? ` till ${fmtDate(l.valid_until)}` : ""}</td>
                    <td className="text-right"><Button variant="ghost" className="!py-1" onClick={() => setOpenId(l.id)}>Details</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {openId && <TxnDetail id={openId} onClose={() => setOpenId(null)} onOpen={setOpenId} />}
    </div>
  );
}

function TxnDetail({ id, onClose, onOpen }: { id: string; onClose: () => void; onOpen: (id: string) => void }) {
  const { data: d } = useFetch<Detail>(`/admin/payments/${id}`);
  return (
    <Modal title="Transaction" onClose={onClose}>
      {!d ? <Loading /> : (
        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div><div className="text-lg font-semibold">{money(d.amount)}</div><div className="text-gray-600">{d.item}</div></div>
            <TxnStatus t={d} />
          </div>
          {d.error_reason && <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-800">{d.error_code ? `${d.error_code}: ` : ""}{d.error_reason}</p>}
          <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1 text-xs">
            <dt className="text-gray-500">Customer</dt><dd>{d.owner_name} · {d.owner_email}{d.owner_phone ? ` · ${d.owner_phone}` : ""}</dd>
            <dt className="text-gray-500">Business</dt><dd>{d.business_name ?? "—"}</dd>
            <dt className="text-gray-500">Started</dt><dd>{when(d.created_at)}</dd>
            {d.paid_at && <><dt className="text-gray-500">Paid</dt><dd>{when(d.paid_at)}</dd></>}
            <dt className="text-gray-500">Taxable + GST</dt><dd>{money(d.taxable)} + {money(d.gst)} ({d.gst_rate}%)</dd>
            <dt className="text-gray-500">Order id</dt><dd className="font-mono">{d.order_id}</dd>
            {d.payment_id && <><dt className="text-gray-500">Payment id</dt><dd className="font-mono">{d.payment_id}</dd></>}
            {d.method && <><dt className="text-gray-500">Method</dt><dd>{d.method.toUpperCase()}</dd></>}
            {d.receipt_no && <><dt className="text-gray-500">Receipt</dt><dd className="font-mono">{d.receipt_no}</dd></>}
          </dl>
          <Link href={`/receipt/${d.id}`} target="_blank" className="inline-flex items-center gap-1.5 text-brand-600 hover:underline">
            <Receipt size={15} /> {d.status === "PAID" ? "Open receipt" : "Open payment details"}
          </Link>
          {d.account_history.length > 1 && (
            <div>
              <div className="mb-1 text-xs font-semibold text-gray-500 uppercase">This customer&apos;s other payments</div>
              <div className="max-h-56 overflow-y-auto rounded-lg border border-gray-100">
                {d.account_history.filter((h) => h.id !== d.id).map((h) => (
                  <button key={h.id} onClick={() => onOpen(h.id)} className="flex w-full items-center justify-between gap-2 border-b border-gray-50 px-3 py-2 text-left text-xs hover:bg-gray-50">
                    <span>{when(h.created_at)} · {h.item}</span><span className="flex items-center gap-2">{money(h.amount)} <TxnStatus t={h} /></span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
