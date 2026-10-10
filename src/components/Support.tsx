"use client";

import { Bug, CircleHelp, CreditCard, LifeBuoy, Lightbulb, MessageSquareHeart, Paperclip, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Field, Input, Select, Textarea } from "@/components/ui";
import { api, apiBlob } from "@/lib/api";

export interface TicketFile { id: string; name: string; size: number; content_type: string }
export interface TicketMsg { id: string; body: string; by_team: boolean; internal: boolean; created_at: string; author: string; files: TicketFile[] }
export interface TicketSummary {
  id: string; code: string; number: number; category: string; category_label: string; subject: string; priority: string; status: string;
  status_label: string; team: string; module: string | null; page: string | null; created_at: string; last_activity_at: string;
  first_response_at: string | null; resolved_at: string | null; rating: number | null; rating_note: string | null;
  business_name: string | null; assigned_name: string | null;
}
export interface TicketDetail extends TicketSummary { messages: TicketMsg[]; files: (TicketFile & { created_at: string })[] }

export const CATEGORY_ICON: Record<string, React.ElementType> = {
  ISSUE: Bug, QUESTION: CircleHelp, FEEDBACK: MessageSquareHeart, FEATURE: Lightbulb, BILLING: CreditCard,
};
const CATEGORIES: [string, string][] = [
  ["ISSUE", "Something is not working"], ["QUESTION", "Question / how do I"], ["FEATURE", "New feature / requirement"],
  ["FEEDBACK", "Feedback"], ["BILLING", "Billing & subscription"],
];
const STATUS_STYLE: Record<string, string> = {
  OPEN: "bg-brand-50 text-brand-700 ring-brand-100", IN_PROGRESS: "bg-amber-50 text-amber-800 ring-amber-200",
  WAITING: "bg-violet-50 text-violet-700 ring-violet-200", RESOLVED: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  CLOSED: "bg-gray-100 text-gray-600 ring-gray-200",
};
const PRIORITY_STYLE: Record<string, string> = { URGENT: "text-red-700", HIGH: "text-orange-700", NORMAL: "text-gray-600", LOW: "text-gray-400" };

export function TicketStatus({ t }: { t: Pick<TicketSummary, "status" | "status_label"> }) {
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset ${STATUS_STYLE[t.status] ?? STATUS_STYLE.OPEN}`}>{t.status_label}</span>;
}
export const Priority = ({ p }: { p: string }) => <span className={`text-xs font-medium ${PRIORITY_STYLE[p] ?? ""}`}>{p.charAt(0) + p.slice(1).toLowerCase()}</span>;

export const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export async function openTicketFile(f: TicketFile) {
  const { blob } = await apiBlob(`/support/files/${f.id}`);
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function FileChips({ files }: { files: TicketFile[] }) {
  if (!files.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {files.map((f) => (
        <button key={f.id} onClick={() => openTicketFile(f).catch(() => alert("Could not open the file"))}
          className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-0.5 text-xs text-gray-700 hover:bg-gray-50">
          <Paperclip size={11} /> {f.name} <span className="text-gray-400">{Math.max(1, Math.round(f.size / 1024))} KB</span>
        </button>
      ))}
    </div>
  );
}

/** Conversation of a ticket. `teamView` shows internal notes (yellow) and real agent names. */
export function TicketThread({ t, teamView = false }: { t: TicketDetail; teamView?: boolean }) {
  const loose = t.files.filter((f) => !t.messages.some((m) => m.files.some((x) => x.id === f.id)));
  return (
    <div className="space-y-3">
      {t.messages.map((m) => {
        const mine = teamView ? m.by_team : !m.by_team;
        return (
          <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm ${m.internal ? "border border-amber-200 bg-amber-50" : mine ? "bg-brand-50" : "bg-gray-100"}`}>
              <div className="mb-0.5 flex items-center gap-2 text-[11px] text-gray-500">
                <b className="text-gray-700">{m.author}</b>{m.internal && <span className="rounded bg-amber-200 px-1 text-amber-900">internal note</span>}{when(m.created_at)}
              </div>
              <div className="whitespace-pre-wrap text-gray-800">{m.body}</div>
              <FileChips files={m.files} />
            </div>
          </div>
        );
      })}
      {loose.length > 0 && <FileChips files={loose} />}
    </div>
  );
}

export function FilePicker({ files, onChange }: { files: File[]; onChange: (f: File[]) => void }) {
  return (
    <div>
      <label className="inline-flex cursor-pointer items-center gap-1.5 text-sm text-brand-600 hover:underline">
        <Paperclip size={14} /> Attach screenshot / file
        <input type="file" multiple className="hidden" accept="image/*,application/pdf,.txt,.csv,.xlsx"
          onChange={(e) => { onChange([...files, ...Array.from(e.target.files ?? [])].slice(0, 5)); e.target.value = ""; }} />
      </label>
      {files.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {files.map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
              {f.name} <button aria-label="Remove" onClick={() => onChange(files.filter((_, j) => j !== i))}><X size={11} /></button>
            </span>
          ))}
        </div>
      )}
      <p className="mt-1 text-[11px] text-gray-400">Up to 5 files, 5 MB each — images, PDF, text, CSV or Excel.</p>
    </div>
  );
}

/** Floating “Help” button on every screen of the app: raise a ticket about what you are looking at. */
export function HelpButton({ module }: { module?: string }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)} aria-label="Help & support"
        className="no-print fixed right-4 bottom-20 z-30 inline-flex items-center gap-1.5 rounded-full bg-brand-600 px-4 py-2.5 text-sm font-medium text-white shadow-lg shadow-brand-900/20 hover:bg-brand-700 md:bottom-5">
        <LifeBuoy size={17} /> Help
      </button>
      {open && <RaiseTicket module={module} page={pathname} onClose={() => setOpen(false)} />}
    </>
  );
}

export function RaiseTicket({ module, page, onClose, onDone }: { module?: string; page?: string; onClose: () => void; onDone?: (t: TicketSummary) => void }) {
  const [f, setF] = useState({ category: "ISSUE", subject: "", body: "", priority: "NORMAL" });
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<TicketSummary | null>(null);

  async function submit() {
    setErr(null); setBusy(true);
    const form = new FormData();
    Object.entries(f).forEach(([k, v]) => form.append(k, v));
    if (module) form.append("module", module.slice(0, 80));
    if (page) form.append("page", page.slice(0, 300));
    files.forEach((x) => form.append("files", x));
    try {
      const t = await api<TicketSummary>("/support/tickets", { form });
      setDone(t); onDone?.(t);
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }

  return (
    <Modal title={done ? "Ticket raised" : "Help & support"} onClose={onClose} wide>
      {done ? (
        <div className="space-y-3 text-sm">
          <p className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-800">Thank you — your ticket <b>{done.code}</b> has reached our support team. We&apos;ll reply here and by e-mail.</p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>Close</Button>
            <Link href={`/support?t=${done.id}`} onClick={onClose} className="inline-flex items-center rounded-lg bg-brand-600 px-3 py-2 text-white hover:bg-brand-700">View my tickets</Link>
          </div>
        </div>
      ) : (
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {CATEGORIES.map(([k, label]) => {
              const Icon = CATEGORY_ICON[k];
              return (
                <button key={k} onClick={() => setF({ ...f, category: k })}
                  className={`flex flex-col items-center gap-1 rounded-lg border px-2 py-2.5 text-center text-xs ${f.category === k ? "border-brand-500 bg-brand-50 text-brand-800" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
                  <Icon size={18} /> {label}
                </button>
              );
            })}
          </div>
          <Field label="Subject"><Input value={f.subject} maxLength={200} placeholder={f.category === "FEATURE" ? "e.g. Add a sales report by salesperson" : "In a few words"} onChange={(e) => setF({ ...f, subject: e.target.value })} /></Field>
          <Field label={f.category === "ISSUE" ? "What happened, and what did you expect?" : "Details"}>
            <Textarea rows={5} value={f.body} maxLength={10000} onChange={(e) => setF({ ...f, body: e.target.value })} />
          </Field>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <FilePicker files={files} onChange={setFiles} />
            <Field label="How urgent?"><Select value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>
              <option value="LOW">Low — whenever possible</option><option value="NORMAL">Normal</option>
              <option value="HIGH">High — blocking my work</option><option value="URGENT">Urgent — business stopped</option>
            </Select></Field>
          </div>
          {module && <p className="text-xs text-gray-500">We&apos;ll note that you raised this from <b>{module}</b>{page ? ` (${page})` : ""}, so the team knows where to look.</p>}
          <ErrorBox message={err} />
          <div className="flex items-center justify-between gap-2">
            <Link href="/support" onClick={onClose} className="text-xs text-gray-500 hover:underline">My tickets</Link>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={onClose}>Cancel</Button>
              <Button disabled={busy || f.subject.trim().length < 3 || f.body.trim().length < 5} onClick={submit}>{busy ? "Sending…" : "Send to support"}</Button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
