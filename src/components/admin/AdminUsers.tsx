"use client";

import { KeyRound, Lock, LogOut, MailCheck, MoreHorizontal, Plus, ShieldOff, Trash2, UserCog, UserX } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

export interface AdminUser {
  id: string; name: string; email: string; phone: string | null; level: string; active: boolean; locked: boolean; totp: boolean;
  last_login_at: string | null; created_at: string; commission_pct: number | null; plan: string | null; reseller: string | null;
  memberships: { business_id: string; business: string; role: string; owner: boolean }[];
}
interface Biz { id: string; name: string; owner_email: string | null }
interface Reseller { id: string; name: string }

const LEVELS = { SUPERADMIN: "Super admin", RESELLER: "Reseller", OWNER: "Account owner", STAFF: "Staff", USER: "No access yet" } as const;
const LEVEL_TONE: Record<string, string> = {
  SUPERADMIN: "bg-purple-50 text-purple-700", RESELLER: "bg-amber-50 text-amber-800", OWNER: "bg-brand-50 text-brand-700",
  STAFF: "bg-gray-100 text-gray-700", USER: "bg-gray-50 text-gray-500",
};

export function AdminUsers({ onChanged }: { onChanged?: () => void }) {
  const [filter, setFilter] = useState({ search: "", level: "", status: "" });
  const { data, reload } = useFetch<AdminUser[]>(`/admin/users${qs(filter)}`);
  const { data: businesses } = useFetch<Biz[]>("/admin/businesses");
  const { data: resellers } = useFetch<Reseller[]>("/admin/resellers");
  const [creating, setCreating] = useState(false);
  const [menu, setMenu] = useState<AdminUser | null>(null);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [secret, setSecret] = useState<{ title: string; text: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try { const r = await fn(); reload(); onChanged?.(); return r; } catch (e) { setErr((e as Error).message); return null; }
  };

  return (
    <>
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <Field label="Search"><Input placeholder="Name, email, phone" value={filter.search} onChange={(e) => setFilter({ ...filter, search: e.target.value })} /></Field>
        <Field label="Level">
          <Select value={filter.level} onChange={(e) => setFilter({ ...filter, level: e.target.value })}>
            <option value="">All levels</option>
            {Object.entries(LEVELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </Field>
        <Field label="Status">
          <Select value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}>
            <option value="">Any</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="locked">Locked</option>
          </Select>
        </Field>
        <div className="flex-1" />
        <Button onClick={() => setCreating(true)}><Plus size={16} /> Add user</Button>
      </div>
      <ErrorBox message={err} />
      <Card className="overflow-x-auto">
        {!data ? <Loading /> : (
          <table className="tbl">
            <thead><tr><th>User</th><th>Level</th><th>Businesses / role</th><th>Plan</th><th>Last sign-in</th><th>Status</th><th /></tr></thead>
            <tbody>
              {data.map((u) => (
                <tr key={u.id} className={u.active ? "" : "text-gray-400"}>
                  <td>{u.name}<div className="text-xs text-gray-500">{u.email}{u.phone ? ` · ${u.phone}` : ""}</div></td>
                  <td><span className={`rounded px-2 py-0.5 text-xs font-medium ${LEVEL_TONE[u.level]}`}>{LEVELS[u.level as keyof typeof LEVELS] ?? u.level}</span>
                    {u.commission_pct !== null && <div className="text-xs text-gray-500">{u.commission_pct}% commission</div>}
                    {u.reseller && <div className="text-xs text-gray-500">via {u.reseller}</div>}</td>
                  <td className="text-xs">{u.memberships.map((m) => `${m.business} (${m.owner ? "owner" : m.role.toLowerCase()})`).join(", ") || "—"}</td>
                  <td>{u.plan ?? ""}</td>
                  <td className="text-xs">{u.last_login_at ? new Date(u.last_login_at).toLocaleString("en-IN") : "never"}</td>
                  <td className="text-xs">
                    {u.active ? <span className="text-emerald-700">Active</span> : <span className="text-red-700">Inactive</span>}
                    {u.locked && <div className="text-amber-700">Locked</div>}
                    {u.totp && <div className="text-gray-500">2FA on</div>}
                  </td>
                  <td className="text-right"><button className="rounded p-1 hover:bg-gray-100" aria-label="Actions" onClick={() => setMenu(u)}><MoreHorizontal size={18} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {menu && (
        <Modal title={`${menu.name} — ${menu.email}`} onClose={() => setMenu(null)}>
          <div className="grid gap-2">
            <Action icon={UserCog} label="Edit name / email / phone" onClick={() => { setEditing(menu); setMenu(null); }} />
            <Action icon={MailCheck} label="E-mail a password reset link" onClick={async () => {
              const r = await run(() => api<{ dev_link: string | null }>(`/admin/users/${menu.id}/reset-password`, { body: { mode: "email" } }));
              setMenu(null);
              if (r) setSecret({ title: "Reset link sent", text: (r as { dev_link: string | null }).dev_link ? `E-mail isn't set up — share this link:\n${(r as { dev_link: string }).dev_link}` : `A reset link was e-mailed to ${menu.email}.` });
            }} />
            <Action icon={KeyRound} label="Set a temporary password" onClick={async () => {
              const r = await run(() => api<{ temporary_password: string }>(`/admin/users/${menu.id}/reset-password`, { body: { mode: "temp" } }));
              setMenu(null);
              if (r) setSecret({ title: "Temporary password", text: `Email: ${menu.email}\nPassword: ${(r as { temporary_password: string }).temporary_password}\n\nThey must choose a new password after signing in. All their sessions were signed out.` });
            }} />
            {menu.locked && <Action icon={Lock} label="Unlock (clear failed sign-ins)" onClick={() => { run(() => api(`/admin/users/${menu.id}/unlock`, { body: {} })); setMenu(null); }} />}
            {menu.totp && <Action icon={ShieldOff} label="Turn off two-factor sign-in (lost phone)" onClick={() => { run(() => api(`/admin/users/${menu.id}/reset-2fa`, { body: {} })); setMenu(null); }} />}
            <Action icon={LogOut} label="Sign out of all devices" onClick={() => { run(() => api(`/admin/users/${menu.id}/sign-out`, { body: {} })); setMenu(null); }} />
            <div className="grid grid-cols-3 gap-2 pt-1">
              {(["SUPERADMIN", "RESELLER", null] as const).map((r) => (
                <Button key={r ?? "none"} variant="secondary" className="!text-xs" disabled={(menu.level === r) || (r === null && !["SUPERADMIN", "RESELLER"].includes(menu.level))}
                  onClick={() => { run(() => api(`/admin/users/${menu.id}/platform-role`, { method: "PUT", body: { role: r } })); setMenu(null); }}>
                  {r === null ? "Remove platform role" : `Make ${LEVELS[r].toLowerCase()}`}
                </Button>
              ))}
            </div>
            <div className="mt-2 flex justify-between gap-2 border-t border-gray-100 pt-3">
              <Button variant={menu.active ? "danger" : "secondary"} onClick={() => { run(() => api(`/admin/users/${menu.id}/active`, { method: "PUT", body: { active: !menu.active } })); setMenu(null); }}>
                <UserX size={15} /> {menu.active ? "Deactivate" : "Activate"}
              </Button>
              <Button variant="danger" onClick={async () => {
                const owns = menu.memberships.filter((m) => m.owner).length;
                if (!confirm(owns ? `${menu.name} owns ${owns} business(es). Delete the user AND those businesses? A backup is taken first.` : `Delete ${menu.email} permanently?`)) return;
                const r = await run(() => api(`/admin/users/${menu.id}${owns ? "?force=true" : ""}`, { method: "DELETE" }));
                setMenu(null);
                if (r && (r as { safety_backup_id: string | null }).safety_backup_id) setSecret({ title: "User deleted", text: "Their businesses were backed up first — find it under Backups (Safety)." });
              }}><Trash2 size={15} /> Delete</Button>
            </div>
          </div>
        </Modal>
      )}
      {editing && <EditUser user={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />}
      {creating && businesses && resellers && (
        <CreateUser businesses={businesses} resellers={resellers} onClose={() => setCreating(false)}
          onCreated={(t) => { setCreating(false); reload(); onChanged?.(); if (t) setSecret(t); }} />
      )}
      {secret && (
        <Modal title={secret.title} onClose={() => setSecret(null)}>
          <pre className="rounded-lg bg-gray-50 p-3 text-sm whitespace-pre-wrap">{secret.text}</pre>
          <div className="mt-3 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => navigator.clipboard?.writeText(secret.text)}>Copy</Button>
            <Button onClick={() => setSecret(null)}>Done</Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function Action({ icon: Icon, label, onClick }: { icon: React.ElementType; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-left text-sm hover:bg-gray-50">
      <Icon size={16} className="text-gray-500" /> {label}
    </button>
  );
}

function EditUser({ user, onClose, onSaved }: { user: AdminUser; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ name: user.name, email: user.email, phone: user.phone ?? "" });
  const [err, setErr] = useState<string | null>(null);
  return (
    <Modal title="Edit user" onClose={onClose}>
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault();
        try { await api(`/admin/users/${user.id}`, { method: "PUT", body: { ...f, phone: f.phone || null } }); onSaved(); } catch (x) { setErr((x as Error).message); }
      }}>
        <ErrorBox message={err} />
        <Field label="Name"><Input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Email (login)"><Input type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Phone"><Input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit">Save</Button></div>
      </form>
    </Modal>
  );
}

function CreateUser({ businesses, resellers, onClose, onCreated }: {
  businesses: Biz[]; resellers: Reseller[]; onClose: () => void; onCreated: (t: { title: string; text: string } | null) => void;
}) {
  const [f, setF] = useState({
    name: "", email: "", phone: "", level: "OWNER", password: "", commission_pct: "20", plan: "FREE", valid_days: "0",
    reseller_id: "", business_id: "", role: "BILLING", send_email: false,
  });
  const [err, setErr] = useState<string | null>(null);
  const set = (p: Partial<typeof f>) => setF({ ...f, ...p });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const r = await api<{ email: string; temporary_password: string | null; emailed: boolean }>("/admin/users", { body: {
        name: f.name, email: f.email, phone: f.phone || null, level: f.level, password: f.password || null,
        commission_pct: Number(f.commission_pct), plan: f.plan, valid_days: Number(f.valid_days), reseller_id: f.reseller_id || null,
        business_id: f.business_id || null, role: f.role, send_email: f.send_email,
      } });
      onCreated(r.temporary_password ? { title: "User created", text: `Email: ${r.email}\nTemporary password: ${r.temporary_password}\n${r.emailed ? "\nLogin details were also e-mailed." : ""}\nThey will be asked to choose their own password.` } : null);
    } catch (x) {
      setErr((x as Error).message);
    }
  }

  return (
    <Modal title="Add user" onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-3">
        <ErrorBox message={err} />
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Level" className="sm:col-span-2">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {(["SUPERADMIN", "RESELLER", "OWNER", "STAFF"] as const).map((l) => (
                <button type="button" key={l} onClick={() => set({ level: l })} className={`rounded-lg border px-3 py-2 text-sm ${f.level === l ? "border-brand-500 bg-brand-50 font-medium" : "border-gray-200"}`}>{LEVELS[l]}</button>
              ))}
            </div>
          </Field>
          <Field label="Name" required><Input required value={f.name} onChange={(e) => set({ name: e.target.value })} /></Field>
          <Field label="Email (login)" required><Input type="email" required value={f.email} onChange={(e) => set({ email: e.target.value })} /></Field>
          <Field label="Phone"><Input value={f.phone} onChange={(e) => set({ phone: e.target.value })} /></Field>
          <Field label="Password" hint="Leave blank to generate a temporary one"><Input type="password" autoComplete="new-password" value={f.password} onChange={(e) => set({ password: e.target.value })} /></Field>
          {f.level === "RESELLER" && <Field label="Commission %"><Input type="number" min={0} max={90} value={f.commission_pct} onChange={(e) => set({ commission_pct: e.target.value })} /></Field>}
          {f.level === "OWNER" && (
            <>
              <Field label="Plan">
                <Select value={f.plan} onChange={(e) => set({ plan: e.target.value })}>{["FREE", "STARTER", "PROFESSIONAL", "ENTERPRISE"].map((p) => <option key={p}>{p}</option>)}</Select>
              </Field>
              <Field label="Valid for (days)" hint="0 = no end date"><Input type="number" min={0} value={f.valid_days} onChange={(e) => set({ valid_days: e.target.value })} /></Field>
              <Field label="Under reseller (optional)">
                <Select value={f.reseller_id} onChange={(e) => set({ reseller_id: e.target.value })}><option value="">Direct customer</option>{resellers.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select>
              </Field>
            </>
          )}
          {f.level === "STAFF" && (
            <>
              <Field label="Business" required>
                <Select required value={f.business_id} onChange={(e) => set({ business_id: e.target.value })}>
                  <option value="">Select business</option>{businesses.map((b) => <option key={b.id} value={b.id}>{b.name}{b.owner_email ? ` — ${b.owner_email}` : ""}</option>)}
                </Select>
              </Field>
              <Field label="Role">
                <Select value={f.role} onChange={(e) => set({ role: e.target.value })}>
                  <option value="ADMIN">Business admin</option><option value="MANAGER">Store manager</option><option value="BILLING">Billing operator</option>
                  <option value="INVENTORY">Inventory manager</option><option value="ACCOUNTANT">Accountant / CA</option>
                </Select>
              </Field>
            </>
          )}
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.send_email} onChange={(e) => set({ send_email: e.target.checked })} /> E-mail the login details (needs platform e-mail set up)</label>
        <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit">Create user</Button></div>
      </form>
    </Modal>
  );
}
