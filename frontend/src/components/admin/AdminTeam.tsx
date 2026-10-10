"use client";

import { Pencil, ShieldCheck, ShieldAlert, UserPlus, UsersRound } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Member { id: string; name: string; email: string; phone: string | null; team: string; areas: string[]; active: boolean; totp_enabled: boolean; last_login_at: string | null; open_tickets: number }
interface Data { members: Member[]; areas: Record<string, string>; teams: Record<string, string>; team_areas: Record<string, string[]>; superadmins: { id: string; name: string; email: string }[] }
type Draft = { id?: string; name: string; email: string; phone: string; team: string; areas: string[]; active: boolean };

/** Admin → Team: the company's own staff and what each may open in the admin panel. Super admin only. */
export function AdminTeam() {
  const { data, reload } = useFetch<Data>("/admin/team");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [created, setCreated] = useState<{ email: string; temporary_password: string | null; emailed: boolean } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (!data) return <Loading />;

  async function save() {
    if (!draft) return;
    setErr(null);
    try {
      if (draft.id) await api(`/admin/team/${draft.id}`, { method: "PUT", body: { team: draft.team, areas: draft.areas, active: draft.active } });
      else {
        const r = await api<Member & { temporary_password: string | null; emailed: boolean }>("/admin/team", { body: { name: draft.name, email: draft.email, phone: draft.phone || null, team: draft.team, areas: draft.areas } });
        setCreated({ email: r.email, temporary_password: r.temporary_password, emailed: r.emailed });
      }
      setDraft(null); reload();
    } catch (e) { setErr((e as Error).message); }
  }
  async function remove(m: Member) {
    if (!confirm(`Remove ${m.name} from the team? Their login stays (they lose admin access). Open tickets go back to the queue.`)) return;
    try { await api(`/admin/team/${m.id}`, { method: "DELETE" }); reload(); } catch (e) { setErr((e as Error).message); }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900"><UsersRound size={18} className="text-brand-600" /> Team</h2>
          <p className="max-w-2xl text-sm text-gray-500">
            Your company&apos;s staff — support, technical, finance, sales. Each signs in with their own login and sees only the areas you tick.
            Keys, pricing, backups, settings and this team list stay with the super admin.
          </p>
        </div>
        <Button onClick={() => setDraft({ name: "", email: "", phone: "", team: "SUPPORT", areas: data.team_areas.SUPPORT, active: true })}><UserPlus size={15} /> Add member</Button>
      </div>
      <ErrorBox message={err} />
      {created && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          {created.temporary_password ? <>Added <b>{created.email}</b>. Temporary password: <code className="rounded bg-white px-1.5 py-0.5">{created.temporary_password}</code> — shown once.
            {created.emailed ? " It was also e-mailed to them." : " E-mail is not set up, so please pass it on securely."} They must choose a new password at first sign-in.</>
            : <>Added <b>{created.email}</b> — they already had a login and can open the admin panel now.</>}
          <button className="ml-2 underline" onClick={() => setCreated(null)}>Dismiss</button>
        </div>
      )}

      <Card className="overflow-x-auto">
        {data.members.length === 0 ? <p className="p-5 text-sm text-gray-500">No team members yet.</p> : (
          <table className="tbl">
            <thead><tr><th>Member</th><th>Team</th><th>Can open</th><th className="num">Open tickets</th><th>Last sign-in</th><th /></tr></thead>
            <tbody>
              {data.members.map((m) => (
                <tr key={m.id} className={m.active ? "" : "text-gray-400"}>
                  <td>{m.name}<div className="flex items-center gap-1 text-xs text-gray-500">{m.email}
                    {m.totp_enabled ? <span title="Two-step sign-in on"><ShieldCheck size={13} className="text-emerald-600" /></span> : <span title="Two-step sign-in off — ask them to turn it on"><ShieldAlert size={13} className="text-amber-600" /></span>}</div></td>
                  <td>{data.teams[m.team] ?? m.team}{!m.active && <div className="text-xs">deactivated</div>}</td>
                  <td className="text-xs">{m.areas.map((a) => data.areas[a]?.split(" — ")[0] ?? a).join(", ") || "—"}</td>
                  <td className="num">{m.open_tickets}</td>
                  <td className="text-xs">{m.last_login_at ? fmtDate(m.last_login_at) : "never"}</td>
                  <td className="text-right whitespace-nowrap">
                    <Button variant="ghost" className="!px-2" title="Edit" onClick={() => setDraft({ id: m.id, name: m.name, email: m.email, phone: m.phone ?? "", team: m.team, areas: m.areas, active: m.active })}><Pencil size={15} /></Button>
                    <Button variant="ghost" className="!py-1 text-red-600" onClick={() => remove(m)}>Remove</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card className="p-4 text-sm text-gray-600">
        <b>Super admins:</b> {data.superadmins.map((s) => s.email).join(", ")}. A <b>backup super admin</b> (full control, e.g. a co-founder) is added on the server
        in <code>SUPERADMIN_EMAILS</code> — deliberately not from this screen, so a stolen team login can never create one. For a day-to-day second-in-command,
        add a member to the <b>Deputy admin</b> team: they get every area above, but not keys, pricing or the team.
      </Card>

      {draft && (
        <Modal title={draft.id ? `Edit ${draft.name}` : "Add team member"} onClose={() => setDraft(null)}>
          <div className="space-y-3 text-sm">
            {!draft.id && (
              <>
                <Field label="Name"><Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></Field>
                <Field label="Work e-mail" hint="A new login is created; an existing one simply gets team access"><Input type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} /></Field>
                <Field label="Phone (optional)"><Input value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} /></Field>
              </>
            )}
            <Field label="Team"><Select value={draft.team} onChange={(e) => setDraft({ ...draft, team: e.target.value, areas: draft.id ? draft.areas : data.team_areas[e.target.value] })}>
              {Object.entries(data.teams).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select></Field>
            <div>
              <div className="mb-1 text-xs font-medium text-gray-700">Can open</div>
              {Object.entries(data.areas).map(([k, v]) => (
                <label key={k} className="flex items-center gap-2 py-0.5">
                  <input type="checkbox" checked={draft.areas.includes(k)} onChange={(e) => setDraft({ ...draft, areas: e.target.checked ? [...draft.areas, k] : draft.areas.filter((a) => a !== k) })} /> {v}
                </label>
              ))}
            </div>
            {draft.id && <label className="flex items-center gap-2"><input type="checkbox" checked={draft.active} onChange={(e) => setDraft({ ...draft, active: e.target.checked })} /> Active (untick to block sign-in)</label>}
            <ErrorBox message={err} />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDraft(null)}>Cancel</Button>
              <Button disabled={!draft.id && (draft.name.trim().length < 2 || !draft.email)} onClick={save}>Save</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
