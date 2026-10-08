"use client";

import { BellRing } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Input, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useConfig } from "@/lib/config";

/** Payment reminder for one unpaid invoice: e-mail (with PDF) or WhatsApp. */
export function RemindButton({ partyId, voucherId }: { partyId: string; voucherId: string }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [phone, setPhone] = useState("");
  const waApi = !!useConfig().whatsapp?.send;

  async function email() {
    setBusy(true); setErr(null);
    try {
      const r = await api<{ sent: number; results: { error: string | null; to?: string }[] }>("/reminders/send",
        { body: { party_ids: [partyId], voucher_ids: [voucherId], note: note || null } });
      if (r.sent) setDone(`Reminder e-mailed to ${r.results[0].to}.`); else setErr(r.results[0]?.error ?? "Not sent");
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  async function whatsappApi() {
    setBusy(true); setErr(null);
    try {
      const r = await api<{ to: string; charged_credits: boolean; sandbox?: boolean; preview?: string }>(`/reminders/whatsapp-send/${partyId}?voucher_id=${voucherId}`,
        { body: phone ? { phone } : {} });
      setDone(r.sandbox ? `Sandbox — nothing was sent to ${r.to}. Would send: ${r.preview ?? ""}`
        : `Reminder sent on WhatsApp to ${r.to}${r.charged_credits ? " (1 API credit used)" : ""}.`);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  async function whatsapp() {
    const win = window.open("", "_blank");
    try {
      const r = await api<{ url: string }>(`/reminders/whatsapp/${partyId}?voucher_id=${voucherId}`);
      if (win) win.location.href = r.url; else window.location.href = r.url;
      setOpen(false);
    } catch (e) { win?.close(); setErr((e as Error).message); }
  }

  return (
    <>
      <Button variant="secondary" onClick={() => { setOpen(true); setDone(null); setErr(null); }}><BellRing size={16} /> Remind</Button>
      {open && (
        <Modal title="Send a payment reminder" onClose={() => setOpen(false)}>
          <div className="space-y-3 text-sm">
            <p className="text-gray-600">A polite reminder with the amount due, a link to the invoice, your UPI ID and bank details. The e-mail also attaches the PDF.</p>
            <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Personal note (optional, e-mail only)" />
            {waApi && (
              <Input type="tel" inputMode="numeric" maxLength={10} placeholder="WhatsApp number (blank = party's mobile)" value={phone}
                onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))} />
            )}
            <ErrorBox message={err} />
            {done && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-800">{done}</div>}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={whatsapp}>{waApi ? "Open my WhatsApp" : "WhatsApp"}</Button>
              {waApi && <Button variant="secondary" disabled={busy} onClick={whatsappApi}>Send on WhatsApp</Button>}
              <Button disabled={busy} onClick={email}>E-mail reminder</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
