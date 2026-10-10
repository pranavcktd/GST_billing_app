"use client";

import { ArrowDown, ArrowUp, ExternalLink, History, Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Markdown, fillPlaceholders } from "@/components/SiteContent";
import { Button, Card, ErrorBox, Field, Input, Loading, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useConfig } from "@/lib/config";
import { DEFAULT_LANDING, type LandingContent, mergeLanding } from "@/lib/landingContent";
import { toast } from "@/lib/toast";
import { useFetch } from "@/lib/useFetch";

interface PageRow { slug: string; title: string; custom: boolean; updated_at: string | null; updated_by: string | null; versions: number; format: string; consent: boolean }
interface PageFull extends PageRow { body: string | null; default_body: string | null }
interface Version { id: string; title: string; saved_at: string; saved_by: string | null; note: string | null; size: number }

const PATHS: Record<string, string> = { landing: "/" };
const PLACEHOLDERS = ["{{brand}}", "{{company.name}}", "{{company.email}}", "{{company.address}}", "{{company.phone}}",
  "{{legal.grievance_officer}}", "{{legal.grievance_email}}", "{{legal.grievance_phone}}", "{{legal.jurisdiction|fallback text}}",
  "{{legal.data_location}}", "{{legal.cin}}", "{{#if legal.cin}}…{{/if}}"];
const LABEL = (k: string) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** Generic form for the home page content: strings, string lists, object lists, nested objects. */
function JsonForm({ value, shape, onChange, path = "" }: { value: unknown; shape: unknown; onChange: (v: unknown) => void; path?: string }) {
  if (typeof shape === "string") {
    const v = typeof value === "string" ? value : "";
    return shape.length > 70 || v.length > 70
      ? <Textarea rows={Math.min(6, Math.max(2, Math.ceil(v.length / 90)))} value={v} onChange={(e) => onChange(e.target.value)} />
      : <Input value={v} onChange={(e) => onChange(e.target.value)} />;
  }
  if (Array.isArray(shape)) {
    const list = Array.isArray(value) ? value : [];
    const item = shape[0];
    const move = (i: number, d: number) => { const n = [...list]; [n[i], n[i + d]] = [n[i + d], n[i]]; onChange(n); };
    const blank = typeof item === "string" ? "" : Array.isArray(item) ? [] : Object.fromEntries(Object.entries(item as object).map(([k, v]) => [k, typeof v === "string" ? "" : Array.isArray(v) ? [] : v]));
    return (
      <div className="space-y-2">
        {list.map((v, i) => (
          <div key={`${path}-${i}`} className={typeof item === "string" ? "flex gap-1" : "rounded-lg border border-gray-200 p-3"}>
            <div className="min-w-0 flex-1"><JsonForm value={v} shape={item} path={`${path}.${i}`} onChange={(nv) => onChange(list.map((x, j) => (j === i ? nv : x)))} /></div>
            <div className={typeof item === "string" ? "flex shrink-0" : "mt-2 flex justify-end gap-1"}>
              <Button type="button" variant="ghost" className="!px-1.5" disabled={i === 0} onClick={() => move(i, -1)} title="Move up"><ArrowUp size={14} /></Button>
              <Button type="button" variant="ghost" className="!px-1.5" disabled={i === list.length - 1} onClick={() => move(i, 1)} title="Move down"><ArrowDown size={14} /></Button>
              <Button type="button" variant="ghost" className="!px-1.5 text-red-600" onClick={() => onChange(list.filter((_, j) => j !== i))} title="Remove"><Trash2 size={14} /></Button>
            </div>
          </div>
        ))}
        <Button type="button" variant="secondary" className="!py-1 !text-xs" onClick={() => onChange([...list, blank])}><Plus size={13} /> Add</Button>
      </div>
    );
  }
  if (shape && typeof shape === "object") {
    const obj = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {Object.entries(shape as Record<string, unknown>).map(([k, s]) => (
          <div key={k} className={typeof s === "string" && (s as string).length <= 70 ? "" : "sm:col-span-2"}>
            <div className="mb-1 text-xs font-medium text-gray-600">{LABEL(k)}</div>
            <JsonForm value={obj[k]} shape={s} path={`${path}.${k}`} onChange={(nv) => onChange({ ...obj, [k]: nv })} />
          </div>
        ))}
      </div>
    );
  }
  return null;
}

const LANDING_SECTIONS: [keyof LandingContent, string][] = [
  ["hero", "Top banner (hero)"], ["ticker", "Scrolling feature strip"], ["day", "A day in your business"], ["checks", "Smart checks"],
  ["demo", "GST demo heading"], ["features", "Features (tabs)"], ["pricing", "Pricing section"], ["faq", "Questions (FAQ)"],
  ["final", "Closing call to action"], ["footer_note", "Footer disclaimer"],
];

function initialLanding(data: PageFull): LandingContent | null {
  if (data.format !== "json") return null;
  try { return mergeLanding(data.body ? JSON.parse(data.body) : null); } catch { return mergeLanding(null); }
}

function Editor({ slug, onSaved }: { slug: string; onSaved: () => void }) {
  const { data, setData } = useFetch<PageFull>(`/admin/site/${slug}`);
  if (!data) return <Loading />;
  return <EditorForm key={`${data.updated_at ?? "builtin"}-${data.custom}`} slug={slug} data={data} setData={setData} onSaved={onSaved} />;
}

function EditorForm({ slug, data, setData, onSaved }: { slug: string; data: PageFull; setData: (d: PageFull) => void; onSaved: () => void }) {
  const cfg = useConfig();
  const { data: versions, reload: reloadVersions } = useFetch<Version[]>(`/admin/site/${slug}/versions`);
  const [title, setTitle] = useState(data.title);
  const [body, setBody] = useState(data.format === "json" ? "" : data.body ?? "");
  const [landing, setLanding] = useState<LandingContent | null>(() => initialLanding(data));
  const [section, setSection] = useState<keyof LandingContent>("hero");
  const [reaccept, setReaccept] = useState(false);
  const [note, setNote] = useState("");
  const [view, setView] = useState<{ id: string; title: string; body: string } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const isLanding = data.format === "json";

  async function save() {
    setErr(null); setMsg(null);
    try {
      const r = await api<PageFull & { legal_version: string | null }>(`/admin/site/${slug}`, { method: "PUT",
        body: { title, body: isLanding ? JSON.stringify(landing) : body, note: note || null, reaccept } });
      setData({ ...data, ...r }); setReaccept(false); setNote(""); reloadVersions(); onSaved();
      toast(r.legal_version ? "Saved — every user will be asked to accept the new version at their next visit." : "Saved and live on the website.");
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Field label="Page title" className="min-w-[16rem] flex-1"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        <div className="flex flex-wrap gap-2">
          <Link href={PATHS[slug] ?? `/${slug}`} target="_blank" className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"><ExternalLink size={14} /> View page</Link>
          {data.custom && <Button variant="secondary" onClick={async () => {
            if (!confirm("Go back to the built-in text? The current text is kept in the version history.")) return;
            setData({ ...data, ...(await api<PageFull>(`/admin/site/${slug}/reset`, { body: {} })) }); reloadVersions(); onSaved();
          }}><RotateCcw size={14} /> Built-in text</Button>}
        </div>
      </div>

      {isLanding && landing ? (
        <div className="grid gap-4 lg:grid-cols-[13rem_1fr]">
          <div className="flex flex-wrap gap-1 lg:flex-col">
            {LANDING_SECTIONS.map(([k, label]) => (
              <button key={k} onClick={() => setSection(k)} className={`rounded-lg px-3 py-1.5 text-left text-sm ${section === k ? "bg-brand-600 text-white" : "text-gray-700 hover:bg-gray-100"}`}>{label}</button>
            ))}
          </div>
          <Card className="p-4">
            <p className="mb-3 text-xs text-gray-500">Use <code>{"{brand}"}</code> for the product name and <code>{"{trial}"}</code> for the free-trial days. Icons follow the order of the items.</p>
            <JsonForm value={landing[section]} shape={DEFAULT_LANDING[section]} path={section}
              onChange={(v) => setLanding({ ...landing, [section]: v } as LandingContent)} />
          </Card>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="space-y-2">
            <Textarea rows={26} className="font-mono text-xs" value={body} onChange={(e) => setBody(e.target.value)} />
            <details className="text-xs text-gray-600">
              <summary className="cursor-pointer">Formatting & placeholders</summary>
              <p className="mt-1"><code>## Heading</code> · <code>**bold**</code> · <code>- list item</code> · <code>1. numbered</code> · <code>[link](/privacy)</code> ·
                <code> &gt; intro box</code> · tables with <code>| a | b |</code>. Placeholders are filled from Admin → GST config (company, legal):</p>
              <p className="mt-1 font-mono">{PLACEHOLDERS.join("  ")}</p>
            </details>
          </div>
          <Card className="max-h-[42rem] overflow-y-auto p-5 text-sm leading-relaxed text-gray-700 [&_h2]:mt-6 [&_h2]:font-semibold [&_h2]:text-gray-900 [&_li]:ml-5 [&_li]:list-disc [&_ol>li]:list-decimal [&_table]:w-full [&_td]:border-t [&_td]:py-1 [&_td]:pr-2 [&_th]:text-left [&_th]:text-xs">
            <div className="mb-2 text-[11px] font-semibold tracking-wider text-gray-400 uppercase">Preview</div>
            <h1 className="text-xl font-bold text-gray-900">{title}</h1>
            <Markdown text={fillPlaceholders(body, cfg)} />
          </Card>
        </div>
      )}

      <Card className="space-y-3 p-4">
        {data.consent && (
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={reaccept} onChange={(e) => setReaccept(e.target.checked)} />
            <span><b>Ask every user to accept this new version</b> — use for material changes to the Terms, Privacy Policy or Data Processing Addendum. Acceptances are recorded with the version and time.</span></label>
        )}
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Note for the version history (optional)" className="min-w-[16rem] flex-1"><Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Updated refund window" /></Field>
          <Button onClick={save}><Save size={15} /> Save & publish</Button>
        </div>
        <ErrorBox message={err} />
        {msg && <p className="text-sm text-emerald-700">{msg}</p>}
      </Card>

      <Card className="overflow-x-auto">
        <h3 className="flex items-center gap-2 px-4 pt-3 pb-2 text-sm font-semibold text-gray-900"><History size={15} /> Version history</h3>
        {!versions?.length ? <p className="px-4 pb-3 text-sm text-gray-500">No earlier versions yet — every save keeps the previous text here.</p> : (
          <table className="tbl">
            <thead><tr><th>Saved</th><th>By</th><th>Note</th><th /></tr></thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.id}>
                  <td className="text-xs whitespace-nowrap">{new Date(v.saved_at).toLocaleString("en-IN")}</td><td className="text-xs">{v.saved_by}</td><td className="text-xs">{v.note}</td>
                  <td className="space-x-1 text-right whitespace-nowrap">
                    {!isLanding && <Button variant="ghost" className="!py-1 !text-xs" onClick={async () => setView(await api(`/admin/site/${slug}/versions/${v.id}`))}>View</Button>}
                    <Button variant="secondary" className="!py-1 !text-xs" onClick={async () => {
                      if (!confirm("Restore this version? The current text is kept in the history.")) return;
                      setData({ ...data, ...(await api<PageFull>(`/admin/site/${slug}/versions/${v.id}/restore`, { body: {} })) }); reloadVersions(); onSaved();
                    }}>Restore</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {view && (
        <Modal title={`${view.title} — earlier version`} onClose={() => setView(null)}>
          <div className="max-h-[60vh] overflow-y-auto text-sm [&_h2]:mt-4 [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc"><Markdown text={fillPlaceholders(view.body, cfg)} /></div>
        </Modal>
      )}
    </div>
  );
}

/** Super admin → Website: home page and policy pages. */
export function AdminSite() {
  const { data, reload } = useFetch<{ pages: PageRow[]; legal_version: string | null }>("/admin/site");
  const [slug, setSlug] = useState("landing");
  if (!data) return <Loading />;
  return (
    <div className="grid gap-5 lg:grid-cols-[15rem_1fr]">
      <Card className="h-fit p-2">
        {data.pages.map((p) => (
          <button key={p.slug} onClick={() => setSlug(p.slug)}
            className={`block w-full rounded-lg px-3 py-2 text-left text-sm ${slug === p.slug ? "bg-brand-50 font-medium text-brand-700" : "text-gray-700 hover:bg-gray-50"}`}>
            {p.title}
            <span className="block text-[11px] text-gray-400">{p.custom ? `Edited ${p.updated_at ? new Date(p.updated_at).toLocaleDateString("en-IN") : ""}` : "Built-in text"}{p.versions ? ` · ${p.versions} earlier` : ""}</span>
          </button>
        ))}
        <p className="px-3 pt-2 pb-1 text-[11px] text-gray-400">Consent version: {data.legal_version ?? "—"}</p>
      </Card>
      <div key={slug}><Editor slug={slug} onSaved={reload} /></div>
    </div>
  );
}
