"use client";

import { Megaphone, Pencil, Plus, Send, Trash2 } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Change { hsn_prefix: string; description: string | null; new_rate: number; new_cess: number | null }
interface Notice {
  id: string; title: string; reference: string | null; effective_from: string; changes: Change[]; note: string | null;
  published_at: string | null; created_by: string | null; businesses_applied: number;
}
interface Draft { id?: string; title: string; reference: string; effective_from: string; note: string; changesText: string }

const empty: Draft = { title: "", reference: "", effective_from: new Date().toISOString().slice(0, 10), note: "", changesText: "" };

/** "HSN prefix, new GST %, [cess %], [description]" — one change per line. */
function parseChanges(t: string): Change[] {
  return t.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
    const [prefix, rate, cess, ...desc] = l.split(",").map((x) => x.trim());
    return { hsn_prefix: prefix, new_rate: Number(rate), new_cess: cess ? Number(cess) : null, description: desc.join(", ") || null };
  });
}
const changesText = (cs: Change[]) => cs.map((c) => [c.hsn_prefix, c.new_rate, c.new_cess ?? "", c.description ?? ""].join(", ").replace(/, (, )?$/, "")).join("\n");

export function AdminRateNotices() {
  const { data, reload } = useFetch<Notice[]>("/admin/rate-notices");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    if (!draft) return;
    setErr(null);
    const body = { title: draft.title, reference: draft.reference || null, effective_from: draft.effective_from,
      note: draft.note || null, changes: parseChanges(draft.changesText) };
    try {
      await api(draft.id ? `/admin/rate-notices/${draft.id}` : "/admin/rate-notices", { method: draft.id ? "PUT" : "POST", body });
      setDraft(null);
      reload();
    } catch (e) { setErr((e as Error).message); }
  }

  async function publish(n: Notice) {
    if (!confirm(`Publish "${n.title}" to every business?\nMatching codes in the HSN master will be updated to the new rates. A published notice cannot be edited.`)) return;
    try { await api(`/admin/rate-notices/${n.id}/publish`, { body: {} }); reload(); } catch (e) { setErr((e as Error).message); }
  }

  return (
    <div className="space-y-5">
      <Card className="flex flex-wrap items-center justify-between gap-3 p-4 text-sm text-gray-600">
        <span>When the GST Council changes rates, publish a notice here. Every business sees which of its items are affected and updates them in one click.</span>
        <Button onClick={() => setDraft(empty)}><Plus size={15} /> New notice</Button>
      </Card>
      <ErrorBox message={err} />
      {!data ? <Loading /> : data.length === 0 ? <Card className="p-5 text-sm text-gray-500">No notices yet.</Card> : data.map((n) => (
        <Card key={n.id} className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 font-semibold text-gray-900"><Megaphone size={16} /> {n.title}</div>
              <div className="text-xs text-gray-500">
                Effective {fmtDate(n.effective_from)}{n.reference ? ` · ${n.reference}` : ""} ·{" "}
                {n.published_at ? <span className="text-emerald-700">Published {new Date(n.published_at).toLocaleDateString("en-IN")} · applied by {n.businesses_applied} businesses</span> : <span className="text-amber-700">Draft</span>}
              </div>
            </div>
            <div className="flex gap-2">
              {!n.published_at && (
                <>
                  <Button variant="ghost" onClick={() => setDraft({ id: n.id, title: n.title, reference: n.reference ?? "", effective_from: n.effective_from, note: n.note ?? "", changesText: changesText(n.changes) })}><Pencil size={14} /> Edit</Button>
                  <Button onClick={() => publish(n)}><Send size={14} /> Publish</Button>
                </>
              )}
              <Button variant="ghost" onClick={async () => { if (confirm("Delete this notice?")) { await api(`/admin/rate-notices/${n.id}`, { method: "DELETE" }).catch((e) => setErr(e.message)); reload(); } }}><Trash2 size={14} /></Button>
            </div>
          </div>
          {n.note && <p className="mt-2 text-sm text-gray-600">{n.note}</p>}
          <table className="tbl mt-3">
            <thead><tr><th>HSN / SAC starting with</th><th>Description</th><th className="num">New GST %</th><th className="num">New cess %</th></tr></thead>
            <tbody>{n.changes.map((c, i) => <tr key={i}><td className="font-mono">{c.hsn_prefix}</td><td className="text-xs">{c.description ?? "—"}</td><td className="num">{c.new_rate}</td><td className="num">{c.new_cess ?? "unchanged"}</td></tr>)}</tbody>
          </table>
        </Card>
      ))}

      {draft && (
        <Modal title={draft.id ? "Edit rate notice" : "New rate notice"} onClose={() => setDraft(null)} wide>
          <div className="space-y-3">
            <Field label="Title" required><Input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} placeholder="e.g. GST 2.0 — rate rationalisation" /></Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Notification no."><Input value={draft.reference} onChange={(e) => setDraft({ ...draft, reference: e.target.value })} placeholder="9/2025-Central Tax (Rate)" /></Field>
              <Field label="Effective from" required><Input type="date" value={draft.effective_from} onChange={(e) => setDraft({ ...draft, effective_from: e.target.value })} /></Field>
            </div>
            <Field label="Rate changes" hint="One per line: HSN prefix, new GST %, cess % (optional), description (optional). The longest matching prefix wins.">
              <Textarea rows={8} className="font-mono text-xs" value={draft.changesText} onChange={(e) => setDraft({ ...draft, changesText: e.target.value })}
                placeholder={"61, 5, , Apparel (knitted)\n8471, 18\n2202, 40, , Aerated waters"} />
            </Field>
            <Field label="Message to businesses"><Textarea rows={2} value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} /></Field>
            <ErrorBox message={err} />
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setDraft(null)}>Cancel</Button><Button onClick={save}>Save draft</Button></div>
          </div>
        </Modal>
      )}
    </div>
  );
}
