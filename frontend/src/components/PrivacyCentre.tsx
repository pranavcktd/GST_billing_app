"use client";

import { Download, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button, Card, ErrorBox, Field, Select, Textarea } from "@/components/ui";
import { api, apiBlob, saveBlob } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Req { id: string; ref: string; kind: string; kind_label: string; details: string | null; status: string; response: string | null; created_at: string; due_on: string | null }

const KINDS: [string, string][] = [["ACCESS", "A copy of my personal data"], ["CORRECTION", "Correct my personal data"],
  ["ERASURE", "Erase my personal data / close my account"], ["WITHDRAW", "Withdraw consent"], ["GRIEVANCE", "A grievance or complaint"]];

/** Settings → Security: DPDP rights — download my data, raise a request, follow its status. */
export function PrivacyCentre() {
  const { data: reqs, reload } = useFetch<Req[]>("/privacy/requests");
  const [kind, setKind] = useState("ACCESS");
  const [details, setDetails] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  return (
    <Card className="space-y-3 p-5 md:col-span-2">
      <h2 className="flex items-center gap-2 font-semibold text-gray-900"><ShieldCheck size={17} className="text-brand-600" /> Your data &amp; privacy</h2>
      <p className="text-sm text-gray-600">
        Your rights under the Digital Personal Data Protection Act, 2023. Business records (invoices, books) are exported by the owner from
        Utilities → Backup &amp; restore. See the <Link href="/privacy" className="text-brand-600 underline">Privacy Policy</Link>.
      </p>
      <ErrorBox message={err} />
      {msg && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={async () => {
          try { const { blob, filename } = await apiBlob("/privacy/my-data"); saveBlob(blob, filename || "my-personal-data.json"); }
          catch (e) { setErr((e as Error).message); }
        }}><Download size={15} /> Download my personal data</Button>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="I would like"><Select value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
        <Field label="Details" className="sm:col-span-2"><Textarea rows={2} value={details} onChange={(e) => setDetails(e.target.value)} placeholder="What should we do? For corrections, say what is wrong." /></Field>
      </div>
      <div className="flex justify-end">
        <Button onClick={async () => {
          setErr(null); setMsg(null);
          try {
            const r = await api<Req>("/privacy/requests", { body: { kind, details } });
            setMsg(`Request ${r.ref} received — we will respond by ${fmtDate(r.due_on!)}.`); setDetails(""); reload();
          } catch (e) { setErr((e as Error).message); }
        }}>Send request</Button>
      </div>
      {!!reqs?.length && (
        <table className="tbl">
          <thead><tr><th>Ref.</th><th>Request</th><th>Raised</th><th>Status</th><th>Response</th></tr></thead>
          <tbody>
            {reqs.map((r) => (
              <tr key={r.id}><td className="font-mono text-xs">{r.ref}</td><td>{r.kind_label}</td><td>{fmtDate(r.created_at)}</td>
                <td>{r.status.replace("_", " ").toLowerCase()}{r.status === "OPEN" && r.due_on ? ` · by ${fmtDate(r.due_on)}` : ""}</td>
                <td className="text-xs text-gray-600">{r.response}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
