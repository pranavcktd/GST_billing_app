"use client";

import { Coins, Crown, PlusCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { type Cycle, type PlanOut, CycleToggle, PlanCards } from "@/components/PlanCards";
import { MyTransactions, type Txn } from "@/components/Transactions";
import { Button, Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import { APP_NAME } from "@/lib/brand";
import { trackEvent } from "@/lib/track";

interface Status {
  plan: PlanOut & { businesses: number | null; users: number | null; api_quota: number; backup_mb: number; godowns: number | null; invoices_per_year: number | null };
  status: "TRIAL" | "ACTIVE" | "EXPIRED"; valid_until: string | null; extra_businesses: number; is_owner: boolean;
  usage: { invoices_this_month: number; invoices_this_year: number; businesses: number; users: number; godowns: number; api_calls_this_month: number; backup_mb: number };
  payments_live: boolean; dev_mode: boolean; test_mode: boolean;
  payments: Txn[];
}
interface Plans { plans: PlanOut[]; cycles?: Cycle[]; trial_days: number; addon: { code: string; name: string; yearly: number; yearly_with_gst: number } }
interface Credits {
  allowance: number; used_this_month: number; free_left: number; balance: number; api_enabled: boolean;
  costs: Record<string, number>; actions: Record<string, string>;
  packs: { credits: number; price: number; price_with_gst: number }[];
  history: { at: string; kind: string; action: string | null; units: number; delta: number; from_pack: number; ref: string | null; note: string | null }[];
}
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
  const { data: credits, reload: reloadCredits } = useFetch<Credits>("/billing/credits");
  const [cycle, setCycle] = useState<string>("YEARLY");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [now] = useState(() => Date.now());
  useEffect(() => { trackEvent("PRICING_VIEW"); }, []);  // existing users exploring plans (Admin → Analytics)

  if (error) return <ErrorBox message={error} />;
  if (!st || !plans) return <Loading />;

  async function buy(plan: string, c: string) {
    setErr(null); setMsg(null);
    trackEvent("PLAN_CLICK", { plan, cycle: c });
    try {
      const order = await api<Order>("/billing/order", { body: { plan, cycle: c } });
      if (!order.live) {
        if (!confirm(`Local development: payments aren't configured.\nSimulate a successful payment of ${money(order.amount)}?`)) return;
        await api("/billing/verify", { body: { order_id: order.order_id, simulate: true } });
        setMsg(plan.startsWith("CREDITS_") ? "Credits added (simulated payment)." : "Plan activated (simulated payment).");
      } else {
        await loadRazorpay();
        await new Promise<void>((resolve, reject) => {
          const rzp = new window.Razorpay!({
            key: order.key_id, order_id: order.order_id, amount: order.amount_paise, currency: "INR",
            name: APP_NAME, description: plan.startsWith("CREDITS_") ? `${plan.slice(8)} API credits` : `${plan} plan — ${c.startsWith("YEARS_") ? `${c.slice(6)} years` : c.toLowerCase()}`,
            prefill: { email: order.email, contact: order.phone ?? "" }, theme: { color: "#b8532a" },
            handler: async (r: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => {
              try {
                await api("/billing/verify", { body: { order_id: r.razorpay_order_id, payment_id: r.razorpay_payment_id, signature: r.razorpay_signature } });
                resolve();
              } catch (e) { reject(e); }
            },
            modal: { ondismiss: () => {
              api("/billing/failed", { body: { order_id: order.order_id, cancelled: true } }).catch(() => undefined).finally(reload);
              reject(new Error("Payment was cancelled"));
            } },
            notes: { plan, cycle: c },
          });
          type Failure = { error?: { code?: string; description?: string; reason?: string; metadata?: { payment_id?: string } } };
          (rzp as unknown as { on?: (ev: string, cb: (r: Failure) => void) => void }).on?.("payment.failed", (r) => {
            setErr(`Payment failed: ${r.error?.description ?? "please try again"}`);
            api("/billing/failed", { body: { order_id: order.order_id, payment_id: r.error?.metadata?.payment_id ?? null,
              code: r.error?.code ?? null, reason: r.error?.description ?? r.error?.reason ?? null } }).catch(() => undefined).finally(reload);
          });
          rzp.open();
        });
        setMsg(plan.startsWith("CREDITS_") ? "Payment successful — credits added." : "Payment successful — your plan is active.");
      }
      await refresh();
      reload();
      reloadCredits();
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
            <Meter label="API credits included (month)" used={Math.min(st.usage.api_calls_this_month, p.api_quota)} cap={p.api_quota} />
            <Meter label="Cloud backup" used={st.usage.backup_mb} cap={p.backup_mb} unit=" MB" />
          </div>
        </Card>
      </div>

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Plans</h2>
        <CycleToggle cycles={plans.cycles} value={cycle} onChange={(c) => { setCycle(c); trackEvent("CYCLE", { cycle: c }); }} />
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

      {credits?.api_enabled && (
        <div id="credits" className="scroll-mt-20"><Card className="mt-5 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="flex items-center gap-2 font-semibold text-gray-900"><Coins size={18} className="text-amber-500" /> API credits</h2>
              <p className="mt-1 max-w-xl text-sm text-gray-500">
                Used when the app talks to the government portals for you: {Object.entries(credits.actions).map(([k, v]) => `${v} — ${credits.costs[k]} credit${credits.costs[k] === 1 ? "" : "s"}`).join(" · ")}.
                Your plan&apos;s monthly credits are used first, then prepaid credits. Failed or test-mode calls are free.
              </p>
            </div>
            <div className="flex gap-6 text-center">
              <div><div className="text-2xl font-semibold tabular-nums text-gray-900">{credits.free_left}</div><div className="text-xs text-gray-500">of {credits.allowance} left this month</div></div>
              <div><div className="text-2xl font-semibold tabular-nums text-brand-700">{credits.balance}</div><div className="text-xs text-gray-500">prepaid (never expire)</div></div>
            </div>
          </div>
          {st.is_owner && credits.packs.length > 0 && (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {credits.packs.map((pk) => (
                <button key={pk.credits} onClick={() => buy(`CREDITS_${pk.credits}`, "YEARLY")}
                  className="rounded-xl border border-gray-200 p-4 text-left transition hover:border-brand-400 hover:shadow-sm">
                  <div className="text-lg font-semibold text-gray-900">{pk.credits.toLocaleString("en-IN")} credits</div>
                  <div className="text-sm text-gray-600">{money(pk.price)} + GST <span className="text-xs text-gray-400">· ₹{(pk.price / pk.credits).toFixed(2)} each</span></div>
                  <div className="mt-2 text-xs font-medium text-brand-700">Buy now →</div>
                </button>
              ))}
            </div>
          )}
          {credits.history.length > 0 && (
            <details className="mt-4">
              <summary className="cursor-pointer text-sm text-gray-600">Recent use</summary>
              <div className="mt-2 overflow-x-auto">
                <table className="tbl">
                  <thead><tr><th>When</th><th>What</th><th>Reference</th><th className="num">Credits</th><th>From</th></tr></thead>
                  <tbody>
                    {credits.history.map((h, i) => (
                      <tr key={i}>
                        <td>{new Date(h.at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</td>
                        <td>{h.kind === "USE" ? credits.actions[h.action ?? ""] ?? h.action : h.note ?? "Credits added"}</td>
                        <td className="font-mono text-xs">{h.ref}</td>
                        <td className={`num ${h.delta > 0 ? "text-emerald-700" : ""}`}>{h.delta > 0 ? `+${h.delta}` : h.delta}</td>
                        <td className="text-xs text-gray-500">{h.kind !== "USE" ? "" : h.from_pack === 0 ? "monthly" : h.from_pack === h.units ? "prepaid" : "monthly + prepaid"}{h.kind === "USE" && h.note ? ` · ${h.note}` : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </Card></div>
      )}

      {st.is_owner && (
        <div id="transactions" className="scroll-mt-20"><Card className="mt-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pt-4 pb-2">
            <h2 className="font-semibold text-gray-900">Transactions</h2>
            <span className="text-xs text-gray-500">Every payment attempt — successful, failed or not completed. Open a paid one for its receipt.</span>
          </div>
          <MyTransactions rows={st.payments} />
        </Card></div>
      )}
    </>
  );
}
