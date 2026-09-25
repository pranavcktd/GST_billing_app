"use client";

import { History, Save, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading, Textarea } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

type FieldType = "money" | "int" | "number" | "text" | "bool" | "rates" | "list" | "map_text" | "map_number";
interface ConfigField { key: string; group: string; label: string; type: FieldType; default: unknown; help: string }
interface Version { id: string; effective_from: string; values: Record<string, unknown>; note: string | null; by: string; at: string }
interface ConfigData { fields: ConfigField[]; effective: Record<string, unknown>; on: string; versions: Version[] }

const today = () => new Date().toISOString().slice(0, 10);

/** Value ⇄ text used in the editors. */
function toText(type: FieldType, v: unknown): string {
  if (v === null || v === undefined) return "";
  if (type === "rates") return (v as number[]).join(", ");
  if (type === "list") return (v as string[]).join("\n");
  if (type === "map_text" || type === "map_number") return Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k} = ${x}`).join("\n");
  return String(v);
}

function fromText(type: FieldType, t: string): unknown {
  if (type === "rates") return t.split(/[,\s]+/).filter(Boolean).map(Number);
  if (type === "list") return t.split("\n").map((x) => x.trim()).filter(Boolean);
  if (type === "map_text" || type === "map_number") {
    const out: Record<string, unknown> = {};
    for (const line of t.split("\n")) {
      const i = line.indexOf("=");
      if (i < 1) continue;
      const k = line.slice(0, i).trim();
      const x = line.slice(i + 1).trim();
      out[k] = type === "map_number" ? Number(x) : x;
    }
    return out;
  }
  if (type === "text") return t;
  if (type === "bool") return t === "true";
  return t === "" ? null : Number(t);
}

const summary = (f: ConfigField | undefined, v: unknown) => {
  if (!f) return String(v);
  const t = toText(f.type, v).replace(/\n/g, "; ");
  return t.length > 80 ? t.slice(0, 80) + "…" : t;
};

export function AdminConfig() {
  const [on, setOn] = useState(today());
  const { data, error, reload } = useFetch<ConfigData>(`/admin/config${qs({ on })}`);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [from, setFrom] = useState(today());
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const groups = useMemo(() => {
    const g: Record<string, ConfigField[]> = {};
    for (const f of data?.fields ?? []) (g[f.group] ??= []).push(f);
    return g;
  }, [data]);
  const byKey = useMemo(() => Object.fromEntries((data?.fields ?? []).map((f) => [f.key, f])), [data]);

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;

  const current = (f: ConfigField) => toText(f.type, data.effective[f.key]);
  const changed = Object.keys(edits).filter((k) => edits[k] !== current(byKey[k]));

  async function save() {
    setErr(null);
    setMsg(null);
    if (!changed.length) return setErr("Change at least one value first");
    setBusy(true);
    try {
      const values = Object.fromEntries(changed.map((k) => [k, fromText(byKey[k].type, edits[k])]));
      await api("/admin/config/versions", { body: { effective_from: from, values, note: note || null } });
      setEdits({});
      setNote("");
      setMsg(`Saved — applies to documents dated ${fmtDate(from)} onwards.`);
      reload();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(v: Version) {
    if (!confirm(`Remove the change effective ${fmtDate(v.effective_from)}? Documents will follow the previous values again.`)) return;
    try { await api(`/admin/config/versions/${v.id}`, { method: "DELETE" }); reload(); } catch (e) { setErr((e as Error).message); }
  }

  return (
    <div className="space-y-5">
      <Card className="p-4 text-sm text-gray-600">
        Every value here is used by the app at run time — no code change needed when the GST department changes a rule.
        Changes are <b>effective-dated</b>: bills dated before the date keep the old rule, bills on or after it follow the new one.
        Changes to the structure of return files (new tables or fields) still need a software update.
      </Card>
      <ErrorBox message={err} />
      {msg && <div className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{msg}</div>}

      <div className="flex flex-wrap items-end gap-3">
        <Field label="Show values in force on"><Input type="date" value={on} onChange={(e) => { setOn(e.target.value || today()); setEdits({}); }} /></Field>
      </div>

      {Object.entries(groups).map(([group, fields]) => (
        <Card key={group} className="p-5">
          <h2 className="mb-4 font-semibold text-gray-900">{group}</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {fields.map((f) => {
              const value = edits[f.key] ?? current(f);
              const dirty = f.key in edits && edits[f.key] !== current(f);
              const multi = f.type === "list" || f.type.startsWith("map_");
              const hint = f.type === "rates" ? "Comma separated, e.g. 0, 5, 18, 40" : multi ? (f.type === "list" ? "One per line" : "One per line: CODE = value") : undefined;
              return (
                <Field key={f.key} label={f.label + (dirty ? " •" : "")} hint={[f.help, hint].filter(Boolean).join(" ")} className={multi ? "md:col-span-2" : ""}>
                  {f.type === "bool" ? (
                    <label className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={value === "true"} onChange={(e) => setEdits({ ...edits, [f.key]: String(e.target.checked) })} />
                      {value === "true" ? "On" : "Off"}
                    </label>
                  ) : multi ? (
                    <Textarea rows={Math.min(10, Math.max(3, value.split("\n").length))} className={`font-mono text-xs ${dirty ? "!border-amber-400" : ""}`}
                      value={value} onChange={(e) => setEdits({ ...edits, [f.key]: e.target.value })} />
                  ) : (
                    <Input className={dirty ? "!border-amber-400" : ""} inputMode={f.type === "text" ? undefined : "decimal"}
                      value={value} onChange={(e) => setEdits({ ...edits, [f.key]: e.target.value })} />
                  )}
                </Field>
              );
            })}
          </div>
        </Card>
      ))}

      <Card className="sticky bottom-3 z-10 flex flex-wrap items-end gap-3 p-4 shadow-lg">
        <Field label="Effective from" hint="Use the date in the notification / circular"><Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label="Note (notification no., reason)" className="min-w-64 flex-1"><Input value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Notification 9/2025-CT(Rate)" /></Field>
        <div className="pb-0.5 text-xs text-gray-500">{changed.length ? `${changed.length} value(s) changed` : "No changes"}</div>
        {changed.length > 0 && <Button variant="ghost" onClick={() => setEdits({})}>Discard</Button>}
        <Button onClick={save} disabled={busy || !changed.length}><Save size={15} /> Save change</Button>
      </Card>

      <Card className="overflow-x-auto">
        <h2 className="flex items-center gap-2 px-5 pt-4 pb-2 font-semibold"><History size={16} /> Change history</h2>
        {data.versions.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">No changes yet — the app is using its built-in defaults.</p> : (
          <table className="tbl">
            <thead><tr><th>Effective from</th><th>Changed</th><th>Note</th><th>By</th><th /></tr></thead>
            <tbody>
              {data.versions.map((v) => (
                <tr key={v.id}>
                  <td className="whitespace-nowrap">{fmtDate(v.effective_from)}</td>
                  <td className="text-xs">
                    {Object.entries(v.values).map(([k, x]) => <div key={k}><b>{byKey[k]?.label ?? k}:</b> {summary(byKey[k], x)}</div>)}
                  </td>
                  <td className="text-xs">{v.note ?? "—"}</td>
                  <td className="text-xs">{v.by}<div className="text-gray-400">{new Date(v.at).toLocaleString("en-IN")}</div></td>
                  <td><button className="text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => remove(v)}><Trash2 size={15} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
