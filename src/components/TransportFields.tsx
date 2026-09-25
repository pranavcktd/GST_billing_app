"use client";

import { Field, Input, Select, Textarea } from "@/components/ui";
import type { Transport } from "@/lib/types";

const SUB_SUPPLY: Record<string, string> = {
  "1": "Supply", "2": "Import", "3": "Export", "4": "Job work", "5": "For own use", "6": "Job work returns",
  "7": "Sales return", "8": "Others", "9": "SKD/CKD/Lots", "10": "Line sales", "11": "Recipient not known", "12": "Exhibition or fairs",
};

/** Vehicle, transporter, distance… printed on the bill and used for the e-way bill. */
export function TransportFields({ value, onChange }: { value: Transport; onChange: (t: Transport) => void }) {
  const set = <K extends keyof Transport>(k: K, v: Transport[K]) => onChange({ ...value, [k]: v });
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Field label="Mode">
        <Select value={value.mode ?? "1"} onChange={(e) => set("mode", e.target.value as Transport["mode"])}>
          <option value="1">Road</option><option value="2">Rail</option><option value="3">Air</option><option value="4">Ship</option>
        </Select>
      </Field>
      <Field label="Vehicle no."><Input className="uppercase" value={value.vehicle_no ?? ""} placeholder="MH12AB1234" onChange={(e) => set("vehicle_no", e.target.value)} /></Field>
      <Field label="Distance (km)" hint="For e-way bill validity">
        <Input type="number" min={0} max={4000} value={value.distance_km ?? ""} onChange={(e) => set("distance_km", e.target.value ? Number(e.target.value) : undefined)} />
      </Field>
      <Field label="Transporter name"><Input value={value.transporter_name ?? ""} onChange={(e) => set("transporter_name", e.target.value)} /></Field>
      <Field label="Transporter ID" hint="GSTIN / TRANSIN"><Input className="uppercase" maxLength={15} value={value.transporter_id ?? ""} onChange={(e) => set("transporter_id", e.target.value.toUpperCase())} /></Field>
      <Field label="Sub-type (e-way bill)">
        <Select value={value.sub_supply_type ?? "1"} onChange={(e) => set("sub_supply_type", e.target.value)}>
          {Object.entries(SUB_SUPPLY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      </Field>
      <Field label="LR / transport doc no."><Input value={value.doc_no ?? ""} onChange={(e) => set("doc_no", e.target.value)} /></Field>
      <Field label="Doc date"><Input type="date" value={value.doc_date ?? ""} onChange={(e) => set("doc_date", e.target.value || undefined)} /></Field>
      <Field label="Ship-to address" className="sm:col-span-3"><Textarea rows={2} value={value.ship_to ?? ""} onChange={(e) => set("ship_to", e.target.value)} /></Field>
    </div>
  );
}
