"use client";

import { Boxes, Briefcase, Layers } from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { type BusinessMode, businessMode, MODULES, presetHidden } from "@/lib/modules";

const MODES: { mode: BusinessMode; title: string; text: string; icon: React.ElementType }[] = [
  { mode: "SERVICES", title: "Services only", text: "Consultants, agencies, repairs, professionals — no stock, godowns or e-way bills", icon: Briefcase },
  { mode: "GOODS", title: "Products only", text: "Traders, shops, distributors, manufacturers", icon: Boxes },
  { mode: "BOTH", title: "Products & services", text: "Everything switched on", icon: Layers },
];

/** Settings → Modules: choose what the business deals in and switch off menus it does not use. */
export function ModuleSettings({ canEdit }: { canEdit: boolean }) {
  const { business, refresh } = useAuth();
  const [mode, setMode] = useState<BusinessMode>(businessMode(business));
  const [hidden, setHidden] = useState<Set<string>>(() => new Set(business?.modules?.hidden ?? []));
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function pick(m: BusinessMode) {
    setMode(m);
    setHidden(new Set(presetHidden(m)));
  }
  const toggle = (key: string) => setHidden((cur) => {
    const next = new Set(cur);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  async function save() {
    setBusy(true); setErr(null);
    try {
      await api("/businesses/current/modules", { method: "PUT", body: { mode, hidden: [...hidden] } });
      await refresh();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const groups: [string, typeof MODULES][] = [
    ["Mostly for products", MODULES.filter((m) => m.kind === "goods")],
    ["Mostly for services", MODULES.filter((m) => m.kind === "services")],
    ["Optional for everyone", MODULES.filter((m) => m.kind === "general")],
  ];
  return (
    <div className="max-w-3xl space-y-5">
      <ErrorBox message={err} />
      <Card className="p-5">
        <h2 className="font-semibold text-gray-900">What does this business deal in?</h2>
        <p className="mt-1 text-sm text-gray-600">We switch off menus you are unlikely to need so the app stays simple. You can fine-tune the list below.</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {MODES.map(({ mode: m, title, text, icon: Icon }) => (
            <button key={m} type="button" disabled={!canEdit} onClick={() => pick(m)}
              className={`rounded-lg border p-3 text-left transition ${mode === m ? "border-brand-500 bg-brand-50 ring-2 ring-brand-100" : "border-gray-200 hover:bg-gray-50"}`}>
              <div className="flex items-center gap-2 font-medium text-gray-900"><Icon size={16} /> {title}</div>
              <div className="mt-1 text-xs text-gray-600">{text}</div>
            </button>
          ))}
        </div>
      </Card>
      <Card className="p-5">
        <h2 className="font-semibold text-gray-900">Menus</h2>
        <p className="mt-1 text-sm text-gray-600">Switched-off menus disappear from the sidebar and search. Nothing is deleted — switch them on any time.</p>
        <div className="mt-4 space-y-5">
          {groups.map(([title, mods]) => (
            <div key={title}>
              <div className="mb-2 text-xs font-semibold tracking-wider text-gray-400 uppercase">{title}</div>
              <div className="grid gap-2 sm:grid-cols-2">
                {mods.map((m) => (
                  <label key={m.key} className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-gray-200 p-2.5 text-sm hover:bg-gray-50">
                    <input type="checkbox" className="mt-0.5" disabled={!canEdit} checked={!hidden.has(m.key)} onChange={() => toggle(m.key)} />
                    <span><span className="font-medium text-gray-900">{m.label}</span><span className="block text-xs text-gray-500">{m.hint}</span></span>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>
      {canEdit && <div className="flex justify-end"><Button disabled={busy} onClick={save}>{busy ? "Saving…" : "Save modules"}</Button></div>}
    </div>
  );
}
