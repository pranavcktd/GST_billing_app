"use client";

import { FolderLock, Save } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface S {
  enabled: boolean; allow_links: boolean; storage: "LINKS" | "CLOUDINARY" | "DATABASE"; max_file_mb: number; quota_mb: number; share_days: number;
  cloudinary_configured: boolean; images_storage: "CLOUDINARY" | "DATABASE"; image_max_mb: number;
}

/** Super admin: how businesses may keep documents in their vault. */
export function AdminDocuments() {
  const { data, error, reload } = useFetch<S>("/admin/documents-settings");
  const [edit, setEdit] = useState<Partial<S>>({});
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;
  const s = { ...data, ...edit };
  async function save() {
    setErr(null); setMsg(null);
    try { await api("/admin/documents-settings", { method: "PUT", body: edit }); setEdit({}); setMsg("Saved — applies to every business."); reload(); } catch (e) { setErr((e as Error).message); }
  }
  const num = (k: "max_file_mb" | "quota_mb" | "share_days" | "image_max_mb") => ({ inputMode: "numeric" as const, value: String(s[k]), onChange: (e: React.ChangeEvent<HTMLInputElement>) => setEdit({ ...edit, [k]: Number(e.target.value) || 1 }) });
  return (
    <Card className="p-5">
      <h2 className="mb-1 flex items-center gap-2 font-semibold text-gray-900"><FolderLock size={18} /> File storage</h2>
      <p className="mb-4 text-sm text-gray-600">Where the app keeps files that businesses upload. {s.cloudinary_configured ? "Cloudinary is configured on the server." : "Cloudinary is not configured on the server (CLOUDINARY_URL), so only 'Our database' is available."}</p>
      <ErrorBox message={err} />
      {msg && <div className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      <h3 className="mb-2 text-sm font-semibold text-gray-900">Images — logos, signatures, item photos</h3>
      <div className="mb-5 grid gap-4 md:grid-cols-3">
        <Field label="Image storage" hint="Shown on invoices customers open, so image links are public (but unguessable). Changing it affects new uploads only.">
          <Select value={s.images_storage} onChange={(e) => setEdit({ ...edit, images_storage: e.target.value as S["images_storage"] })}>
            <option value="CLOUDINARY" disabled={!s.cloudinary_configured}>Cloud storage (Cloudinary)</option>
            <option value="DATABASE">Our database (resized to 1200 px)</option>
          </Select>
        </Field>
        <Field label="Largest image (MB)"><Input {...num("image_max_mb")} /></Field>
      </div>
      <h3 className="mb-2 text-sm font-semibold text-gray-900">Document vault — ITRs, certificates, licences (private)</h3>
      <div className="grid gap-4 md:grid-cols-3">
        <Field label="Status"><label className="flex items-center gap-2 pt-2 text-sm"><input type="checkbox" checked={s.enabled} onChange={(e) => setEdit({ ...edit, enabled: e.target.checked })} /> {s.enabled ? "On for all businesses" : "Off"}</label></Field>
        <Field label="File storage" hint={s.cloudinary_configured ? "Cloudinary is configured on the server" : "Cloudinary is not configured on the server (CLOUDINARY_URL)"}>
          <Select value={s.storage} onChange={(e) => setEdit({ ...edit, storage: e.target.value as S["storage"] })}>
            <option value="LINKS">Links only (Google Drive etc.) — no files stored</option>
            <option value="CLOUDINARY" disabled={!s.cloudinary_configured}>Cloud storage (Cloudinary, private)</option>
            <option value="DATABASE">Our database (testing / small installations)</option>
          </Select>
        </Field>
        <Field label="Links (Google Drive, OneDrive…)"><label className="flex items-center gap-2 pt-2 text-sm"><input type="checkbox" checked={s.allow_links} onChange={(e) => setEdit({ ...edit, allow_links: e.target.checked })} /> {s.allow_links ? "Allowed" : "Not allowed"}</label></Field>
        <Field label="Largest file (MB)"><Input {...num("max_file_mb")} /></Field>
        <Field label="Storage per business (MB)"><Input {...num("quota_mb")} /></Field>
        <Field label="Share links work for (days)"><Input {...num("share_days")} /></Field>
      </div>
      <div className="mt-4"><Button onClick={save} disabled={!Object.keys(edit).length}><Save size={15} /> Save</Button></div>
    </Card>
  );
}
