"use client";

import { AlertTriangle, Banknote, Boxes, Landmark, Receipt } from "lucide-react";
import Link from "next/link";
import { TrendChart } from "@/components/TrendChart";
import { Card, ErrorBox, Loading, PageHeader, StatusBadge } from "@/components/ui";
import { KINDS, kindOf } from "@/lib/constants";
import { fmtDate, money, qty } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Voucher } from "@/lib/types";

interface Dashboard {
  inventory: { items: number; value: number; sale_value: number; low: number; out: number };
  cash_bank: { total: number; cheques_in: number; cheques_out: number; accounts: { id: string; name: string; type: string; balance: number }[] };
  expenses: { month: number; top: { category: string; amount: number }[] };
  sales_today: number; sales_month: number; purchases_month: number; received_month: number;
  receivable: number; payable: number;
  trend: { month: string; sales: number; purchases: number; expenses: number }[];
  low_stock: { id: string; name: string; stock: number; unit: string; level: number }[];
  recent: Voucher[];
}

function Tile({ label, value, href, sub }: { label: string; value: number; href?: string; sub?: string }) {
  const body = (
    <Card className="h-full p-4 transition-colors hover:border-gray-300">
      <div className="text-xs font-medium text-gray-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-gray-900 tabular-nums">{money(value)}</div>
      {sub && <div className="mt-0.5 text-xs text-gray-500">{sub}</div>}
    </Card>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

export default function DashboardPage() {
  const { data, error, loading } = useFetch<Dashboard>("/reports/dashboard");

  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox message={error} />;

  return (
    <>
      <PageHeader title="Dashboard" sub="Your business at a glance" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <Tile label="Sales today" value={data.sales_today} href="/v/sales" />
        <Tile label="Sales this month" value={data.sales_month} href="/v/sales" sub="net of credit notes" />
        <Tile label="Purchases this month" value={data.purchases_month} href="/v/purchases" />
        <Tile label="Received this month" value={data.received_month} href="/payments/in" />
        <Tile label="To collect" value={data.receivable} href="/reports/outstanding" sub="receivable" />
        <Tile label="To pay" value={data.payable} href="/reports/outstanding" sub="payable" />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card className="p-5">
          <h2 className="mb-3 flex items-center justify-between font-semibold text-gray-900">
            <span className="flex items-center gap-2"><Landmark size={16} className="text-gray-500" aria-hidden /> Cash & bank</span>
            <span className="tabular-nums">{money(data.cash_bank.total)}</span>
          </h2>
          <ul className="divide-y divide-gray-100 text-sm">
            {data.cash_bank.accounts.map((a) => (
              <li key={a.id} className="flex justify-between py-2">
                <span className="flex items-center gap-2 text-gray-700">
                  {a.type === "CASH" ? <Banknote size={14} aria-hidden /> : <Landmark size={14} aria-hidden />}{a.name}
                </span>
                <span className={`tabular-nums ${a.balance < 0 ? "text-red-700" : "text-gray-900"}`}>{money(a.balance)}</span>
              </li>
            ))}
          </ul>
          {(data.cash_bank.cheques_in > 0 || data.cash_bank.cheques_out > 0) && (
            <Link href="/cash-bank/cheques" className="mt-2 block text-xs text-brand-600 hover:underline">
              Open cheques: {money(data.cash_bank.cheques_in)} to receive · {money(data.cash_bank.cheques_out)} to pay
            </Link>
          )}
        </Card>
        <Card className="p-5">
          <h2 className="mb-3 flex items-center justify-between font-semibold text-gray-900">
            <span className="flex items-center gap-2"><Boxes size={16} className="text-gray-500" aria-hidden /> Inventory</span>
            <Link href="/reports/r/stock-summary" className="text-xs font-normal text-brand-600 hover:underline">Stock summary</Link>
          </h2>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-xs text-gray-500">Stock value (cost)</dt><dd className="font-semibold tabular-nums">{money(data.inventory.value)}</dd></div>
            <div><dt className="text-xs text-gray-500">At sale price</dt><dd className="font-semibold tabular-nums">{money(data.inventory.sale_value)}</dd></div>
            <div><dt className="text-xs text-gray-500">Items in stock list</dt><dd className="font-semibold">{data.inventory.items}</dd></div>
            <div>
              <dt className="text-xs text-gray-500">Low / out of stock</dt>
              <dd className="font-semibold">
                <Link href="/reports/r/low-stock" className={data.inventory.low + data.inventory.out ? "text-red-700 hover:underline" : ""}>
                  {data.inventory.low} low · {data.inventory.out} out
                </Link>
              </dd>
            </div>
          </dl>
        </Card>
        <Card className="p-5">
          <h2 className="mb-3 flex items-center justify-between font-semibold text-gray-900">
            <span className="flex items-center gap-2"><Receipt size={16} className="text-gray-500" aria-hidden /> Expenses this month</span>
            <span className="tabular-nums">{money(data.expenses.month)}</span>
          </h2>
          {data.expenses.top.length === 0 ? (
            <p className="text-sm text-gray-500">No expenses recorded this month. <Link href="/v/expenses/new" className="text-brand-600 hover:underline">Add expense</Link></p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.expenses.top.map((e) => (
                <li key={e.category}>
                  <div className="flex justify-between"><span className="text-gray-700">{e.category}</span><span className="tabular-nums">{money(e.amount)}</span></div>
                  <div className="mt-1 h-1.5 rounded-full bg-gray-100">
                    <div className="h-1.5 rounded-full bg-gray-400" style={{ width: `${Math.max(4, (e.amount / data.expenses.month) * 100)}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <h2 className="mb-3 font-semibold text-gray-900">Sales, purchases & expenses — last 6 months</h2>
          <TrendChart data={data.trend} />
        </Card>
        <Card className="p-5">
          <h2 className="mb-3 flex items-center gap-2 font-semibold text-gray-900">
            <AlertTriangle size={16} className="text-amber-600" aria-hidden /> Low stock
          </h2>
          {data.low_stock.length === 0 ? (
            <p className="text-sm text-gray-500">No items below their low-stock level.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {data.low_stock.map((i) => (
                <li key={i.id} className="flex justify-between py-2 text-sm">
                  <Link href={`/items/${i.id}`} className="text-gray-800 hover:underline">{i.name}</Link>
                  <span className="text-gray-700 tabular-nums">
                    {qty(i.stock)} {i.unit} <span className="text-gray-400">/ min {qty(i.level)}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card className="mt-5 overflow-x-auto">
        <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Recent activity</h2>
        {data.recent.length === 0 ? (
          <p className="px-5 pb-5 text-sm text-gray-500">No transactions yet — create your first sale invoice.</p>
        ) : (
          <table className="tbl">
            <thead>
              <tr><th>Date</th><th>Type</th><th>Number</th><th>Party</th><th className="num">Amount</th><th>Status</th></tr>
            </thead>
            <tbody>
              {data.recent.map((v) => {
                const k = kindOf(v.type);
                return (
                  <tr key={v.id}>
                    <td>{fmtDate(v.date)}</td>
                    <td>{KINDS[k].label}</td>
                    <td><Link href={`/v/${k}/${v.id}`} className="font-medium text-brand-600 hover:underline">{v.number}</Link></td>
                    <td>{v.party_name}</td>
                    <td className="num">{money(v.grand_total)}</td>
                    <td><StatusBadge status={v.status} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
