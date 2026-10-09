"use client";

import { FileKey2, ShieldCheck, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

export interface DscStatus {
  configured: boolean; subject?: string; organisation?: string | null; issuer?: string; serial?: string; not_after?: string;
  days_left?: number; expired?: boolean; mode?: "AUTO" | "ON_REQUEST"; uploaded_by?: string | null; uploaded_at?: string;
}

/** Settings → Business: digital signature certificate (.pfx / .p12) used to sign document PDFs. */
export function DscSettings({ canEdit }: { canEdit: boolean }) {
  const { data, setData } = useFetch<DscStatus>("/dsc");
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"AUTO" | "ON_REQUEST">("AUTO");
  const [replace, setReplace] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!data) return null;

  async function upload() {
    setBusy(true); setErr(null); setMsg(null);
    try {
      const form = new FormData();
      form.append("file", file!);
      form.append("password", password);
      form.append("mode", mode);
      setData(await api<DscStatus>("/dsc", { form }));
      setFile(null); setPassword(""); setReplace(false);
      setMsg("Certificate saved — PDFs will now carry your digital signature.");
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  const modeRadios = (value: string, onChange: (m: "AUTO" | "ON_REQUEST") => void) => (
    <div className="space-y-1.5 text-sm">
      <label className="flex items-start gap-2"><input type="radio" className="mt-1" checked={value === "AUTO"} onChange={() => onChange("AUTO")} />
        <span><b>Sign every PDF</b> <span className="text-gray-500">— downloads, e-mails, WhatsApp and the customer link</span></span></label>
      <label className="flex items-start gap-2"><input type="radio" className="mt-1" checked={value === "ON_REQUEST"} onChange={() => onChange("ON_REQUEST")} />
        <span><b>Only when I ask</b> <span className="text-gray-500">— a “Signed PDF” button and an e-mail option appear</span></span></label>
    </div>
  );

  return (
    <Card className="mt-5 space-y-4 p-5">
      <div>
        <h2 className="flex items-center gap-2 font-semibold text-gray-900"><FileKey2 size={18} className="text-brand-600" /> Digital signature (DSC)</h2>
        <p className="mt-1 text-sm text-gray-500">
          Sign invoices and other documents with your digital signature certificate. The signature is embedded in the PDF, so
          Adobe Reader shows who signed it and warns if it is changed afterwards.
        </p>
      </div>
      <ErrorBox message={err} />
      {msg && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</p>}

      {data.configured && !replace ? (
        <div className="space-y-4">
          <div className={`flex flex-wrap items-start gap-3 rounded-xl border p-4 ${data.expired ? "border-red-200 bg-red-50" : (data.days_left ?? 0) < 30 ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`}>
            <ShieldCheck size={22} className={data.expired ? "text-red-600" : "text-emerald-600"} />
            <div className="min-w-0 flex-1 text-sm">
              <div className="font-semibold text-gray-900">{data.subject}{data.organisation ? ` · ${data.organisation}` : ""}</div>
              <div className="text-gray-600">Issued by {data.issuer} · Serial {data.serial}</div>
              <div className={data.expired ? "font-medium text-red-700" : (data.days_left ?? 0) < 30 ? "font-medium text-amber-800" : "text-gray-600"}>
                {data.expired ? `Expired on ${fmtDate(data.not_after!)} — documents are not being signed. Upload the renewed certificate.`
                  : `Valid till ${fmtDate(data.not_after!)} (${data.days_left} days left)`}
              </div>
              {data.uploaded_by && <div className="text-xs text-gray-500">Added by {data.uploaded_by}{data.uploaded_at ? ` on ${fmtDate(data.uploaded_at)}` : ""}</div>}
            </div>
          </div>
          {canEdit && (
            <>
              {modeRadios(data.mode ?? "AUTO", async (m) => {
                try { setData(await api<DscStatus>("/dsc/mode", { method: "PUT", body: { mode: m } })); } catch (e) { setErr((e as Error).message); }
              })}
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => { setReplace(true); setMode(data.mode ?? "AUTO"); }}><Upload size={15} /> Replace certificate</Button>
                <Button variant="danger" onClick={async () => {
                  if (!confirm("Remove the digital signature certificate? New PDFs will not be signed.")) return;
                  await api("/dsc", { method: "DELETE" }); setData({ configured: false });
                }}><Trash2 size={15} /> Remove</Button>
              </div>
            </>
          )}
        </div>
      ) : canEdit ? (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Certificate file (.pfx or .p12)">
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-gray-300 px-3 py-2 text-sm hover:bg-gray-50">
                <Upload size={15} className="text-gray-500" /><span className="truncate">{file ? file.name : "Choose file"}</span>
                <input type="file" accept=".pfx,.p12,application/x-pkcs12" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </label>
            </Field>
            <Field label="Certificate password"><Input type="password" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
          </div>
          {modeRadios(mode, setMode)}
          <div className="flex gap-2">
            <Button disabled={!file || busy} onClick={upload}><ShieldCheck size={15} /> {busy ? "Checking…" : "Save certificate"}</Button>
            {replace && <Button variant="secondary" onClick={() => setReplace(false)}>Cancel</Button>}
          </div>
          <p className="text-xs text-gray-500">
            The file and password are stored encrypted and are never shown again. Most Class 3 DSCs are on a USB token whose key cannot
            be exported as a file — signing with a USB token is coming in a later update.
          </p>
        </div>
      ) : (
        <p className="text-sm text-gray-500">No certificate added. The owner or an admin can add one.</p>
      )}
    </Card>
  );
}
