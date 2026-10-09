"use client";

import { Save, UserPlus } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface S { verify: "OFF" | "WHATSAPP" | "EMAIL" | "EITHER"; google_enabled: boolean; google_client_id: string; methods_now: string[]; email_ready: boolean }

/** Super admin: how new accounts are verified, and "Continue with Google". */
export function AdminSignup() {
  const { data, setData } = useFetch<S>("/admin/signup");
  const [edit, setEdit] = useState<Partial<S>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (!data) return <Loading />;
  const s = { ...data, ...edit };
  const now = data.methods_now.length ? data.methods_now.map((m) => (m === "WHATSAPP" ? "WhatsApp code" : "e-mail code")).join(" or ") : "no verification";
  return (
    <Card className="space-y-3 p-5">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900"><UserPlus size={18} className="text-brand-600" /> Sign-up & sign-in</h2>
      <ErrorBox message={err} />
      {msg && <p className="text-sm text-emerald-700">{msg}</p>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Verify new accounts with" hint={`Right now new users verify by: ${now}. A channel that is not set up is skipped so sign-ups never break.`}>
          <Select value={s.verify} onChange={(e) => setEdit({ ...edit, verify: e.target.value as S["verify"] })}>
            <option value="OFF">No verification</option>
            <option value="WHATSAPP">WhatsApp code (mobile)</option>
            <option value="EMAIL">E-mail code</option>
            <option value="EITHER">User chooses: WhatsApp or e-mail</option>
          </Select>
        </Field>
        <div className="space-y-2">
          <label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" checked={s.google_enabled} onChange={(e) => setEdit({ ...edit, google_enabled: e.target.checked })} /> “Continue with Google” on sign-up and sign-in</label>
        </div>
        <Field label="Google OAuth Client ID" className="sm:col-span-2"
          hint="Google Cloud Console → APIs & Services → Credentials → OAuth client ID (type: Web application). Add your site address (and http://localhost:3000 for testing) under Authorised JavaScript origins. This ID is public — no secret is needed.">
          <Input placeholder="1234567890-abc123.apps.googleusercontent.com" value={s.google_client_id} onChange={(e) => setEdit({ ...edit, google_client_id: e.target.value.trim() })} />
        </Field>
      </div>
      {!data.email_ready && <p className="text-xs text-amber-700">E-mail codes need the platform e-mail (Admin → Email) to be set up.</p>}
      <div className="flex justify-end">
        <Button onClick={async () => {
          setErr(null); setMsg(null);
          try { setData(await api<S>("/admin/signup", { method: "PUT", body: edit })); setEdit({}); setMsg("Saved."); }
          catch (e) { setErr((e as Error).message); }
        }}><Save size={15} /> Save</Button>
      </div>
    </Card>
  );
}
