"use client";

import { Copy, CreditCard, PlugZap, Save } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

type Mode = "TEST" | "LIVE";
interface Side { key_id: string | null; key_secret_set: boolean; webhook_secret_set: boolean }
interface Data {
  settings: { mode: Mode; TEST: Side; LIVE: Side; active: { mode: Mode; key_id: string; source: "admin" | "env"; webhook: boolean } | null };
  webhook_url: string;
  payments: { id: string; account: string; plan: string; cycle: string; amount: number; status: string; mode: string; method: string | null; payment_id: string | null; created_at: string }[];
}
type Draft = Record<Mode, { key_id?: string; key_secret?: string; webhook_secret?: string }>;

const MODE_BADGE: Record<string, string> = { LIVE: "bg-emerald-50 text-emerald-700", TEST: "bg-amber-50 text-amber-800", DEV: "bg-gray-100 text-gray-600" };

/** Razorpay keys (Test and Live) for subscription payments, the webhook to register, and payments received. */
export function AdminRazorpay() {
  const { data, setData } = useFetch<Data>("/admin/razorpay");
  const [draft, setDraft] = useState<Draft>({ TEST: {}, LIVE: {} });
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [test, setTest] = useState<string | null>(null);
  if (!data) return <Loading />;
  const s = data.settings;

  async function save(body: Record<string, unknown>) {
    setErr(null); setMsg(null);
    try {
      setData(await api<Data>("/admin/razorpay", { method: "PUT", body }));
      setDraft({ TEST: {}, LIVE: {} });
      setMsg("Saved.");
    } catch (e) { setErr((e as Error).message); }
  }

  async function testConn() {
    setTest("Testing…");
    try {
      const r = await api<{ ok: boolean; mode?: string; key_id?: string; error?: string }>("/admin/razorpay/test", { body: {} });
      setTest(r.ok ? `Connected to Razorpay (${r.mode} mode, ${r.key_id}).` : `Failed: ${r.error}`);
    } catch (e) { setTest((e as Error).message); }
  }

  const keyFields = (m: Mode) => {
    const side = s[m];
    const d = draft[m];
    const set = (k: keyof Draft[Mode], v: string) => setDraft({ ...draft, [m]: { ...d, [k]: v } });
    return (
      <div className={`rounded-lg border p-4 ${s.mode === m ? "border-brand-300 bg-brand-50/30" : "border-gray-200"}`}>
        <div className="mb-3 flex items-center justify-between">
          <span className={`rounded px-2 py-0.5 text-xs font-semibold ${MODE_BADGE[m]}`}>{m === "TEST" ? "Test mode (sandbox)" : "Live mode (real money)"}</span>
          {s.mode === m && <span className="text-xs font-medium text-brand-700">In use</span>}
        </div>
        <div className="space-y-3">
          <Field label="Key ID" hint={m === "TEST" ? "Starts with rzp_test_" : "Starts with rzp_live_"}>
            <Input placeholder={side.key_id ?? (m === "TEST" ? "rzp_test_…" : "rzp_live_…")} value={d.key_id ?? ""} onChange={(e) => set("key_id", e.target.value.trim())} />
          </Field>
          <Field label="Key secret" hint={side.key_secret_set ? "Saved — type a new one to replace it" : "Shown once when you generate the key"}>
            <Input type="password" autoComplete="off" placeholder={side.key_secret_set ? "•••••••• (unchanged)" : ""} value={d.key_secret ?? ""} onChange={(e) => set("key_secret", e.target.value)} />
          </Field>
          <Field label="Webhook secret (optional)" hint={side.webhook_secret_set ? "Saved — type a new one to replace it" : "The secret you type when creating the webhook"}>
            <Input type="password" autoComplete="off" placeholder={side.webhook_secret_set ? "•••••••• (unchanged)" : ""} value={d.webhook_secret ?? ""} onChange={(e) => set("webhook_secret", e.target.value)} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!Object.values(d).some(Boolean)} onClick={() => save({ [m]: d })}><Save size={14} /> Save {m.toLowerCase()} keys</Button>
            {(side.key_id || side.key_secret_set) && <Button variant="ghost" onClick={() => confirm(`Remove the ${m.toLowerCase()} keys?`) && save({ [m]: { clear: true } })}>Remove</Button>}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="mb-1 flex items-center gap-2 font-semibold text-gray-900"><CreditCard size={18} /> Razorpay — subscription payments</div>
        <p className="mb-4 text-sm text-gray-600">
          Customers pay for plans through Razorpay Checkout. Use <b>Test mode</b> keys to try the full flow without real money, then switch to Live.
          Test payments are marked TEST and never count as revenue.
        </p>
        <ErrorBox message={err} />
        {msg && <div className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}

        <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
          <span className="text-gray-600">Mode in use:</span>
          <div className="inline-flex rounded-lg border border-gray-200 p-0.5">
            {(["TEST", "LIVE"] as Mode[]).map((m) => (
              <button key={m} onClick={() => m !== s.mode && (m === "TEST" || confirm("Switch to LIVE? Customers will be charged real money.")) && save({ mode: m })}
                className={`rounded-md px-4 py-1.5 ${s.mode === m ? (m === "LIVE" ? "bg-emerald-600 text-white" : "bg-amber-500 text-white") : "text-gray-700"}`}>
                {m === "TEST" ? "Test" : "Live"}
              </button>
            ))}
          </div>
          <span className="text-xs text-gray-500">
            {s.active ? <>Active: <b>{s.active.mode}</b> · {s.active.key_id}{s.active.source === "env" ? " (from backend .env)" : ""}{s.active.webhook ? " · webhook secret set" : " · no webhook secret"}</>
              : "No keys for this mode — payments are simulated in local development."}
          </span>
          <Button variant="secondary" disabled={!s.active} onClick={testConn}><PlugZap size={14} /> Test connection</Button>
        </div>
        {test && <p className="mb-4 text-xs text-gray-600">{test}</p>}

        <div className="grid gap-4 lg:grid-cols-2">{keyFields("TEST")}{keyFields("LIVE")}</div>

        <div className="mt-5 rounded-lg bg-gray-50 p-4 text-sm text-gray-700">
          <div className="font-medium text-gray-900">Webhook (recommended)</div>
          <p className="mt-1 text-xs">In the Razorpay Dashboard → Accounts &amp; Settings → Webhooks → Add new webhook, use this URL, choose a secret,
            and tick the events <b>payment.captured</b> and <b>order.paid</b>. It activates the plan even if the customer closes the browser before returning.</p>
          <div className="mt-2 flex items-center gap-2">
            <code className="flex-1 truncate rounded bg-white px-2 py-1 text-xs">{data.webhook_url}</code>
            <Button variant="ghost" className="!px-2 !py-1" onClick={() => navigator.clipboard.writeText(data.webhook_url)} title="Copy"><Copy size={14} /></Button>
          </div>
          <p className="mt-2 text-xs text-gray-500">Razorpay can only reach a public https address. On localhost the webhook will not arrive — that is fine for testing, because the
            checkout is confirmed directly with Razorpay when the customer returns. Set APP_URL in backend/.env to your public address after deployment.</p>
        </div>
      </Card>

      <Card className="overflow-x-auto">
        <h2 className="px-5 pt-4 pb-2 font-semibold">Recent subscription payments</h2>
        {data.payments.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">None yet.</p> : (
          <table className="tbl">
            <thead><tr><th>When</th><th>Account</th><th>Plan</th><th className="num">Amount</th><th>Status</th><th>Mode</th><th>Method</th><th>Payment ID</th></tr></thead>
            <tbody>
              {data.payments.map((p) => (
                <tr key={p.id}>
                  <td className="whitespace-nowrap text-xs">{new Date(p.created_at).toLocaleString("en-IN")}</td>
                  <td className="text-xs">{p.account}</td>
                  <td className="text-xs">{p.plan} · {p.cycle.toLowerCase()}</td>
                  <td className="num">{money(p.amount)}</td>
                  <td className={`text-xs ${p.status === "PAID" ? "text-emerald-700" : p.status === "FAILED" ? "text-red-700" : "text-gray-500"}`}>{p.status}</td>
                  <td><span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${MODE_BADGE[p.mode] ?? ""}`}>{p.mode}</span></td>
                  <td className="text-xs">{p.method ?? ""}</td>
                  <td className="font-mono text-[11px]">{p.payment_id ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
