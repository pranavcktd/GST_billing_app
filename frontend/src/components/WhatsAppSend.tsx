"use client";

import { MessageCircle, Send } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { useConfig } from "@/lib/config";

interface WaStatus { send: boolean; quota: number; used: number; left: number }

/**
 * WhatsApp for a bill or a reminder: send it from the platform's WhatsApp number (Business API, PDF attached) when the
 * super admin has set it up, or open the user's own WhatsApp with the message ready (`openOwn`).
 */
export function WhatsAppSend({ label = "WhatsApp", title, phone, sendPath, openOwn, what = "bill" }: {
  label?: string; title: string; phone: string | null | undefined; sendPath: string; openOwn: () => void; what?: string;
}) {
  const enabled = !!useConfig().whatsapp?.send;
  const [open, setOpen] = useState(false);
  const [to, setTo] = useState("");
  const [status, setStatus] = useState<WaStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function start() {
    if (!enabled) return openOwn();
    setOpen(true); setErr(null); setDone(null);
    setTo((phone ?? "").replace(/\D/g, "").slice(-10));
    setStatus(await api<WaStatus>("/whatsapp/status").catch(() => null));
  }
  async function send() {
    setBusy(true); setErr(null);
    try {
      const r = await api<{ to: string; charged_credits: boolean }>(sendPath, { body: { phone: to } });
      setDone(`Sent to ${r.to}${r.charged_credits ? " (1 API credit used)" : ""}.`);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <>
      <Button variant="secondary" onClick={start}><MessageCircle size={16} /> {label}</Button>
      {open && (
        <Modal title={title} onClose={() => setOpen(false)}>
          <div className="space-y-3 text-sm">
            <Field label="Customer's WhatsApp number">
              <Input type="tel" inputMode="numeric" maxLength={10} placeholder="10-digit mobile" value={to} onChange={(e) => setTo(e.target.value.replace(/\D/g, ""))} />
            </Field>
            <p className="text-gray-600">The {what} goes from our WhatsApp business number with your business name{what === "bill" ? " and the PDF attached" : " and a link to the bill"}.</p>
            {status && (
              <p className="text-xs text-gray-500">
                {status.left > 0 ? `${status.left} of ${status.quota} WhatsApp messages left this month.` : "This month's WhatsApp messages are used up — each message now uses 1 API credit."}
              </p>
            )}
            <ErrorBox message={err} />
            {done && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-800">{done}</div>}
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="secondary" onClick={() => { openOwn(); setOpen(false); }}>Open my WhatsApp instead</Button>
              <Button disabled={busy || to.length !== 10 || !!done} onClick={send}><Send size={15} /> {busy ? "Sending…" : "Send now"}</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
