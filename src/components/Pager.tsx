"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

const SIZES = [25, 50, 100, 250];

/**
 * Client-side paging for long tables. Returns the rows of the current page and a pager bar.
 * The page resets when the data changes (new filters). Exports should use the full list, not `rows`.
 */
export function usePaged<T>(all: T[] | null | undefined, initialSize = 50) {
  const list = all ?? [];
  const [size, setSize] = useState(initialSize);
  const [state, setState] = useState<{ page: number; of: T[] | null | undefined }>({ page: 0, of: all });
  const page = state.of === all ? state.page : 0; // new data → first page
  const pages = Math.max(1, Math.ceil(list.length / size));
  const current = Math.min(page, pages - 1);
  const rows = list.length > size ? list.slice(current * size, current * size + size) : list;
  const go = (p: number) => setState({ page: Math.max(0, Math.min(pages - 1, p)), of: all });

  const pager = list.length > SIZES[0] ? (
    <div className="no-print flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 px-4 py-2.5 text-sm text-gray-600">
      <span>
        {(current * size + 1).toLocaleString("en-IN")}–{Math.min(list.length, (current + 1) * size).toLocaleString("en-IN")} of {list.length.toLocaleString("en-IN")}
      </span>
      <div className="flex items-center gap-2">
        <select className="rounded-md border border-gray-200 bg-white px-1.5 py-1 text-xs" value={size}
          onChange={(e) => { setSize(Number(e.target.value)); go(0); }} aria-label="Rows per page">
          {SIZES.map((s) => <option key={s} value={s}>{s} / page</option>)}
        </select>
        <button className="rounded-md border border-gray-200 p-1 disabled:opacity-40" disabled={current === 0} onClick={() => go(current - 1)} aria-label="Previous page"><ChevronLeft size={16} /></button>
        <span className="tabular-nums">{current + 1} / {pages}</span>
        <button className="rounded-md border border-gray-200 p-1 disabled:opacity-40" disabled={current >= pages - 1} onClick={() => go(current + 1)} aria-label="Next page"><ChevronRight size={16} /></button>
      </div>
    </div>
  ) : null;

  return { rows, pager, offset: current * size };
}
