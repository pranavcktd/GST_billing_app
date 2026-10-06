"use client";

import { BellRing } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Textarea } from "@/components/ui";
import { api } from "@/lib/api";

/** Payment reminder for one unpaid invoice: e-mail (with PDF) or WhatsApp. */
export function RemindButton({ partyId, voucherId }: { partyId: string; voucherId: string }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function email() {
    setBusy(true); setErr(null);
    try {
      const r = await api<{ sent: number; results: { error: string | null; to?: string }[] }>("/reminders/send",
        { body: { party_ids: [partyId], voucher_ids: [voucherId], note: note || null } });
      if (r.sent) setDone(`Reminder e-mailed to ${r.results[0].to}.`); else setErr(r.results[0]?.error ?? "Not sent");
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
            <ErrorBox message={err} />
            {done && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-800">{done}</div>}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={whatsapp}>WhatsApp</Button>
              <Button disabled={busy} onClick={email}>E-mail reminder</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
