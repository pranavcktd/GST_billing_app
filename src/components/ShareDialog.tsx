"use client";

import { Link2, Mail } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Field, Input, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import type { VoucherDetail } from "@/lib/types";

/** E-mail a document to the customer (with a view link), or copy its public link. */
export function EmailButton({ v, defaultTo }: { v: VoucherDetail; defaultTo?: string | null }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ to: defaultTo ?? "", cc: "", message: "" });
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function send() {
    setBusy(true); setErr(null);
    try {
      const split = (s: string) => s.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean);
      const r = await api<{ via: string }>(`/vouchers/${v.id}/email`, { body: { to: split(f.to), cc: split(f.cc), message: f.message || null } });
      setDone(`Sent to ${f.to} (via ${r.via?.toLowerCase()} mail settings).`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="secondary" onClick={() => { setOpen(true); setDone(null); setErr(null); }}><Mail size={16} /> Email</Button>
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
              <Field label="To" hint="Separate several addresses with commas"><Input value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} /></Field>
              <Field label="Cc"><Input value={f.cc} onChange={(e) => setF({ ...f, cc: e.target.value })} /></Field>
              <Field label="Message (optional)"><Textarea rows={3} value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} /></Field>
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
