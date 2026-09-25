"use client";

import { Check, Plus, SlidersHorizontal, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, LinkButton, Loading, PageHeader, Select } from "@/components/ui";
import { api, session } from "@/lib/api";
import { useAuth, usePerms } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";
import type { Action, Business, Module, Permissions } from "@/lib/types";

interface Member { id: string; user_id: string; name: string; email: string; role: string; you: boolean; custom: boolean; permissions: Permissions; has_pin: boolean }
interface Meta {
  modules: Record<Module, string>; actions: Action[]; flags: string[];
  roles: Record<string, { label: string; defaults: Permissions }>;
}

const STAFF_ROLES = ["ADMIN", "MANAGER", "BILLING", "INVENTORY", "ACCOUNTANT"] as const;
const ROLE_HELP: Record<string, string> = {
  ADMIN: "Runs the business: everything including staff (owner adds admins)",
  MANAGER: "Store manager: create, edit and view all reports; approves edits with a PIN",
  BILLING: "Billing desk: sale bills and receipts, sees stock — no costs, no deleting",
  INVENTORY: "Purchase & inventory: bills, stock, items — no customer ledgers, P&L or GST",
  ACCOUNTANT: "CA / auditor: read-only books, GST returns and audit trail",
};
const FLAG_LABEL: Record<string, string> = { view_cost: "See purchase rates & profit", edit_past: "Edit/cancel older entries without approval" };

export default function CompaniesPage() {
  const { me, business, switchBusiness, refresh } = useAuth();
  const { can } = usePerms();
  const { data: members, error, reload } = useFetch<Member[]>(can("users") ? "/members" : null);
  const { data: meta } = useFetch<Meta>("/permissions/meta");
  const { data: biz } = useFetch<Business>("/businesses/current");
  const [invite, setInvite] = useState({ email: "", role: "BILLING" });
  const [err, setErr] = useState<string | null>(null);
  const [confirmName, setConfirmName] = useState("");
  const [editing, setEditing] = useState<{ member: Member; perms: Permissions } | null>(null);

  if (!me || !business || !meta) return <Loading />;
  const isOwner = business.role === "OWNER";
  const customRoles = !!biz?.plan?.custom_roles;

  const run = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try { await fn(); reload(); return true; } catch (e) { setErr((e as Error).message); return false; }
  };

  const toggle = (m: Module, a: Action) => {
    if (!editing) return;
    const cur = new Set(editing.perms.modules[m] ?? []);
    if (cur.has(a)) cur.delete(a); else cur.add(a);
    if (a !== "view" && cur.size && !cur.has("view")) cur.add("view");
    if (a === "view" && !cur.has("view")) cur.clear();
    setEditing({ ...editing, perms: { ...editing.perms, modules: { ...editing.perms.modules, [m]: [...cur] } } });
  };

  return (
    <>
      <PageHeader title="Companies & staff" sub="One login can run several businesses. Give each person exactly the access they need."
        actions={<LinkButton href="/onboarding"><Plus size={16} /> New business</LinkButton>} />
      <ErrorBox message={err ?? error} />
      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="overflow-x-auto lg:col-span-2">
          <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Your businesses</h2>
          <table className="tbl">
            <thead><tr><th>Business</th><th>Your role</th><th /></tr></thead>
            <tbody>
              {me.businesses.map((b) => (
                <tr key={b.id}>
                  <td className="font-medium">{b.name}<div className="font-mono text-xs text-gray-500">{b.gstin ?? "—"}</div></td>
                  <td>{meta.roles[b.role]?.label ?? b.role}</td>
                  <td className="text-right">
                    {b.id === business.id ? <span className="inline-flex items-center gap-1 text-xs text-emerald-700"><Check size={14} /> Current</span>
                      : <Button variant="secondary" className="!py-1" onClick={() => switchBusiness(b.id)}>Open</Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card className="overflow-x-auto lg:col-span-3">
          <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">People with access to {business.name}</h2>
          {!can("users") ? <p className="px-5 pb-5 text-sm text-gray-500">Your role cannot manage staff.</p> : !members ? <Loading /> : (
            <table className="tbl">
              <thead><tr><th>Name</th><th>Role</th><th /></tr></thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.id}>
                    <td>{m.name}{m.you && " (you)"}<div className="text-xs text-gray-500">{m.email}</div></td>
                    <td>
                      {m.role === "OWNER" || !can("users", "edit") ? meta.roles[m.role]?.label ?? m.role : (
                        <Select value={m.role} onChange={(e) => run(() => api(`/members/${m.id}`, { method: "PUT", body: { role: e.target.value } }))}>
                          {STAFF_ROLES.filter((r) => r !== "ADMIN" || isOwner || m.role === "ADMIN").map((r) => <option key={r} value={r}>{meta.roles[r].label}</option>)}
                        </Select>
                      )}
                      {m.custom && <div className="mt-0.5 text-xs text-brand-700">custom permissions</div>}
                      {m.has_pin && <div className="text-xs text-gray-500">has approval PIN</div>}
                    </td>
                    <td className="whitespace-nowrap text-right">
                      {m.role !== "OWNER" && can("users", "edit") && (
                        <button className="mr-3 text-xs text-brand-600 hover:underline" onClick={() => run(async () => {
                          const r = await api<{ dev_link: string | null }>(`/members/${m.id}/reset-password`, { body: {} });
                          alert(r.dev_link ? `E-mail isn't set up. Share this reset link with ${m.name}:\n${r.dev_link}` : `A password reset link was e-mailed to ${m.email}.`);
                        })}>Reset password</button>
                      )}
                      {m.role !== "OWNER" && can("users", "edit") && (
                        <button className="mr-3 text-gray-400 hover:text-gray-700" title="Permissions" aria-label="Permissions" onClick={() => setEditing({ member: m, perms: m.permissions })}><SlidersHorizontal size={15} /></button>
                      )}
                      {m.role !== "OWNER" && can("users", "delete") && (
                        <button className="text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => confirm(`Remove ${m.name}?`) && run(() => api(`/members/${m.id}`, { method: "DELETE" }))}><Trash2 size={15} /></button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {can("users", "create") && (
            <form className="grid gap-2 border-t border-gray-100 p-4 sm:grid-cols-[1fr_auto_auto]" onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/members", { body: invite }); setInvite({ ...invite, email: "" }); }); }}>
              <Input type="email" required placeholder="Email of a registered user" value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} />
              <Select value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value })}>
                {STAFF_ROLES.filter((r) => r !== "ADMIN" || isOwner).map((r) => <option key={r} value={r}>{meta.roles[r].label}</option>)}
              </Select>
              <Button type="submit">Add</Button>
              <p className="text-xs text-gray-500 sm:col-span-3">{ROLE_HELP[invite.role]}. They sign up first with this email. Users count towards your plan across all businesses.</p>
            </form>
          )}
        </Card>
      </div>

      {editing && (
        <Modal title={`Permissions — ${editing.member.name}`} onClose={() => setEditing(null)} wide>
          {!customRoles && (
            <p className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
              Custom permissions are part of the Enterprise plan — this shows what the <b>{meta.roles[editing.member.role].label}</b> role allows.{" "}
              <Link href="/billing?plan=ENTERPRISE" className="font-medium underline">Upgrade</Link>
            </p>
          )}
          <div className="max-h-[60vh] overflow-auto">
            <table className="tbl">
              <thead><tr><th>Module</th>{meta.actions.map((a) => <th key={a} className="text-center capitalize">{a}</th>)}</tr></thead>
              <tbody>
                {(Object.keys(meta.modules) as Module[]).filter((m) => m !== "users" || editing.member.role === "ADMIN").map((m) => (
                  <tr key={m}>
                    <td className="text-sm">{meta.modules[m]}</td>
                    {meta.actions.map((a) => (
                      <td key={a} className="text-center">
                        <input type="checkbox" disabled={!customRoles} checked={!!editing.perms.modules[m]?.includes(a)} onChange={() => toggle(m, a)} aria-label={`${m} ${a}`} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 space-y-1">
            {meta.flags.map((f) => (
              <label key={f} className="flex items-center gap-2 text-sm">
                <input type="checkbox" disabled={!customRoles} checked={editing.perms.flags.includes(f as "view_cost")}
                  onChange={(e) => setEditing({ ...editing, perms: { ...editing.perms, flags: e.target.checked ? [...editing.perms.flags, f as "view_cost"] : editing.perms.flags.filter((x) => x !== f) } })} />
                {FLAG_LABEL[f] ?? f}
              </label>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap justify-between gap-2">
            <Button variant="secondary" disabled={!customRoles} onClick={async () => { if (await run(() => api(`/members/${editing.member.id}/permissions`, { method: "PUT", body: { modules: null, flags: [] } }))) setEditing(null); }}>Reset to role default</Button>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setEditing(null)}>Close</Button>
              <Button disabled={!customRoles} onClick={async () => { if (await run(() => api(`/members/${editing.member.id}/permissions`, { method: "PUT", body: editing.perms }))) setEditing(null); }}>Save permissions</Button>
            </div>
          </div>
        </Modal>
      )}

      {isOwner && (
        <Card className="mt-5 border-red-200 p-5">
          <h2 className="font-semibold text-red-800">Delete this business</h2>
          <p className="mt-1 mb-3 text-sm text-gray-600">Permanently deletes {business.name} and all its data. Take a backup first. Type the business name to confirm.</p>
          <div className="flex flex-wrap gap-2">
            <Field label="Business name" className="w-72"><Input value={confirmName} onChange={(e) => setConfirmName(e.target.value)} /></Field>
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
