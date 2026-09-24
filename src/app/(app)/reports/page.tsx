"use client";

import { BookOpen, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Card, Input, Loading } from "@/components/ui";
import { useFetch } from "@/lib/useFetch";
import type { ReportMeta } from "@/lib/types";

export default function ReportsIndex() {
  const { data } = useFetch<ReportMeta[]>("/reports/catalog");
  const [q, setQ] = useState("");
  if (!data) return <Loading />;

  const needle = q.trim().toLowerCase();
  const list = needle ? data.filter((r) => `${r.title} ${r.description} ${r.category}`.toLowerCase().includes(needle)) : data;
  const categories = [...new Set(list.map((r) => r.category))];
  const extra = !needle || "outstanding receivables payables".includes(needle);

  return (
    <>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Reports</h1>
          <p className="mt-0.5 text-sm text-gray-500">{data.length} reports in {new Set(data.map((r) => r.category)).size} categories</p>
        </div>
        <div className="relative w-full max-w-xs">
          <Search size={16} className="pointer-events-none absolute top-2.5 left-3 text-gray-400" />
          <Input placeholder="Search reports" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
        </div>
      </div>
      <div className="columns-1 gap-5 md:columns-2 xl:columns-3">
        {categories.map((cat) => (
          <Card key={cat} className="mb-5 break-inside-avoid p-4">
            <h2 className="mb-2 text-xs font-semibold tracking-wider text-gray-500 uppercase">{cat} reports</h2>
            <ul className="-mx-2">
              {list.filter((r) => r.category === cat).map((r) => (
                <li key={r.slug}>
                  <Link href={r.href ?? `/reports/r/${r.slug}`} className="block rounded-lg px-2 py-1.5 hover:bg-brand-50">
                    <span className="text-sm font-medium text-gray-900">{r.title}</span>
                    <span className="block text-xs text-gray-500">{r.description}</span>
                  </Link>
                </li>
              ))}
              {cat === "Party" && extra && (
                <li>
                  <Link href="/reports/outstanding" className="block rounded-lg px-2 py-1.5 hover:bg-brand-50">
                    <span className="text-sm font-medium text-gray-900">Outstanding</span>
                    <span className="block text-xs text-gray-500">Receivables and payables by party</span>
                  </Link>
                </li>
              )}
            </ul>
          </Card>
        ))}
      </div>
      <p className="mt-2 flex items-start gap-2 text-xs text-gray-500">
        <BookOpen size={14} className="mt-0.5 shrink-0" />
        Reports are prepared from the documents recorded here. Review GST and tax reports with your tax consultant before filing.
      </p>
    </>
  );
}
