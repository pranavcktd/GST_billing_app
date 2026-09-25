"use client";

import { Download, FileBadge, Pencil, Truck, XCircle, Zap } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { TransportFields } from "@/components/TransportFields";
import { Button, Card, ErrorBox, Field, Input, Select } from "@/components/ui";
import { api, downloadFile } from "@/lib/api";
import type { Business, Transport, VoucherDetail } from "@/lib/types";

const within24h = (iso: string | null) => !!iso && Date.now() - new Date(iso).getTime() < 24 * 3600 * 1000;

/** e-Invoice (IRN) and e-Way bill actions for a document. */
export function EInvoicePanel({ v, business, onChange, canEdit }: {
  v: VoucherDetail; business: Business; onChange: (v: VoucherDetail) => void; canEdit: boolean;
}) {
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<null | "transport" | "irn" | "ewb" | "cancel">(null);
  const [transport, setTransport] = useState<Transport>(v.transport ?? {});
  const [manual, setManual] = useState({ irn: "", ack_no: "", ack_date: "", ewb_no: "", ewb_date: "", valid_till: "" });
  const [reason, setReason] = useState({ reason: "2", remark: "" });

  const plan = business.plan;
  const eligibleIrn = (v.type === "SALE" || v.type === "SALE_RETURN") && !!v.party_gstin && business.gst_type === "REGULAR";
  const eligibleEwb = ["SALE", "DELIVERY_CHALLAN", "PURCHASE"].includes(v.type) && !!business.gstin;
  if (v.cancelled || (!eligibleIrn && !eligibleEwb)) return null;

  const run = async (fn: () => Promise<VoucherDetail | void>) => {
    setBusy(true); setErr(null);
    try {
      const r = await fn();
      if (r) onChange(r);
      setDialog(null);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const api_ok = plan?.einvoice === "API";
  const json_ok = plan?.einvoice === "API" || plan?.einvoice === "JSON";

  return (
    <Card className="no-print mb-4 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1 text-sm">
          <div className="flex items-center gap-2 font-semibold text-gray-900"><FileBadge size={16} /> e-Invoice & e-Way Bill</div>
          {eligibleIrn && (
            <div className="text-gray-600">
              IRN: {v.einvoice_status === "GENERATED" ? <span className="font-mono text-xs text-emerald-700">{v.irn?.slice(0, 24)}… (Ack {v.ack_no})</span>
                : v.einvoice_status === "CANCELLED" ? <span className="text-red-700">cancelled</span> : <span className="text-gray-500">not generated</span>}
              {v.einvoice_sandbox && <span className="ml-2 rounded bg-amber-100 px-1.5 text-xs text-amber-800">sandbox</span>}
            </div>
          )}
          {eligibleEwb && (
            <div className="text-gray-600">
              E-way bill: {v.ewb_no ? <span className="font-medium text-emerald-700">{v.ewb_no}{v.ewb_valid_till ? ` · valid till ${new Date(v.ewb_valid_till).toLocaleString("en-IN")}` : ""}</span> : <span className="text-gray-500">not generated</span>}
            </div>
          )}
          <div className="text-gray-600">
            Transport: {v.transport?.vehicle_no || v.transport?.transporter_name
              ? `${v.transport.vehicle_no ?? ""} ${v.transport.transporter_name ?? ""} · ${v.transport.distance_km ?? 0} km` : "not added"}
          </div>
          {!json_ok && <div className="text-xs text-amber-700">e-Invoice & e-way bill need the Starter plan or above.</div>}
        </div>
        <div className="flex flex-wrap gap-2">
          {canEdit && <Button variant="secondary" onClick={() => setDialog("transport")}><Truck size={15} /> Transport</Button>}
          {eligibleIrn && v.einvoice_status !== "GENERATED" && (
            <>
              <Button variant="secondary" disabled={!json_ok} onClick={() => downloadFile(`/vouchers/${v.id}/einvoice/json`).catch((e) => setErr(e.message))}>
                <Download size={15} /> e-Invoice JSON
              </Button>
              {canEdit && <Button variant="secondary" disabled={!json_ok} onClick={() => setDialog("irn")}><Pencil size={15} /> Record IRN</Button>}
              {canEdit && (
                <Button disabled={busy || !api_ok} title={api_ok ? "" : "Direct generation needs the Professional plan"}
                  onClick={() => run(() => api<VoucherDetail>(`/vouchers/${v.id}/einvoice`, { body: {} }))}>
                  <Zap size={15} /> Generate IRN
                </Button>
              )}
            </>
          )}
          {eligibleIrn && v.einvoice_status === "GENERATED" && canEdit && within24h(v.ack_date) && (
            <Button variant="danger" onClick={() => setDialog("cancel")}><XCircle size={15} /> Cancel IRN</Button>
          )}
          {eligibleEwb && !v.ewb_no && (
            <>
              <Button variant="secondary" disabled={!json_ok} onClick={() => downloadFile(`/vouchers/${v.id}/ewaybill/json`).catch((e) => setErr(e.message))}>
                <Download size={15} /> E-way JSON
              </Button>
              {canEdit && <Button variant="secondary" disabled={!json_ok} onClick={() => setDialog("ewb")}><Pencil size={15} /> Record EWB</Button>}
              {canEdit && (
                <Button disabled={busy || !api_ok} title={api_ok ? "" : "Direct generation needs the Professional plan"}
                  onClick={() => run(() => api<VoucherDetail>(`/vouchers/${v.id}/ewaybill`, { body: {} }))}>
                  <Zap size={15} /> Generate EWB
                </Button>
              )}
            </>
          )}
        </div>
      </div>
      {err && <div className="mt-3"><ErrorBox message={err} /></div>}

      {dialog === "transport" && (
        <Modal title="Transport details" onClose={() => setDialog(null)} wide>
          <TransportFields value={transport} onChange={setTransport} />
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDialog(null)}>Cancel</Button>
            <Button disabled={busy} onClick={() => run(() => api<VoucherDetail>(`/vouchers/${v.id}/transport`, { method: "PUT", body: transport }))}>Save</Button>
          </div>
        </Modal>
      )}
      {dialog === "irn" && (
        <Modal title="Record IRN from the portal" onClose={() => setDialog(null)}>
          <div className="space-y-3">
            <p className="text-xs text-gray-500">Upload the JSON on the e-invoice portal (or its offline tool), then copy the IRN and acknowledgement here.</p>
            <Field label="IRN (64 characters)"><Input value={manual.irn} onChange={(e) => setManual({ ...manual, irn: e.target.value.trim() })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Ack no."><Input value={manual.ack_no} onChange={(e) => setManual({ ...manual, ack_no: e.target.value })} /></Field>
              <Field label="Ack date & time"><Input type="datetime-local" value={manual.ack_date} onChange={(e) => setManual({ ...manual, ack_date: e.target.value })} /></Field>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDialog(null)}>Cancel</Button>
              <Button disabled={busy} onClick={() => run(() => api<VoucherDetail>(`/vouchers/${v.id}/einvoice`, { method: "PUT",
                body: { irn: manual.irn, ack_no: manual.ack_no, ack_date: manual.ack_date } }))}>Save</Button>
            </div>
          </div>
        </Modal>
      )}
      {dialog === "ewb" && (
        <Modal title="Record e-way bill" onClose={() => setDialog(null)}>
          <div className="space-y-3">
            <Field label="E-way bill no. (12 digits)"><Input inputMode="numeric" maxLength={12} value={manual.ewb_no} onChange={(e) => setManual({ ...manual, ewb_no: e.target.value.replace(/\D/g, "") })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Generated on"><Input type="datetime-local" value={manual.ewb_date} onChange={(e) => setManual({ ...manual, ewb_date: e.target.value })} /></Field>
              <Field label="Valid till"><Input type="datetime-local" value={manual.valid_till} onChange={(e) => setManual({ ...manual, valid_till: e.target.value })} /></Field>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDialog(null)}>Cancel</Button>
              <Button disabled={busy} onClick={() => run(() => api<VoucherDetail>(`/vouchers/${v.id}/ewaybill`, { method: "PUT",
                body: { ewb_no: manual.ewb_no, ewb_date: manual.ewb_date, valid_till: manual.valid_till || null } }))}>Save</Button>
            </div>
          </div>
        </Modal>
      )}
      {dialog === "cancel" && (
        <Modal title="Cancel IRN" onClose={() => setDialog(null)}>
          <div className="space-y-3">
            <p className="text-sm text-gray-600">An IRN can be cancelled within 24 hours. The bill can then be edited or cancelled.</p>
            <Field label="Reason">
              <Select value={reason.reason} onChange={(e) => setReason({ ...reason, reason: e.target.value })}>
                <option value="1">Duplicate</option><option value="2">Data entry mistake</option>
                <option value="3">Order cancelled</option><option value="4">Other</option>
              </Select>
            </Field>
            <Field label="Remark"><Input maxLength={100} value={reason.remark} onChange={(e) => setReason({ ...reason, remark: e.target.value })} /></Field>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDialog(null)}>Back</Button>
              <Button variant="danger" disabled={busy} onClick={() => run(() => api<VoucherDetail>(`/vouchers/${v.id}/einvoice/cancel`, { body: reason }))}>Cancel IRN</Button>
            </div>
          </div>
        </Modal>
      )}
    </Card>
  );
}
