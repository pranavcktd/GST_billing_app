"use client";

import { Landmark, Save } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface S { enabled: boolean; base_url: string; hourly_limit_user: number }

/** Super admin: IFSC → bank branch lookup used by every bank-details form. */
export function AdminIfsc() {
  const { data, setData } = useFetch<S>("/admin/ifsc-api");
  const [edit, setEdit] = useState<Partial<S>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (!data) return <Loading />;
  const s = { ...data, ...edit };
  return (
    <Card className="space-y-3 p-5">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900"><Landmark size={18} className="text-brand-600" /> IFSC lookup</h2>
      <p className="text-xs text-gray-500">Typing an IFSC in any bank form fills the bank name and branch (users can still edit). Free source: Razorpay IFSC API — no key needed. Answers are cached.</p>
      <ErrorBox message={err} />
      {msg && <p className="text-sm text-emerald-700">{msg}</p>}
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" checked={s.enabled} onChange={(e) => setEdit({ ...edit, enabled: e.target.checked })} /> {s.enabled ? "On" : "Off — users type bank details"}</label>
        <Field label="Service URL" hint="GET <url>/<IFSC> returning JSON"><Input value={s.base_url} onChange={(e) => setEdit({ ...edit, base_url: e.target.value })} /></Field>
        <Field label="Lookups per user per hour"><Input type="number" min={1} value={s.hourly_limit_user} onChange={(e) => setEdit({ ...edit, hourly_limit_user: Number(e.target.value) })} /></Field>
      </div>
      <div className="flex justify-end">
        <Button onClick={async () => {
          setErr(null); setMsg(null);
          try { setData(await api<S>("/admin/ifsc-api", { method: "PUT", body: edit })); setEdit({}); setMsg("Saved."); }
          catch (e) { setErr((e as Error).message); }
        }}><Save size={15} /> Save</Button>
      </div>
    </Card>
  );
}
