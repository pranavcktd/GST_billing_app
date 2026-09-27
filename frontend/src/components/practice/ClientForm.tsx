"use client";

import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox, Field, Input, Select, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import type { Entity, PClient } from "./types";

/** Add / edit a practice client. */
export function ClientForm({ initial, onClose, onSaved }: { initial?: PClient; onClose: () => void; onSaved: (c: PClient) => void }) {
  const [f, setF] = useState({
    name: initial?.name ?? "", entity_type: (initial?.entity_type ?? "PROPRIETORSHIP") as Entity, pan: initial?.pan ?? "",
    gstin: initial?.gstin ?? "", address: initial?.address ?? "", phone: initial?.phone ?? "", email: initial?.email ?? "",
    nature_of_business: initial?.nature_of_business ?? "", notes: initial?.notes ?? "",
  });
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f, v: string) => setF({ ...f, [k]: v });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const body = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v === "" ? null : v]));
    try {
      onSaved(await api<PClient>(initial ? `/practice/clients/${initial.id}` : "/practice/clients", { method: initial ? "PUT" : "POST", body }));
    } catch (x) { setErr((x as Error).message); }
  }

  return (
    <Modal title={initial ? "Edit client" : "Add client"} onClose={onClose} wide>
      <form onSubmit={save} className="space-y-3">
        <ErrorBox message={err} />
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Client / business name" required><Input required value={f.name} onChange={(e) => set("name", e.target.value)} /></Field>
          <Field label="Constitution">
            <Select value={f.entity_type} onChange={(e) => set("entity_type", e.target.value)}>
              <option value="PROPRIETORSHIP">Proprietorship (individual)</option>
              <option value="PARTNERSHIP">Partnership firm</option>
            </Select>
          </Field>
          <Field label="PAN"><Input maxLength={10} className="uppercase" value={f.pan} onChange={(e) => set("pan", e.target.value.toUpperCase())} /></Field>
          <Field label="GSTIN"><Input maxLength={15} className="uppercase" value={f.gstin} onChange={(e) => set("gstin", e.target.value.toUpperCase())} /></Field>
          <Field label="Nature of business"><Input value={f.nature_of_business} onChange={(e) => set("nature_of_business", e.target.value)} placeholder="e.g. Retail trade — hardware" /></Field>
          <Field label="Phone"><Input value={f.phone} onChange={(e) => set("phone", e.target.value)} /></Field>
          <Field label="Email"><Input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} /></Field>
          <Field label="Address" className="sm:col-span-2"><Textarea rows={2} value={f.address} onChange={(e) => set("address", e.target.value)} /></Field>
          <Field label="Notes" className="sm:col-span-2"><Textarea rows={2} value={f.notes} onChange={(e) => set("notes", e.target.value)} /></Field>
        </div>
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button type="submit">Save</Button></div>
      </form>
    </Modal>
  );
}
