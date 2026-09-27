"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button, Card, Field, Input, Select } from "@/components/ui";
import { useConfig } from "@/lib/config";
import type { Asset, FileData, Partner } from "./types";

const cell = "input !py-1";

/** Depreciation schedule: Income-tax Act blocks or Companies Act useful life. */
export function AssetsTab({ data, setData, locked }: { data: FileData; setData: (d: FileData) => void; locked: boolean }) {
  const rates = useConfig().it_depreciation_rates ?? {};
  const dep = data.depreciation;
  const it = dep.method === "IT";
  const setDep = (patch: Partial<FileData["depreciation"]>) => setData({ ...data, depreciation: { ...dep, ...patch } });
  const upd = (i: number, patch: Partial<Asset>) => setDep({ assets: dep.assets.map((a, j) => (j === i ? { ...a, ...patch } : a)) });
  const inp = (i: number, k: keyof Asset, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <input className={cell} disabled={locked} value={(dep.assets[i][k] as string) ?? ""} onChange={(e) => upd(i, { [k]: e.target.value })} {...props} />
  );

  return (
    <div className="space-y-4">
      <Card className="grid gap-3 p-4 sm:grid-cols-3">
        <Field label="Depreciation method for these accounts">
          <Select value={dep.method} disabled={locked} onChange={(e) => setDep({ method: e.target.value as "IT" | "CA" })}>
            <option value="IT">Income-tax Act rates — block of assets, WDV (usual for proprietors &amp; firms)</option>
            <option value="CA">Companies Act — useful life, SLM or WDV</option>
          </Select>
        </Field>
        <Field label="Previous year's depreciation" hint="For the comparative column (carried forward automatically)">
          <Input inputMode="decimal" disabled={locked} value={dep.py_amount === "0" ? "" : dep.py_amount} onChange={(e) => setDep({ py_amount: e.target.value || "0" })} />
        </Field>
        <p className="text-xs text-gray-500 sm:pt-6">
          {it ? "Half the rate applies to additions put to use for less than 180 days in the year (date put to use on or after 3 October). Rates come from Admin → GST config."
            : "Depreciation runs from the date put to use, day by day, down to a residual value set in Admin → GST config (5% by default)."}
        </p>
      </Card>
      <Card className="overflow-x-auto">
        <table className="tbl">
          <thead>
            {it ? (
              <tr><th>Asset</th><th>Block (rate)</th><th className="num">Opening WDV</th><th className="num">Addition</th><th>Put to use on</th><th className="num">Sale value</th><th /></tr>
            ) : (
              <tr><th>Asset</th><th className="num">Cost (opening)</th><th className="num">Acc. dep. (opening)</th><th>Put to use</th><th className="num">Life (yrs)</th><th>Method</th><th className="num">Addition</th><th>Addition date</th><th className="num">Sale value</th><th /></tr>
            )}
          </thead>
          <tbody>
            {dep.assets.map((a, i) => (
              <tr key={i}>
                <td className="min-w-40">{inp(i, "description", { placeholder: "e.g. Office furniture" })}</td>
                {it ? (
                  <>
                    <td className="min-w-56">
                      <select className={cell} disabled={locked} value={a.block ?? ""} onChange={(e) => upd(i, { block: e.target.value })}>
                        <option value="">Choose block…</option>
                        {Object.entries(rates).map(([b, r]) => <option key={b} value={b}>{b} — {r}%</option>)}
                      </select>
                    </td>
                    <td>{inp(i, "opening", { inputMode: "decimal", className: `${cell} !w-28 text-right` })}</td>
                    <td>{inp(i, "addition", { inputMode: "decimal", className: `${cell} !w-28 text-right` })}</td>
                    <td>{inp(i, "addition_date", { type: "date" })}</td>
                    <td>{inp(i, "sale", { inputMode: "decimal", className: `${cell} !w-28 text-right` })}</td>
                  </>
                ) : (
                  <>
                    <td>{inp(i, "cost", { inputMode: "decimal", className: `${cell} !w-28 text-right` })}</td>
                    <td>{inp(i, "opening_acc_dep", { inputMode: "decimal", className: `${cell} !w-28 text-right` })}</td>
                    <td>{inp(i, "put_to_use", { type: "date" })}</td>
                    <td>{inp(i, "life", { inputMode: "numeric", className: `${cell} !w-16 text-right` })}</td>
                    <td>
                      <select className={cell} disabled={locked} value={a.ca_method ?? "SLM"} onChange={(e) => upd(i, { ca_method: e.target.value as "SLM" | "WDV" })}>
                        <option value="SLM">SLM</option><option value="WDV">WDV</option>
                      </select>
                    </td>
                    <td>{inp(i, "addition", { inputMode: "decimal", className: `${cell} !w-28 text-right` })}</td>
                    <td>{inp(i, "addition_date", { type: "date" })}</td>
                    <td>{inp(i, "sale", { inputMode: "decimal", className: `${cell} !w-28 text-right` })}</td>
                  </>
                )}
                <td>{!locked && <button className="text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => setDep({ assets: dep.assets.filter((_, j) => j !== i) })}><Trash2 size={15} /></button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!dep.assets.length && <p className="p-5 text-sm text-gray-500">No assets yet. Add each asset (or one line per block) with its opening written-down value and this year&apos;s additions.</p>}
        {!locked && <div className="border-t border-gray-100 p-3"><Button variant="secondary" onClick={() => setDep({ assets: [...dep.assets, {}] })}><Plus size={15} /> Add asset</Button></div>}
      </Card>
    </div>
  );
}

/** Partners (partnership) — profit share, interest on capital, remuneration as per the deed. */
export function PartnersTab({ data, setData, locked }: { data: FileData; setData: (d: FileData) => void; locked: boolean }) {
  const ps = data.partners;
  const upd = (i: number, patch: Partial<Partner>) => setData({ ...data, partners: ps.map((p, j) => (j === i ? { ...p, ...patch } : p)) });
  const share = ps.reduce((s, p) => s + (Number(p.share) || 0), 0);
  return (
    <Card className="overflow-x-auto">
      <div className="p-4 text-sm text-gray-600">
        Enter the terms of the partnership deed. If interest on capital or remuneration is <b>already booked</b> in the ledgers (classified as such), those
        amounts are used instead of these rates. Assign each partner&apos;s capital and drawings ledgers on the Figures tab.
      </div>
      <table className="tbl">
        <thead><tr><th>Partner</th><th>PAN</th><th className="num">Profit share %</th><th className="num">Interest on capital %</th><th className="num">Remuneration (₹ / year)</th><th /></tr></thead>
        <tbody>
          {ps.map((p, i) => (
            <tr key={p.id}>
              <td><input className={cell} disabled={locked} value={p.name} onChange={(e) => upd(i, { name: e.target.value })} /></td>
              <td><input className={`${cell} !w-32 uppercase`} disabled={locked} maxLength={10} value={p.pan ?? ""} onChange={(e) => upd(i, { pan: e.target.value.toUpperCase() })} /></td>
              <td><input className={`${cell} !w-24 text-right`} disabled={locked} inputMode="decimal" value={p.share} onChange={(e) => upd(i, { share: e.target.value })} /></td>
              <td><input className={`${cell} !w-24 text-right`} disabled={locked} inputMode="decimal" value={p.interest_rate} onChange={(e) => upd(i, { interest_rate: e.target.value })} /></td>
              <td><input className={`${cell} !w-32 text-right`} disabled={locked} inputMode="decimal" value={p.remuneration} onChange={(e) => upd(i, { remuneration: e.target.value })} /></td>
              <td>{!locked && <button className="text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => setData({ ...data, partners: ps.filter((_, j) => j !== i) })}><Trash2 size={15} /></button>}</td>
            </tr>
          ))}
        </tbody>
        {ps.length > 0 && <tfoot><tr><td colSpan={2}>Total share</td><td className={`num ${share !== 100 ? "text-red-700" : ""}`}>{share}%</td><td colSpan={3} /></tr></tfoot>}
      </table>
      {!locked && (
        <div className="border-t border-gray-100 p-3">
          <Button variant="secondary" onClick={() => setData({ ...data, partners: [...ps, { id: Math.random().toString(36).slice(2, 10), name: "", share: "", interest_rate: "0", remuneration: "0" }] })}>
            <Plus size={15} /> Add partner
          </Button>
        </div>
      )}
    </Card>
  );
}
