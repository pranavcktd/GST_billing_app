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
import { CredentialsDialog, StaffSignIns } from "@/components/StaffComponents";

interface Member {
  id: string; user_id: string; name: string; email: string; phone: string | null; role: string; you: boolean; custom: boolean;
  permissions: Permissions; has_pin: boolean; status: "ACTIVE" | "INVITED"; last_login_at: string | null; other_businesses: number; managed: boolean;
}
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
  const [invite, setInvite] = useState({ name: "", email: "", phone: "", role: "BILLING", password: "" });
  const [creds, setCreds] = useState<{ name: string; email: string; password: string; mailed: boolean; phone?: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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
      {notice && <p className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>}
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
                    <td>
                      {m.name}{m.you && " (you)"}
                      {m.status === "INVITED" && <span className="ml-1.5 rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-800">invited — not accepted yet</span>}
                      <div className="text-xs text-gray-500">{m.email}</div>
                      {m.role !== "OWNER" && <div className="text-[11px] text-gray-400">
                        {m.last_login_at ? `Last sign-in ${new Date(m.last_login_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}` : "Never signed in"}
                        {m.other_businesses > 0 && ` · also works for ${m.other_businesses} other business${m.other_businesses === 1 ? "" : "es"}`}
                      </div>}
                    </td>
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
                      {m.role !== "OWNER" && m.status === "ACTIVE" && can("users", "edit") && (m.managed ? (
                        <button className="mr-3 text-xs text-brand-600 hover:underline" title="Give a new temporary password — they choose their own at the next sign-in"
                          onClick={() => confirm(`Set a new temporary password for ${m.name}? They will be signed out.`) && run(async () => {
                            const r = await api<{ temp_password: string; email: string }>(`/members/${m.id}/temp-password`, { body: {} });
                            setCreds({ name: m.name, email: r.email, password: r.temp_password, mailed: false, phone: m.phone ?? undefined });
                          })}>New password</button>
                      ) : (
                        <button className="mr-3 text-xs text-brand-600 hover:underline" title="Only they can change their password — a reset link goes to their own e-mail"
                          onClick={() => run(async () => {
                            const r = await api<{ dev_link: string | null }>(`/members/${m.id}/reset-password`, { body: {} });
                            setNotice(r.dev_link ? `E-mail isn't set up (development). Reset link for ${m.name}: ${r.dev_link}` : `A password reset link was e-mailed to ${m.email}. Only they can set the new password.`);
                          })}>Send reset link</button>
                      ))}
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
            <form className="space-y-2 border-t border-gray-100 p-4" onSubmit={(e) => { e.preventDefault(); run(async () => {
              setNotice(null);
              const r = await api<{ created: boolean; invited: boolean; email: string; temp_password?: string; mailed?: boolean; name?: string }>("/members",
                { body: { ...invite, name: invite.name || null, phone: invite.phone || null, password: invite.password || null } });
              if (r.created && r.temp_password) setCreds({ name: invite.name, email: r.email, password: r.temp_password, mailed: !!r.mailed, phone: invite.phone });
              else setNotice(`${r.name ?? r.email} already has a login (maybe with another business). They were invited — after they accept, they work here with their own password.`);
              setInvite({ name: "", email: "", phone: "", role: invite.role, password: "" });
            }); }}>
              <h3 className="text-sm font-semibold text-gray-900">Add staff</h3>
              <div className="grid gap-2 sm:grid-cols-2">
                <Input placeholder="Name" value={invite.name} maxLength={120} onChange={(e) => setInvite({ ...invite, name: e.target.value })} />
                <Input type="email" required placeholder="E-mail (their login ID)" value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} />
                <Input placeholder="Mobile (optional, to share on WhatsApp)" value={invite.phone} maxLength={20} onChange={(e) => setInvite({ ...invite, phone: e.target.value })} />
                <Select value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value })}>
                  {STAFF_ROLES.filter((r) => r !== "ADMIN" || isOwner).map((r) => <option key={r} value={r}>{meta.roles[r].label}</option>)}
                </Select>
                <Input type="text" placeholder="Temporary password (optional — we make one)" minLength={8} value={invite.password} onChange={(e) => setInvite({ ...invite, password: e.target.value })} />
                <Button type="submit">Add staff</Button>
              </div>
              <p className="text-xs text-gray-500">
                {ROLE_HELP[invite.role]}. A new e-mail gets a login with a temporary password. If the person already has a login (for example an
                accountant who works for several businesses), they get an invitation instead and keep their own password. Staff count towards your plan.
              </p>
            </form>
          )}
        </Card>
      </div>

      {can("users") && <div className="mt-5"><StaffSignIns /></div>}

      {creds && <CredentialsDialog {...creds} onClose={() => setCreds(null)} />}

      {editing && (
        <Modal title={`Permissions — ${editing.member.name}`} onClose={() => setEditing(null)} wide>
          {!customRoles && (
            <p className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
              Custom permissions are part of the Business plan — this shows what the <b>{meta.roles[editing.member.role].label}</b> role allows.{" "}
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
