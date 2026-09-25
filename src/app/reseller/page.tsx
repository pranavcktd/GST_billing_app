"use client";

import { Copy, Plus } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { PlatformShell } from "@/components/PlatformShell";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Account { account_id: string; name: string; email: string; phone: string | null; plan: string; status: string; valid_until: string | null; businesses: { name: string }[]; users: number; invoices_this_month: number }
interface Licenses { rows: { id: string; created_at: string; account: string; plan: string; months: number; amount: number; commission: number; payout_status: string }[]; commission_pct: number; total_sales: number; commission_earned: number; commission_pending: number }

export default function ResellerPage() {
  return <PlatformShell need="RESELLER"><Reseller /></PlatformShell>;
}

function Reseller() {
  const { data: accounts, reload } = useFetch<Account[]>("/reseller/accounts");
  const { data: lic, reload: reloadLic } = useFetch<Licenses>("/reseller/licenses");
  const [newAcc, setNewAcc] = useState<{ name: string; email: string; phone: string } | null>(null);
  const [created, setCreated] = useState<{ email: string; temporary_password: string } | null>(null);
  const [issue, setIssue] = useState<{ account: Account; plan: string; months: number } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try { await fn(); reload(); reloadLic(); return true; } catch (e) { setErr((e as Error).message); return false; }
  };

  return (
    <>
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card className="p-4"><div className="text-xs text-gray-500">Accounts</div><div className="mt-1 text-2xl font-semibold">{accounts?.length ?? "—"}</div></Card>
        <Card className="p-4"><div className="text-xs text-gray-500">Licence sales</div><div className="mt-1 text-2xl font-semibold">{lic ? money(lic.total_sales) : "—"}</div></Card>
        <Card className="p-4"><div className="text-xs text-gray-500">Commission earned ({lic?.commission_pct ?? 0}%)</div><div className="mt-1 text-2xl font-semibold">{lic ? money(lic.commission_earned) : "—"}</div></Card>
        <Card className="p-4"><div className="text-xs text-gray-500">Payout pending</div><div className="mt-1 text-2xl font-semibold">{lic ? money(lic.commission_pending) : "—"}</div></Card>
      </div>
      <ErrorBox message={err} />
      <Card className="mb-5 overflow-x-auto">
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <h2 className="font-semibold text-gray-900">My accounts</h2>
          <Button onClick={() => setNewAcc({ name: "", email: "", phone: "" })}><Plus size={16} /> Register business owner</Button>
        </div>
        {!accounts ? <Loading /> : accounts.length === 0 ? <Empty title="No accounts yet — register your first customer" /> : (
          <table className="tbl">
            <thead><tr><th>Owner</th><th>Businesses</th><th>Plan</th><th>Valid till</th><th className="num">Users</th><th className="num">Invoices (month)</th><th /></tr></thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.account_id}>
                  <td>{a.name}<div className="text-xs text-gray-500">{a.email}{a.phone ? ` · ${a.phone}` : ""}</div></td>
                  <td className="text-xs">{a.businesses.map((b) => b.name).join(", ") || <span className="text-gray-400">not set up yet</span>}</td>
                  <td>{a.plan}<div className="text-xs text-gray-500">{a.status}</div></td>
                  <td>{fmtDate(a.valid_until)}</td>
                  <td className="num">{a.users}</td><td className="num">{a.invoices_this_month}</td>
                  <td className="text-right"><Button className="!py-1" onClick={() => setIssue({ account: a, plan: "STARTER", months: 12 })}>Issue licence</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Card className="overflow-x-auto">
        <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Licences & commission</h2>
        {!lic ? <Loading /> : lic.rows.length === 0 ? <Empty title="No licences issued yet" /> : (
          <table className="tbl">
            <thead><tr><th>Date</th><th>Account</th><th>Plan</th><th className="num">Amount (incl. GST)</th><th className="num">Commission</th><th>Payout</th></tr></thead>
            <tbody>
              {lic.rows.map((r) => (
                <tr key={r.id}>
                  <td>{new Date(r.created_at).toLocaleDateString("en-IN")}</td><td>{r.account}</td><td>{r.plan} · {r.months} mo</td>
                  <td className="num">{money(r.amount)}</td><td className="num">{money(r.commission)}</td>
                  <td className={r.payout_status === "PAID" ? "text-emerald-700" : "text-amber-700"}>{r.payout_status === "PAID" ? "Paid" : "Pending"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <p className="mt-4 text-xs text-gray-500">For confidentiality you see account details and usage counts only — never customers&apos; invoices, parties or books.</p>

      {newAcc && (
        <Modal title="Register a business owner" onClose={() => setNewAcc(null)}>
          <form className="space-y-3" onSubmit={async (e) => {
            e.preventDefault();
            setErr(null);
            try {
              const r = await api<{ email: string; temporary_password: string }>("/reseller/accounts", { body: { ...newAcc, phone: newAcc.phone || null } });
              setCreated(r); setNewAcc(null); reload();
            } catch (x) { setErr((x as Error).message); }
          }}>
            <ErrorBox message={err} />
            <Field label="Owner name" required><Input required value={newAcc.name} onChange={(e) => setNewAcc({ ...newAcc, name: e.target.value })} /></Field>
            <Field label="Email (their login)" required><Input type="email" required value={newAcc.email} onChange={(e) => setNewAcc({ ...newAcc, email: e.target.value })} /></Field>
            <Field label="Mobile"><Input value={newAcc.phone} onChange={(e) => setNewAcc({ ...newAcc, phone: e.target.value })} /></Field>
            <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={() => setNewAcc(null)}>Cancel</Button><Button type="submit">Create login</Button></div>
          </form>
        </Modal>
      )}
      {created && (
        <Modal title="Login created" onClose={() => setCreated(null)}>
          <div className="space-y-3 text-sm">
            <p>Share these with the owner. They should change the password after signing in (Settings → Security).</p>
            <div className="rounded-lg bg-gray-50 p-3 font-mono text-sm">Email: {created.email}<br />Password: {created.temporary_password}</div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => navigator.clipboard?.writeText(`Login: ${created.email}\nPassword: ${created.temporary_password}`)}><Copy size={15} /> Copy</Button>
              <Button onClick={() => setCreated(null)}>Done</Button>
            </div>
            <p className="text-xs text-gray-500">This password is shown only once.</p>
          </div>
        </Modal>
      )}
      {issue && (
        <Modal title={`Issue licence — ${issue.account.name}`} onClose={() => setIssue(null)}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Plan">
                <Select value={issue.plan} onChange={(e) => setIssue({ ...issue, plan: e.target.value })}>
                  <option value="STARTER">Starter</option><option value="PROFESSIONAL">Professional</option><option value="ENTERPRISE">Enterprise</option>
                </Select>
              </Field>
              <Field label="Duration">
                <Select value={issue.months} onChange={(e) => setIssue({ ...issue, months: Number(e.target.value) })}>
                  {[1, 3, 6, 12, 24, 36].map((m) => <option key={m} value={m}>{m} month(s)</option>)}
                </Select>
              </Field>
            </div>
            <p className="text-xs text-gray-500">Remaining paid time on the account is carried over. Your commission is recorded for payout.</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setIssue(null)}>Cancel</Button>
              <Button onClick={async () => { if (await run(() => api("/reseller/licenses", { body: { account_id: issue.account.account_id, plan: issue.plan, months: issue.months } }))) setIssue(null); }}>Issue licence</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
