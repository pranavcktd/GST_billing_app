"use client";

import { ArrowRightLeft } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, ErrorBox, Field, Input, Loading } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

interface Biz { id: string; name: string; gstin: string | null; created_at: string; owner: string | null; owner_email: string | null; members: number; backups: number }

/** All businesses (metadata only) with ownership transfer. */
export function AdminBusinesses() {
  const [search, setSearch] = useState("");
  const { data, reload } = useFetch<Biz[]>(`/admin/businesses${qs({ search })}`);
  const [transfer, setTransfer] = useState<Biz | null>(null);
  const [email, setEmail] = useState("");
  const [err, setErr] = useState<string | null>(null);

  return (
    <>
      <Input placeholder="Search business, GSTIN or owner e-mail" value={search} onChange={(e) => setSearch(e.target.value)} className="mb-3 max-w-sm" />
      <ErrorBox message={err} />
      <Card className="overflow-x-auto">
        {!data ? <Loading /> : (
          <table className="tbl">
            <thead><tr><th>Business</th><th>GSTIN</th><th>Owner</th><th className="num">People</th><th className="num">Backups</th><th>Created</th><th /></tr></thead>
            <tbody>
              {data.map((b) => (
                <tr key={b.id}>
                  <td className="font-medium">{b.name}</td><td className="font-mono text-xs">{b.gstin ?? "—"}</td>
                  <td>{b.owner}<div className="text-xs text-gray-500">{b.owner_email}</div></td>
                  <td className="num">{b.members}</td><td className="num">{b.backups}</td>
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
