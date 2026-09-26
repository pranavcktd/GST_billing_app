"use client";

import {
  ArrowRight, BarChart3, Box, CornerDownLeft, FileText, Lock, Plus, Search, Settings, Users, Wallet, Wrench, X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, qs } from "@/lib/api";
import { useAuth, usePerms } from "@/lib/auth";
import { kindOf } from "@/lib/constants";
import { fmtDate, money } from "@/lib/format";
import { ENTRIES, type Group, score } from "@/lib/searchIndex";
import type { ReportMeta, VoucherType } from "@/lib/types";

interface Found {
  parties: { id: string; name: string; gstin: string | null; phone: string | null; type: string }[];
  items: { id: string; name: string; code: string | null; hsn: string | null; type: string }[];
  documents: { id: string; type: VoucherType; number: string; date: string; party_name: string; total: number; cancelled: boolean }[];
  payments: { id: string; type: "IN" | "OUT"; number: string; date: string; party_name: string | null; amount: number }[];
}
interface Hit { key: string; section: string; title: string; sub?: string; href: string; icon: React.ElementType; locked?: boolean }

const GROUP_ICON: Record<Group, React.ElementType> = {
  Create: Plus, "Go to": ArrowRight, GST: FileText, Settings, Utilities: Wrench, Account: Settings,
};
const DOC_LABEL: Partial<Record<VoucherType, string>> = {
  SALE: "Sale invoice", SALE_RETURN: "Credit note", PURCHASE: "Purchase bill", PURCHASE_RETURN: "Debit note",
  ESTIMATE: "Estimate", SALE_ORDER: "Sale order", PURCHASE_ORDER: "Purchase order", DELIVERY_CHALLAN: "Delivery challan", EXPENSE: "Expense",
};
const RECENT_KEY = "search-recent";
const SUGGEST = ["New sale invoice", "Add party", "Add item / product", "Receive payment (payment in)", "GSTR-1 (with portal JSON)", "Items & stock"];

function readRecent(): Hit[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]"); } catch { return []; }
}

/** Top-bar search: pages & actions, reports, and the business's parties / items / documents / payments. Ctrl + K. */
export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(true); }
      else if (e.key === "/" && !/input|textarea|select/i.test((e.target as HTMLElement)?.tagName ?? "") && !(e.target as HTMLElement)?.isContentEditable) {
        e.preventDefault(); setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <button onClick={() => setOpen(true)} title="Search anything (Ctrl + K)"
        className="flex h-9 w-full max-w-md items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm text-gray-500 hover:bg-white">
        <Search size={16} />
        <span className="flex-1 truncate text-left">Search or jump to… <span className="hidden lg:inline">party, invoice, report, setting</span></span>
        <kbd className="hidden rounded border border-gray-300 bg-white px-1.5 text-[10px] font-medium text-gray-500 sm:inline">Ctrl K</kbd>
      </button>
      {open && <Palette onClose={() => setOpen(false)} />}
    </>
  );
}

function Palette({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const { me } = useAuth();
  const { can } = usePerms();
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Found | null>(null);
  const [reports, setReports] = useState<ReportMeta[]>([]);
  const [active, setActive] = useState(0);
  const [recent] = useState<Hit[]>(readRecent);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => { api<ReportMeta[]>("/reports/catalog").then(setReports).catch(() => {}); }, []);
  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) return;
    let alive = true;
    const t = setTimeout(() => api<Found>(`/search${qs({ q: term })}`).then((r) => alive && setFound(r)).catch(() => {}), 200);
    return () => { alive = false; clearTimeout(t); };
  }, [q]);

  const hits = useMemo<Hit[]>(() => {
    const term = q.trim();
    const allowed = ENTRIES.filter((e) => (!e.perm || can(...e.perm)) && (!e.platform || me?.platform_role === e.platform || me?.platform_role === "SUPERADMIN"));
    if (!term) {
      const sug = SUGGEST.map((t) => allowed.find((e) => e.title === t)).filter(Boolean)
        .map((e) => ({ key: e!.href, section: "Suggestions", title: e!.title, href: e!.href, icon: GROUP_ICON[e!.group] }));
      return [...recent.slice(0, 5).map((h) => ({ ...h, section: "Recent", icon: ArrowRight })), ...sug];
    }
    const pages = allowed.map((e) => ({ e, s: score(term, e.title, `${e.k ?? ""} ${e.group}`) })).filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s).slice(0, 8)
      .map(({ e }) => ({ key: e.href + e.title, section: e.group === "Create" ? "Create" : "Pages & settings", title: e.title, href: e.href, icon: GROUP_ICON[e.group] }));
    const reps = reports.filter((r) => can(r.module, "view")).map((r) => ({ r, s: score(term, r.title, `${r.description} ${r.category} report`) }))
      .filter((x) => x.s > 0).sort((a, b) => b.s - a.s).slice(0, 6)
      .map(({ r }) => ({ key: "r:" + r.slug, section: "Reports", title: r.title, sub: r.category, href: r.href ?? `/reports/r/${r.slug}`, icon: BarChart3, locked: r.locked }));
    const f = term.length >= 2 ? found : null;
    const data: Hit[] = [
      ...(f?.parties ?? []).map((p) => ({ key: "p:" + p.id, section: "Parties", title: p.name, sub: [p.gstin, p.phone].filter(Boolean).join(" · "), href: `/parties/${p.id}`, icon: Users })),
      ...(f?.documents ?? []).map((d) => ({ key: "d:" + d.id, section: "Documents", title: `${d.number} — ${d.party_name}`,
        sub: `${DOC_LABEL[d.type] ?? d.type} · ${fmtDate(d.date)} · ${money(d.total)}${d.cancelled ? " · cancelled" : ""}`, href: `/v/${kindOf(d.type)}/${d.id}`, icon: FileText })),
      ...(f?.items ?? []).map((i) => ({ key: "i:" + i.id, section: "Items", title: i.name, sub: [i.code, i.hsn && `HSN ${i.hsn}`].filter(Boolean).join(" · "), href: `/items/${i.id}`, icon: Box })),
      ...(f?.payments ?? []).map((p) => ({ key: "y:" + p.id, section: "Payments", title: `${p.number}${p.party_name ? ` — ${p.party_name}` : ""}`,
        sub: `${p.type === "IN" ? "Received" : "Paid"} · ${fmtDate(p.date)} · ${money(p.amount)}`, href: `/payments/${p.type === "IN" ? "in" : "out"}`, icon: Wallet })),
    ];
    // actions first when the query reads like a command ("add party"), records first otherwise
    const commandy = /^(add|new|create|make|receive|pay|go|open)\b/i.test(term) || data.length === 0;
    return commandy ? [...pages, ...data, ...reps] : [...data, ...pages, ...reps];
  }, [q, found, reports, can, me, recent]);

  const current = Math.min(active, Math.max(0, hits.length - 1));

  function go(h: Hit) {
    try {
      const keep = [{ key: h.key, section: "Recent", title: h.title, sub: h.sub, href: h.href }, ...readRecent().filter((r) => r.key !== h.key)].slice(0, 8);
      localStorage.setItem(RECENT_KEY, JSON.stringify(keep));
    } catch { /* storage unavailable */ }
    onClose();
    router.push(h.href);
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive(Math.min(hits.length - 1, current + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive(Math.max(0, current - 1)); }
    else if (e.key === "Enter" && hits[current]) { e.preventDefault(); go(hits[current]); }
    else if (e.key === "Escape") onClose();
  }

  useEffect(() => {
    listRef.current?.querySelector(`[data-i="${current}"]`)?.scrollIntoView({ block: "nearest" });
  }, [current]);

  let lastSection = "";
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 px-3 pt-[10vh]" onMouseDown={onClose}>
      <div className="w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-2xl" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-label="Search">
        <div className="flex items-center gap-2 border-b border-gray-100 px-4">
          <Search size={18} className="text-gray-400" />
          <input autoFocus value={q} onChange={(e) => { setQ(e.target.value); setActive(0); }} onKeyDown={onKey}
            placeholder="Type to search — e.g. add party, gstr, invoice number, customer name, HSN…"
            className="h-12 flex-1 border-0 bg-transparent text-sm outline-none focus:ring-0" />
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700" aria-label="Close"><X size={18} /></button>
        </div>
        <div ref={listRef} className="max-h-[60vh] overflow-y-auto py-2">
          {hits.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-gray-500">{q.trim().length < 2 ? "Start typing…" : `Nothing found for “${q}”.`}</p>
          ) : hits.map((h, i) => {
            const head = h.section !== lastSection ? h.section : null;
            lastSection = h.section;
            const Icon = h.icon;
            return (
              <div key={h.key + i}>
                {head && <div className="px-4 pt-2 pb-1 text-[11px] font-semibold tracking-wider text-gray-400 uppercase">{head}</div>}
                <button data-i={i} onMouseMove={() => setActive(i)} onClick={() => go(h)}
                  className={`flex w-full items-center gap-3 px-4 py-2 text-left text-sm ${i === current ? "bg-brand-50 text-brand-900" : "text-gray-800"}`}>
                  <Icon size={16} className={i === current ? "text-brand-600" : "text-gray-400"} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{h.title}</span>
                    {h.sub && <span className="block truncate text-xs text-gray-500">{h.sub}</span>}
                  </span>
                  {h.locked && <Lock size={13} className="text-amber-600" aria-label="Upgrade needed" />}
                  {i === current && <CornerDownLeft size={14} className="text-gray-400" />}
                </button>
              </div>
            );
          })}
        </div>
        <div className="flex gap-4 border-t border-gray-100 bg-gray-50 px-4 py-2 text-[11px] text-gray-500">
          <span><kbd className="font-sans">↑ ↓</kbd> move</span><span><kbd className="font-sans">Enter</kbd> open</span><span><kbd className="font-sans">Esc</kbd> close</span>
          <span className="ml-auto">Open anytime with Ctrl + K or /</span>
        </div>
      </div>
    </div>
  );
}
