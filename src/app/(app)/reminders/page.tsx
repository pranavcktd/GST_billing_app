"use client";

import { BellRing, Mail, MessageCircle, Settings } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";
import { usePaged } from "@/components/Pager";
import { Button, Card, Empty, ErrorBox, Loading, PageHeader, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface DueParty {
  party_id: string; name: string; email: string | null; phone: string | null; whatsapp: string | null;
  invoices: { id: string; number: string; date: string; due: string; balance: number; overdue: number }[];
  total: number; net_balance: number; max_overdue: number; last_reminded: string | null;
}

const ageTone = (d: number) => (d > 30 ? "text-red-700" : d > 0 ? "text-amber-700" : "text-gray-500");

/** Who owes money, how late, and one-click reminders by e-mail (with invoice PDFs) or WhatsApp. */
export default function CollectPage() {
  const { data, error, reload } = useFetch<DueParty[]>("/reminders/due");
  const { data: st } = useFetch<{ enabled: boolean }>("/reminders/settings");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const { rows, pager } = usePaged(data);

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;
  const total = data.reduce((s, p) => s + p.total, 0);
  const overdue = data.filter((p) => p.max_overdue > 0).reduce((s, p) => s + p.total, 0);
  const emailable = data.filter((p) => p.email);

  async function send(ids: string[]) {
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await api<{ sent: number; results: { name: string; sent: boolean; error: string | null }[] }>("/reminders/send", { body: { party_ids: ids, note: note || null } });
      const failed = r.results.filter((x) => !x.sent);
      setMsg(`${r.sent} reminder e-mail(s) sent.${failed.length ? ` Not sent: ${failed.map((x) => `${x.name} (${x.error})`).join(", ")}` : ""}`);
      setSel(new Set());
      reload();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  async function whatsapp(p: DueParty) {
    const win = window.open("", "_blank");
    try {
      const r = await api<{ url: string }>(`/reminders/whatsapp/${p.party_id}`);
      if (win) win.location.href = r.url; else window.location.href = r.url;
      reload();
    } catch (e) { win?.close(); setErr((e as Error).message); }
  }

  return (
    <>
      <PageHeader title="Collect payments" sub="Unpaid sale invoices by customer — remind by e-mail (with the invoice PDFs) or WhatsApp"
        actions={<Link href="/settings?tab=reminders" className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"><Settings size={15} /> Automatic reminders: {st?.enabled ? "On" : "Off"}</Link>} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card className="p-4"><div className="text-xs text-gray-500">To collect</div><div className="text-xl font-semibold">{money(total)}</div></Card>
        <Card className="p-4"><div className="text-xs text-gray-500">Overdue</div><div className="text-xl font-semibold text-red-700">{money(overdue)}</div></Card>
        <Card className="p-4"><div className="text-xs text-gray-500">Customers</div><div className="text-xl font-semibold">{data.length}</div></Card>
        <Card className="p-4"><div className="text-xs text-gray-500">Without e-mail</div><div className="text-xl font-semibold">{data.length - emailable.length}</div></Card>
      </div>
      <ErrorBox message={err} />
      {msg && <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      {!data.length ? <Card><Empty title="Nothing to collect — every sale invoice is paid." /></Card> : (
        <>
          <Card className="mb-3 flex flex-wrap items-end gap-3 p-4">
            <div className="min-w-64 flex-1">
              <label className="mb-1 block text-xs font-medium text-gray-600">Personal note in the e-mail (optional)</label>
              <Textarea rows={1} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Kindly clear the dues by Friday." />
            </div>
            <Button variant="secondary" disabled={busy || !emailable.length} onClick={() => setSel(new Set(emailable.map((p) => p.party_id)))}>Select all with e-mail</Button>
            <Button disabled={busy || !sel.size} onClick={() => send([...sel])}><Mail size={15} /> E-mail {sel.size || ""} reminder{sel.size === 1 ? "" : "s"}</Button>
          </Card>
          <Card className="overflow-x-auto">
            <table className="tbl">
              <thead><tr><th /><th>Customer</th><th className="num">Due</th><th>Oldest</th><th>Last reminded</th><th className="text-right">Remind</th></tr></thead>
              <tbody>
                {rows.map((p) => (
                  <Fragment key={p.party_id}>
                    <tr>
                      <td><input type="checkbox" disabled={!p.email} checked={sel.has(p.party_id)} title={p.email ? "" : "No e-mail address"}
                        onChange={(e) => { const s = new Set(sel); if (e.target.checked) s.add(p.party_id); else s.delete(p.party_id); setSel(s); }} /></td>
                      <td>
                        <Link href={`/parties/${p.party_id}`} className="font-medium text-brand-600 hover:underline">{p.name}</Link>
                        <div className="text-xs text-gray-500">{[p.email, p.phone].filter(Boolean).join(" · ") || "No contact details"}</div>
                        {p.net_balance <= 0 && <div className="text-xs text-amber-700">Advance / credit covers these bills — not reminded automatically</div>}
                      </td>
                      <td className="num font-medium">{money(p.total)}
                        <button className="block w-full text-right text-xs text-brand-600 hover:underline" onClick={() => setOpen(open === p.party_id ? null : p.party_id)}>
                          {p.invoices.length} invoice{p.invoices.length > 1 ? "s" : ""}
                        </button>
                      </td>
                      <td className={ageTone(p.max_overdue)}>{p.max_overdue ? `${p.max_overdue} days overdue` : "Not due yet"}</td>
                      <td className="text-xs text-gray-500">{p.last_reminded ? fmtDate(p.last_reminded) : "—"}</td>
                      <td className="whitespace-nowrap text-right">
                        <Button variant="ghost" className="!px-2 !py-1" disabled={!p.email || busy} onClick={() => send([p.party_id])} title={p.email ?? "No e-mail address"}><Mail size={15} /></Button>
                        <Button variant="ghost" className="!px-2 !py-1 text-emerald-700" disabled={!p.phone} onClick={() => whatsapp(p)} title={p.phone ? "WhatsApp" : "No phone number"}><MessageCircle size={15} /></Button>
                      </td>
                    </tr>
                    {open === p.party_id && (
                      <tr className="bg-gray-50">
                        <td />
                        <td colSpan={5}>
                          <table className="w-full text-xs">
                            <tbody>
                              {p.invoices.map((i) => (
                                <tr key={i.id}>
                                  <td className="py-1"><Link href={`/doc/${i.id}`} className="text-brand-600 hover:underline">{i.number}</Link></td>
                                  <td>{fmtDate(i.date)}</td><td>due {fmtDate(i.due)}</td>
                                  <td className={ageTone(i.overdue)}>{i.overdue ? `${i.overdue} days overdue` : ""}</td>
                                  <td className="text-right tabular-nums">{money(i.balance)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            {pager}
          </Card>
          <p className="mt-3 flex items-center gap-1.5 text-xs text-gray-500"><BellRing size={13} /> E-mails go from your business e-mail settings and include a link to each invoice, your UPI ID and bank details. WhatsApp opens with the message ready to send from your phone or WhatsApp Web.</p>
        </>
      )}
    </>
  );
}
