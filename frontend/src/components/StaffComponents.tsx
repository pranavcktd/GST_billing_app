"use client";

import { Check, Copy, MailPlus, MessageCircle, ShieldCheck, UserCheck, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading } from "@/components/ui";
import { api, session } from "@/lib/api";
import { useAuth, usePerms } from "@/lib/auth";
import { useLink } from "@/lib/config";
import { useFetch } from "@/lib/useFetch";

const when = (d: string | null) =>
  d ? new Date(d).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

// ------------------------------------------------------------------ credentials after creating a login
export function CredentialsDialog({ name, email, password, mailed, phone, onClose }: {
  name: string; email: string; password: string; mailed: boolean; phone?: string; onClose: () => void;
}) {
  const wa = useLink("whatsapp_send");
  const [copied, setCopied] = useState(false);
  const loginUrl = typeof window !== "undefined" ? `${window.location.origin}/login` : "/login";
  const text = `Hello ${name}, your login is ready.\nSign in: ${loginUrl}\nE-mail: ${email}\nTemporary password: ${password}\nYou will set your own password at the first sign-in.`;
  const digits = (phone ?? "").replace(/\D/g, "").slice(-10);
  return (
    <Modal title="Staff login created" onClose={onClose}>
      <div className="space-y-3 text-sm">
        <p className="text-gray-600">Share these details with {name}. The password is shown only now — they choose their own at the first sign-in.</p>
        <div className="rounded-lg bg-gray-50 p-3 font-mono text-xs leading-6">
          Login: {loginUrl}<br />E-mail: <b>{email}</b><br />Temporary password: <b>{password}</b>
        </div>
        {mailed && <p className="text-emerald-700">The details were also e-mailed to {email}.</p>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={async () => { await navigator.clipboard?.writeText(text).catch(() => {}); setCopied(true); }}>
            {copied ? <Check size={15} /> : <Copy size={15} />} {copied ? "Copied" : "Copy"}
          </Button>
          <a className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3.5 py-2 font-medium hover:bg-gray-50" target="_blank" rel="noreferrer"
            href={`${wa}${digits ? "91" + digits : ""}?text=${encodeURIComponent(text)}`}><MessageCircle size={15} /> WhatsApp</a>
          <Button onClick={onClose}>Done</Button>
        </div>
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ invitations for people who already have a login
export function InvitationsBanner() {
  const { me, refresh } = useAuth();
  const [busy, setBusy] = useState<string | null>(null);
  if (!me?.invitations?.length) return null;
  async function answer(id: string, businessId: string, action: "accept" | "decline") {
    setBusy(id);
    try {
      await api(`/auth/invitations/${id}/${action}`, { body: {} });
      if (action === "accept") {
        session.setBusinessId(businessId); // open the business just joined
        window.location.assign("/dashboard");
        return;
      }
      await refresh();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="mb-4 space-y-2">
      {me.invitations.map((inv) => (
        <div key={inv.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-brand-200 bg-brand-50 px-4 py-3 text-sm">
          <MailPlus size={18} className="text-brand-700" />
          <span className="flex-1"><b>{inv.business_name}</b> added you as {inv.role.toLowerCase()}{inv.invited_by ? ` (by ${inv.invited_by})` : ""}. You keep your own login and password.</span>
          <Button disabled={busy === inv.id} onClick={() => answer(inv.id, inv.business_id, "accept")}><Check size={15} /> Accept</Button>
          <Button variant="secondary" disabled={busy === inv.id} onClick={() => answer(inv.id, inv.business_id, "decline")}>Decline</Button>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ top bar: sign-ins waiting for approval
export function PendingSignIns() {
  const { can } = usePerms();
  const allowed = can("users", "edit");
  const { data } = useFetch<{ count: number }>(allowed ? "/staff/pending" : null, { refreshMs: 30000 });
  if (!allowed || !data?.count) return null;
  return (
    <Link href="/utilities/companies#sign-ins" title="Staff sign-ins waiting for your approval"
      className="inline-flex items-center gap-1.5 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100">
      <UserCheck size={14} /> {data.count} sign-in{data.count === 1 ? "" : "s"} to approve
    </Link>
  );
}

// ------------------------------------------------------------------ sign-in rules + recent sign-ins
interface Policy { approval: boolean; approval_hours: number; ip_allowlist: string[]; hours_from: string | null; hours_to: string | null; include_admins: boolean; your_ip?: string | null }
interface Sess { id: string; name: string; email: string; role: string | null; status: string; ip: string | null; device: string; first_seen: string; last_seen: string; decided_by: string | null; valid_until: string | null }

const STATUS: Record<string, [string, string]> = {
  AUTO: ["Signed in", "text-gray-600"], PENDING: ["Waiting for approval", "text-amber-700"],
  APPROVED: ["Approved", "text-emerald-700"], DENIED: ["Blocked", "text-red-700"],
};

export function StaffSignIns() {
  const { can } = usePerms();
  const canEdit = can("users", "edit");
  const { data: policy, reload: reloadPolicy } = useFetch<Policy>("/staff/policy");
  const { data: rows, reload } = useFetch<Sess[]>("/staff/sessions", { refreshMs: 30000 });
  const [editing, setEditing] = useState(false);

  async function decide(id: string, action: "approve" | "deny") {
    try { await api(`/staff/sessions/${id}/${action}`, { body: {} }); reload(); } catch (e) { alert((e as Error).message); }
  }
  if (!policy || !rows) return <Card className="p-5"><Loading /></Card>;
  const rules = [
    policy.approval && `every new sign-in needs approval (valid ${policy.approval_hours} h)`,
    policy.ip_allowlist.length > 0 && `only from ${policy.ip_allowlist.join(", ")}`,
    policy.hours_from && `only ${policy.hours_from}–${policy.hours_to}`,
  ].filter(Boolean);
  return (
    <div id="sign-ins"><Card className="overflow-x-auto">
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-4 pb-2">
        <div>
          <h2 className="flex items-center gap-2 font-semibold text-gray-900"><ShieldCheck size={17} /> Staff sign-ins</h2>
          <p className="text-sm text-gray-600">
            {rules.length ? `Rules: ${rules.join(" · ")}` : "No restrictions — staff can sign in from anywhere. Every sign-in is still listed here."}
            {policy.approval || policy.ip_allowlist.length || policy.hours_from ? (policy.include_admins ? " Applies to admins too." : " Admins are not restricted.") : ""}
          </p>
        </div>
        {canEdit && <Button variant="secondary" onClick={() => setEditing(true)}>Sign-in rules</Button>}
      </div>
      {rows.length === 0 ? <p className="px-5 pb-5 text-sm text-gray-500">No staff sign-ins yet.</p> : (
        <table className="tbl">
          <thead><tr><th>Staff</th><th>Signed in</th><th>Last active</th><th>From</th><th>Status</th><th /></tr></thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id} className={s.status === "PENDING" ? "bg-amber-50" : ""}>
                <td>{s.name}<div className="text-xs text-gray-500">{s.email}</div></td>
                <td className="whitespace-nowrap text-xs">{when(s.first_seen)}</td>
                <td className="whitespace-nowrap text-xs">{when(s.last_seen)}</td>
                <td className="text-xs">{s.device}<div className="font-mono text-gray-500">{s.ip ?? ""}</div></td>
                <td className={`text-xs ${STATUS[s.status]?.[1] ?? ""}`}>
                  {STATUS[s.status]?.[0] ?? s.status}
                  {s.decided_by && <div className="text-gray-500">by {s.decided_by}{s.valid_until && s.status === "APPROVED" ? ` · till ${when(s.valid_until)}` : ""}</div>}
                </td>
                <td className="whitespace-nowrap text-right">
                  {canEdit && s.status !== "APPROVED" && s.status !== "AUTO" && <Button className="!px-2 !py-1" onClick={() => decide(s.id, "approve")}><Check size={14} /> Approve</Button>}
                  {canEdit && s.status !== "DENIED" && (s.status !== "AUTO" || policy.approval) && (
                    <Button variant="ghost" className="!px-2 !py-1" onClick={() => decide(s.id, "deny")} title="Block this sign-in"><X size={14} /> {s.status === "PENDING" ? "Deny" : "Block"}</Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && <PolicyDialog policy={policy} onClose={() => setEditing(false)} onSaved={() => { reloadPolicy(); reload(); }} />}
    </Card></div>
  );
}

function PolicyDialog({ policy, onClose, onSaved }: { policy: Policy; onClose: () => void; onSaved: () => void }) {
  const [p, setP] = useState({ ...policy, ips: policy.ip_allowlist.join("\n"), hours: !!policy.hours_from });
  const [err, setErr] = useState<string | null>(null);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await api("/staff/policy", { method: "PUT", body: {
        approval: p.approval, approval_hours: Number(p.approval_hours) || 12, include_admins: p.include_admins,
        ip_allowlist: p.ips.split(/[\n,]+/).map((x) => x.trim()).filter(Boolean),
        hours_from: p.hours ? p.hours_from || "09:00" : null, hours_to: p.hours ? p.hours_to || "20:00" : null,
      } });
      onSaved();
      onClose();
    } catch (x) {
      setErr((x as Error).message);
    }
  }
  return (
    <Modal title="Staff sign-in rules" onClose={onClose}>
      <form onSubmit={save} className="space-y-4 text-sm">
        <ErrorBox message={err} />
        <p className="text-gray-600">These rules apply to staff of this business only — never to you (the owner). A person who also works for other businesses is not affected there.</p>
        <label className="flex items-start gap-2.5">
          <input type="checkbox" className="mt-0.5" checked={p.approval} onChange={(e) => setP({ ...p, approval: e.target.checked })} />
          <span><b>Approve every new sign-in</b><span className="block text-xs text-gray-500">Staff wait on a “waiting for approval” screen; you approve from the top bar or this page.</span></span>
        </label>
        {p.approval && (
          <Field label="An approval lasts (hours)" hint="e.g. 12 = one working day; after that they need a new approval">
            <Input type="number" min={1} max={168} value={p.approval_hours} onChange={(e) => setP({ ...p, approval_hours: Number(e.target.value) })} />
          </Field>
        )}
        <Field label="Only from these internet addresses (office)" hint={`One per line — an address or a range like 203.0.113.0/24. Leave empty to allow anywhere.${policy.your_ip ? ` Your address now: ${policy.your_ip}` : ""}`}>
          <textarea className="input font-mono text-xs" rows={3} value={p.ips} onChange={(e) => setP({ ...p, ips: e.target.value })} />
        </Field>
        {policy.your_ip && !p.ips.includes(policy.your_ip) && (
          <button type="button" className="text-xs text-brand-600 hover:underline" onClick={() => setP({ ...p, ips: [p.ips.trim(), policy.your_ip].filter(Boolean).join("\n") })}>
            + Add the address I am using now ({policy.your_ip})
          </button>
        )}
        <label className="flex items-center gap-2.5">
          <input type="checkbox" checked={p.hours} onChange={(e) => setP({ ...p, hours: e.target.checked })} /> <b>Only during working hours</b>
        </label>
        {p.hours && (
          <div className="grid grid-cols-2 gap-3">
            <Field label="From"><Input type="time" value={p.hours_from ?? "09:00"} onChange={(e) => setP({ ...p, hours_from: e.target.value })} /></Field>
            <Field label="To"><Input type="time" value={p.hours_to ?? "20:00"} onChange={(e) => setP({ ...p, hours_to: e.target.value })} /></Field>
          </div>
        )}
        <label className="flex items-center gap-2.5">
          <input type="checkbox" checked={p.include_admins} onChange={(e) => setP({ ...p, include_admins: e.target.checked })} /> Apply to business admins too
        </label>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit">Save rules</Button>
        </div>
      </form>
    </Modal>
  );
}
