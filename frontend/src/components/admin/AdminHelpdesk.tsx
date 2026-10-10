"use client";

import { LifeBuoy, Search } from "lucide-react";
import { useState } from "react";
import { CATEGORY_ICON, FilePicker, Priority, type TicketDetail, type TicketSummary, TicketStatus, TicketThread, when } from "@/components/Support";
import { Button, Card, ErrorBox, Input, Loading, Select, Textarea } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Row extends TicketSummary { assigned_to: string | null; user_name: string | null; user_email: string | null; user_phone: string | null }
interface Queue { rows: Row[]; counts: Record<string, number>; mine: number; unassigned: number; rating: { average: number | null; count: number } }
interface Meta { categories: Record<string, string>; priorities: string[]; statuses: Record<string, string>; teams: Record<string, string>; agents: { id: string; name: string; team: string }[]; me: string }
interface Detail extends TicketDetail, Omit<Row, keyof TicketSummary> {
  device: string | null; user_id: string; business_id: string | null;
  requester: { signed_up: string | null; last_login_at: string | null; plan: string | null; plan_status: string | null };
  other_tickets: Row[];
}

const age = (iso: string) => {
  const h = (Date.now() - new Date(iso).getTime()) / 3600000;
  return h < 1 ? `${Math.max(1, Math.round(h * 60))}m` : h < 48 ? `${Math.round(h)}h` : `${Math.round(h / 24)}d`;
};

/** Admin → Helpdesk: ticket queue, conversation, assignment, internal notes, status. */
export function AdminHelpdesk({ initialId }: { initialId?: string | null }) {
  const [f, setF] = useState({ status: "ACTIVE", assigned: "", team: "", category: "", priority: "", q: "" });
  const [openId, setOpenId] = useState<string | null>(initialId ?? null);
  const { data: meta } = useFetch<Meta>("/admin/helpdesk/meta");
  const { data, reload } = useFetch<Queue>(`/admin/helpdesk${qs(f)}`, { refreshMs: 60000 });

  const chips: [string, string, number | undefined][] = [
    ["ACTIVE", "Active", data ? data.counts.OPEN + data.counts.IN_PROGRESS + data.counts.WAITING : undefined],
    ["OPEN", "Open", data?.counts.OPEN], ["WAITING", "Waiting for customer", data?.counts.WAITING],
    ["RESOLVED", "Resolved", data?.counts.RESOLVED], ["CLOSED", "Closed", data?.counts.CLOSED], ["", "All", undefined],
  ];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900"><LifeBuoy size={18} className="text-brand-600" /> Helpdesk</h2>
          <p className="text-sm text-gray-500">Tickets raised from the Help button in the app. New tickets alert the right team (bell + e-mail).</p>
        </div>
        {data && <div className="flex gap-4 text-center text-xs text-gray-500">
          <div><div className="text-xl font-semibold text-gray-900">{data.mine}</div>mine</div>
          <div><div className="text-xl font-semibold text-amber-700">{data.unassigned}</div>unassigned</div>
          <div><div className="text-xl font-semibold text-emerald-700">{data.rating.average ?? "–"}</div>rating ({data.rating.count})</div>
        </div>}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {chips.map(([k, l, n]) => (
          <button key={l} onClick={() => setF({ ...f, status: k })}
            className={`rounded-full px-3 py-1 text-sm ${f.status === k ? "bg-brand-600 text-white" : "bg-white text-gray-700 ring-1 ring-gray-200 hover:bg-gray-50"}`}>
            {l}{n !== undefined ? ` · ${n}` : ""}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <div className="relative"><Search size={15} className="absolute top-2.5 left-2.5 text-gray-400" />
          <Input className="!pl-8" placeholder="T-1001, subject, name, e-mail, business" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} /></div>
        <Select value={f.assigned} onChange={(e) => setF({ ...f, assigned: e.target.value })}>
          <option value="">Anyone</option><option value="me">Assigned to me</option><option value="none">Unassigned</option>
          {meta?.agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </Select>
        <Select value={f.team} onChange={(e) => setF({ ...f, team: e.target.value })}>
          <option value="">All teams</option>{meta && Object.entries(meta.teams).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
          <option value="">All types</option>{meta && Object.entries(meta.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Select value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>
          <option value="">Any priority</option>{meta?.priorities.map((p) => <option key={p} value={p}>{p.charAt(0) + p.slice(1).toLowerCase()}</option>)}
        </Select>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <Card className="self-start overflow-hidden">
          {!data ? <Loading /> : data.rows.length === 0 ? <p className="p-5 text-sm text-gray-500">No tickets here.</p> : data.rows.map((t) => {
            const Icon = CATEGORY_ICON[t.category] ?? LifeBuoy;
            return (
              <button key={t.id} onClick={() => setOpenId(t.id)}
                className={`flex w-full gap-2.5 border-b border-gray-100 px-4 py-3 text-left hover:bg-gray-50 ${openId === t.id ? "bg-brand-50/60" : ""}`}>
                <Icon size={16} className="mt-0.5 shrink-0 text-gray-400" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-gray-900">{t.subject}</span>
                  <span className="block truncate text-xs text-gray-500">{t.code} · {t.user_name}{t.business_name ? ` · ${t.business_name}` : ""}</span>
                  <span className="mt-0.5 flex items-center gap-2 text-xs text-gray-500"><Priority p={t.priority} /> · {t.assigned_name ?? <span className="text-amber-700">unassigned</span>} · {age(t.created_at)} old</span>
                </span>
                <TicketStatus t={t} />
              </button>
            );
          })}
        </Card>
        <div>{openId ? <TicketPane key={openId} id={openId} meta={meta} onChange={reload} onOpen={setOpenId} /> : <Card className="p-6 text-sm text-gray-500">Pick a ticket.</Card>}</div>
      </div>
    </div>
  );
}

function TicketPane({ id, meta, onChange, onOpen }: { id: string; meta: Meta | null; onChange: () => void; onOpen: (id: string) => void }) {
  const { data: t, setData, error } = useFetch<Detail>(`/admin/helpdesk/${id}`);
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);
  const [after, setAfter] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (error) return <ErrorBox message={error} />;
  if (!t) return <Loading />;

  const run = async (fn: () => Promise<Detail>) => {
    setErr(null); setBusy(true);
    try { setData(await fn()); onChange(); return true; } catch (e) { setErr((e as Error).message); return false; } finally { setBusy(false); }
  };
  const update = (body: Record<string, unknown>) => run(() => api<Detail>(`/admin/helpdesk/${id}`, { method: "PUT", body }));
  async function send() {
    const form = new FormData();
    form.append("body", body);
    form.append("internal", String(internal));
    if (after) form.append("status", after);
    files.forEach((x) => form.append("files", x));
    if (await run(() => api<Detail>(`/admin/helpdesk/${id}/messages`, { form }))) { setBody(""); setFiles([]); setAfter(""); }
  }

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 pb-3">
        <div className="min-w-0">
          <div className="text-xs text-gray-500">{t.code} · {t.category_label} · raised {when(t.created_at)}{t.first_response_at ? ` · first reply ${age(t.created_at)} → ${when(t.first_response_at)}` : " · no reply yet"}</div>
          <h3 className="text-lg font-semibold text-gray-900">{t.subject}</h3>
          <div className="text-sm text-gray-700">{t.user_name} · <a className="text-brand-600 hover:underline" href={`mailto:${t.user_email}`}>{t.user_email}</a>
            {t.user_phone && <> · <a className="text-brand-600 hover:underline" href={`tel:+${t.user_phone.replace(/\D/g, "")}`}>{t.user_phone}</a></>}</div>
          <div className="text-xs text-gray-500">
            {t.business_name ?? "No business"} · {t.requester.plan} {t.requester.plan_status?.toLowerCase()} · joined {fmtDate(t.requester.signed_up)}
            {t.module ? ` · from ${t.module}` : ""}{t.page ? ` (${t.page})` : ""}
          </div>
          {t.device && <div className="truncate text-[11px] text-gray-400" title={t.device}>{t.device}</div>}
        </div>
        <TicketStatus t={t} />
      </div>
      <div className="grid gap-2 border-b border-gray-100 py-3 sm:grid-cols-4">
        <Select value={t.status} onChange={(e) => update({ status: e.target.value })} aria-label="Status">
          {meta && Object.entries(meta.statuses).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Select value={t.assigned_to ?? ""} onChange={(e) => update(e.target.value ? { assigned_to: e.target.value } : { unassign: true })} aria-label="Assigned to">
          <option value="">Unassigned</option>{meta?.agents.map((a) => <option key={a.id} value={a.id}>{a.name}{a.id === meta.me ? " (me)" : ""} · {a.team}</option>)}
        </Select>
        <Select value={t.team} onChange={(e) => update({ team: e.target.value })} aria-label="Team">
          {meta && Object.entries(meta.teams).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Select value={t.priority} onChange={(e) => update({ priority: e.target.value })} aria-label="Priority">
          {meta?.priorities.map((p) => <option key={p} value={p}>{p.charAt(0) + p.slice(1).toLowerCase()}</option>)}
        </Select>
      </div>
      <div className="py-4"><TicketThread t={t} teamView /></div>
      {t.rating && <p className="mb-3 rounded-md bg-emerald-50 px-3 py-2 text-xs text-emerald-800">Customer rated {t.rating}/5{t.rating_note ? ` — “${t.rating_note}”` : ""}</p>}
      <ErrorBox message={err} />
      <div className={`space-y-2 rounded-xl border p-3 ${internal ? "border-amber-300 bg-amber-50/50" : "border-gray-200"}`}>
        <div className="flex gap-1 text-xs">
          <button onClick={() => setInternal(false)} className={`rounded-md px-2.5 py-1 ${!internal ? "bg-brand-600 text-white" : "text-gray-600"}`}>Reply to customer</button>
          <button onClick={() => setInternal(true)} className={`rounded-md px-2.5 py-1 ${internal ? "bg-amber-500 text-white" : "text-gray-600"}`}>Internal note</button>
        </div>
        <Textarea rows={4} placeholder={internal ? "Only the team sees this" : "The customer gets this in the app and by e-mail"} value={body} onChange={(e) => setBody(e.target.value)} />
        <div className="flex flex-wrap items-start justify-between gap-2">
          <FilePicker files={files} onChange={setFiles} />
          <div className="flex items-center gap-2">
            <Select value={after} onChange={(e) => setAfter(e.target.value)} aria-label="Status after sending">
              <option value="">Keep status</option><option value="WAITING">Waiting for customer</option><option value="RESOLVED">Mark resolved</option>
            </Select>
            <Button disabled={busy || !body.trim()} onClick={send}>{internal ? "Add note" : "Send reply"}</Button>
          </div>
        </div>
      </div>
      {t.other_tickets.length > 0 && (
        <div className="mt-4">
          <div className="mb-1 text-xs font-semibold text-gray-500 uppercase">Their other tickets</div>
          {t.other_tickets.map((o) => (
            <button key={o.id} onClick={() => onOpen(o.id)} className="flex w-full items-center justify-between gap-2 border-b border-gray-50 py-1.5 text-left text-xs hover:bg-gray-50">
              <span className="truncate">{o.code} · {o.subject}</span><TicketStatus t={o} />
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}
