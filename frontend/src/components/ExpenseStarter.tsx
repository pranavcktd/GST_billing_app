"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Tpl { name: string; kind: string; itc_blocked: boolean; exists: boolean; items: { name: string; gst_rate: number; exists: boolean }[] }
interface Data { choice: string | null; ask: boolean; categories: Tpl[] }

/** Offers the platform's standard expense categories (with typical items) to copy into this business. Opens by itself
 *  on the first visit of a business that has none; `open` forces it (the “Import standard categories” button). */
export function ExpenseStarter({ open, onClose, onImported }: { open: boolean; onClose: () => void; onImported: () => void }) {
  const { data } = useFetch<Data>("/expenses/templates");
  const [dismissed, setDismissed] = useState(false);
  const [picked, setPicked] = useState<Set<string> | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (!data) return null;
  const show = open || (data.ask && !dismissed);
  if (!show) return null;
  const fresh = data.categories.filter((c) => !c.exists || c.items.some((i) => !i.exists));
  const chosen = picked ?? new Set(fresh.map((c) => c.name));

  const close = () => { setDismissed(true); onClose(); };
  async function skip() {
    await api("/expenses/templates/skip", { body: {} }).catch(() => undefined);
    close();
  }
  async function importNow() {
    setErr(null); setBusy(true);
    try {
      await api("/expenses/templates/import", { body: { names: [...chosen] } });
      onImported();
      close();
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }
  const toggle = (n: string) => { const s = new Set(chosen); if (s.has(n)) s.delete(n); else s.add(n); setPicked(s); };

  return (
    <Modal title="Start with standard expense categories?" onClose={data.ask && !open ? skip : close} wide>
      <div className="space-y-3 text-sm">
        <p className="flex items-start gap-2 rounded-lg bg-brand-50 px-3 py-2 text-brand-900">
          <Sparkles size={16} className="mt-0.5 shrink-0" />
          Most businesses use these. Import the ones you want — they become your own, and you can rename, edit or delete them any time.
        </p>
        {fresh.length === 0 ? <p className="text-gray-600">You already have every standard category and item.</p> : (
          <>
            <div className="flex gap-3 text-xs">
              <button className="text-brand-600 hover:underline" onClick={() => setPicked(new Set(fresh.map((c) => c.name)))}>Select all</button>
              <button className="text-brand-600 hover:underline" onClick={() => setPicked(new Set())}>Clear</button>
            </div>
            <div className="grid max-h-[50vh] gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
              {fresh.map((c) => (
                <label key={c.name} className={`flex cursor-pointer gap-2 rounded-lg border p-2.5 ${chosen.has(c.name) ? "border-brand-300 bg-brand-50/40" : "border-gray-200"}`}>
                  <input type="checkbox" className="mt-0.5" checked={chosen.has(c.name)} onChange={() => toggle(c.name)} />
                  <span className="min-w-0">
                    <span className="font-medium text-gray-900">{c.name}</span>
                    <span className="ml-1.5 text-[11px] text-gray-500">{c.kind === "DIRECT" ? "direct" : "indirect"}{c.itc_blocked ? " · no GST credit" : ""}{c.exists ? " · you have it" : ""}</span>
                    {c.items.length > 0 && <span className="block truncate text-xs text-gray-500">{c.items.map((i) => `${i.name} (${i.gst_rate}%)`).join(", ")}</span>}
                  </span>
                </label>
              ))}
            </div>
          </>
        )}
        <ErrorBox message={err} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={data.ask && !open ? skip : close}>{data.ask && !open ? "No thanks, I'll add my own" : "Close"}</Button>
          {fresh.length > 0 && <Button disabled={busy || chosen.size === 0} onClick={importNow}>{busy ? "Importing…" : `Import ${chosen.size} categor${chosen.size === 1 ? "y" : "ies"}`}</Button>}
        </div>
      </div>
    </Modal>
  );
}
