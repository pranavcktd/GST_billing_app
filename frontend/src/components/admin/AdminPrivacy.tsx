"use client";

import { AlertOctagon, Inbox, Send } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading, Select, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Req { id: string; ref: string; kind: string; kind_label: string; details: string | null; status: string; response: string | null;
  created_at: string; due_on: string | null; user_email: string; user_name: string | null; handled_by: string | null }
interface Inc { id: string; title: string; description: string; affected: string | null; actions: string | null; severity: string; status: string;
  detected_at: string; notified_at: string | null; notified_count: number; created_by: string | null }

/** Super admin: DPDP rights requests / grievances, and the security-incident register. */
export function AdminPrivacy() {
  const { data: reqs, reload } = useFetch<Req[]>("/admin/privacy-requests");
  const { data: incs, reload: reloadInc } = useFetch<Inc[]>("/admin/incidents");
  const [open, setOpen] = useState<Req | null>(null);
  const [resp, setResp] = useState({ status: "CLOSED", response: "", erase: false });
  const [inc, setInc] = useState<Partial<Inc> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (!reqs || !incs) return <Loading />;
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-6">
      <ErrorBox message={err} />
      <Card className="overflow-x-auto">
        <h2 className="flex items-center gap-2 px-5 pt-4 pb-2 font-semibold"><Inbox size={17} /> Privacy requests &amp; grievances</h2>
        <p className="px-5 pb-2 text-xs text-gray-500">Acknowledge within 24 hours; grievances within 15 days, other requests within 30 days. Erasure removes the person’s login details — business books stay for the statutory period.</p>
        {reqs.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">No requests.</p> : (
          <table className="tbl">
            <thead><tr><th>Ref.</th><th>From</th><th>Request</th><th>Raised</th><th>Due</th><th>Status</th><th /></tr></thead>
            <tbody>
              {reqs.map((r) => (
                <tr key={r.id}>
                  <td className="font-mono text-xs">{r.ref}</td><td>{r.user_name}<div className="text-xs text-gray-500">{r.user_email}</div></td>
                  <td>{r.kind_label}<div className="max-w-xs text-xs text-gray-500">{r.details}</div></td>
                  <td className="text-xs">{fmtDate(r.created_at)}</td>
                  <td className={`text-xs ${r.status === "OPEN" && r.due_on && r.due_on < today ? "font-medium text-red-700" : ""}`}>{r.due_on ? fmtDate(r.due_on) : ""}</td>
                  <td className="text-xs">{r.status}{r.handled_by ? ` · ${r.handled_by}` : ""}</td>
                  <td className="text-right"><Button variant="secondary" className="!py-1" onClick={() => { setOpen(r); setResp({ status: "CLOSED", response: r.response ?? "", erase: false }); }}>Respond</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card className="overflow-x-auto">
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <h2 className="flex items-center gap-2 font-semibold"><AlertOctagon size={17} className="text-red-600" /> Security incidents</h2>
          <Button onClick={() => setInc({ severity: "MEDIUM", status: "OPEN" })}>Record incident</Button>
        </div>
        {incs.length === 0 ? <p className="px-5 pb-4 text-sm text-gray-500">No incidents recorded.</p> : (
          <table className="tbl">
            <thead><tr><th>Detected</th><th>Incident</th><th>Severity</th><th>Status</th><th>Businesses notified</th><th /></tr></thead>
            <tbody>
              {incs.map((i) => (
                <tr key={i.id}>
                  <td className="text-xs">{new Date(i.detected_at).toLocaleString("en-IN")}</td>
                  <td>{i.title}<div className="max-w-sm text-xs text-gray-500">{i.description}</div></td>
                  <td className="text-xs">{i.severity}</td><td className="text-xs">{i.status}</td>
                  <td className="text-xs">{i.notified_at ? `${i.notified_count} on ${new Date(i.notified_at).toLocaleDateString("en-IN")}` : "—"}</td>
                  <td className="space-x-1 text-right whitespace-nowrap">
                    <Button variant="secondary" className="!py-1" onClick={() => setInc(i)}>Edit</Button>
                    <Button variant="danger" className="!py-1" onClick={async () => {
                      if (!confirm("E-mail the owners of ALL businesses about this incident?")) return;
                      setErr(null);
                      try { await api(`/admin/incidents/${i.id}/notify`, { body: {} }); reloadInc(); } catch (e) { setErr((e as Error).message); }
                    }}><Send size={13} /> Notify</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {open && (
        <Modal title={`${open.kind_label} — ${open.ref}`} onClose={() => setOpen(null)}>
          <div className="space-y-3 text-sm">
            <p className="text-gray-600">{open.user_name} ({open.user_email}): {open.details || "no details"}</p>
            <Field label="Status"><Select value={resp.status} onChange={(e) => setResp({ ...resp, status: e.target.value })}>
              {["OPEN", "IN_PROGRESS", "CLOSED", "REJECTED"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
            </Select></Field>
            <Field label="Response to the person (e-mailed when closed)"><Textarea rows={4} value={resp.response} onChange={(e) => setResp({ ...resp, response: e.target.value })} /></Field>
            {open.kind === "ERASURE" && (
              <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={resp.erase} onChange={(e) => setResp({ ...resp, erase: e.target.checked })} />
                <span>Erase this person’s login details now (name, e-mail, mobile, sign-in methods; account deactivated). Business records are kept as the law requires.</span></label>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setOpen(null)}>Cancel</Button>
              <Button onClick={async () => {
                setErr(null);
                try { await api(`/admin/privacy-requests/${open.id}`, { method: "PUT", body: resp }); setOpen(null); reload(); }
                catch (e) { setErr((e as Error).message); }
              }}>Save</Button>
            </div>
          </div>
        </Modal>
      )}

      {inc && (
        <Modal title={inc.id ? "Edit incident" : "Record a security incident"} onClose={() => setInc(null)}>
          <div className="space-y-3 text-sm">
            <Field label="Title"><Input value={inc.title ?? ""} onChange={(e) => setInc({ ...inc, title: e.target.value })} /></Field>
            <Field label="What happened"><Textarea rows={3} value={inc.description ?? ""} onChange={(e) => setInc({ ...inc, description: e.target.value })} /></Field>
            <Field label="Data that may be affected"><Textarea rows={2} value={inc.affected ?? ""} onChange={(e) => setInc({ ...inc, affected: e.target.value })} /></Field>
            <Field label="What we are doing"><Textarea rows={2} value={inc.actions ?? ""} onChange={(e) => setInc({ ...inc, actions: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Severity"><Select value={inc.severity} onChange={(e) => setInc({ ...inc, severity: e.target.value })}>{["LOW", "MEDIUM", "HIGH"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
              <Field label="Status"><Select value={inc.status} onChange={(e) => setInc({ ...inc, status: e.target.value })}>{["OPEN", "CONTAINED", "CLOSED"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setInc(null)}>Cancel</Button>
              <Button onClick={async () => {
                setErr(null);
                const body = { title: inc.title, description: inc.description, affected: inc.affected ?? "", actions: inc.actions ?? "", severity: inc.severity, status: inc.status };
                try {
                  if (inc.id) await api(`/admin/incidents/${inc.id}`, { method: "PUT", body }); else await api("/admin/incidents", { body });
                  setInc(null); reloadInc();
                } catch (e) { setErr((e as Error).message); }
              }}>Save</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
