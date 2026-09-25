"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { PlatformShell } from "@/components/PlatformShell";
import { SmtpForm } from "@/components/SmtpForm";
import { AdminAudit } from "@/components/admin/AdminAudit";
import { AdminBackups } from "@/components/admin/AdminBackups";
import { AdminBusinesses } from "@/components/admin/AdminBusinesses";
import { AdminConfig } from "@/components/admin/AdminConfig";
import { AdminHsnMaster } from "@/components/admin/AdminHsnMaster";
import { AdminIntegrations } from "@/components/admin/AdminIntegrations";
import { AdminPlanConfig } from "@/components/admin/AdminPlanConfig";
import { AdminRateNotices } from "@/components/admin/AdminRateNotices";
import { AdminHierarchy } from "@/components/admin/AdminHierarchy";
import { AdminUsers } from "@/components/admin/AdminUsers";
import { Button, Card, ErrorBox, Field, Input, Loading, Select, Textarea } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Stats { accounts: number; businesses: number; users: number; trials: number; by_plan: Record<string, number>; mrr: number; invoices_30d: number; signups_30d: number; revenue_30d: number }
interface Account {
  account_id: string; name: string; email: string; phone: string | null; active: boolean; created_at: string; plan: string;
  status: string; valid_until: string | null; extra_businesses: number; feature_flags: Record<string, unknown>;
  businesses: { id: string; name: string; gstin: string | null }[]; users: number; invoices_this_month: number; reseller: string | null;
}
interface Reseller { id: string; name: string; email: string; commission_pct: number; accounts: number; sales: number; commission_due: number }
interface License { id: string; created_at: string; reseller: string; account: string; plan: string; months: number; amount: number; commission: number; payout_status: string }
interface Health { app_env: string; database: boolean; database_engine: string; einvoice_provider: string; gsp_configured: boolean; razorpay_live: boolean; razorpay_webhook: boolean; email_configured: boolean; cloudinary_configured: boolean }

const TABS = ["Overview", "Users", "Hierarchy", "Plans", "Businesses", "Resellers", "Payouts", "GST config", "HSN master", "Rate notices", "Pricing", "Integrations", "Backups", "Audit", "Email", "System"] as const;

export default function AdminPage() {
  return <PlatformShell need="SUPERADMIN"><Admin /></PlatformShell>;
}

function Admin() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [search, setSearch] = useState("");
  const { data: stats } = useFetch<Stats>("/admin/stats");
  const { data: accounts, reload: reloadAcc } = useFetch<Account[]>(tab === "Plans" ? `/admin/accounts${qs({ search })}` : null);
  const { data: resellers, reload: reloadRes } = useFetch<Reseller[]>(tab === "Resellers" ? "/admin/resellers" : null);
  const { data: licenses, reload: reloadLic } = useFetch<License[]>(tab === "Payouts" ? "/admin/licenses" : null);
  const { data: health } = useFetch<Health>(tab === "System" ? "/admin/health" : null);
  const [edit, setEdit] = useState<(Account & { flagsText: string }) | null>(null);
  const [newRes, setNewRes] = useState({ email: "", commission_pct: "20" });
  const [err, setErr] = useState<string | null>(null);

  const run = async (fn: () => Promise<unknown>, after: () => void) => {
    setErr(null);
    try { await fn(); after(); return true; } catch (e) { setErr((e as Error).message); return false; }
  };

  return (
    <>
      <div className="mb-5 flex flex-wrap gap-1 rounded-lg border border-gray-200 bg-white p-1 text-sm">
        {TABS.map((t) => <button key={t} onClick={() => setTab(t)} className={`rounded-md px-4 py-1.5 ${tab === t ? "bg-brand-600 text-white" : "text-gray-700"}`}>{t}</button>)}
      </div>
      <ErrorBox message={err} />

      {tab === "Overview" && (!stats ? <Loading /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[["Accounts", stats.accounts], ["Businesses", stats.businesses], ["Users", stats.users], ["On trial", stats.trials]].map(([l, v]) => (
              <Card key={l} className="p-4"><div className="text-xs text-gray-500">{l}</div><div className="mt-1 text-2xl font-semibold">{v}</div></Card>
            ))}
            <Card className="p-4"><div className="text-xs text-gray-500">MRR (paid plans)</div><div className="mt-1 text-2xl font-semibold">{money(stats.mrr)}</div></Card>
            <Card className="p-4"><div className="text-xs text-gray-500">Revenue, last 30 days</div><div className="mt-1 text-2xl font-semibold">{money(stats.revenue_30d)}</div></Card>
            <Card className="p-4"><div className="text-xs text-gray-500">Invoices billed, 30 days</div><div className="mt-1 text-2xl font-semibold">{stats.invoices_30d}</div></Card>
            <Card className="p-4"><div className="text-xs text-gray-500">Sign-ups, 30 days</div><div className="mt-1 text-2xl font-semibold">{stats.signups_30d}</div></Card>
          </div>
          <Card className="mt-5 overflow-x-auto">
            <h2 className="px-5 pt-4 pb-2 font-semibold">Accounts by plan</h2>
            <table className="tbl"><tbody>{Object.entries(stats.by_plan).map(([p, n]) => <tr key={p}><td>{p}</td><td className="num">{n}</td></tr>)}</tbody></table>
          </Card>
        </>
      ))}

      {tab === "Users" && <AdminUsers />}
      {tab === "Hierarchy" && <AdminHierarchy />}
      {tab === "Businesses" && <AdminBusinesses />}
      {tab === "GST config" && <AdminConfig />}
      {tab === "HSN master" && <AdminHsnMaster />}
      {tab === "Rate notices" && <AdminRateNotices />}
      {tab === "Pricing" && <AdminPlanConfig />}
      {tab === "Integrations" && <AdminIntegrations />}
      {tab === "Backups" && <AdminBackups />}
      {tab === "Audit" && <AdminAudit />}
      {tab === "Email" && (
        <SmtpForm base="/admin/smtp" title="Platform e-mail"
          help="Used for system e-mails — password resets, new account details — and as the fallback for resellers and businesses that have not set up their own." />
      )}

      {tab === "Plans" && (
        <>
          <Input placeholder="Search name, email, phone" value={search} onChange={(e) => setSearch(e.target.value)} className="mb-3 max-w-xs" />
          <Card className="overflow-x-auto">
            {!accounts ? <Loading /> : (
              <table className="tbl">
                <thead><tr><th>Account owner</th><th>Businesses</th><th>Plan</th><th>Valid till</th><th className="num">Users</th><th className="num">Invoices (month)</th><th>Reseller</th><th /></tr></thead>
                <tbody>
                  {accounts.map((a) => (
                    <tr key={a.account_id} className={a.active ? "" : "text-gray-400"}>
                      <td>{a.name}<div className="text-xs text-gray-500">{a.email}{a.phone ? ` · ${a.phone}` : ""}</div></td>
                      <td className="text-xs">{a.businesses.map((b) => b.name).join(", ") || "—"}</td>
                      <td>{a.plan}<div className="text-xs text-gray-500">{a.status}{a.extra_businesses ? ` · +${a.extra_businesses} biz` : ""}</div></td>
                      <td>{fmtDate(a.valid_until)}</td>
                      <td className="num">{a.users}</td>
                      <td className="num">{a.invoices_this_month}</td>
                      <td>{a.reseller ?? ""}</td>
                      <td className="whitespace-nowrap text-right">
                        <Button variant="secondary" className="!py-1" onClick={() => setEdit({ ...a, flagsText: JSON.stringify(a.feature_flags ?? {}, null, 1) })}>Manage</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </>
      )}

      {tab === "Resellers" && (
        <>
          <Card className="mb-4 p-4">
            <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); run(() => api("/admin/resellers", { body: { email: newRes.email, commission_pct: Number(newRes.commission_pct) } }), () => { setNewRes({ ...newRes, email: "" }); reloadRes(); }); }}>
              <Field label="Make a registered user a reseller"><Input type="email" required placeholder="partner@email.com" value={newRes.email} onChange={(e) => setNewRes({ ...newRes, email: e.target.value })} /></Field>
              <Field label="Commission %"><Input type="number" min={0} max={90} value={newRes.commission_pct} onChange={(e) => setNewRes({ ...newRes, commission_pct: e.target.value })} className="!w-24" /></Field>
              <Button type="submit">Add reseller</Button>
            </form>
          </Card>
          <Card className="overflow-x-auto">
            {!resellers ? <Loading /> : (
              <table className="tbl">
                <thead><tr><th>Reseller</th><th className="num">Commission</th><th className="num">Accounts</th><th className="num">Sales</th><th className="num">Commission due</th><th /></tr></thead>
                <tbody>
                  {resellers.map((r) => (
                    <tr key={r.id}>
                      <td>{r.name}<div className="text-xs text-gray-500">{r.email}</div></td>
                      <td className="num">{r.commission_pct}%</td><td className="num">{r.accounts}</td>
                      <td className="num">{money(r.sales)}</td><td className="num">{money(r.commission_due)}</td>
                      <td className="text-right"><Button variant="danger" className="!py-1" onClick={() => confirm(`Remove ${r.name} as reseller?`) && run(() => api(`/admin/resellers/${r.id}`, { method: "DELETE" }), reloadRes)}>Remove</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </>
      )}

      {tab === "Payouts" && (
        <Card className="overflow-x-auto">
          {!licenses ? <Loading /> : (
            <table className="tbl">
              <thead><tr><th>Date</th><th>Reseller</th><th>Account</th><th>Plan</th><th className="num">Amount</th><th className="num">Commission</th><th>Payout</th></tr></thead>
              <tbody>
                {licenses.map((l) => (
                  <tr key={l.id}>
                    <td>{new Date(l.created_at).toLocaleDateString("en-IN")}</td><td>{l.reseller}</td><td>{l.account}</td>
                    <td>{l.plan} · {l.months} mo</td><td className="num">{money(l.amount)}</td><td className="num">{money(l.commission)}</td>
                    <td>{l.payout_status === "PAID" ? <span className="text-emerald-700">Paid</span> : <Button className="!py-1" onClick={() => run(() => api(`/admin/licenses/${l.id}/paid`, { body: {} }), reloadLic)}>Mark paid</Button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {tab === "System" && (!health ? <Loading /> : (
        <Card className="max-w-xl divide-y divide-gray-100">
          {([
            ["Environment", health.app_env, true], ["Database", `${health.database_engine}`, health.database],
            ["e-Invoice provider", health.einvoice_provider, health.einvoice_provider !== "gsp" || health.gsp_configured],
            ["GSP credentials", health.gsp_configured ? "configured" : "not set", health.gsp_configured],
            ["Razorpay payments", health.razorpay_live ? "live keys set" : "not configured (simulated)", health.razorpay_live],
            ["Razorpay webhook", health.razorpay_webhook ? "secret set" : "not set", health.razorpay_webhook],
            ["Email (backups)", health.email_configured ? "SMTP set" : "not set", health.email_configured],
            ["Cloudinary (images)", health.cloudinary_configured ? "configured" : "not set", health.cloudinary_configured],
          ] as [string, string, boolean][]).map(([k, v, ok]) => (
            <div key={k} className="flex items-center justify-between px-5 py-3 text-sm">
              <span className="text-gray-600">{k}</span>
              <span className="flex items-center gap-2">{v}{ok ? <CheckCircle2 size={16} className="text-emerald-600" /> : <XCircle size={16} className="text-amber-600" />}</span>
            </div>
          ))}
        </Card>
      ))}

      {edit && (
        <Modal title={`Manage — ${edit.name}`} onClose={() => setEdit(null)}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Plan">
                <Select value={edit.plan} onChange={(e) => setEdit({ ...edit, plan: e.target.value })}>
                  {["FREE", "STARTER", "PROFESSIONAL", "ENTERPRISE"].map((p) => <option key={p}>{p}</option>)}
                </Select>
              </Field>
              <Field label="Status">
                <Select value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>
                  {["TRIAL", "ACTIVE", "EXPIRED"].map((p) => <option key={p}>{p}</option>)}
                </Select>
              </Field>
              <Field label="Valid until"><Input type="date" value={edit.valid_until ?? ""} onChange={(e) => setEdit({ ...edit, valid_until: e.target.value || null })} /></Field>
              <Field label="Extra businesses"><Input type="number" min={0} value={edit.extra_businesses} onChange={(e) => setEdit({ ...edit, extra_businesses: Number(e.target.value) || 0 })} /></Field>
            </div>
            <Field label="Feature flags (JSON)" hint='Overrides plan limits, e.g. {"api_quota": 2000, "tally": true, "report:batch": true}'>
              <Textarea rows={4} className="font-mono text-xs" value={edit.flagsText} onChange={(e) => setEdit({ ...edit, flagsText: e.target.value })} />
            </Field>
            <div className="flex flex-wrap justify-between gap-2">
              <Button variant={edit.active ? "danger" : "secondary"} onClick={() => run(() => api(`/admin/users/${edit.account_id}/active`, { method: "PUT", body: { active: !edit.active } }), () => { setEdit(null); reloadAcc(); })}>
                {edit.active ? "Disable login" : "Enable login"}
              </Button>
              <Button onClick={() => {
                let flags: Record<string, unknown> | null = null;
                try { flags = edit.flagsText.trim() ? JSON.parse(edit.flagsText) : null; } catch { setErr("Feature flags must be valid JSON"); return; }
                run(() => api(`/admin/accounts/${edit.account_id}/subscription`, { method: "PUT", body: { plan: edit.plan, status: edit.status, valid_until: edit.valid_until, extra_businesses: edit.extra_businesses, feature_flags: flags } }), () => { setEdit(null); reloadAcc(); });
              }}>Save</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
