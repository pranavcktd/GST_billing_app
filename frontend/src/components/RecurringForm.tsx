"use client";

import { Repeat } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Field, Input, Select } from "@/components/ui";
import { api } from "@/lib/api";

export const FREQ: Record<string, string> = { WEEKLY: "Weekly", MONTHLY: "Monthly", QUARTERLY: "Every 3 months", HALF_YEARLY: "Every 6 months", YEARLY: "Yearly" };

const nextMonth = (iso: string) => {
  const d = new Date(iso + "T00:00:00");
  d.setMonth(d.getMonth() + 1);
  return d.toISOString().slice(0, 10);
};

/** "Make recurring" on a sale invoice: repeat it on a schedule. */
export function MakeRecurringButton({ voucherId, date, partyName }: { voucherId: string; date: string; partyName: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: `${partyName} — monthly`, frequency: "MONTHLY", interval: "1", start_date: nextMonth(date), end_date: "", due_days: "0", auto_email: false });
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setErr(null);
    try {
      await api("/recurring", { body: { voucher_id: voucherId, ...f, interval: Number(f.interval) || 1, due_days: Number(f.due_days) || 0, end_date: f.end_date || null } });
      router.push("/recurring");
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)} title="Repeat this invoice automatically"><Repeat size={16} /> Make recurring</Button>
      {open && (
        <Modal title="Repeat this invoice" onClose={() => setOpen(false)}>
          <div className="space-y-3 text-sm">
            <p className="text-gray-600">A copy of this invoice — same customer, items, rates and notes — is created automatically on each date, with its own number and today&apos;s GST rules.</p>
            <Field label="Name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Repeat">
                <Select value={f.frequency} onChange={(e) => setF({ ...f, frequency: e.target.value, name: f.name.replace(/— .*$/, `— ${FREQ[e.target.value].toLowerCase()}`) })}>
                  {Object.entries(FREQ).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select>
              </Field>
              <Field label="Every" hint="e.g. 2 = every second period"><Input inputMode="numeric" value={f.interval} onChange={(e) => setF({ ...f, interval: e.target.value })} /></Field>
              <Field label="First invoice on"><Input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} /></Field>
              <Field label="Stop after (optional)"><Input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} /></Field>
              <Field label="Payment due after (days)"><Input inputMode="numeric" value={f.due_days} onChange={(e) => setF({ ...f, due_days: e.target.value })} /></Field>
            </div>
            <label className="flex items-center gap-2"><input type="checkbox" checked={f.auto_email} onChange={(e) => setF({ ...f, auto_email: e.target.checked })} /> E-mail each invoice (with PDF) to the customer automatically</label>
            <ErrorBox message={err} />
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={save}>Start schedule</Button></div>
          </div>
        </Modal>
      )}
    </>
  );
}
