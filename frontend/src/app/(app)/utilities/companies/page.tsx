"use client";

import { Check, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, LinkButton, Loading, PageHeader, Select } from "@/components/ui";
import { api, session } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";

interface Member { id: string; user_id: string; name: string; email: string; role: string; you: boolean }

const ROLE_HELP: Record<string, string> = {
  OWNER: "Full control", ADMIN: "Everything except deleting the company",
  STAFF: "Create & edit bills, parties, items, payments", ACCOUNTANT: "Read-only: view everything, run reports (for your CA)",
};

export default function CompaniesPage() {
  const { me, business, switchBusiness, refresh } = useAuth();
  const { data: members, error, reload } = useFetch<Member[]>("/members");
  const [invite, setInvite] = useState({ email: "", role: "STAFF" });
  const [err, setErr] = useState<string | null>(null);
  const [confirmName, setConfirmName] = useState("");

  if (!me || !business) return <Loading />;
  const isOwner = business.role === "OWNER";
  const canManage = isOwner || business.role === "ADMIN";

  const run = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try { await fn(); reload(); } catch (e) { setErr((e as Error).message); }
  };

  return (
    <>
      <PageHeader title="Manage companies" sub="One login can run several companies (or a CA can manage clients)."
        actions={<LinkButton href="/onboarding"><Plus size={16} /> New company</LinkButton>} />
      <ErrorBox message={err ?? error} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="overflow-x-auto">
          <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Your companies</h2>
          <table className="tbl">
            <thead><tr><th>Company</th><th>GSTIN</th><th>Your role</th><th /></tr></thead>
            <tbody>
              {me.businesses.map((b) => (
                <tr key={b.id}>
                  <td className="font-medium">{b.name}</td>
                  <td className="font-mono text-xs">{b.gstin ?? "—"}</td>
                  <td>{b.role.charAt(0) + b.role.slice(1).toLowerCase()}</td>
                  <td className="text-right">
                    {b.id === business.id ? <span className="inline-flex items-center gap-1 text-xs text-emerald-700"><Check size={14} /> Current</span>
                      : <Button variant="secondary" className="!py-1" onClick={() => switchBusiness(b.id)}>Open</Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card className="overflow-x-auto">
          <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">People with access to {business.name}</h2>
          {!members ? <Loading /> : (
            <table className="tbl">
              <thead><tr><th>Name</th><th>Role</th><th /></tr></thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.id}>
                    <td>{m.name}{m.you && " (you)"}<div className="text-xs text-gray-500">{m.email}</div></td>
                    <td>
                      {m.role === "OWNER" || !isOwner ? m.role.charAt(0) + m.role.slice(1).toLowerCase() : (
                        <Select value={m.role} onChange={(e) => run(() => api(`/members/${m.id}`, { method: "PUT", body: { role: e.target.value } }))}>
                          <option value="ADMIN">Admin</option><option value="STAFF">Staff</option><option value="ACCOUNTANT">Accountant</option>
                        </Select>
                      )}
                    </td>
                    <td className="text-right">
                      {canManage && m.role !== "OWNER" && (
                        <button className="text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => confirm(`Remove ${m.name}?`) && run(() => api(`/members/${m.id}`, { method: "DELETE" }))}><Trash2 size={15} /></button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {canManage && (
            <form className="grid gap-2 border-t border-gray-100 p-4 sm:grid-cols-[1fr_auto_auto]" onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/members", { body: invite }); setInvite({ ...invite, email: "" }); }); }}>
              <Input type="email" required placeholder="Email of a registered user" value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} />
              <Select value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value })}>
                <option value="ADMIN">Admin</option><option value="STAFF">Staff</option><option value="ACCOUNTANT">Accountant (CA)</option>
              </Select>
              <Button type="submit">Add</Button>
              <p className="text-xs text-gray-500 sm:col-span-3">{ROLE_HELP[invite.role]}. They must sign up first.</p>
            </form>
          )}
        </Card>
      </div>

      {isOwner && (
        <Card className="mt-5 border-red-200 p-5">
          <h2 className="font-semibold text-red-800">Delete this company</h2>
          <p className="mt-1 mb-3 text-sm text-gray-600">Permanently deletes {business.name} and all its data. Take a backup first. Type the company name to confirm.</p>
          <div className="flex flex-wrap gap-2">
            <Field label="Company name" className="w-72"><Input value={confirmName} onChange={(e) => setConfirmName(e.target.value)} /></Field>
            <div className="flex items-end">
              <Button variant="danger" disabled={confirmName !== business.name} onClick={() => run(async () => {
                await api("/company/delete", { body: { confirm_name: confirmName } });
                session.setBusinessId(null);
                await refresh();
                window.location.href = "/";
              })}>Delete permanently</Button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
}
