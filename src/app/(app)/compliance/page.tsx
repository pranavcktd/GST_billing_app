"use client";

import { AlertTriangle, CalendarClock, CheckCircle2, Clock, Settings2, Undo2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { PortalLink } from "@/components/PortalLink";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { usePerms } from "@/lib/auth";
import { ENTITY_TYPES } from "@/lib/constants";
import { fmtDate, money, today } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

type Status = "OVERDUE" | "DUE_SOON" | "UPCOMING" | "DONE";
interface Item {
  code: string; name: string; authority: string; authority_label: string; description: string; penalty: string;
  link: string | null; period_key: string; period: string; due_date: string; status: Status; days_overdue: number;
  days_left: number; late_fee_so_far: number | null;
  done: { id: string; done_on: string; reference: string | null; note: string | null; by: string | null } | null;
}
interface Settings { gst_filing: "MONTHLY" | "QUARTERLY"; tax_audit: boolean; tds: boolean; payroll: boolean; track_from: string }
interface Calendar { settings: Settings; items: Item[]; summary: Record<Status, number>; disclaimer: string; entity_type: string; gst_type: string }

const GST_LABEL: Record<string, string> = { REGULAR: "GST regular", COMPOSITION: "GST composition", UNREGISTERED: "Not GST registered" };
const TONE: Record<Status, string> = {
  OVERDUE: "border-red-200 bg-red-50 text-red-700", DUE_SOON: "border-amber-200 bg-amber-50 text-amber-800",
  UPCOMING: "border-gray-200 bg-gray-50 text-gray-700", DONE: "border-emerald-200 bg-emerald-50 text-emerald-700",
};
const FILTERS: { key: "PENDING" | Status; label: string }[] = [
  { key: "PENDING", label: "To do" }, { key: "OVERDUE", label: "Overdue" }, { key: "DUE_SOON", label: "Due in 15 days" },
  { key: "UPCOMING", label: "Upcoming" }, { key: "DONE", label: "Filed" },
];

function badge(i: Item) {
  if (i.status === "DONE") return "Filed";
  if (i.status === "OVERDUE") return `${i.days_overdue} day${i.days_overdue === 1 ? "" : "s"} late`;
  if (i.days_left === 0) return "Due today";
  return `In ${i.days_left} day${i.days_left === 1 ? "" : "s"}`;
}

export default function CompliancePage() {
  const { data, error, reload } = useFetch<Calendar>("/compliance/calendar");
  const { can } = usePerms();
  const [filter, setFilter] = useState<"PENDING" | Status>("PENDING");
  const [authority, setAuthority] = useState("");
  const [marking, setMarking] = useState<Item | null>(null);
  const [profile, setProfile] = useState(false);

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;

  const authorities = [...new Map(data.items.map((i) => [i.authority, i.authority_label])).entries()];
  const shown = data.items.filter((i) => (filter === "PENDING" ? i.status !== "DONE" : i.status === filter) && (!authority || i.authority === authority));

  async function undo(i: Item) {
    if (!i.done || !confirm(`Mark ${i.name} (${i.period}) as not filed?`)) return;
    await api(`/compliance/tasks/${i.done.id}`, { method: "DELETE" }).catch((e) => alert(e.message));
    reload();
  }

  const cards: { status: Status; label: string; icon: React.ElementType }[] = [
    { status: "OVERDUE", label: "Overdue", icon: AlertTriangle }, { status: "DUE_SOON", label: "Due in 15 days", icon: Clock },
    { status: "UPCOMING", label: "Upcoming", icon: CalendarClock }, { status: "DONE", label: "Filed", icon: CheckCircle2 },
  ];

  return (
    <>
      <PageHeader title="Compliance calendar"
        sub={`${ENTITY_TYPES[data.entity_type] ?? data.entity_type} · ${GST_LABEL[data.gst_type] ?? data.gst_type} — returns and filings that apply to you, with due dates`}
        actions={<Button variant="secondary" onClick={() => setProfile(true)}><Settings2 size={16} /> Your compliance profile</Button>} />

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {cards.map(({ status, label, icon: Icon }) => (
          <button key={status} onClick={() => setFilter(status)} className="text-left">
            <Card className={`p-4 ${filter === status ? "ring-2 ring-brand-200" : ""}`}>
              <div className="flex items-center gap-1.5 text-xs text-gray-500"><Icon size={14} /> {label}</div>
              <div className={`mt-1 text-2xl font-semibold ${status === "OVERDUE" && data.summary.OVERDUE ? "text-red-700" : status === "DUE_SOON" && data.summary.DUE_SOON ? "text-amber-700" : "text-gray-900"}`}>{data.summary[status]}</div>
            </Card>
          </button>
        ))}
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="inline-flex flex-wrap rounded-lg border border-gray-200 bg-white p-0.5 text-sm">
          {FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)} className={`rounded-md px-3 py-1.5 ${filter === f.key ? "bg-brand-600 text-white" : "text-gray-700"}`}>{f.label}</button>
          ))}
        </div>
        <Select className="!w-auto" value={authority} onChange={(e) => setAuthority(e.target.value)}>
          <option value="">All laws</option>
          {authorities.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      </div>

      {shown.length === 0 ? (
        <Card><Empty title={filter === "OVERDUE" ? "Nothing overdue — well done." : "Nothing here"} /></Card>
      ) : (
        <div className="space-y-2.5">
          {shown.map((i) => (
            <Card key={`${i.code}:${i.period_key}`} className={`p-4 ${i.status === "OVERDUE" ? "border-red-200" : ""}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded border px-1.5 py-0.5 text-[11px] font-medium ${TONE[i.status]}`}>{badge(i)}</span>
                    <span className="text-[11px] tracking-wide text-gray-400 uppercase">{i.authority_label}</span>
                  </div>
                  <div className="mt-1 font-medium text-gray-900">{i.name} <span className="font-normal text-gray-500">— {i.period}</span></div>
                  <div className="text-sm text-gray-600">Due {fmtDate(i.due_date)} · {i.description}</div>
                  {i.status === "OVERDUE" && (
                    <div className="mt-2 rounded-md bg-red-50 px-3 py-2 text-xs text-red-800">
                      <b>If not filed:</b> {i.penalty}
                      {i.late_fee_so_far !== null && <> <b>Late fee so far: about {money(i.late_fee_so_far)}</b> (estimate — the actual amount depends on your turnover and the return).</>}
                    </div>
                  )}
                  {i.status === "DUE_SOON" && <div className="mt-1.5 text-xs text-amber-800">If late: {i.penalty}</div>}
                  {i.done && (
                    <div className="mt-1.5 text-xs text-emerald-800">
                      Filed on {fmtDate(i.done.done_on)}{i.done.reference ? ` · Ref. ${i.done.reference}` : ""}{i.done.by ? ` · marked by ${i.done.by}` : ""}{i.done.note ? ` · ${i.done.note}` : ""}
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  {i.link && i.status !== "DONE" && <PortalLink to={i.link} button>Portal</PortalLink>}
                  {i.status === "DONE"
                    ? <Button variant="ghost" onClick={() => undo(i)}><Undo2 size={15} /> Undo</Button>
                    : <Button variant={i.status === "OVERDUE" ? "primary" : "secondary"} onClick={() => setMarking(i)}><CheckCircle2 size={15} /> Mark as filed</Button>}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <p className="mt-5 text-xs text-gray-500">{data.disclaimer}</p>

      {marking && <MarkDone item={marking} onClose={() => setMarking(null)} onDone={reload} />}
      {profile && <ProfileDialog cal={data} canEdit={can("settings", "edit")} onClose={() => setProfile(false)} onSaved={reload} />}
    </>
  );
}

function MarkDone({ item, onClose, onDone }: { item: Item; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ done_on: today(), reference: "", note: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await api("/compliance/tasks", { body: { rule_code: item.code, period_key: item.period_key, ...f, reference: f.reference || null, note: f.note || null } });
      onDone();
      onClose();
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={`${item.name} — ${item.period}`} onClose={onClose}>
      <form onSubmit={save} className="space-y-3">
        <ErrorBox message={err} />
        <p className="text-sm text-gray-600">Record that this was filed / paid. It helps you and your accountant see what is pending.</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Filed / paid on"><Input type="date" required value={f.done_on} onChange={(e) => setF({ ...f, done_on: e.target.value })} /></Field>
          <Field label="Reference" hint="ARN / SRN / challan no."><Input value={f.reference} maxLength={100} onChange={(e) => setF({ ...f, reference: e.target.value })} /></Field>
        </div>
        <Field label="Note"><Input value={f.note} maxLength={300} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Mark as filed"}</Button>
        </div>
      </form>
    </Modal>
  );
}

function ProfileDialog({ cal, canEdit, onClose, onSaved }: { cal: Calendar; canEdit: boolean; onClose: () => void; onSaved: () => void }) {
  const [s, setS] = useState<Settings>(cal.settings);
  const [err, setErr] = useState<string | null>(null);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await api("/compliance/settings", { method: "PUT", body: s });
      onSaved();
      onClose();
    } catch (x) {
      setErr((x as Error).message);
    }
  }
  const check = (k: "tax_audit" | "tds" | "payroll", label: string, hint: string) => (
    <label className="flex items-start gap-2.5 text-sm">
      <input type="checkbox" className="mt-0.5" disabled={!canEdit} checked={s[k]} onChange={(e) => setS({ ...s, [k]: e.target.checked })} />
      <span><span className="font-medium text-gray-900">{label}</span><span className="block text-xs text-gray-500">{hint}</span></span>
    </label>
  );
  return (
    <Modal title="Your compliance profile" onClose={onClose}>
      <form onSubmit={save} className="space-y-4">
        <ErrorBox message={err} />
        <p className="text-sm text-gray-600">
          Type of business: <b>{ENTITY_TYPES[cal.entity_type] ?? cal.entity_type}</b> · {GST_LABEL[cal.gst_type] ?? cal.gst_type}.{" "}
          <Link href="/settings" className="text-brand-600 hover:underline">Change in Settings → Business</Link>
        </p>
        {cal.gst_type === "REGULAR" && (
          <Field label="GST returns" hint="Quarterly (QRMP) is open to businesses with turnover up to ₹5 crore that opted for it">
            <Select disabled={!canEdit} value={s.gst_filing} onChange={(e) => setS({ ...s, gst_filing: e.target.value as Settings["gst_filing"] })}>
              <option value="MONTHLY">Monthly GSTR-1 and GSTR-3B</option>
              <option value="QUARTERLY">Quarterly (QRMP) with monthly tax payment</option>
            </Select>
          </Field>
        )}
        {check("tax_audit", "Our accounts need a tax audit", "Turnover above the income-tax audit limit (or other audit cases) — return due 31 Oct")}
        {check("tds", "We deduct TDS (we have a TAN)", "Shows monthly TDS deposit and quarterly TDS returns")}
        {check("payroll", "We have employees under PF / ESI", "Shows monthly PF and ESI deposits")}
        <Field label="Show filings due from" hint="Earlier filings are not listed — set an older date to track past returns too">
          <Input type="date" disabled={!canEdit} value={s.track_from} onChange={(e) => setS({ ...s, track_from: e.target.value })} />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>{canEdit ? "Cancel" : "Close"}</Button>
          {canEdit && <Button type="submit">Save</Button>}
        </div>
      </form>
    </Modal>
  );
}
