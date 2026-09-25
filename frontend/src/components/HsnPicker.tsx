"use client";

import { AlertTriangle, CheckCircle2, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Field, Input, Select, Textarea } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { useConfig } from "@/lib/config";

interface Hit { code: string; kind: "HSN" | "SAC"; description: string | null; gst_rate: number | null; cess_rate: number }
interface Lookup {
  code: string; kind: "HSN" | "SAC" | null; found: boolean; description: string | null; gst_rate: number | null;
  cess_rate: number | null; parents: { code: string; description: string | null }[]; strict: boolean; min_digits: number;
}

/**
 * HSN / SAC field backed by the platform's official master: type a code or words to search,
 * pick a code to see its description and apply the suggested GST rate. Codes that are not in the
 * master show a warning (an error in strict mode) with a button to request them.
 */
export function HsnPicker({ value, onChange, service, onRate }: {
  value: string; onChange: (code: string) => void; service: boolean;
  onRate: (gst: number, cess: number | null) => void;
}) {
  const config = useConfig();
  const [query, setQuery] = useState(value);
  const [hits, setHits] = useState<Hit[]>([]);
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState<Lookup | null>(null);
  const [requesting, setRequesting] = useState(false);
  const lastLookup = useRef("");

  useEffect(() => {
    if (!open || query.trim().length < 2) return;
    const t = setTimeout(() => {
      api<Hit[]>(`/hsn-master${qs({ search: query.trim(), kind: service ? "SAC" : "HSN" })}`).then(setHits).catch(() => setHits([]));
    }, 250);
    return () => clearTimeout(t);
  }, [query, open, service]);

  async function lookup(code: string, applyRate: boolean) {
    if (!/^\d{4,8}$/.test(code)) { setInfo(null); return; }
    lastLookup.current = code;
    try {
      const r = await api<Lookup>(`/hsn-master/lookup/${code}`);
      if (lastLookup.current !== code) return;
      setInfo(r);
      if (applyRate && r.found && r.gst_rate !== null) onRate(r.gst_rate, r.cess_rate);
    } catch { setInfo(null); }
  }

  useEffect(() => {
    if (value) lookup(value, false); // eslint-disable-line react-hooks/set-state-in-effect -- show the saved code's details
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pick(h: Hit) {
    setQuery(h.code);
    onChange(h.code);
    setOpen(false);
    lookup(h.code, true);
  }

  const code = value;
  const wrongKind = code && (service ? !code.startsWith("99") : code.startsWith("99"));
  const short = code && /^\d+$/.test(code) && code.length < (info?.min_digits ?? config.hsn_digits_small);

  return (
    <div className="relative">
      <Input
        value={query}
        placeholder={service ? "SAC code or service name" : "HSN code or product name"}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          const v = e.target.value;
          setQuery(v);
          setOpen(true);
          const digits = v.replace(/\s/g, "");
          onChange(/^\d*$/.test(digits) ? digits : value);
        }}
        onBlur={() => setTimeout(() => { setOpen(false); if (/^\d{4,8}$/.test(query.replace(/\s/g, ""))) lookup(query.replace(/\s/g, ""), code !== info?.code); }, 150)}
      />
      {open && hits.length > 0 && query.trim().length >= 2 && (
        <div className="absolute z-30 mt-1 max-h-72 w-[min(36rem,90vw)] overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
          {hits.map((h) => (
            <button key={h.code} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => pick(h)}
              className="block w-full border-b border-gray-50 px-3 py-2 text-left text-sm hover:bg-brand-50">
              <span className="font-mono font-semibold">{h.code}</span>
              <span className="ml-2 text-xs text-gray-500">{h.gst_rate !== null ? `${h.gst_rate}% GST` : "rate not set"}</span>
              <span className="block truncate text-xs text-gray-600">{h.description}</span>
            </button>
          ))}
        </div>
      )}

      {wrongKind ? (
        <p className="mt-1 text-xs text-red-700">{service ? "Services use SAC codes starting with 99." : "Codes starting with 99 are SAC (services) — switch the type to Service."}</p>
      ) : info && info.code === code ? (
        info.found ? (
          <div className="mt-1 text-xs text-emerald-800">
            <CheckCircle2 size={12} className="mr-1 inline" />
            {info.parents.map((p) => p.description).filter(Boolean).slice(-1).map((d) => <span key={d} className="text-gray-500">{d} › </span>)}
            {info.description}
            {info.gst_rate !== null ? <b> · suggested {info.gst_rate}% GST</b> : <span className="text-gray-500"> · no standard rate — check the notification</span>}
          </div>
        ) : (
          <div className={`mt-1 text-xs ${info.strict ? "text-red-700" : "text-amber-800"}`}>
            <AlertTriangle size={12} className="mr-1 inline" />
            {info.strict ? "Not in the official HSN/SAC list — this code cannot be used." : "Not in the official HSN/SAC list — please double-check."}{" "}
            <button type="button" className="font-medium underline" onClick={() => setRequesting(true)}>Request it</button>
          </div>
        )
      ) : null}
      {!wrongKind && short && <p className="mt-1 text-xs text-amber-800">At least {info?.min_digits ?? config.hsn_digits_small} digits are required on tax invoices.</p>}

      {requesting && <RequestCode code={code} service={service} onClose={() => setRequesting(false)} />}
    </div>
  );
}

export function RequestCode({ code, service, onClose, onDone }: { code: string; service: boolean; onClose: () => void; onDone?: () => void }) {
  const config = useConfig();
  const [f, setF] = useState({ code, description: "", gst_rate: "", note: "" });
  const [err, setErr] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function send() {
    setErr(null);
    try {
      await api("/hsn-master/requests", { body: { code: f.code, description: f.description, gst_rate: f.gst_rate === "" ? null : Number(f.gst_rate), note: f.note || null } });
      setSent(true);
      onDone?.();
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <Modal title={`Request a missing ${service ? "SAC" : "HSN"} code`} onClose={onClose}>
      {sent ? (
        <div className="space-y-3 text-sm">
          <p>Sent. The code becomes available to everyone once the platform team verifies it — you&apos;ll see the status under Utilities → HSN / SAC.</p>
          <div className="flex justify-end"><Button onClick={onClose}>OK</Button></div>
        </div>
      ) : (
        <div className="space-y-3">
          <Field label="Code" required><Input value={f.code} pattern="\d{4,8}" onChange={(e) => setF({ ...f, code: e.target.value.replace(/\D/g, "") })} /></Field>
          <Field label="Description (as in the notification / tariff)" required><Textarea rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
          <Field label="GST rate, if you know it">
            <Select value={f.gst_rate} onChange={(e) => setF({ ...f, gst_rate: e.target.value })}>
              <option value="">Not sure</option>
              {config.gst_rates.map((r) => <option key={r} value={r}>{r}%</option>)}
            </Select>
          </Field>
          <Field label="Source / note" hint="e.g. notification number or where you found the code"><Input value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
          <ErrorBox message={err} />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button onClick={send} disabled={!/^\d{4,8}$/.test(f.code) || f.description.trim().length < 3}><Send size={14} /> Send request</Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
