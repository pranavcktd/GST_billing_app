"use client";

import { LifeBuoy, Plus, Star } from "lucide-react";
import { useState } from "react";
import { CATEGORY_ICON, FilePicker, RaiseTicket, type TicketDetail, type TicketSummary, TicketStatus, TicketThread, when } from "@/components/Support";
import { Button, Card, Empty, ErrorBox, Loading, PageHeader, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useConfig } from "@/lib/config";
import { useFetch } from "@/lib/useFetch";

/** Help & support: the person's own tickets, the conversation with our team, reply / close / rate. */
export default function SupportPage() {
  const [openId, setOpenId] = useState<string | null>(() => (typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("t")));
  const [raising, setRaising] = useState(false);
  const { data: list, reload } = useFetch<TicketSummary[]>("/support/tickets");
  const company = useConfig().company;

  return (
    <>
      <PageHeader title="Help & support" sub="Raise an issue, ask a question or suggest a feature — our team replies here and by e-mail."
        actions={<Button onClick={() => setRaising(true)}><Plus size={16} /> New ticket</Button>} />
      <div className="grid gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Card className="self-start overflow-hidden">
          {!list ? <Loading /> : list.length === 0 ? <Empty title="No tickets yet." action={<Button variant="secondary" onClick={() => setRaising(true)}>Ask for help</Button>} /> : list.map((t) => {
            const Icon = CATEGORY_ICON[t.category] ?? LifeBuoy;
            return (
              <button key={t.id} onClick={() => setOpenId(t.id)}
                className={`flex w-full gap-2.5 border-b border-gray-100 px-4 py-3 text-left hover:bg-gray-50 ${openId === t.id ? "bg-brand-50/60" : ""}`}>
                <Icon size={16} className="mt-0.5 shrink-0 text-gray-400" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-gray-900">{t.subject}</span>
                  <span className="text-xs text-gray-500">{t.code} · {when(t.last_activity_at)}</span>
                </span>
                <TicketStatus t={t} />
              </button>
            );
          })}
        </Card>
        <div>
          {openId ? <TicketView key={openId} id={openId} onChange={reload} /> : (
            <Card className="p-6 text-sm text-gray-600">
              <p>Pick a ticket to see the conversation, or raise a new one. You can also tap <b>Help</b> at the bottom-right of any screen.</p>
              <p className="mt-3 text-xs text-gray-500">Prefer to talk? {company.phone} · {company.email}</p>
            </Card>
          )}
        </div>
      </div>
      {raising && <RaiseTicket page="/support" onClose={() => setRaising(false)} onDone={(t) => { reload(); setOpenId(t.id); }} />}
    </>
  );
}

function TicketView({ id, onChange }: { id: string; onChange: () => void }) {
  const { data: t, setData, error } = useFetch<TicketDetail>(`/support/tickets/${id}`);
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [stars, setStars] = useState(0);

  if (error) return <ErrorBox message={error} />;
  if (!t) return <Loading />;

  const run = async (fn: () => Promise<TicketDetail>) => {
    setErr(null); setBusy(true);
    try { setData(await fn()); onChange(); return true; } catch (e) { setErr((e as Error).message); return false; } finally { setBusy(false); }
  };
  async function send() {
    const form = new FormData();
    form.append("body", body);
    files.forEach((f) => form.append("files", f));
    if (await run(() => api<TicketDetail>(`/support/tickets/${id}/messages`, { form }))) { setBody(""); setFiles([]); }
  }

  const closed = t.status === "CLOSED";
  return (
    <Card className="p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2 border-b border-gray-100 pb-3">
        <div>
          <div className="text-xs text-gray-500">{t.code} · {t.category_label}{t.module ? ` · from ${t.module}` : ""}</div>
          <h2 className="text-lg font-semibold text-gray-900">{t.subject}</h2>
          <div className="text-xs text-gray-500">Raised {when(t.created_at)}{t.assigned_name ? ` · handled by our support team` : ""}</div>
        </div>
        <div className="flex items-center gap-2">
          <TicketStatus t={t} />
          {closed ? <Button variant="secondary" className="!py-1" disabled={busy} onClick={() => run(() => api(`/support/tickets/${id}/state`, { body: { action: "reopen" } }))}>Reopen</Button>
            : <Button variant="ghost" className="!py-1" disabled={busy} onClick={() => run(() => api(`/support/tickets/${id}/state`, { body: { action: "close" } }))}>Close ticket</Button>}
        </div>
      </div>
      <TicketThread t={t} />
      <ErrorBox message={err} />
      {!closed && (
        <div className="mt-4 space-y-2 border-t border-gray-100 pt-4">
          <Textarea rows={3} placeholder={t.status === "RESOLVED" ? "Still not fixed? Reply and the ticket opens again." : "Write a reply…"} value={body} onChange={(e) => setBody(e.target.value)} />
          <div className="flex flex-wrap items-start justify-between gap-2">
            <FilePicker files={files} onChange={setFiles} />
            <Button disabled={busy || !body.trim()} onClick={send}>Send reply</Button>
          </div>
        </div>
      )}
      {(t.status === "RESOLVED" || closed) && (
        <div className="mt-4 rounded-lg bg-gray-50 p-3 text-sm">
          {t.rating ? <p className="text-gray-600">You rated this help {t.rating}/5{t.rating_note ? ` — “${t.rating_note}”` : ""}. Thank you!</p> : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-gray-600">How was our help?</span>
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} aria-label={`${n} stars`} onClick={() => setStars(n)}><Star size={20} className={n <= stars ? "fill-amber-400 text-amber-400" : "text-gray-300"} /></button>
              ))}
              {stars > 0 && <Button className="!py-1" disabled={busy} onClick={() => run(() => api(`/support/tickets/${id}/rate`, { body: { rating: stars } }))}>Send rating</Button>}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
