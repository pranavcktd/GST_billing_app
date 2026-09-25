"use client";

import { Megaphone } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Notice { id: string; title: string; reference: string | null; effective_from: string; note: string | null; affected: number }
interface Preview extends Notice { items: { id: string; name: string; hsn: string; old_rate: number; new_rate: number; old_cess: number; new_cess: number }[] }

/** Dashboard banner: GST rate changes published by the platform that affect this business's items. */
export function RateNotices() {
  const { data, reload } = useFetch<Notice[]>("/rate-notices");
  const [open, setOpen] = useState<string | null>(null);
  if (!data?.length) return null;
  return (
    <div className="mb-5 space-y-2">
      {data.map((n) => (
        <div key={n.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm">
          <div className="flex items-start gap-2 text-amber-900">
            <Megaphone size={18} className="mt-0.5 shrink-0" />
            <div>
              <b>GST rate change: {n.title}</b> — effective {fmtDate(n.effective_from)}{n.reference ? ` (${n.reference})` : ""}.
              <div className="text-xs">{n.affected ? `${n.affected} of your items are affected.` : "None of your items are affected."}{n.note ? ` ${n.note}` : ""}</div>
            </div>
          </div>
          <div className="flex gap-2">
            {n.affected > 0 && <Button onClick={() => setOpen(n.id)}>Review & apply</Button>}
            <Button variant="ghost" onClick={() => api(`/rate-notices/${n.id}/dismiss`, { body: {} }).then(reload).catch((e) => alert(e.message))}>Dismiss</Button>
          </div>
        </div>
      ))}
      {open && <ApplyDialog id={open} onClose={() => setOpen(null)} onDone={() => { setOpen(null); reload(); }} />}
    </div>
  );
}

function ApplyDialog({ id, onClose, onDone }: { id: string; onClose: () => void; onDone: () => void }) {
  const { data } = useFetch<Preview>(`/rate-notices/${id}/preview`);
  const [skip, setSkip] = useState<Set<string>>(new Set());
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function apply() {
    if (!data) return;
    setBusy(true);
    try {
      await api(`/rate-notices/${id}/apply`, { body: { item_ids: data.items.filter((i) => !skip.has(i.id)).map((i) => i.id) } });
      onDone();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal title="Update item GST rates" onClose={onClose} wide>
      {!data ? <Loading /> : (
        <>
          <p className="mb-3 text-sm text-gray-600">
            New rates apply to bills you create from now on. Bills already saved keep their rates. Effective {fmtDate(data.effective_from)} —
            if that date is still ahead, apply on or after it.
          </p>
          <div className="max-h-96 overflow-y-auto">
            <table className="tbl">
              <thead><tr><th /><th>Item</th><th>HSN</th><th className="num">GST %</th><th className="num">Cess %</th></tr></thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.id}>
                    <td><input type="checkbox" checked={!skip.has(i.id)} onChange={(e) => { const s = new Set(skip); if (e.target.checked) s.delete(i.id); else s.add(i.id); setSkip(s); }} /></td>
                    <td>{i.name}</td><td className="font-mono">{i.hsn}</td>
                    <td className="num">{i.old_rate} → <b>{i.new_rate}</b></td>
                    <td className="num">{i.old_cess === i.new_cess ? i.new_cess : <>{i.old_cess} → <b>{i.new_cess}</b></>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ErrorBox message={err} />
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button disabled={busy} onClick={apply}>Update {data.items.length - skip.size} items</Button>
          </div>
        </>
      )}
    </Modal>
  );
}
