"use client";

import { DatabaseBackup, Download, RotateCcw, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { ApiError, api, downloadFile } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface PB { id: string; scope: "FULL" | "ACCOUNT"; label: string; kind: string; size: number; created_at: string }
interface BB { id: string; business_id: string; business: string | null; kind: string; size: number; created_at: string }
interface Listing { platform: PB[]; business: BB[]; auto_full_backup: boolean }
interface Owner { id: string; name: string; email: string; level: string }
interface Biz { id: string; name: string; owner_email: string | null }

const size = (n: number) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
const when = (s: string) => new Date(s).toLocaleString("en-IN");

export function AdminBackups() {
  const { data, reload } = useFetch<Listing>("/admin/backups");
  const { data: owners } = useFetch<Owner[]>("/admin/users?level=OWNER");
  const { data: businesses } = useFetch<Biz[]>("/admin/businesses");
  const [target, setTarget] = useState({ account: "", business: "" });
  const [restore, setRestore] = useState<null | { file?: File; stored?: { id: string; kind: "platform" | "business"; label: string }; full?: boolean }>(null);
  const [ownerEmail, setOwnerEmail] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true); setErr(null); setMsg(null);
    try { await fn(); setMsg(ok); reload(); return true; } catch (e) {
      if (e instanceof ApiError && e.code === "CONFIRM_FULL") { setRestore((r) => r && { ...r, full: true }); setErr(null); }
      else setErr((e as Error).message);
      return false;
    } finally { setBusy(false); }
  };

  async function doRestore() {
    if (!restore) return;
    const ok = await run(async () => {
      if (restore.file) {
        const form = new FormData();
        form.append("file", restore.file);
        if (ownerEmail) form.append("owner_email", ownerEmail);
        if (confirmText) form.append("confirm", confirmText);
        return api("/admin/backups/import", { form });
      }
      return api(`/admin/backups/${restore.stored!.id}/restore?kind=${restore.stored!.kind}`, { body: { owner_email: ownerEmail || null, confirm: confirmText || null } });
    }, restore.full ? "Full platform restore completed. A safety backup of the previous data was kept." : "Backup restored as new business(es).");
    if (ok) { setRestore(null); setConfirmText(""); }
  }

  if (!data) return <Loading />;
  return (
    <>
      <ErrorBox message={err} />
      {msg && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      <div className="mb-5 grid gap-4 lg:grid-cols-4">
        <Card className="space-y-2 p-4">
          <div className="font-semibold text-gray-900">Full platform</div>
          <p className="text-xs text-gray-500">Every account, business, user and setting.</p>
          <Button className="w-full" disabled={busy} onClick={() => run(() => api("/admin/backups", { body: { scope: "FULL" } }), "Full backup created")}><DatabaseBackup size={15} /> Back up now</Button>
          <label className="flex items-center gap-2 text-xs text-gray-600">
            <input type="checkbox" checked={data.auto_full_backup} onChange={(e) => run(() => api("/admin/backups/auto", { method: "PUT", body: { enabled: e.target.checked } }), "Setting saved")} />
            Automatic daily (last 7 kept)
          </label>
        </Card>
        <Card className="space-y-2 p-4">
          <div className="font-semibold text-gray-900">One account</div>
          <p className="text-xs text-gray-500">All businesses of an owner.</p>
          <Select value={target.account} onChange={(e) => setTarget({ ...target, account: e.target.value })}>
            <option value="">Choose owner</option>{owners?.map((o) => <option key={o.id} value={o.id}>{o.name} — {o.email}</option>)}
          </Select>
          <Button className="w-full" disabled={busy || !target.account} onClick={() => run(() => api("/admin/backups", { body: { scope: "ACCOUNT", ref_id: target.account } }), "Account backup created")}><DatabaseBackup size={15} /> Back up</Button>
        </Card>
        <Card className="space-y-2 p-4">
          <div className="font-semibold text-gray-900">One business</div>
          <p className="text-xs text-gray-500">Saved with the business&apos;s own backups.</p>
          <Select value={target.business} onChange={(e) => setTarget({ ...target, business: e.target.value })}>
            <option value="">Choose business</option>{businesses?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </Select>
          <Button className="w-full" disabled={busy || !target.business} onClick={() => run(() => api("/admin/backups", { body: { scope: "BUSINESS", ref_id: target.business } }), "Business backup created")}><DatabaseBackup size={15} /> Back up</Button>
        </Card>
        <Card className="space-y-2 p-4">
          <div className="font-semibold text-gray-900">Import a backup file</div>
          <p className="text-xs text-gray-500">Business or account backups become new businesses; a full backup replaces everything.</p>
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-gray-300 px-3 py-2 text-sm hover:bg-gray-50">
            <Upload size={15} /> Choose .gstbak file
            <input type="file" accept=".gstbak" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) { setRestore({ file: f }); setOwnerEmail(""); setConfirmText(""); } }} />
          </label>
        </Card>
      </div>

      <Card className="mb-5 overflow-x-auto">
        <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Platform backups</h2>
        <table className="tbl">
          <thead><tr><th>Created</th><th>Scope</th><th>Label</th><th>Type</th><th>Size</th><th /></tr></thead>
          <tbody>
            {data.platform.map((b) => (
              <tr key={b.id}>
                <td className="text-xs">{when(b.created_at)}</td><td>{b.scope}</td><td>{b.label}</td>
                <td className={b.kind === "SAFETY" ? "text-amber-700" : ""}>{b.kind}</td><td>{size(b.size)}</td>
                <td className="text-right whitespace-nowrap">
                  <Button variant="ghost" className="!px-2 !py-1" title="Download" onClick={() => downloadFile(`/admin/backups/${b.id}/download?kind=platform`).catch((e) => setErr(e.message))}><Download size={15} /></Button>
                  <Button variant="ghost" className="!px-2 !py-1" title="Restore" onClick={() => { setRestore({ stored: { id: b.id, kind: "platform", label: b.label }, full: b.scope === "FULL" }); setOwnerEmail(""); setConfirmText(""); }}><RotateCcw size={15} /></Button>
                  <Button variant="ghost" className="!px-2 !py-1 text-red-600" title="Delete" onClick={() => confirm("Delete this backup?") && run(() => api(`/admin/backups/${b.id}?kind=platform`, { method: "DELETE" }), "Deleted")}><Trash2 size={15} /></Button>
                </td>
              </tr>
            ))}
            {!data.platform.length && <tr><td colSpan={6} className="text-center text-sm text-gray-500">No platform backups yet</td></tr>}
          </tbody>
        </table>
      </Card>
      <Card className="overflow-x-auto">
        <h2 className="px-5 pt-4 pb-2 font-semibold text-gray-900">Business backups (latest 200)</h2>
        <table className="tbl">
          <thead><tr><th>Created</th><th>Business</th><th>Type</th><th>Size</th><th /></tr></thead>
          <tbody>
            {data.business.map((b) => (
              <tr key={b.id}>
                <td className="text-xs">{when(b.created_at)}</td><td>{b.business}</td><td>{b.kind}</td><td>{size(b.size)}</td>
                <td className="text-right whitespace-nowrap">
                  <Button variant="ghost" className="!px-2 !py-1" title="Download" onClick={() => downloadFile(`/admin/backups/${b.id}/download?kind=business`).catch((e) => setErr(e.message))}><Download size={15} /></Button>
                  <Button variant="ghost" className="!px-2 !py-1" title="Restore as new business" onClick={() => { setRestore({ stored: { id: b.id, kind: "business", label: b.business ?? "" } }); setOwnerEmail(b.business ? businesses?.find((x) => x.id === b.business_id)?.owner_email ?? "" : ""); }}><RotateCcw size={15} /></Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {restore && (
        <Modal title={restore.full ? "Restore FULL platform backup" : "Restore backup"} onClose={() => setRestore(null)}>
          <div className="space-y-3 text-sm">
            <p className="text-gray-600">{restore.file ? restore.file.name : restore.stored?.label}</p>
            {restore.full ? (
              <>
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-red-800">
                  This <b>replaces ALL data</b> on the platform — every account, business and user — with the backup. A safety backup of the current data is taken first. Your own super-admin login is kept.
                </div>
                <Field label='Type RESTORE ALL DATA to confirm'><Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} /></Field>
              </>
            ) : (
              <Field label="Restore into account (owner e-mail)" hint="The businesses are added as new businesses of this owner — nothing existing is overwritten">
                <Input type="email" list="owner-emails" value={ownerEmail} onChange={(e) => setOwnerEmail(e.target.value)} />
                <datalist id="owner-emails">{owners?.map((o) => <option key={o.id} value={o.email}>{o.name}</option>)}</datalist>
              </Field>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setRestore(null)}>Cancel</Button>
              <Button variant={restore.full ? "danger" : "primary"} disabled={busy || (restore.full ? confirmText !== "RESTORE ALL DATA" : false)} onClick={doRestore}>
                {busy ? "Restoring…" : restore.full ? "Replace all data" : "Restore"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
