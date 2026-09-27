"use client";

import { ArrowLeft, Lock, LockOpen, Save } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AssetsTab, PartnersTab } from "@/components/practice/AssetsTab";
import { FiguresTab } from "@/components/practice/FiguresTab";
import { StatementsTab } from "@/components/practice/StatementsTab";
import type { FileData, Head, PFile, Statements } from "@/components/practice/types";
import { Button, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

type Tab = "figures" | "assets" | "partners" | "statements";

export default function PracticeFilePage() {
  const { id } = useParams<{ id: string }>();
  const { data: loaded, error, setData: setLoaded } = useFetch<PFile>(`/practice/files/${id}`);
  const { data: heads } = useFetch<Head[]>("/practice/heads");
  const [draft, setDraft] = useState<FileData | null>(null);
  const [dirty, setDirty] = useState(false);
  const [tab, setTab] = useState<Tab>("figures");
  const [st, setSt] = useState<Statements | null>(null);
  const [stLoading, setStLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const file = loaded;
  const data = draft ?? file?.data ?? null;
  const locked = file?.status === "FINAL";
  const setData = (d: FileData) => { setDraft(d); setDirty(true); };

  const save = useCallback(async () => {
    if (!file || !draft || !dirty) return;
    setBusy(true); setErr(null);
    try {
      const f = await api<PFile>(`/practice/files/${file.id}`, { method: "PUT", body: { data: draft } });
      setLoaded(f); setDraft(null); setDirty(false);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }, [file, draft, dirty, setLoaded]);

  const loadStatements = useCallback(async () => {
    setStLoading(true);
    try { setSt(await api<Statements>(`/practice/files/${id}/statements`)); } catch (e) { setErr((e as Error).message); } finally { setStLoading(false); }
  }, [id]);

  useEffect(() => {
    if (tab !== "statements") return;
    let cancelled = false;
    (async () => { await save(); if (!cancelled) await loadStatements(); })();
    return () => { cancelled = true; };
  }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (error) return <ErrorBox message={error} />;
  if (!file || !data || !heads) return <Loading />;
  const partnership = file.client.entity_type === "PARTNERSHIP";

  async function finalize() {
    await save();
    setErr(null);
    try { setLoaded(await api<PFile>(`/practice/files/${id}/finalize`, { body: {} })); loadStatements(); }
    catch (e) { setErr((e as Error).message); setTab("statements"); }
  }
  async function reopen() {
    if (!confirm("Reopen these accounts for changes? A new version number is created; the finalised copy stays on record.")) return;
    try { setLoaded(await api<PFile>(`/practice/files/${id}/reopen`, { body: {} })); } catch (e) { setErr((e as Error).message); }
  }

  const TABS: [Tab, string][] = [["figures", "1. Figures"], ["assets", "2. Depreciation"], ...(partnership ? [["partners", "3. Partners"] as [Tab, string]] : []), ["statements", `${partnership ? 4 : 3}. Statements`]];

  return (
    <>
      <Link href={`/practice/clients/${file.client.id}`} className="mb-3 inline-flex items-center gap-1 text-sm text-gray-600 hover:underline"><ArrowLeft size={14} /> {file.client.name}</Link>
      <PageHeader title={`${file.client.name} — FY ${file.fy}`}
        sub={`${partnership ? "Partnership firm" : "Proprietorship"} · version ${file.version} · ${locked ? `finalised${file.finalized_by ? ` by ${file.finalized_by.split(" <")[0]}` : ""}` : "draft"}${file.source ? ` · figures from ${file.source.toLowerCase().replace("_", " ")}` : ""}`}
        actions={<>
          {!locked && <Button variant={dirty ? "primary" : "secondary"} disabled={!dirty || busy} onClick={save}><Save size={15} /> {dirty ? "Save" : "Saved"}</Button>}
          {locked ? <Button variant="secondary" onClick={reopen}><LockOpen size={15} /> Reopen</Button>
            : <Button variant="secondary" onClick={finalize} title="Locks this version; errors in the checks must be fixed first"><Lock size={15} /> Finalise</Button>}
        </>} />
      <ErrorBox message={err} />
      {locked && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Finalised and locked. Reopen to make changes — a new version is created.</div>}
      <div className="mb-4 flex flex-wrap gap-1 rounded-lg border border-gray-200 bg-white p-1 text-sm">
        {TABS.map(([k, label]) => <button key={k} onClick={() => setTab(k)} className={`rounded-md px-4 py-1.5 ${tab === k ? "bg-brand-600 text-white" : "text-gray-700"}`}>{label}</button>)}
      </div>
      {tab === "figures" && <FiguresTab file={file} data={data} setData={setData} heads={heads} locked={locked} onReplaced={(f) => { setLoaded(f); setDraft(null); setDirty(false); }} />}
      {tab === "assets" && <AssetsTab data={data} setData={setData} locked={locked} />}
      {tab === "partners" && <PartnersTab data={data} setData={setData} locked={locked} />}
      {tab === "statements" && <StatementsTab st={st} loading={stLoading} />}
    </>
  );
}
