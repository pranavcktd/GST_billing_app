"use client";

import { Link2, Mail } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Field, Input, Textarea } from "@/components/ui";
import { useFetch } from "@/lib/useFetch";
import type { DscStatus } from "@/components/DscSettings";
import { api } from "@/lib/api";
import type { Business, Party, VoucherDetail } from "@/lib/types";

/** E-mail a document to the customer (with a view link), or copy its public link.
 *  To = the party's e-mail and Cc = your business e-mail (from their profiles) — both can be changed before sending. */
export function EmailButton({ v, defaultTo }: { v: VoucherDetail; defaultTo?: string | null }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ to: defaultTo ?? "", cc: "", message: "", attach: true, sign: false });
  const { data: dsc } = useFetch<DscStatus>("/dsc");
  const askSign = !!dsc?.configured && !dsc.expired && dsc.mode === "ON_REQUEST";
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function openDialog() {
    setOpen(true); setDone(null); setErr(null);
    const [party, biz] = await Promise.all([
      v.party_id ? api<Party>(`/parties/${v.party_id}`).catch(() => null) : Promise.resolve(null),
      api<Business>("/businesses/current").catch(() => null),
    ]);
    setF((cur) => ({ ...cur, to: cur.to || defaultTo || party?.email || "", cc: cur.cc || biz?.email || "" }));
  }

  async function send() {
    setBusy(true); setErr(null);
    try {
      const split = (s: string) => s.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean);
      const r = await api<{ via: string }>(`/vouchers/${v.id}/email`, { body: { to: split(f.to), cc: split(f.cc), message: f.message || null, attach_pdf: f.attach, sign: askSign ? f.sign : undefined } });
      setDone(`Sent to ${f.to} (via ${r.via?.toLowerCase()} mail settings).`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="secondary" onClick={openDialog}><Mail size={16} /> Email</Button>
      {open && (
        <Modal title={`E-mail ${v.number}`} onClose={() => setOpen(false)}>
          {done ? (
            <div className="space-y-3 text-sm">
              <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">{done}</p>
              <div className="flex justify-end"><Button onClick={() => setOpen(false)}>Done</Button></div>
            </div>
          ) : (
            <div className="space-y-3">
              <ErrorBox message={err} />
              <Field label="To" hint="Party's e-mail from their profile — change it if needed. Separate several addresses with commas."><Input value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} /></Field>
              <Field label="Cc" hint="Your business e-mail, so you keep a copy — remove or change it if you like"><Input value={f.cc} onChange={(e) => setF({ ...f, cc: e.target.value })} /></Field>
              <Field label="Message (optional)"><Textarea rows={3} value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} /></Field>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.attach} onChange={(e) => setF({ ...f, attach: e.target.checked })} /> Attach the PDF</label>
              {askSign && f.attach && (
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.sign} onChange={(e) => setF({ ...f, sign: e.target.checked })} /> Digitally sign the PDF ({dsc?.subject})</label>
              )}
              <p className="text-xs text-gray-500">The e-mail includes a summary and a secure link where the customer can view, print or save the full document as PDF.</p>
              <div className="flex justify-end gap-2">
                <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
                <Button disabled={busy || !f.to} onClick={send}>{busy ? "Sending…" : "Send"}</Button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}

export async function getShareLink(id: string): Promise<string> {
  const r = await api<{ url: string }>(`/vouchers/${id}/share-link`, { body: {} });
  return r.url;
}

export function CopyLinkButton({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button variant="secondary" onClick={async () => {
      const url = await getShareLink(id);
      await navigator.clipboard?.writeText(url).catch(() => prompt("Copy this link", url));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }}><Link2 size={16} /> {copied ? "Link copied" : "Copy link"}</Button>
  );
}
