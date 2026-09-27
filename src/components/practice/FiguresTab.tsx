"use client";

import { Download, FileSpreadsheet, ListPlus, Plus, Store, Trash2, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { Modal } from "@/components/Modal";
import { usePaged } from "@/components/Pager";
import { Button, Card, ErrorBox, Field, Input, Select } from "@/components/ui";
import { api, downloadFile } from "@/lib/api";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import { type FileData, type Head, type Ledger, type PFile, toNum } from "./types";

const SECTIONS = ["P&L", "Capital", "Liabilities", "Assets", "Check"];
const PARTNER_HEADS = new Set(["CAPITAL", "DRAWINGS", "PARTNER_INTEREST", "PARTNER_REMUNERATION"]);
const GUIDED = ["REVENUE", "OTHER_INCOME", "OPENING_STOCK", "PURCHASES", "DIRECT_EXP", "EMPLOYEE", "FINANCE", "OTHER_EXP",
  "CAPITAL", "DRAWINGS", "LT_SECURED", "LT_UNSECURED", "ST_BORROWINGS", "TRADE_PAYABLES", "OTHER_CUR_LIAB",
  "FIXED_ASSETS", "TRADE_RECEIVABLES", "CASH_BANK", "ST_LOANS_ADV"];
const rid = () => Math.random().toString(36).slice(2, 14);

/** Signed amount (debit +, credit −) edited as two columns. */
function DrCr({ value, onChange, disabled }: { value: string; onChange: (v: string) => void; disabled?: boolean }) {
  const n = toNum(value);
  const cell = "input !w-28 !py-1 text-right tabular-nums";
  return (
    <>
      <td><input className={cell} inputMode="decimal" disabled={disabled} value={n > 0 ? String(n) : ""} placeholder="—"
        onChange={(e) => onChange(e.target.value === "" ? "0" : String(Math.abs(toNum(e.target.value))))} /></td>
      <td><input className={cell} inputMode="decimal" disabled={disabled} value={n < 0 ? String(-n) : ""} placeholder="—"
        onChange={(e) => onChange(e.target.value === "" ? "0" : String(-Math.abs(toNum(e.target.value))))} /></td>
    </>
  );
}

export function FiguresTab({ file, data, setData, heads, locked, onReplaced }: {
  file: PFile; data: FileData; setData: (d: FileData) => void; heads: Head[]; locked: boolean; onReplaced: (f: PFile) => void;
}) {
  const [filter, setFilter] = useState<"" | "unmapped">("");
  const [search, setSearch] = useState("");
  const [importing, setImporting] = useState(false);
  const [books, setBooks] = useState(false);
  const partnership = data.entity_type === "PARTNERSHIP";
  const headMap = useMemo(() => Object.fromEntries(heads.map((h) => [h.code, h])), [heads]);

  const ledgers = data.ledgers;
  const shown = ledgers.filter((l) => (!filter || !l.head) && (!search || l.name.toLowerCase().includes(search.toLowerCase())));
  const { rows, pager } = usePaged(shown, 100);
  const tot = (k: "cy" | "py") => {
    let dr = 0, cr = 0;
    for (const l of ledgers) { const n = toNum(l[k]); if (n > 0) dr += n; else cr -= n; }
    return { dr, cr, diff: Math.round((dr - cr) * 100) / 100 };
  };
  const t = tot("cy"), tp = tot("py");
  const unmapped = ledgers.filter((l) => !l.head && (toNum(l.cy) || toNum(l.py))).length;

  const update = (id: string, patch: Partial<Ledger>) => setData({ ...data, ledgers: ledgers.map((l) => (l.id === id ? { ...l, ...patch } : l)) });
  const add = (items: Partial<Ledger>[]) => setData({ ...data, ledgers: [...ledgers, ...items.map((x) => ({ id: rid(), name: "", group: null, head: null, partner: null, cy: "0", py: "0", ...x }))] });

  function guided() {
    const have = new Set(ledgers.map((l) => l.head));
    add(GUIDED.filter((h) => !have.has(h) && headMap[h]).map((h) => ({ name: headMap[h].label.replace(/ \(.*\)$/, ""), head: h })));
  }

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-2 p-4">
        <span className="mr-2 text-sm text-gray-600">Bring in the year&apos;s figures:</span>
        <Button variant="secondary" disabled={locked} onClick={() => setImporting(true)}><Upload size={15} /> Import trial balance</Button>
        <Button variant="secondary" disabled={locked} onClick={() => setBooks(true)}><Store size={15} /> From SmartHisab books</Button>
        <Button variant="secondary" disabled={locked} onClick={guided} title="Adds one line for each common head — type the annual totals"><ListPlus size={15} /> Guided entry</Button>
        <Button variant="ghost" disabled={locked} onClick={() => add([{}])}><Plus size={15} /> Add ledger</Button>
        <div className="flex-1" />
        <Button variant="ghost" onClick={() => downloadFile("/practice/tb-template").catch((e) => alert(e.message))}><Download size={15} /> TB template</Button>
      </Card>

      <div className="grid gap-3 sm:grid-cols-4">
        <Card className="p-4"><div className="text-xs text-gray-500">Ledgers</div><div className="text-xl font-semibold">{ledgers.length}</div></Card>
        <Card className="p-4"><div className="text-xs text-gray-500">Not classified</div><div className={`text-xl font-semibold ${unmapped ? "text-red-700" : ""}`}>{unmapped}</div></Card>
        <Card className="p-4"><div className="text-xs text-gray-500">This year: debit / credit</div><div className="text-sm font-semibold tabular-nums">{money(t.dr)} / {money(t.cr)}</div></Card>
        <Card className="p-4"><div className="text-xs text-gray-500">Difference</div><div className={`text-xl font-semibold ${t.diff ? "text-red-700" : "text-emerald-700"}`}>{t.diff ? money(t.diff) : "Tallies ✓"}</div></Card>
      </div>

      <Card className="grid gap-3 p-4 sm:grid-cols-3">
        <Field label="Closing stock — this year" hint="Value of goods on hand at 31 March (not a ledger balance)">
          <Input inputMode="decimal" disabled={locked} value={data.closing_stock.cy === "0" ? "" : data.closing_stock.cy}
            onChange={(e) => setData({ ...data, closing_stock: { ...data.closing_stock, cy: e.target.value || "0" } })} />
        </Field>
        <Field label="Closing stock — previous year">
          <Input inputMode="decimal" disabled={locked} value={data.closing_stock.py === "0" ? "" : data.closing_stock.py}
            onChange={(e) => setData({ ...data, closing_stock: { ...data.closing_stock, py: e.target.value || "0" } })} />
        </Field>
        <div className="flex items-end gap-2">
          <Input placeholder="Search ledger" value={search} onChange={(e) => setSearch(e.target.value)} />
          <label className="flex shrink-0 items-center gap-1.5 text-sm"><input type="checkbox" checked={filter === "unmapped"} onChange={(e) => setFilter(e.target.checked ? "unmapped" : "")} /> Unclassified only</label>
        </div>
      </Card>

      <Card className="overflow-x-auto">
        {!ledgers.length ? (
          <p className="p-6 text-center text-sm text-gray-500">No figures yet — import a trial balance, pull from SmartHisab books, or use Guided entry.</p>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>Ledger</th><th>Classification</th>{partnership && <th>Partner</th>}
                <th className="num">This year Dr</th><th className="num">This year Cr</th>
                <th className="num">Prev. year Dr</th><th className="num">Prev. year Cr</th><th />
              </tr>
            </thead>
            <tbody>
              {rows.map((l) => (
                <tr key={l.id} className={!l.head && (toNum(l.cy) || toNum(l.py)) ? "bg-red-50/60" : ""}>
                  <td className="min-w-48">
                    <input className="input !py-1" disabled={locked} value={l.name} onChange={(e) => update(l.id, { name: e.target.value })} placeholder="Ledger name" />
                    {l.group && <div className="mt-0.5 text-[10px] text-gray-400">{l.group}</div>}
                  </td>
                  <td className="min-w-56">
                    <select className="input !py-1 text-sm" disabled={locked} value={l.head ?? ""} title={l.head ? headMap[l.head]?.help : "Choose where this ledger goes"}
                      onChange={(e) => update(l.id, { head: e.target.value || null })}>
                      <option value="">— choose —</option>
                      {SECTIONS.map((s) => (
                        <optgroup key={s} label={s === "P&L" ? "Profit & loss" : s}>
                          {heads.filter((h) => h.section === s).map((h) => <option key={h.code} value={h.code}>{h.label}</option>)}
                        </optgroup>
                      ))}
                    </select>
                  </td>
                  {partnership && (
                    <td>
                      {l.head && PARTNER_HEADS.has(l.head) ? (
                        <select className="input !w-32 !py-1 text-sm" disabled={locked} value={l.partner ?? ""} onChange={(e) => update(l.id, { partner: e.target.value || null })}>
                          <option value="">—</option>
                          {data.partners.map((p) => <option key={p.id} value={p.id}>{p.name || "(unnamed)"}</option>)}
                        </select>
                      ) : null}
                    </td>
                  )}
                  <DrCr value={l.cy} disabled={locked} onChange={(v) => update(l.id, { cy: v })} />
                  <DrCr value={l.py} disabled={locked} onChange={(v) => update(l.id, { py: v })} />
                  <td>{!locked && <button className="text-gray-400 hover:text-red-600" aria-label="Remove" onClick={() => setData({ ...data, ledgers: ledgers.filter((x) => x.id !== l.id) })}><Trash2 size={15} /></button>}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={partnership ? 3 : 2}>Total {t.diff ? <span className="ml-2 text-red-700">difference {money(t.diff)}</span> : <span className="ml-2 text-emerald-700">tallies</span>}</td>
                <td className="num">{money(t.dr)}</td><td className="num">{money(t.cr)}</td>
                <td className="num">{money(tp.dr)}</td><td className="num">{money(tp.cr)}</td><td />
              </tr>
            </tfoot>
          </table>
        )}
        {pager}
      </Card>

      {importing && <ImportTb fileId={file.id} onClose={() => setImporting(false)} onDone={(f) => { setImporting(false); onReplaced(f); }} />}
      {books && <FromBooks fileId={file.id} onClose={() => setBooks(false)} onDone={(f) => { setBooks(false); onReplaced(f); }} />}
    </div>
  );
}

function ImportTb({ fileId, onClose, onDone }: { fileId: string; onClose: () => void; onDone: (f: PFile) => void }) {
  const [mode, setMode] = useState<"replace" | "merge">("replace");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ file: PFile; imported: number; unmapped: number; warnings: string[] } | null>(null);

  async function upload(f: File) {
    setBusy(true); setErr(null);
    const form = new FormData();
    form.append("file", f);
    try {
      setResult(await api(`/practice/files/${fileId}/import-tb?mode=${mode}`, { form }));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal title="Import trial balance" onClose={onClose}>
      <div className="space-y-3 text-sm">
        <p className="text-gray-600">Excel or CSV with one row per ledger: <b>Ledger, Group (optional), Debit, Credit</b>, plus previous-year columns if you have them.
          A Tally trial balance exported to Excel works as it is. Ledgers are classified automatically from their group and name, and your choices are remembered for next year.</p>
        <Field label="If figures already exist">
          <Select value={mode} onChange={(e) => setMode(e.target.value as "replace" | "merge")}>
            <option value="replace">Replace all ledgers</option>
            <option value="merge">Update matching ledgers, add new ones</option>
          </Select>
        </Field>
        {!result && (
          <label className="flex cursor-pointer items-center gap-3 rounded-lg border-2 border-dashed border-gray-300 p-4 hover:border-brand-400">
            <FileSpreadsheet size={20} className="text-gray-400" /> {busy ? "Reading…" : "Choose the trial balance file…"}
            <input type="file" accept=".xlsx,.csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} />
          </label>
        )}
        <ErrorBox message={err} />
        {result && (
          <>
            <div className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-900">
              Imported {result.imported} ledgers.{result.unmapped ? ` ${result.unmapped} need a classification (highlighted in red).` : " All classified."}
            </div>
            {result.warnings.map((w) => <div key={w} className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">{w}</div>)}
            <div className="flex justify-end"><Button onClick={() => onDone(result.file)}>Continue</Button></div>
          </>
        )}
      </div>
    </Modal>
  );
}

function FromBooks({ fileId, onClose, onDone }: { fileId: string; onClose: () => void; onDone: (f: PFile) => void }) {
  const { data } = useFetch<{ id: string; name: string; gstin: string | null; role: string }[]>("/practice/linkable-businesses");
  const [bid, setBid] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function run() {
    setErr(null);
    try { onDone((await api<{ file: PFile }>(`/practice/files/${fileId}/import-books`, { body: { business_id: bid } })).file); }
    catch (e) { setErr((e as Error).message); }
  }
  return (
    <Modal title="Pull figures from SmartHisab books" onClose={onClose}>
      <div className="space-y-3 text-sm">
        <p className="text-gray-600">Uses the client&apos;s sales, purchases, expenses, stock, bank, parties and loans kept in SmartHisab for this year and the previous year.
          The client must add you as a staff member (CA / Auditor role) of their business first.</p>
        {data && !data.length && <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">You are not a member of any business yet.</p>}
        <Field label="Business">
          <Select value={bid} onChange={(e) => setBid(e.target.value)}>
            <option value="">Select…</option>
            {(data ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}{b.gstin ? ` · ${b.gstin}` : ""}</option>)}
          </Select>
        </Field>
        <ErrorBox message={err} />
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!bid} onClick={run}>Pull figures</Button></div>
      </div>
    </Modal>
  );
}
