"use client";

import { AlertTriangle, ArrowDownLeft, ArrowUpRight, Banknote, Boxes, CalendarDays, HandCoins, Landmark, Receipt,
  ReceiptIndianRupee, ShoppingCart, Sparkles, TrendingUp, Wallet } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useAuth, usePerms } from "@/lib/auth";
import { TrendChart } from "@/components/TrendChart";
import { Card, ErrorBox, Loading, StatusBadge } from "@/components/ui";
import { KINDS, kindOf } from "@/lib/constants";
import { fmtDate, money, qty } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import { ComplianceAlert } from "@/components/ComplianceAlert";
import { EinvoiceAlert } from "@/components/EinvoiceAlert";
import { RateNotices } from "@/components/RateNotices";
import type { Voucher } from "@/lib/types";

interface Dashboard {
  inventory: { items: number; value: number | null; sale_value: number; low: number; out: number; negative?: number };
  cash_bank: { total: number; cheques_in: number; cheques_out: number; accounts: { id: string; name: string; type: string; balance: number }[] } | null;
  expenses: { month: number; top: { category: string; amount: number }[] } | null;
  sales_today: number | null; sales_month: number | null; purchases_month: number | null; received_month: number | null;
  receivable: number | null; payable: number | null;
  trend: { month: string; sales: number; purchases: number | null; expenses: number | null }[];
  low_stock: { id: string; name: string; stock: number; unit: string; level: number }[];
  recent: Voucher[];
}

const TONES = {
  indigo: "from-indigo-500 to-violet-500 shadow-indigo-500/30", emerald: "from-emerald-500 to-teal-500 shadow-emerald-500/30",
  amber: "from-amber-400 to-orange-500 shadow-amber-500/30", sky: "from-sky-500 to-cyan-500 shadow-sky-500/30",
  rose: "from-rose-500 to-pink-500 shadow-rose-500/30", slate: "from-slate-600 to-slate-800 shadow-slate-500/30",
};

function Tile({ label, value, href, sub, icon: Icon, tone }: {
  label: string; value: number | null; href?: string; sub?: string; icon: React.ElementType; tone: keyof typeof TONES;
}) {
  if (value === null) return null;
  const body = (
    <Card className="group h-full p-4 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-indigo-100">
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs font-medium text-gray-500">{label}</div>
        <span className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-md ${TONES[tone]}`}>
          <Icon size={16} aria-hidden />
        </span>
      </div>
      <div className="mt-1 text-xl font-semibold tracking-tight text-gray-900 tabular-nums">{money(value)}</div>
      {sub && <div className="mt-0.5 text-xs text-gray-500">{sub}</div>}
    </Card>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

function Welcome({ salesToday }: { salesToday: number | null }) {
  const { me, business } = useAuth();
  const { can } = usePerms();
  const [now] = useState(() => new Date());
  const h = now.getHours();
  const hello = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  const first = (me?.user.name ?? "").split(" ")[0];
  const actions = [
    { href: "/v/sales/new", label: "New sale", icon: ReceiptIndianRupee, ok: can("sales", "create") },
    { href: "/v/purchases/new", label: "Purchase", icon: ShoppingCart, ok: can("purchases", "create") },
    { href: "/payments/in", label: "Receive payment", icon: HandCoins, ok: can("payments_in", "create") },
    { href: "/v/expenses/new", label: "Add expense", icon: Wallet, ok: can("expenses", "create") },
  ].filter((a) => a.ok);
  return (
    <div className="relative mb-5 overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 via-violet-600 to-indigo-800 p-5 text-white shadow-xl shadow-indigo-500/20 sm:p-7">
      <div aria-hidden className="pointer-events-none absolute -top-16 -right-10 h-56 w-56 rounded-full bg-amber-300/25 blur-3xl" />
      <div aria-hidden className="pointer-events-none absolute -bottom-20 left-1/3 h-56 w-56 rounded-full bg-sky-400/20 blur-3xl" />
      <div className="relative flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="flex items-center gap-1.5 text-sm text-indigo-100"><CalendarDays size={15} aria-hidden />
            {now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">{hello}{first ? `, ${first}` : ""}</h1>
          <p className="mt-1 text-sm text-indigo-100">{business?.name}{salesToday !== null ? <> · Sales today <b className="text-white">{money(salesToday)}</b></> : null}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {actions.map(({ href, label, icon: Icon }) => (
            <Link key={label} href={href} className="inline-flex items-center gap-1.5 rounded-xl bg-white/15 px-3.5 py-2 text-sm font-medium ring-1 ring-white/25 backdrop-blur transition hover:bg-white/25">
              <Icon size={16} aria-hidden /> {label}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function CardTitle({ icon: Icon, tone, children, right }: { icon: React.ElementType; tone: keyof typeof TONES; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <h2 className="mb-3 flex items-center justify-between gap-2 font-semibold text-gray-900">
      <span className="flex items-center gap-2">
        <span className={`inline-flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br text-white ${TONES[tone]}`}><Icon size={14} aria-hidden /></span>
        {children}
      </span>
      {right}
    </h2>
  );
}

export default function DashboardPage() {
  const { data, error, loading } = useFetch<Dashboard>("/reports/dashboard");

  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox message={error} />;

  return (
    <>
      <Welcome salesToday={data.sales_today} />
      <ComplianceAlert />
      <EinvoiceAlert />
      <RateNotices />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <Tile label="Sales today" value={data.sales_today} href="/v/sales" icon={Sparkles} tone="indigo" />
        <Tile label="Sales this month" value={data.sales_month} href="/v/sales" sub="net of credit notes" icon={TrendingUp} tone="emerald" />
        <Tile label="Purchases this month" value={data.purchases_month} href="/v/purchases" icon={ShoppingCart} tone="sky" />
        <Tile label="Received this month" value={data.received_month} href="/payments/in" icon={HandCoins} tone="slate" />
        <Tile label="To collect" value={data.receivable} href="/reports/outstanding" sub="receivable" icon={ArrowDownLeft} tone="amber" />
        <Tile label="To pay" value={data.payable} href="/reports/outstanding" sub="payable" icon={ArrowUpRight} tone="rose" />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        {data.cash_bank && <Card className="p-5">
          <CardTitle icon={Landmark} tone="indigo" right={<span className="tabular-nums">{money(data.cash_bank.total)}</span>}>Cash & bank</CardTitle>
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
        </Card>}
        <Card className="p-5">
          <CardTitle icon={Boxes} tone="sky" right={<Link href="/reports/r/stock-summary" className="text-xs font-normal text-brand-600 hover:underline">Stock summary</Link>}>Inventory</CardTitle>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-xs text-gray-500">Stock value (cost)</dt><dd className="font-semibold tabular-nums">{data.inventory.value === null ? "—" : money(data.inventory.value)}</dd></div>
            <div><dt className="text-xs text-gray-500">At sale price</dt><dd className="font-semibold tabular-nums">{money(data.inventory.sale_value)}</dd></div>
            <div><dt className="text-xs text-gray-500">Items in stock list</dt><dd className="font-semibold">{data.inventory.items}</dd></div>
            <div>
              <dt className="text-xs text-gray-500">Low / out of stock</dt>
              <dd className="font-semibold">
                <Link href="/reports/r/low-stock" className={data.inventory.low + data.inventory.out ? "text-red-700 hover:underline" : ""}>
                  {data.inventory.low} low · {data.inventory.out} out{data.inventory.negative ? ` (${data.inventory.negative} below zero)` : ""}
                </Link>
              </dd>
            </div>
          </dl>
        </Card>
        {data.expenses && <Card className="p-5">
          <CardTitle icon={Receipt} tone="rose" right={<span className="tabular-nums">{money(data.expenses.month)}</span>}>Expenses this month</CardTitle>
          {data.expenses.top.length === 0 ? (
            <p className="text-sm text-gray-500">No expenses recorded this month. <Link href="/v/expenses/new" className="text-brand-600 hover:underline">Add expense</Link></p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.expenses.top.map((e) => (
                <li key={e.category}>
                  <div className="flex justify-between"><span className="text-gray-700">{e.category}</span><span className="tabular-nums">{money(e.amount)}</span></div>
                  <div className="mt-1 h-1.5 rounded-full bg-gray-100">
                    <div className="h-1.5 rounded-full bg-gradient-to-r from-rose-400 to-pink-500" style={{ width: `${Math.max(4, (e.amount / (data.expenses?.month || 1)) * 100)}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>}
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <CardTitle icon={TrendingUp} tone="emerald">Sales, purchases & expenses — last 6 months</CardTitle>
          {data.trend.length ? <TrendChart data={data.trend.map((t) => ({ ...t, purchases: t.purchases ?? 0, expenses: t.expenses ?? 0 }))} /> : <p className="text-sm text-gray-500">Not available for your role.</p>}
        </Card>
        <Card className="p-5">
          <CardTitle icon={AlertTriangle} tone="amber">Low stock</CardTitle>
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
