"use client";

import { ExternalLink, MessagesSquare } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Input, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Chat { enabled: boolean; provider: string; property_id: string; widget_id: string; show_on: "WEBSITE" | "APP" | "BOTH"; pass_user: boolean; secure_key_set: boolean }

/** Admin → Integrations → Live chat (tawk.to). The ids are public; the optional secure-mode key is stored encrypted. */
export function AdminLiveChat() {
  const { data, setData } = useFetch<Chat>("/admin/live-chat");
  if (!data) return <Loading />;
  return <ChatForm key={JSON.stringify(data)} initial={data} onSaved={setData} />;
}

function ChatForm({ initial, onSaved }: { initial: Chat; onSaved: (c: Chat) => void }) {
  const [f, setF] = useState(initial);
  const [key, setKey] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function save(over: Partial<Chat> = {}, secure_key?: string) {
    setErr(null); setMsg(null);
    try {
      const body = { enabled: f.enabled, property_id: f.property_id, widget_id: f.widget_id, show_on: f.show_on, pass_user: f.pass_user, ...over,
        ...(secure_key !== undefined ? { secure_key } : key ? { secure_key: key } : {}) };
      onSaved(await api<Chat>("/admin/live-chat", { method: "PUT", body }));
      setMsg("Saved — the chat appears on the next page load.");
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <Card className="space-y-3 p-5 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 font-semibold text-gray-900"><MessagesSquare size={18} /> Live chat (tawk.to)</div>
          <p className="mt-1 max-w-2xl text-gray-500">
            A chat bubble for visitors and users. tawk.to is free; you and your team answer from its dashboard or mobile app.
            Sign up at <a href="https://www.tawk.to" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-brand-600 hover:underline">tawk.to <ExternalLink size={11} /></a>,
            then copy the ids from <b>Administration → Chat Widget</b> — the widget link looks like <code>embed.tawk.to/<b>PROPERTY_ID</b>/<b>WIDGET_ID</b></code>.
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${initial.enabled ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-600"}`}>{initial.enabled ? "On" : "Off"}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Property id"><Input value={f.property_id} placeholder="e.g. 64fa1b2c3d4e5f6a7b8c9d0e" onChange={(e) => setF({ ...f, property_id: e.target.value.trim() })} /></Field>
        <Field label="Widget id"><Input value={f.widget_id} placeholder="e.g. 1h9abcdef or default" onChange={(e) => setF({ ...f, widget_id: e.target.value.trim() })} /></Field>
        <Field label="Show on"><Select value={f.show_on} onChange={(e) => setF({ ...f, show_on: e.target.value as Chat["show_on"] })}>
          <option value="BOTH">Website and app</option><option value="WEBSITE">Website only (visitors, sign-in pages)</option><option value="APP">Inside the app only (signed-in users)</option>
        </Select></Field>
        <Field label="Secure-mode key (optional)" hint={f.secure_key_set ? "Saved — type a new one only to replace it" : "tawk.to → Administration → Property Settings → JavaScript API key. Stored encrypted."}>
          <Input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} />
        </Field>
      </div>
      <label className="flex items-center gap-2"><input type="checkbox" checked={f.pass_user} onChange={(e) => setF({ ...f, pass_user: e.target.checked })} />
        Tell the chat who a signed-in user is (name and e-mail), so agents don&apos;t have to ask</label>
      <p className="text-xs text-gray-500">The Privacy Policy already lists tawk.to as a provider used when live chat is on. In the app, the bubble sits above the Help button.</p>
      <ErrorBox message={err} />
      {msg && <p className="text-emerald-700">{msg}</p>}
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => save({ enabled: true })} disabled={!f.property_id}>{initial.enabled ? "Save" : "Save and switch on"}</Button>
        {initial.enabled && <Button variant="secondary" onClick={() => save({ enabled: false })}>Switch off</Button>}
        {f.secure_key_set && <Button variant="ghost" onClick={() => save({}, "")}>Remove secure key</Button>}
      </div>
    </Card>
  );
}
