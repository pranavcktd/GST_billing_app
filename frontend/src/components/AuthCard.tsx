"use client";

import { BadgeCheck, Boxes, LockKeyhole, ReceiptIndianRupee, WifiOff } from "lucide-react";
import Link from "next/link";
import { BrandLogo } from "@/components/BrandLogo";
import { useConfig } from "@/lib/config";

const POINTS: [React.ElementType, string, string][] = [
  [ReceiptIndianRupee, "GST bills in seconds", "Tax split, e-invoice and e-way bill done for you"],
  [Boxes, "Stock, money and staff together", "One entry updates stock, books and returns"],
  [WifiOff, "Keeps working offline", "Bill even when the internet drops"],
  [LockKeyhole, "Your data stays yours", "Encrypted, backed up, every change logged"],
];

/** Frame for sign-in, sign-up and password pages: a warm welcome panel beside the form (stacked on phones). */
export function AuthCard({ title, sub, notice, children }: { title: string; sub: string; notice?: React.ReactNode; children: React.ReactNode }) {
  const brand = useConfig().brand;
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#fbf3ea] via-[#fbf8f4] to-[#f6ece2] lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-[#d98a4a] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div aria-hidden className="pointer-events-none absolute -top-24 -right-24 h-80 w-80 rounded-full bg-white/10 blur-2xl" />
        <div aria-hidden className="pointer-events-none absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-amber-200/20 blur-3xl" />
        <Link href="/" className="relative inline-flex w-fit rounded-xl bg-white/95 px-3 py-2 shadow-sm"><BrandLogo size="md" /></Link>
        <div className="relative max-w-md">
          <h2 className="text-3xl leading-tight font-bold">Run your business,<br /><span className="text-amber-100">not the paperwork.</span></h2>
          <p className="mt-3 text-[15px] text-white/85">{brand?.tagline}</p>
          <ul className="mt-8 space-y-4">
            {POINTS.map(([Icon, head, text]) => (
              <li key={head} className="flex gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/15"><Icon size={18} /></span>
                <span><span className="block font-semibold">{head}</span><span className="text-sm text-white/80">{text}</span></span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative flex items-center gap-1.5 text-xs text-white/75"><BadgeCheck size={14} /> Made in India for Indian businesses · {brand?.by_line}</p>
      </aside>

      <main className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-[26rem]">
          <Link href="/" className="mb-6 inline-block lg:hidden"><BrandLogo size="lg" /></Link>
          {notice}
          <div className="rounded-3xl border border-[#eadfd3] bg-white/90 p-6 shadow-[0_10px_40px_-12px_rgba(120,70,40,0.18)] backdrop-blur sm:p-8">
            <h1 className="text-2xl font-bold tracking-tight text-gray-900">{title}</h1>
            <p className="mt-1 mb-6 text-sm text-gray-500">{sub}</p>
            {children}
          </div>
          <p className="mt-6 text-center text-xs text-gray-500">
            <Link href="/terms" className="hover:underline">Terms</Link> · <Link href="/privacy" className="hover:underline">Privacy</Link> · <Link href="/contact" className="hover:underline">Help</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
