"use client";

import { BadgeCheck, PlugZap, Save } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Settings {
  enabled: boolean; base_url: string; cache_days: number; daily_limit_business: number; daily_limit_user: number;
  min_plan: string; api_key_set: boolean; api_key_hint: string | null;
}
interface Usage {
  days: number; live_ok: number; live_failed: number; cache: number; credits_remaining: number | null; saved_by_cache_pct: number;
  recent: { gstin: string; source: string; ok: boolean; http_status: number | null; error: string | null; name: string | null; at: string }[];
}
interface Data { settings: Settings; usage: Usage }

export function AdminIntegrations() {
  const { data, setData } = useFetch<Data>("/admin/gstin-api");
  const [edit, setEdit] = useState<Partial<Settings> & { api_key?: string }>({});
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [test, setTest] = useState<string | null>(null);
  if (!data) return <Loading />;
  const s = { ...data.settings, ...edit };
  const u = data.usage;

  async function save(extra: Record<string, unknown> = {}) {
    setErr(null); setMsg(null);
    try {
      setData(await api<Data>("/admin/gstin-api", { method: "PUT", body: { ...edit, ...extra } }));
      setEdit({});
      setMsg("Saved.");
    } catch (e) { setErr((e as Error).message); }
  }

  async function testConnection() {
    setTest("Testing…");
    try {
      const r = await api<{ ok: boolean; stats?: Record<string, unknown>; error?: string; detail?: string }>("/admin/gstin-api/test", { body: {} });
      setTest(r.ok ? `Connected. ${Object.entries(r.stats ?? {}).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ")}`
        : `Failed${r.detail ? ` (${r.detail})` : ""}: ${r.error}`);
    } catch (e) { setTest((e as Error).message); }
  }

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="mb-1 flex items-center gap-2 font-semibold text-gray-900"><BadgeCheck size={18} /> GSTIN verification & autofill — gstinapi.in</div>
        <p className="mb-4 text-sm text-gray-600">
          Adds a <b>Verify & autofill</b> button next to every GSTIN field (onboarding, business settings, parties, quick-add party on bills).
          The API is called only when a user clicks it; typing a GSTIN is free. Results are cached so the same GSTIN is not paid for twice.
        </p>
        <ErrorBox message={err} />
        {msg && <div className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Status">
            <label className="flex items-center gap-2 pt-2 text-sm"><input type="checkbox" checked={s.enabled} onChange={(e) => setEdit({ ...edit, enabled: e.target.checked })} /> {s.enabled ? "Enabled for all users" : "Disabled"}</label>
          </Field>
          <Field label="API key" hint={data.settings.api_key_set ? `Saved: ${data.settings.api_key_hint ?? "••••"} — type a new key to replace it` : "From your gstinapi.in dashboard (starts with gak_)"}>
            <Input type="password" autoComplete="off" placeholder={data.settings.api_key_set ? "•••••••• (unchanged)" : "gak_…"} value={edit.api_key ?? ""} onChange={(e) => setEdit({ ...edit, api_key: e.target.value })} />
          </Field>
          <Field label="API base URL"><Input value={s.base_url} onChange={(e) => setEdit({ ...edit, base_url: e.target.value })} /></Field>
          <Field label="Re-use a verification for (days)" hint="0 = always call the API"><Input inputMode="numeric" value={String(s.cache_days)} onChange={(e) => setEdit({ ...edit, cache_days: Number(e.target.value) || 0 })} /></Field>
          <Field label="Paid lookups per business per day"><Input inputMode="numeric" value={String(s.daily_limit_business)} onChange={(e) => setEdit({ ...edit, daily_limit_business: Number(e.target.value) || 0 })} /></Field>
          <Field label="Paid lookups per user per day"><Input inputMode="numeric" value={String(s.daily_limit_user)} onChange={(e) => setEdit({ ...edit, daily_limit_user: Number(e.target.value) || 0 })} /></Field>
          <Field label="Available from plan">
            <Select value={s.min_plan} onChange={(e) => setEdit({ ...edit, min_plan: e.target.value })}>
              <option value="FREE">All plans (incl. Free)</option><option value="STARTER">Starter and above</option>
              <option value="PROFESSIONAL">Professional and above</option><option value="ENTERPRISE">Enterprise only</option>
            </Select>
          </Field>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button onClick={() => save()} disabled={!Object.keys(edit).length}><Save size={15} /> Save</Button>
          <Button variant="secondary" onClick={testConnection} disabled={!data.settings.api_key_set}><PlugZap size={15} /> Test connection (free)</Button>
          {data.settings.api_key_set && <Button variant="ghost" onClick={() => confirm("Remove the saved API key?") && save({ clear_api_key: true, enabled: false })}>Remove key</Button>}
        </div>
        {test && <p className="mt-2 break-all text-xs text-gray-600">{test}</p>}
      </Card>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {([["Paid lookups", u.live_ok], ["Served from cache (free)", u.cache], ["Failed (not charged)", u.live_failed],
          ["Saved by cache", `${u.saved_by_cache_pct}%`], ["Credits left (last seen)", u.credits_remaining ?? "—"]] as const).map(([l, v]) => (
          <Card key={l} className="p-4"><div className="text-xs text-gray-500">{l}</div><div className="mt-1 text-2xl font-semibold">{v}</div><div className="text-[10px] text-gray-400">last {u.days} days</div></Card>
        ))}
      </div>

      <Card className="overflow-x-auto">
        <h2 className="px-5 pt-4 pb-2 font-semibold">Recent lookups</h2>
        {u.recent.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">None yet.</p> : (
          <table className="tbl">
            <thead><tr><th>When</th><th>GSTIN</th><th>Name</th><th>Source</th><th>Result</th></tr></thead>
            <tbody>
              {u.recent.map((r, i) => (
                <tr key={i}>
                  <td className="whitespace-nowrap text-xs">{new Date(r.at).toLocaleString("en-IN")}</td>
                  <td className="font-mono text-xs">{r.gstin}</td><td className="text-xs">{r.name ?? ""}</td>
                  <td className="text-xs">{r.source === "LIVE" ? "API (paid)" : "Cache"}</td>
                  <td className={`text-xs ${r.ok ? "text-emerald-700" : "text-red-700"}`}>{r.ok ? "OK" : `${r.http_status ?? ""} ${r.error ?? ""}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
