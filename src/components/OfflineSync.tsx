"use client";

import { CloudOff, RefreshCw, Trash2, UploadCloud } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Modal } from "@/components/Modal";
import { Button } from "@/components/ui";
import { ApiError, API_URL, authHeaders } from "@/lib/api";
import { onQueueChange, queue, type QueuedDoc, removeQueued, retryQueued, syncQueue } from "@/lib/offline";

async function send(doc: QueuedDoc): Promise<void> {
  const res = await fetch(`${API_URL}/api${doc.path}`, {
    method: "POST",
    headers: { ...authHeaders(), "X-Business-Id": doc.business_id, "Content-Type": "application/json" },
    body: JSON.stringify(doc.body),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const d = body?.detail;
    throw new ApiError(res.status, typeof d === "string" ? d : d?.message ?? `Upload failed (${res.status})`);
  }
}

/** Top-bar status: offline / documents waiting to upload / errors; uploads automatically when back online. */
export function OfflineSync() {
  const [online, setOnline] = useState(() => typeof navigator === "undefined" || navigator.onLine);
  const [items, setItems] = useState<QueuedDoc[]>(() => (typeof window === "undefined" ? [] : queue()));
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => setItems(queue()), []);
  const run = useCallback(async () => {
    if (!queue().some((d) => !d.error)) return;
    setBusy(true);
    try { await syncQueue(send); } finally { setBusy(false); refresh(); }
  }, [refresh]);

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    const offQ = onQueueChange(refresh);
    const goOnline = () => { update(); run(); };
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", update);
    const timer = window.setInterval(() => { if (navigator.onLine) run(); }, 30000);
    const first = window.setTimeout(run, 1500); // upload anything left from an earlier session
    return () => { offQ(); window.removeEventListener("online", goOnline); window.removeEventListener("offline", update);
      window.clearInterval(timer); window.clearTimeout(first); };
  }, [refresh, run]);

  const waiting = items.filter((d) => !d.error).length;
  const failed = items.filter((d) => d.error).length;
  if (online && !items.length) return null;

  return (
    <>
      <button onClick={() => setOpen(true)}
        className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium ${!online ? "bg-gray-800 text-white" : failed ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-800"}`}>
        {!online ? <CloudOff size={14} /> : busy ? <RefreshCw size={14} className="animate-spin" /> : <UploadCloud size={14} />}
        {!online ? "Offline" : busy ? "Uploading…" : ""}{waiting ? ` · ${waiting} waiting` : ""}{failed ? ` · ${failed} need attention` : ""}
      </button>
      {open && (
        <Modal title="Bills saved on this device" onClose={() => setOpen(false)} wide>
          <div className="space-y-3 text-sm">
            <p className="text-gray-600">
              {online ? "You are online. Waiting bills upload automatically — invoice numbers are given when they upload." :
                "You are offline. You can keep billing — bills are saved on this device and upload automatically when the internet is back."}
            </p>
            {!items.length ? <p className="text-gray-500">Nothing waiting.</p> : (
              <table className="tbl">
                <thead><tr><th>Saved</th><th>Bill</th><th>Status</th><th /></tr></thead>
                <tbody>
                  {items.map((d) => (
                    <tr key={d.id}>
                      <td className="whitespace-nowrap text-xs">{new Date(d.created_at).toLocaleString("en-IN")}</td>
                      <td>{d.label}</td>
                      <td className={`text-xs ${d.error ? "text-red-700" : "text-amber-700"}`}>{d.error ? `Not accepted: ${d.error}` : "Waiting to upload"}</td>
                      <td className="whitespace-nowrap text-right">
                        {d.error && <Button variant="ghost" className="!px-2 !py-1" onClick={() => { retryQueued(d.id); run(); }}>Retry</Button>}
                        <Button variant="ghost" className="!px-2 !py-1" title="Discard" onClick={() => { if (confirm("Discard this bill? It has not been uploaded.")) removeQueued(d.id); }}><Trash2 size={15} /></Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="flex justify-end gap-2">
              {online && waiting > 0 && <Button disabled={busy} onClick={run}><UploadCloud size={15} /> Upload now</Button>}
              <Button variant="ghost" onClick={() => setOpen(false)}>Close</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
