"use client";

import {
  BadgeCheck,
  BarChart3,
  Boxes,
  FileBadge,
  Landmark,
  ReceiptIndianRupee,
  ScanLine,
  ShieldCheck,
  Smartphone,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BrandLogo } from "@/components/BrandLogo";
import { type PlanOut, PlanCards } from "@/components/PlanCards";
import { Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useConfig } from "@/lib/config";
import { useFetch } from "@/lib/useFetch";

/*
 * Wording note: describe what the software helps with, never promise outcomes. Avoid "100% compliant",
 * "guaranteed", "error-free", "certified", "government approved" or "files your returns".
 */
const FEATURES = [
  { icon: ReceiptIndianRupee, title: "GST-ready invoices", text: "Tax invoices and bills of supply with CGST / SGST / IGST worked out from place of supply, HSN/SAC codes, UPI QR and easy sharing." },
  { icon: FileBadge, title: "e-Invoice & e-Way bill support", text: "Prepare e-invoice and e-way bill data in the government JSON format, with transport details on the bill. Direct generation where a GSP connection is set up." },
  { icon: BarChart3, title: "Return-ready reports", text: "GSTR-1 and GSTR-3B summaries and JSON files prepared from your entries for review before upload, plus GSTR-2B matching for purchases." },
  { icon: Boxes, title: "Stock, godowns & batches", text: "Multiple godowns, stock transfers, batch / expiry and serial numbers, low-stock alerts and barcode labels." },
  { icon: Landmark, title: "Cash, bank & books", text: "Cash and bank accounts, cheques, loans and expenses, with profit & loss and balance sheet built on double-entry principles." },
  { icon: ScanLine, title: "Quick counter billing", text: "Scan barcodes, bill at the counter and print 80 mm / 58 mm thermal receipts." },
  { icon: BadgeCheck, title: "GSTIN lookup & HSN directory", text: "Verify a party's GSTIN and fill their details in one click, and pick HSN / SAC codes from a searchable directory." },
  { icon: Users, title: "Role-based staff access", text: "Billing operators, inventory staff, managers and your CA — each with the access you choose." },
  { icon: ShieldCheck, title: "Audit trail & backups", text: "Changes are logged, backups run automatically, and you can export your data or send it to Tally at any time." },
  { icon: Smartphone, title: "Works on any device", text: "Use it in the browser or install it on your phone or computer like an app." },
];

export default function Landing() {
  const { me, loading, business } = useAuth();
  const router = useRouter();
  const config = useConfig();
  const { data } = useFetch<{ plans: PlanOut[]; trial_days: number }>("/billing/plans");
  const [cycle, setCycle] = useState<"MONTHLY" | "YEARLY">("YEARLY");
  const name = config.brand?.app_name || "SmartHisab";

  useEffect(() => {
    if (!loading && me) {
      router.replace(business ? "/dashboard" : me.platform_role === "SUPERADMIN" ? "/admin" : me.platform_role === "RESELLER" ? "/reseller" : "/onboarding");
    }
  }, [me, loading, business, router]);

  if (loading || me) return <Loading />;

  return (
    <div className="bg-white">
      <header className="sticky top-0 z-20 border-b border-gray-100 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <BrandLogo />
          <nav className="flex items-center gap-2 text-sm">
            <a href="#features" className="hidden px-3 py-2 text-gray-700 hover:text-gray-900 sm:block">Features</a>
            <a href="#pricing" className="hidden px-3 py-2 text-gray-700 hover:text-gray-900 sm:block">Pricing</a>
            <Link href="/login" className="px-3 py-2 text-gray-700 hover:text-gray-900">Sign in</Link>
            <Link href="/register" className="rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700">Start free</Link>
          </nav>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-4 pt-16 pb-12 text-center sm:pt-24">
        <p className="mx-auto mb-4 inline-block rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
          Designed around Indian GST requirements
        </p>
        <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          Your business ka hisab — <span className="text-brand-600">smart</span>, simple and in one place
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-gray-600">
          {name} helps you create GST-ready invoices, keep stock and money in order, and prepare return data for review —
          for small and medium businesses, GST-registered or not.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/register" className="rounded-lg bg-brand-600 px-6 py-3 text-base font-medium text-white hover:bg-brand-700">
            Start {data?.trial_days ?? 14}-day free trial
          </Link>
          <a href="#pricing" className="rounded-lg border border-gray-300 px-6 py-3 text-base font-medium text-gray-800 hover:bg-gray-50">See pricing</a>
        </div>
        <p className="mt-3 text-sm text-gray-500">No card needed to start · Free plan available for small shops</p>
      </section>

      <section id="features" className="border-t border-gray-100 bg-gray-50 py-16">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="mb-2 text-center text-3xl font-bold text-gray-900">Everything for day-to-day hisab</h2>
          <p className="mx-auto mb-10 max-w-2xl text-center text-gray-600">Billing, inventory, accounts and GST reports that work together, so your numbers stay consistent.</p>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="rounded-xl border border-gray-200 bg-white p-5">
                <Icon className="text-brand-600" size={22} aria-hidden />
                <h3 className="mt-3 font-semibold text-gray-900">{title}</h3>
                <p className="mt-1 text-sm text-gray-600">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-6xl px-4 py-16">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-3xl font-bold text-gray-900">Simple pricing</h2>
            <p className="mt-1 text-gray-600">One plan covers all your businesses. Upgrade or downgrade any time. Prices exclude GST.</p>
          </div>
          <div className="inline-flex rounded-lg border border-gray-200 p-0.5 text-sm">
            {(["MONTHLY", "YEARLY"] as const).map((c) => (
              <button key={c} onClick={() => setCycle(c)} className={`rounded-md px-4 py-1.5 ${cycle === c ? "bg-brand-600 text-white" : "text-gray-700"}`}>
                {c === "MONTHLY" ? "Monthly" : "Yearly"}
              </button>
            ))}
          </div>
        </div>
        {data ? (
          <PlanCards plans={data.plans} cycle={cycle} cta={(p) => (
            <Link href="/register" className={`block w-full rounded-lg py-2 text-center text-sm font-medium ${p.code === "PROFESSIONAL" ? "bg-brand-600 text-white hover:bg-brand-700" : "border border-gray-300 text-gray-800 hover:bg-gray-50"}`}>
              {p.code === "FREE" ? "Start free" : "Start free trial"}
            </Link>
          )} />
        ) : <Loading />}
      </section>

      <footer className="border-t border-gray-100 bg-gray-50 py-10 text-sm text-gray-500">
        <div className="mx-auto max-w-6xl px-4">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div className="max-w-sm">
              <BrandLogo size="sm" />
              <p className="mt-2 text-xs">{config.brand?.tagline}</p>
            </div>
            <nav className="flex flex-wrap gap-5">
              <Link href="/terms" className="hover:underline">Terms</Link>
              <Link href="/privacy" className="hover:underline">Privacy</Link>
              <Link href="/refund" className="hover:underline">Refunds</Link>
              <Link href="/disclaimer" className="hover:underline">Disclaimer</Link>
              <Link href="/contact" className="hover:underline">Contact</Link>
            </nav>
          </div>
          <p className="mt-6 text-xs leading-relaxed text-gray-400">
            {name} is a software tool that helps businesses record transactions and prepare GST-related documents and reports from the data they enter.
            It does not provide tax, legal or accounting advice, and it does not file returns on your behalf. Please review all documents and returns
            — ideally with a qualified professional — before issuing or filing them. {name} is independent software and is not affiliated with,
            endorsed or certified by GSTN, CBIC or any Government authority. GSTIN and HSN/SAC information is sourced from third parties and public
            records and may not always be current.
          </p>
          <p className="mt-3 text-xs">© {new Date().getFullYear()} {config.company.name}. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
