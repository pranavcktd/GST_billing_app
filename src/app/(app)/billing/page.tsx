"use client";

import { Crown, PlusCircle } from "lucide-react";
import { useState } from "react";
import { type PlanOut, PlanCards } from "@/components/PlanCards";
import { Button, Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import { APP_NAME } from "@/lib/brand";

interface Status {
  plan: PlanOut & { businesses: number | null; users: number | null; api_quota: number; backup_mb: number; godowns: number | null; invoices_per_year: number | null };
  status: "TRIAL" | "ACTIVE" | "EXPIRED"; valid_until: string | null; extra_businesses: number; is_owner: boolean;
  usage: { invoices_this_month: number; invoices_this_year: number; businesses: number; users: number; godowns: number; api_calls_this_month: number; backup_mb: number };
  payments_live: boolean; dev_mode: boolean; test_mode: boolean;
  payments: { id: string; plan: string; cycle: string; amount: number; status: string; payment_id: string | null; mode: string | null; method: string | null; created_at: string }[];
}
interface Plans { plans: PlanOut[]; trial_days: number; addon: { code: string; name: string; yearly: number; yearly_with_gst: number } }
interface Order { order_id: string; amount: number; amount_paise: number; key_id: string | null; live: boolean; test_mode: boolean; business_name: string; email: string; phone: string | null }

declare global {
  interface Window { Razorpay?: new (opts: Record<string, unknown>) => { open: () => void } }
}

function loadRazorpay(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve();
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Could not load Razorpay — check your internet connection"));
    document.body.appendChild(s);
  });
}

function Meter({ label, used, cap, unit = "" }: { label: string; used: number; cap: number | null; unit?: string }) {
  const pct = cap ? Math.min(100, (used / cap) * 100) : 0;
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-600"><span>{label}</span><span className="tabular-nums">{used}{unit} / {cap === null ? "Unlimited" : `${cap}${unit}`}</span></div>
      <div className="mt-1 h-2 rounded-full bg-gray-100">
        <div className={`h-2 rounded-full ${pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : "bg-brand-500"}`} style={{ width: `${cap === null ? 4 : Math.max(pct, 2)}%` }} />
      </div>
    </div>
  );
}

export default function BillingPage() {
  const { refresh } = useAuth();
  const { data: st, error, reload } = useFetch<Status>("/billing/status");
  const { data: plans } = useFetch<Plans>("/billing/plans");
  const [cycle, setCycle] = useState<"MONTHLY" | "YEARLY">("YEARLY");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [now] = useState(() => Date.now());

  if (error) return <ErrorBox message={error} />;
  if (!st || !plans) return <Loading />;

  async function buy(plan: string, c: "MONTHLY" | "YEARLY") {
    setErr(null); setMsg(null);
    try {
      const order = await api<Order>("/billing/order", { body: { plan, cycle: c } });
      if (!order.live) {
        if (!confirm(`Local development: payments aren't configured.\nSimulate a successful payment of ${money(order.amount)}?`)) return;
        await api("/billing/verify", { body: { order_id: order.order_id, simulate: true } });
        setMsg("Plan activated (simulated payment).");
      } else {
        await loadRazorpay();
        await new Promise<void>((resolve, reject) => {
          const rzp = new window.Razorpay!({
            key: order.key_id, order_id: order.order_id, amount: order.amount_paise, currency: "INR",
            name: APP_NAME, description: `${plan} plan — ${c.toLowerCase()}`,
            prefill: { email: order.email, contact: order.phone ?? "" }, theme: { color: "#1f65bb" },
            handler: async (r: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => {
              try {
                await api("/billing/verify", { body: { order_id: r.razorpay_order_id, payment_id: r.razorpay_payment_id, signature: r.razorpay_signature } });
                resolve();
              } catch (e) { reject(e); }
            },
            modal: { ondismiss: () => reject(new Error("Payment was cancelled")) },
            notes: { plan, cycle: c },
          });
          (rzp as unknown as { on?: (ev: string, cb: (r: { error?: { description?: string } }) => void) => void }).on?.(
            "payment.failed", (r) => setErr(`Payment failed: ${r.error?.description ?? "please try again"}`));
          rzp.open();
        });
        setMsg("Payment successful — your plan is active.");
      }
      await refresh();
      reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  const p = st.plan;
  const daysLeft = st.valid_until ? Math.ceil((new Date(st.valid_until).getTime() - now) / 86400000) : null;

  return (
    <>
      <PageHeader title="Subscription" sub="One plan covers every business in your account" />
      <ErrorBox message={err} />
      {msg && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      <div className="mb-6 grid gap-5 lg:grid-cols-3">
        <Card className="p-5">
          <div className="flex items-center gap-2 text-sm text-gray-500"><Crown size={16} className="text-amber-500" /> Current plan</div>
          <div className="mt-1 text-2xl font-semibold text-gray-900">{p.name}</div>
          <div className="mt-1 text-sm">
            {st.status === "TRIAL" && <span className="rounded bg-brand-50 px-2 py-0.5 text-brand-700">Free trial · {daysLeft} day(s) left</span>}
            {st.status === "ACTIVE" && st.valid_until && <span className="text-gray-600">Renews / expires on {fmtDate(st.valid_until)}</span>}
            {st.status === "EXPIRED" && <span className="rounded bg-red-50 px-2 py-0.5 text-red-700">Paid plan expired — you are on Free</span>}
          </div>
          {st.dev_mode && <p className="mt-3 text-xs text-amber-700">Development mode: payments are simulated until Razorpay keys are configured.</p>}
          {st.test_mode && (
            <p className="mt-3 rounded-md bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
              <b>Razorpay TEST mode</b> — no real money is charged. Use UPI ID <code>success@razorpay</code> (or <code>failure@razorpay</code> to see a failure),
              or a Razorpay test card.
            </p>
          )}
          {!st.is_owner && <p className="mt-3 text-xs text-gray-500">Only the account owner can change the plan.</p>}
        </Card>
        <Card className="space-y-3 p-5 lg:col-span-2">
          <Meter label="Invoices this month" used={st.usage.invoices_this_month} cap={p.invoices_per_month} />
          {p.invoices_per_year !== null && <Meter label="Invoices this year" used={st.usage.invoices_this_year} cap={p.invoices_per_year} />}
          <div className="grid gap-3 sm:grid-cols-2">
            <Meter label="Businesses" used={st.usage.businesses} cap={p.businesses} />
            <Meter label="Users" used={st.usage.users} cap={p.users} />
            <Meter label="e-Invoice / e-way API calls (month)" used={st.usage.api_calls_this_month} cap={p.api_quota || null} />
            <Meter label="Cloud backup" used={st.usage.backup_mb} cap={p.backup_mb} unit=" MB" />
          </div>
        </Card>
      </div>

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Plans</h2>
        <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5 text-sm">
          {(["MONTHLY", "YEARLY"] as const).map((c) => (
            <button key={c} onClick={() => setCycle(c)} className={`rounded-md px-4 py-1.5 ${cycle === c ? "bg-brand-600 text-white" : "text-gray-700"}`}>
              {c === "MONTHLY" ? "Monthly" : "Yearly (save ~16%)"}
            </button>
          ))}
        </div>
      </div>
      <PlanCards plans={plans.plans} cycle={cycle} current={st.status === "TRIAL" ? undefined : p.code}
        onChoose={st.is_owner ? (pl) => buy(pl.code, cycle) : undefined} />

      {p.code === "ENTERPRISE" && st.status === "ACTIVE" && st.is_owner && (
        <Card className="mt-5 flex flex-wrap items-center justify-between gap-3 p-5">
          <div>
            <div className="font-semibold text-gray-900">{plans.addon.name}</div>
            <div className="text-sm text-gray-500">{money(plans.addon.yearly)}/year + GST · you have {st.extra_businesses} extra business slot(s)</div>
          </div>
          <Button onClick={() => buy(plans.addon.code, "YEARLY")}><PlusCircle size={16} /> Buy add-on</Button>
        </Card>
      )}

      {st.payments.length > 0 && (
        <Card className="mt-5 overflow-x-auto">
          <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Payment history</h2>
          <table className="tbl">
            <thead><tr><th>Date</th><th>Plan</th><th>Cycle</th><th className="num">Amount (incl. GST)</th><th>Status</th><th>Payment id</th></tr></thead>
            <tbody>
              {st.payments.map((x) => (
                <tr key={x.id}>
                  <td>{new Date(x.created_at).toLocaleDateString("en-IN")}</td><td>{x.plan}</td><td>{x.cycle}</td>
                  <td className="num">{money(x.amount)}</td><td>{x.status}{x.mode === "TEST" ? " · test" : x.mode === "DEV" ? " · simulated" : ""}{x.method ? ` · ${x.method}` : ""}</td><td className="font-mono text-xs">{x.payment_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
