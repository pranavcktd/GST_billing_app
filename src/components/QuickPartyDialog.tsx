"use client";

import { useState } from "react";
import { Button, ErrorBox, Field, Input, Select } from "@/components/ui";
import { STATES } from "@/lib/constants";
import { api } from "@/lib/api";
import { gstinError } from "@/lib/gst";
import type { Party } from "@/lib/types";

/** Add a party without leaving the bill being written. */
export function QuickPartyDialog({
  type,
  initialName,
  onClose,
  onCreated,
}: {
  type: "CUSTOMER" | "SUPPLIER";
  initialName: string;
  onClose: () => void;
  onCreated: (p: Party) => void;
}) {
  const [f, setF] = useState({ name: initialName, phone: "", gstin: "", state_code: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const gstErr = f.gstin ? gstinError(f.gstin) : null;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (gstErr) return;
    setBusy(true);
    setError(null);
    try {
      const p = await api<Party>("/parties", {
        body: { ...f, type, gst_type: f.gstin ? "REGISTERED" : type === "CUSTOMER" ? "CONSUMER" : "UNREGISTERED" },
      });
      onCreated(p);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4" onMouseDown={onClose}>
      <form onSubmit={save} onMouseDown={(e) => e.stopPropagation()} className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
        <h2 className="mb-4 font-semibold text-gray-900">New {type === "CUSTOMER" ? "customer" : "supplier"}</h2>
        <ErrorBox message={error} />
        <div className="space-y-3">
          <Field label="Name" required><Input required autoFocus value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field label="Phone"><Input type="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
          <Field label="GSTIN (if registered)" error={gstErr}>
            <Input
              maxLength={15}
              className="uppercase"
              value={f.gstin}
              onChange={(e) => {
                const g = e.target.value.toUpperCase();
                setF({ ...f, gstin: g, state_code: STATES[g.slice(0, 2)] ? g.slice(0, 2) : f.state_code });
              }}
            />
          </Field>
          <Field label="State">
            <Select value={f.state_code} onChange={(e) => setF({ ...f, state_code: e.target.value })}>
              <option value="">Select state</option>
              {Object.entries(STATES).map(([c, n]) => <option key={c} value={c}>{c} - {n}</option>)}
            </Select>
          </Field>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Add party"}</Button>
        </div>
      </form>
    </div>
  );
}
