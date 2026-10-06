"use client";

import { AlertTriangle, Download, ExternalLink, FileText, Link2, Mail, MessageCircle, Pencil, Plus, Share2, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, PageHeader, Select, Textarea } from "@/components/ui";
import { api, apiBlob, saveBlob } from "@/lib/api";
import { usePerms } from "@/lib/auth";
import { useLink } from "@/lib/config";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Doc {
  id: string; title: string; category: string; financial_year: string | null; doc_date: string | null; expiry_date: string | null;
  kind: "FILE" | "LINK"; url: string | null; file_name: string | null; content_type: string | null; size_bytes: number | null;
  notes: string | null; uploaded_by: string | null; created_at: string; expiry_status: "EXPIRED" | "EXPIRING" | null;
}
interface Meta {
  categories: string[]; enabled: boolean; allow_links: boolean; allow_upload: boolean; max_file_mb: number; quota_mb: number;
  used_bytes: number; extensions: string[]; share_days: number;
}

const size = (b: number | null) => (b == null ? "" : b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);
const fyNow = () => { const d = new Date(); const y = d.getMonth() >= 3 ? d.getFullYear() : d.getFullYear() - 1; return `${y}-${String(y + 1).slice(-2)}`; };
const fyList = () => { const [y] = fyNow().split("-").map(Number); return Array.from({ length: 8 }, (_, i) => `${y - i}-${String(y - i + 1).slice(-2)}`); };

async function openDoc(d: Doc) {
  if (d.kind === "LINK") { window.open(d.url!, "_blank", "noopener"); return; }
  const win = window.open("", "_blank");
  try {
    const { blob } = await apiBlob(`/documents/${d.id}/file`);
    const url = URL.createObjectURL(blob);
    if (win) win.location.href = url; else window.open(url, "_blank");
  } catch (e) {
    win?.close();
    alert((e as Error).message);
  }
}

export default function DocumentsPage() {
  const { can } = usePerms();
  const { data: meta, error: metaErr, reload: reloadMeta } = useFetch<Meta>("/documents/meta");
  const [category, setCategory] = useState("");
  const [fy, setFy] = useState("");
  const [q, setQ] = useState("");
  const qs = new URLSearchParams({ ...(category && { category }), ...(fy && { financial_year: fy }), ...(q.trim() && { q: q.trim() }) }).toString();
  const { data: docs, error, reload } = useFetch<Doc[]>(`/documents${qs ? `?${qs}` : ""}`);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Doc | null>(null);
  const [sharing, setSharing] = useState<Doc | null>(null);

  if (metaErr) return <ErrorBox message={metaErr} />;
  if (!meta) return <Loading />;
  const refresh = () => { reload(); reloadMeta(); };
  const alerts = (docs ?? []).filter((d) => d.expiry_status);
  const usedPct = Math.min(100, Math.round((meta.used_bytes / (meta.quota_mb * 1024 * 1024)) * 100));

  return (
    <>
      <PageHeader title="Documents" sub="Keep income-tax returns, financial statements, audit reports, certificates and licences in one place — find and share them any time."
        actions={can("documents", "create") && meta.enabled && (meta.allow_upload || meta.allow_links) ? <Button onClick={() => setAdding(true)}><Plus size={16} /> Add document</Button> : undefined} />
      {!meta.enabled && <ErrorBox message="The document vault is switched off by the platform administrator." />}

      {alerts.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <div className="flex items-center gap-2 font-medium"><AlertTriangle size={16} /> Renewal needed</div>
          <ul className="mt-1 list-disc pl-6">
            {alerts.map((d) => <li key={d.id}>{d.title} — {d.expiry_status === "EXPIRED" ? "expired on" : "expires on"} {fmtDate(d.expiry_date!)}</li>)}
          </ul>
        </div>
      )}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input className="!w-60" placeholder="Search title, file or notes" value={q} onChange={(e) => setQ(e.target.value)} />
        <Select className="!w-auto" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>{meta.categories.map((c) => <option key={c}>{c}</option>)}
        </Select>
        <Select className="!w-auto" value={fy} onChange={(e) => setFy(e.target.value)}>
          <option value="">All years</option>{fyList().map((y) => <option key={y} value={y}>FY {y}</option>)}
        </Select>
        {meta.allow_upload && (
          <div className="ml-auto flex items-center gap-2 text-xs text-gray-500" title="Files stored for this business">
            <div className="h-1.5 w-28 overflow-hidden rounded bg-gray-200"><div className={`h-full ${usedPct > 90 ? "bg-red-500" : "bg-brand-600"}`} style={{ width: `${usedPct}%` }} /></div>
            {size(meta.used_bytes) || "0 KB"} of {meta.quota_mb} MB
          </div>
        )}
      </div>

      <Card className="overflow-x-auto">
        <ErrorBox message={error} />
        {!docs ? <Loading /> : docs.length === 0 ? (
          <Empty title={q || category || fy ? "No documents match" : "No documents yet — add your ITR, GST certificate, licences…"} />
        ) : (
          <table className="tbl">
            <thead><tr><th>Document</th><th>Category</th><th>Year</th><th>Dates</th><th>Added</th><th /></tr></thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>
                    <button className="flex items-start gap-2 text-left font-medium text-brand-700 hover:underline" onClick={() => openDoc(d)}>
                      {d.kind === "LINK" ? <Link2 size={15} className="mt-0.5 shrink-0" /> : <FileText size={15} className="mt-0.5 shrink-0" />} {d.title}
                    </button>
                    <div className="text-xs text-gray-500">{d.kind === "LINK" ? d.url!.replace(/^https?:\/\//, "").slice(0, 50) : `${d.file_name} · ${size(d.size_bytes)}`}</div>
                    {d.notes && <div className="text-xs text-gray-500">{d.notes}</div>}
                  </td>
                  <td className="text-sm">{d.category}</td>
                  <td className="whitespace-nowrap text-sm">{d.financial_year ? `FY ${d.financial_year}` : "—"}</td>
                  <td className="whitespace-nowrap text-xs">
                    {d.doc_date && <div>Dated {fmtDate(d.doc_date)}</div>}
                    {d.expiry_date && <div className={d.expiry_status === "EXPIRED" ? "text-red-700" : d.expiry_status === "EXPIRING" ? "text-amber-700" : ""}>Valid till {fmtDate(d.expiry_date)}</div>}
                  </td>
                  <td className="whitespace-nowrap text-xs text-gray-500">{fmtDate(d.created_at.slice(0, 10))}<div>{d.uploaded_by}</div></td>
                  <td className="whitespace-nowrap text-right">
                    {d.kind === "FILE" && (
                      <button className="mr-2 text-gray-400 hover:text-gray-700" title="Download" onClick={async () => {
                        try { const { blob, filename } = await apiBlob(`/documents/${d.id}/file?download=true`); saveBlob(blob, d.file_name ?? filename); } catch (e) { alert((e as Error).message); }
                      }}><Download size={15} /></button>
                    )}
                    {d.kind === "LINK" && <button className="mr-2 text-gray-400 hover:text-gray-700" title="Open link" onClick={() => openDoc(d)}><ExternalLink size={15} /></button>}
                    <button className="mr-2 text-gray-400 hover:text-gray-700" title="Share by e-mail or WhatsApp" onClick={() => setSharing(d)}><Share2 size={15} /></button>
                    {can("documents", "edit") && <button className="mr-2 text-gray-400 hover:text-gray-700" title="Edit details" onClick={() => setEditing(d)}><Pencil size={15} /></button>}
                    {can("documents", "delete") && (
                      <button className="text-gray-400 hover:text-red-600" title="Delete" onClick={async () => {
                        if (!confirm(`Delete “${d.title}”?${d.kind === "FILE" ? " The file is removed permanently and shared links stop working." : ""}`)) return;
                        try { await api(`/documents/${d.id}`, { method: "DELETE" }); refresh(); } catch (e) { alert((e as Error).message); }
                      }}><Trash2 size={15} /></button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {adding && <DocForm meta={meta} onClose={() => setAdding(false)} onSaved={refresh} />}
      {editing && <DocForm meta={meta} doc={editing} onClose={() => setEditing(null)} onSaved={refresh} />}
      {sharing && <ShareDoc doc={sharing} shareDays={meta.share_days} onClose={() => setSharing(null)} />}
    </>
  );
}

function DocForm({ meta, doc, onClose, onSaved }: { meta: Meta; doc?: Doc; onClose: () => void; onSaved: () => void }) {
  const [mode, setMode] = useState<"FILE" | "LINK">(doc?.kind ?? (meta.allow_upload ? "FILE" : "LINK"));
  const [f, setF] = useState({
    title: doc?.title ?? "", category: doc?.category ?? "Other", financial_year: doc?.financial_year ?? "", doc_date: doc?.doc_date ?? "",
    expiry_date: doc?.expiry_date ?? "", notes: doc?.notes ?? "", url: doc?.url ?? "",
  });
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!doc && mode === "FILE" && !file) return setErr("Choose a file");
    if (file && file.size > meta.max_file_mb * 1024 * 1024) return setErr(`Files can be up to ${meta.max_file_mb} MB`);
    setBusy(true);
    try {
      if (doc) {
        await api(`/documents/${doc.id}`, { method: "PUT", body: { ...f, financial_year: f.financial_year || null, doc_date: f.doc_date || null,
          expiry_date: f.expiry_date || null, notes: f.notes || null, url: doc.kind === "LINK" ? f.url : null } });
      } else {
        const form = new FormData();
        Object.entries(f).forEach(([k, v]) => { if (v && (k !== "url" || mode === "LINK")) form.append(k, v); });
        if (mode === "FILE" && file) form.append("file", file);
        await api("/documents", { form });
      }
      onSaved();
      onClose();
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={doc ? "Edit document" : "Add document"} onClose={onClose}>
      <form onSubmit={save} className="space-y-3">
        <ErrorBox message={err} />
        {!doc && meta.allow_upload && meta.allow_links && (
          <div className="inline-flex rounded-lg border border-gray-200 p-0.5 text-sm">
            <button type="button" onClick={() => setMode("FILE")} className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 ${mode === "FILE" ? "bg-brand-600 text-white" : ""}`}><Upload size={14} /> Upload file</button>
            <button type="button" onClick={() => setMode("LINK")} className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 ${mode === "LINK" ? "bg-brand-600 text-white" : ""}`}><Link2 size={14} /> Save a link</button>
          </div>
        )}
        {!doc && mode === "FILE" && (
          <Field label="File" hint={`Up to ${meta.max_file_mb} MB · ${meta.extensions.join(", ")}`}>
            <input type="file" accept={meta.extensions.map((x) => `.${x}`).join(",")} className="block w-full text-sm"
              onChange={(e) => { const x = e.target.files?.[0] ?? null; setFile(x); if (x && !f.title) setF({ ...f, title: x.name.replace(/\.[^.]+$/, "") }); }} />
          </Field>
        )}
        {mode === "LINK" && (
          <Field label="Link" hint="Google Drive, OneDrive, Dropbox… — make sure the people you share it with have access">
            <Input type="url" required placeholder="https://drive.google.com/…" value={f.url} onChange={set("url")} />
          </Field>
        )}
        <Field label="Title"><Input required maxLength={200} value={f.title} onChange={set("title")} placeholder="e.g. ITR-3 FY 2025-26" /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Category"><Select value={f.category} onChange={set("category")}>{meta.categories.map((c) => <option key={c}>{c}</option>)}</Select></Field>
          <Field label="Financial year"><Select value={f.financial_year} onChange={set("financial_year")}><option value="">—</option>{fyList().map((y) => <option key={y} value={y}>{y}</option>)}</Select></Field>
          <Field label="Document date"><Input type="date" value={f.doc_date} onChange={set("doc_date")} /></Field>
          <Field label="Valid till" hint="Licences — you are reminded 30 days before"><Input type="date" value={f.expiry_date} onChange={set("expiry_date")} /></Field>
        </div>
        <Field label="Notes"><Textarea rows={2} maxLength={1000} value={f.notes} onChange={set("notes")} /></Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</Button>
        </div>
      </form>
    </Modal>
  );
}

function ShareDoc({ doc, shareDays, onClose }: { doc: Doc; shareDays: number; onClose: () => void }) {
  const wa = useLink("whatsapp_send");
  const [mail, setMail] = useState({ to: "", cc: "", message: "", attach: true });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function link(): Promise<string> {
    const r = await api<{ url: string }>(`/documents/${doc.id}/share-link`, { body: {} });
    return r.url;
  }
  async function whatsapp() {
    const win = window.open("", "_blank");
    try {
      const url = await link();
      const text = `${doc.title}${doc.financial_year ? ` (FY ${doc.financial_year})` : ""}\n${url}${doc.kind === "FILE" ? `\n(link valid for ${shareDays} days)` : ""}`;
      const target = `${wa}?text=${encodeURIComponent(text)}`;
      if (win) win.location.href = target; else window.open(target, "_blank");
    } catch (e) {
      win?.close();
      setErr((e as Error).message);
    }
  }
  async function copy() {
    try { const url = await link(); await navigator.clipboard?.writeText(url); setMsg(doc.kind === "FILE" ? `Link copied — it works for ${shareDays} days.` : "Link copied."); } catch (e) { setErr((e as Error).message); }
  }
  async function email(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    const split = (s: string) => s.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean);
    try {
      await api(`/documents/${doc.id}/email`, { body: { to: split(mail.to), cc: split(mail.cc), message: mail.message || null, attach: mail.attach } });
      setMsg(`E-mailed to ${mail.to}.`);
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={`Share — ${doc.title}`} onClose={onClose}>
      <div className="space-y-4 text-sm">
        <ErrorBox message={err} />
        {msg && <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">{msg}</p>}
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={whatsapp}><MessageCircle size={15} /> WhatsApp</Button>
          <Button variant="secondary" onClick={copy}><Link2 size={15} /> Copy link</Button>
        </div>
        {doc.kind === "FILE" && <p className="text-xs text-gray-500">Anyone with the link can open this file for {shareDays} days. Deleting the document stops the link.</p>}
        <form onSubmit={email} className="space-y-2 border-t border-gray-100 pt-3">
          <div className="flex items-center gap-2 font-medium text-gray-900"><Mail size={15} /> E-mail</div>
          <Field label="To"><Input required value={mail.to} onChange={(e) => setMail({ ...mail, to: e.target.value })} placeholder="ca@firm.in" /></Field>
          <Field label="Cc"><Input value={mail.cc} onChange={(e) => setMail({ ...mail, cc: e.target.value })} /></Field>
          <Field label="Message (optional)"><Textarea rows={2} value={mail.message} onChange={(e) => setMail({ ...mail, message: e.target.value })} /></Field>
          {doc.kind === "FILE" && <label className="flex items-center gap-2"><input type="checkbox" checked={mail.attach} onChange={(e) => setMail({ ...mail, attach: e.target.checked })} /> Attach the file (up to 10 MB)</label>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>Close</Button>
            <Button type="submit" disabled={busy}>{busy ? "Sending…" : "Send e-mail"}</Button>
          </div>
        </form>
      </div>
    </Modal>
  );
}
