"use client";

import { ArrowRightLeft } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Biz {
  id: string; name: string; gstin: string | null; created_at: string; owner: string | null; owner_email: string | null; members: number; backups: number;
  excel_backup: boolean | null; excel_backup_on: boolean;
}

/** All businesses (metadata only) with ownership transfer. */
export function AdminBusinesses() {
  const [search, setSearch] = useState("");
  const { data, reload } = useFetch<Biz[]>(`/admin/businesses${qs({ search })}`);
  const [transfer, setTransfer] = useState<Biz | null>(null);
  const [email, setEmail] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const { data: excelDefault, setData: setExcelDefault } = useFetch<{ default: boolean }>("/admin/excel-backup");

  async function setExcel(b: Biz, v: string) {
    setErr(null);
    try {
      await api(`/admin/businesses/${b.id}/excel-backup`, { method: "PUT", body: { enabled: v === "" ? null : v === "on" } });
      reload();
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <Input placeholder="Search business, GSTIN or owner e-mail" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-sm" />
        {excelDefault && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={excelDefault.default} onChange={async (e) => {
              try { setExcelDefault(await api<{ default: boolean }>("/admin/excel-backup", { method: "PUT", body: { enabled: e.target.checked } })); reload(); }
              catch (x) { setErr((x as Error).message); }
            }} />
            Excel backups (.zip) on for all businesses by default
          </label>
        )}
      </div>
      <ErrorBox message={err} />
      <Card className="overflow-x-auto">
        {!data ? <Loading /> : (
          <table className="tbl">
            <thead><tr><th>Business</th><th>GSTIN</th><th>Owner</th><th className="num">People</th><th className="num">Backups</th><th>Excel backup</th><th>Created</th><th /></tr></thead>
            <tbody>
              {data.map((b) => (
                <tr key={b.id}>
                  <td className="font-medium">{b.name}</td><td className="font-mono text-xs">{b.gstin ?? "—"}</td>
                  <td>{b.owner}<div className="text-xs text-gray-500">{b.owner_email}</div></td>
                  <td className="num">{b.members}</td><td className="num">{b.backups}</td>
                  <td>
                    <select className="rounded border border-gray-300 px-1.5 py-1 text-xs" value={b.excel_backup === null ? "" : b.excel_backup ? "on" : "off"}
                      onChange={(e) => setExcel(b, e.target.value)} title="Excel backups (.zip) for this business">
                      <option value="">Default ({excelDefault?.default ? "on" : "off"})</option>
                      <option value="on">On</option>
                      <option value="off">Off</option>
                    </select>
                    <span className={`ml-1.5 text-xs ${b.excel_backup_on ? "text-emerald-700" : "text-gray-400"}`}>{b.excel_backup_on ? "●" : "○"}</span>
                  </td>
                  <td className="text-xs">{new Date(b.created_at).toLocaleDateString("en-IN")}</td>
                  <td className="text-right"><Button variant="secondary" className="!py-1" onClick={() => { setTransfer(b); setEmail(""); setErr(null); }}><ArrowRightLeft size={14} /> Transfer</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {transfer && (
        <Modal title={`Transfer ${transfer.name}`} onClose={() => setTransfer(null)}>
          <div className="space-y-3 text-sm">
            <p className="text-gray-600">The new owner takes over the business and its plan limits apply. The current owner ({transfer.owner_email}) stays as a business admin.</p>
            <Field label="New owner e-mail (must be registered)"><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            <ErrorBox message={err} />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setTransfer(null)}>Cancel</Button>
              <Button disabled={!email} onClick={async () => {
                try { await api(`/admin/businesses/${transfer.id}/transfer`, { body: { new_owner_email: email } }); setTransfer(null); reload(); }
                catch (e) { setErr((e as Error).message); }
              }}>Transfer</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
