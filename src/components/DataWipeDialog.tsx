"use client";

import { AlertTriangle, Eraser } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Input, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Group { key: string; label: string; help: string; requires: string[]; master: boolean }
interface Options { groups: Group[]; counts: Record<string, number>; business_name: string; backup_email: string | null }
interface Result { cleared: string[]; removed: Record<string, number>; backup_file: string; emailed_to: string | null; email_error: string | null }

/** Choose what to clear; required groups are ticked automatically. A backup is taken and e-mailed first (server side). */
export function DataWipeDialog({ path, onClose, onDone }: { path: string; onClose: () => void; onDone?: (r: Result) => void }) {
  const { data } = useFetch<Options>(path);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Result | null>(null);

  if (!data) return <Modal title="Clear data" onClose={onClose}><Loading /></Modal>;
  const by = Object.fromEntries(data.groups.map((g) => [g.key, g]));
  // everything the ticked groups need
  const needed = new Set<string>();
  const add = (k: string) => { if (!needed.has(k)) { needed.add(k); by[k]?.requires.forEach(add); } };
  picked.forEach(add);
  const forced = (k: string) => needed.has(k) && !picked.has(k);
  const toggle = (k: string) => { const s = new Set(picked); if (s.has(k)) s.delete(k); else s.add(k); setPicked(s); };
  const all = data.groups.every((g) => needed.has(g.key));

  async function submit() {
    setBusy(true); setErr(null);
    try {
      const r = await api<Result>(path, { body: { groups: [...needed], confirm_name: name } });
      setDone(r);
      onDone?.(r);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  if (done) {
    return (
      <Modal title="Data cleared" onClose={onClose}>
        <div className="space-y-3 text-sm">
          <p className="text-gray-700">Cleared: {done.cleared.map((k) => by[k]?.label ?? k).join(", ")}.</p>
          <p className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-800">
            Backup saved first: <b>{done.backup_file}</b> (Utilities → Backup &amp; restore).
            {done.emailed_to ? ` A copy was e-mailed to ${done.emailed_to}.` : ""}
          </p>
          {done.email_error && <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">The backup could not be e-mailed ({done.email_error}) — download it from Backup &amp; restore.</p>}
          <div className="flex justify-end"><Button onClick={onClose}>Close</Button></div>
        </div>
      </Modal>
    );
  }

  const row = (g: Group) => (
    <label key={g.key} className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${needed.has(g.key) ? "border-red-200 bg-red-50" : "border-gray-200"}`}>
      <input type="checkbox" className="mt-0.5" checked={needed.has(g.key)} disabled={forced(g.key)} onChange={() => toggle(g.key)} />
      <span className="flex-1">
        <span className="font-medium text-gray-900">{g.label}</span>
        <span className="ml-1 text-xs text-gray-500">({data.counts[g.key] ?? 0})</span>
        <span className="block text-xs text-gray-500">{forced(g.key) ? "Included because something you ticked needs it" : g.help}</span>
      </span>
    </label>
  );

  return (
    <Modal title={`Clear data — ${data.business_name}`} onClose={onClose}>
      <div className="space-y-3 text-sm">
        <p className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-amber-900">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span>A full backup is saved first{data.backup_email ? ` and e-mailed to ${data.backup_email}` : ""}. The company profile, settings, logins and godowns stay.</span>
        </p>
        <div className="flex justify-between text-xs">
          <span className="font-medium text-gray-600">Entries</span>
          <button className="text-brand-600 hover:underline" onClick={() => setPicked(all ? new Set() : new Set(data.groups.map((g) => g.key)))}>{all ? "Clear selection" : "Select everything"}</button>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">{data.groups.filter((g) => !g.master).map(row)}</div>
        <div className="text-xs font-medium text-gray-600">Masters</div>
        <div className="grid gap-2 sm:grid-cols-2">{data.groups.filter((g) => g.master).map(row)}</div>
        <label className="block">
          <span className="text-xs text-gray-600">Type the business name <b>{data.business_name}</b> to confirm</span>
          <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" />
        </label>
        <ErrorBox message={err} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" disabled={busy || needed.size === 0 || name.trim().toLowerCase() !== data.business_name.trim().toLowerCase()} onClick={submit}>
            <Eraser size={16} /> {busy ? "Backing up & clearing…" : `Back up & clear ${needed.size} group${needed.size === 1 ? "" : "s"}`}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
