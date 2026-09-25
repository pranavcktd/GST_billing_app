"use client";

import {
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
import { type PlanOut, PlanCards } from "@/components/PlanCards";
import { Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";

const FEATURES = [
  { icon: ReceiptIndianRupee, title: "GST invoices in seconds", text: "Tax invoices & bills of supply with automatic CGST/SGST/IGST, HSN, UPI QR and WhatsApp sharing." },
  { icon: FileBadge, title: "e-Invoice & e-Way bill", text: "IRN with signed QR and e-way bills — direct or through the portal JSON, with transport details on the bill." },
  { icon: BarChart3, title: "GSTR-1, 3B, 2B & 9", text: "Portal-ready GSTR-1 JSON, 3B summary, GSTR-2B matching to protect your input tax credit." },
  { icon: Boxes, title: "Stock, godowns & batches", text: "Multiple godowns, transfers, batch/expiry & serial numbers, low-stock alerts, barcode labels." },
  { icon: Landmark, title: "Cash, bank & books", text: "Bank & cash accounts, cheques, loans, expenses, P&L and a balance sheet that always tallies." },
  { icon: ScanLine, title: "Fast POS billing", text: "Scan barcodes, bill at the counter, print 80 mm / 58 mm thermal receipts." },
  { icon: Users, title: "Staff with the right access", text: "Billing operators, inventory clerks, managers and your CA — each sees only what they should." },
  { icon: ShieldCheck, title: "Audit trail & backups", text: "Every change is logged. Daily automatic backups, restore any time, export to Tally." },
  { icon: Smartphone, title: "Works on any device", text: "Install it on your phone or PC like an app. Your data is safely in the cloud." },
];

export default function Landing() {
  const { me, loading, business } = useAuth();
  const router = useRouter();
  const { data } = useFetch<{ plans: PlanOut[]; trial_days: number }>("/billing/plans");
  const [cycle, setCycle] = useState<"MONTHLY" | "YEARLY">("YEARLY");

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
          <div className="flex items-center gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/icon.svg" alt="" className="h-8 w-8" />
            <span className="text-lg font-semibold text-gray-900">GST Billing</span>
          </div>
          <nav className="flex items-center gap-2 text-sm">
            <a href="#pricing" className="hidden px-3 py-2 text-gray-700 hover:text-gray-900 sm:block">Pricing</a>
            <Link href="/login" className="px-3 py-2 text-gray-700 hover:text-gray-900">Sign in</Link>
            <Link href="/register" className="rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700">Start free</Link>
          </nav>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-4 pt-16 pb-12 text-center sm:pt-24">
        <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          GST billing, stock & accounts for Indian businesses
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-gray-600">
          Make GST invoices, e-invoices and e-way bills, track stock and money, and file returns with confidence — whether you are GST registered or not.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/register" className="rounded-lg bg-brand-600 px-6 py-3 text-base font-medium text-white hover:bg-brand-700">
            Start {data?.trial_days ?? 14}-day free trial
          </Link>
          <a href="#pricing" className="rounded-lg border border-gray-300 px-6 py-3 text-base font-medium text-gray-800 hover:bg-gray-50">See pricing</a>
        </div>
        <p className="mt-3 text-sm text-gray-500">No card needed · Free plan forever for small shops</p>
      </section>

      <section className="border-t border-gray-100 bg-gray-50 py-16">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="rounded-xl border border-gray-200 bg-white p-5">
              <Icon className="text-brand-600" size={22} aria-hidden />
              <h3 className="mt-3 font-semibold text-gray-900">{title}</h3>
              <p className="mt-1 text-sm text-gray-600">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-6xl px-4 py-16">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-3xl font-bold text-gray-900">Simple pricing</h2>
            <p className="mt-1 text-gray-600">One plan covers all your businesses. Upgrade or downgrade any time.</p>
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

      <footer className="border-t border-gray-100 py-8 text-center text-sm text-gray-500">
        © {new Date().getFullYear()} GST Billing · Made for Indian MSMEs
      </footer>
    </div>
  );
}
