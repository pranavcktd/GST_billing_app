"use client";

import {
  AlarmClock,
  ArrowRight,
  BadgeCheck,
  BarChart3,
  Bell,
  Boxes,
  Check,
  ChevronDown,
  Coins,
  FileBadge,
  FolderLock,
  IndianRupee,
  Landmark,
  Lock,
  ReceiptIndianRupee,
  ScanLine,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Truck,
  UserCheck,
  Users,
  WifiOff,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { BrandLogo } from "@/components/BrandLogo";
import { type Cycle, type PlanOut, CycleToggle, PlanCards } from "@/components/PlanCards";
import { Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useConfig } from "@/lib/config";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

/*
 * Wording note: describe what the software helps with, never promise outcomes. Avoid "100% compliant",
 * "guaranteed", "error-free", "certified", "government approved" or "files your returns".
 */

interface PlansData {
  plans: PlanOut[]; cycles?: Cycle[]; trial_days: number;
  credit_packs?: { credits: number; price: number }[]; credit_costs?: Record<string, number>;
}

const TICKER = ["GST invoices", "e-Invoice (IRN)", "e-Way bill", "GSTR-1 & 3B JSON", "GSTR-2B matching", "Stock & godowns",
  "Barcode billing", "Offline billing", "Staff attendance", "Payroll with PF / ESI", "Document vault", "Compliance calendar",
  "Cheques & bank", "Profit & loss", "Tally export", "Role-based staff access"];

const DAY = [
  { time: "9 AM", label: "Opening", icon: Boxes,
    pain: "\"Do we still have that item, or is the register wrong again?\"",
    fix: "Live stock shows on every bill line. You choose whether the app warns you or stops a sale of stock you don't have.",
    points: ["Stock by godown, batch & expiry", "Low-stock alerts", "Stock transfers between godowns"] },
  { time: "11 AM", label: "Counter rush", icon: ScanLine,
    pain: "Customers queue while you work out CGST, SGST and IGST by hand.",
    fix: "Scan or search an item and the tax is split from the place of supply. Print a thermal receipt or A4 bill, or share it as a PDF.",
    points: ["Barcode & quick counter billing", "UPI QR on the bill", "Keeps billing when the internet drops"] },
  { time: "2 PM", label: "Big dispatch", icon: Truck,
    pain: "A ₹75,000 order is leaving. Does it need an e-way bill? An IRN?",
    fix: "The app flags it the moment you save the bill and, on plans with direct filing, generates the IRN and e-way bill for you to print.",
    points: ["e-Invoice (IRN) & e-way bill", "Goods-only e-way bill value", "Printable e-way bill"] },
  { time: "6 PM", label: "Collections", icon: IndianRupee,
    pain: "Who owes what? Which cheque is due? Does the cash drawer match?",
    fix: "Party ledgers, payment reminders, a cheque register and cash & bank books, all from the bills you already made.",
    points: ["Outstanding & ageing", "Cheque register", "Day book & cash book"] },
  { time: "Month end", label: "Returns & salaries", icon: AlarmClock,
    pain: "Return deadlines, CA calls, attendance registers and salary sheets.",
    fix: "A compliance calendar built from your registration date, GSTR-1 / 3B data ready to review, attendance & payroll with PF, ESI and PT, and every document in one vault.",
    points: ["Due-date reminders", "Payslips & salary register", "Share access with your CA"] },
];

const CHECKS = [
  { icon: BadgeCheck, title: "GSTIN auto-fill", text: "Type a GSTIN and the party's name, address and state come in from public records." },
  { icon: ReceiptIndianRupee, title: "Tax split for you", text: "CGST + SGST or IGST chosen from the place of supply, every time." },
  { icon: Truck, title: "e-Way bill alerts", text: "Bills that may need an e-way bill or IRN are flagged as soon as they are saved." },
  { icon: Boxes, title: "Stock guard", text: "A warning, or a stop, when a bill sells more than is in stock." },
  { icon: Bell, title: "Due-date reminders", text: "GST, TDS, PF / ESI and other dates, worked out from your own registration." },
  { icon: BarChart3, title: "GSTR-2B matching", text: "Purchases checked against GSTR-2B so input credit at risk stands out." },
  { icon: Lock, title: "Manager approval", text: "Edits to old or locked entries need an approval PIN from the owner or manager." },
  { icon: ShieldCheck, title: "Audit trail", text: "Who changed what, and when, is recorded for every entry." },
];

const FEATURE_GROUPS = [
  { key: "billing", label: "Billing", items: [
    { icon: ReceiptIndianRupee, title: "GST invoices & bills of supply", text: "B2B, B2C, export and service bills with HSN / SAC, discounts and your own invoice themes." },
    { icon: ScanLine, title: "Counter billing (POS)", text: "Barcode scanning, 80 / 58 mm thermal receipts and quick payment entry." },
    { icon: WifiOff, title: "Offline billing", text: "Keep making bills when the internet drops; they are saved when you are back online." },
    { icon: FileBadge, title: "Quotations, challans & returns", text: "Estimates, delivery challans, credit / debit notes and recurring bills." },
  ] },
  { key: "stock", label: "Stock", items: [
    { icon: Boxes, title: "Godowns, batches & serials", text: "Track stock in many places, with batch, expiry and serial numbers." },
    { icon: BarChart3, title: "Stock reports", text: "Stock summary, movement and valuation, low-stock and expiry alerts." },
    { icon: ScanLine, title: "Barcode labels", text: "Print labels for your items and scan them at the counter." },
    { icon: Truck, title: "Purchases & transfers", text: "Purchase bills, returns and transfers that update stock as you go." },
  ] },
  { key: "gst", label: "GST & compliance", items: [
    { icon: FileBadge, title: "e-Invoice & e-way bill", text: "Generate IRN and e-way bills directly through a licensed GSP connection, or download the JSON." },
    { icon: BarChart3, title: "Return-ready data", text: "GSTR-1 and GSTR-3B summaries and JSON files to review before you upload." },
    { icon: AlarmClock, title: "Compliance calendar", text: "GST, income tax, TDS, PF / ESI and labour-law dates, with what is done and what is due." },
    { icon: BadgeCheck, title: "Filing status", text: "Fetch which GST returns are already filed so the calendar stays up to date." },
  ] },
  { key: "money", label: "Money & books", items: [
    { icon: Landmark, title: "Cash, bank & cheques", text: "Bank accounts, cheque register, loans and expenses in one place." },
    { icon: IndianRupee, title: "Receivables & payables", text: "Party ledgers, ageing and payment reminders." },
    { icon: BarChart3, title: "Profit & loss, balance sheet", text: "Built on double-entry from the bills you make, with Tally export." },
    { icon: FolderLock, title: "Document vault", text: "Registration certificates, licences and bills stored and found in seconds." },
  ] },
  { key: "team", label: "Team & payroll", items: [
    { icon: Users, title: "Staff logins", text: "Invite billing staff, store managers and your CA, each with the access you choose." },
    { icon: UserCheck, title: "Attendance", text: "Daily attendance, half days, leave and overtime for every employee." },
    { icon: Coins, title: "Payroll", text: "Monthly salary with PF, ESI, professional tax and advances, plus payslips." },
    { icon: Smartphone, title: "Any device", text: "Phone, tablet or computer. Install it like an app, no download store needed." },
  ] },
];

const FAQ = [
  { q: "Do I need GST registration to use it?", a: "No. Unregistered and composition businesses can bill, track stock and keep accounts. GST features switch on when you add a GSTIN." },
  { q: "Is there a mobile app?", a: "It works in the browser on any phone, tablet or computer, and you can install it to your home screen like an app. One login, all devices." },
  { q: "What if the internet goes down?", a: "You can keep making bills. They are kept on the device and saved to your account when the connection returns." },
  { q: "What are API credits?", a: "Direct e-invoice (IRN), e-way bill, cancellations and filing-status checks go through a licensed GSP and cost us per call. Paid plans include credits every month; if you need more, buy a prepaid pack. Failed calls are not charged." },
  { q: "Does it file my GST returns?", a: "It prepares return data and JSON files from your entries so you or your CA can review and upload them. e-Invoices and e-way bills can be generated directly." },
  { q: "Can my CA or accountant work on my books?", a: "Yes. Invite them with their own login and choose what they can see and change." },
  { q: "Is my data safe?", a: "Data is backed up automatically, every change is logged, and you can export everything (or send it to Tally) whenever you like." },
];

/** Fades its children in when they scroll into view. */
function Reveal({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setShown(true); io.disconnect(); }
    }, { threshold: 0.15 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return <div ref={ref} style={{ transitionDelay: `${delay}ms` }} className={`lp-reveal ${shown ? "lp-in" : ""} ${className}`}>{children}</div>;
}

function HeroMock() {
  return (
    <div className="relative mx-auto w-full max-w-md">
      <div className="lp-float rounded-2xl border border-white/10 bg-white p-5 text-gray-800 shadow-2xl shadow-indigo-950/50">
        <div className="flex items-center justify-between border-b border-gray-100 pb-3">
          <div>
            <div className="text-xs text-gray-400">Tax invoice</div>
            <div className="font-semibold">INV/26-27/0142</div>
          </div>
          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">Paid · UPI</span>
        </div>
        <div className="mt-3 space-y-2 text-sm">
          {[["Steel bottle 1L × 120", "60,000"], ["Gift box × 120", "6,000"]].map(([a, b]) => (
            <div key={a} className="flex justify-between"><span className="text-gray-600">{a}</span><span className="tabular-nums">₹{b}</span></div>
          ))}
          <div className="flex justify-between text-xs text-gray-500"><span>CGST 9% + SGST 9%</span><span className="tabular-nums">₹11,880</span></div>
          <div className="flex justify-between border-t border-gray-100 pt-2 font-semibold"><span>Total</span><span className="tabular-nums">₹77,880</span></div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg bg-indigo-50 px-2 py-1.5 text-indigo-700"><b>IRN</b> · ack 1120100…</div>
          <div className="rounded-lg bg-amber-50 px-2 py-1.5 text-amber-800"><b>EWB</b> · 3510 0000 1234</div>
        </div>
      </div>
      <div className="lp-pop absolute -top-4 -left-3 hidden rounded-xl bg-emerald-500 px-3 py-2 text-xs font-medium text-white shadow-lg sm:block" style={{ animationDelay: "0.6s" }}>
        <Check size={14} className="mr-1 inline" />IRN generated
      </div>
      <div className="lp-pop absolute top-1/3 -right-6 hidden rounded-xl bg-amber-400 px-3 py-2 text-xs font-medium text-amber-950 shadow-lg sm:block" style={{ animationDelay: "1.1s" }}>
        <Truck size={14} className="mr-1 inline" />Over ₹50,000: e-way bill needed
      </div>
      <div className="lp-pop absolute -bottom-5 left-4 rounded-xl bg-white px-3 py-2 text-xs font-medium text-gray-800 shadow-lg ring-1 ring-gray-200" style={{ animationDelay: "1.6s" }}>
        <AlarmClock size={14} className="mr-1 inline text-rose-500" />GSTR-3B due in 3 days
      </div>
      <div className="lp-pop absolute -right-2 -bottom-10 hidden rounded-xl bg-rose-500 px-3 py-2 text-xs font-medium text-white shadow-lg sm:block" style={{ animationDelay: "2.1s" }}>
        <Boxes size={14} className="mr-1 inline" />Gift box: only 4 left
      </div>
    </div>
  );
}

function DayInBusiness({ name }: { name: string }) {
  const [i, setI] = useState(0);
  const [auto, setAuto] = useState(true);
  useEffect(() => {
    if (!auto) return;
    const t = setInterval(() => setI((x) => (x + 1) % DAY.length), 6000);
    return () => clearInterval(t);
  }, [auto]);
  const d = DAY[i];
  const Icon = d.icon;
  return (
    <div>
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-2 sm:mx-0 sm:flex-wrap sm:justify-center sm:px-0">
        {DAY.map((x, k) => (
          <button key={x.label} onClick={() => { setI(k); setAuto(false); }}
            className={`shrink-0 rounded-full border px-4 py-2 text-sm transition ${k === i ? "border-indigo-600 bg-indigo-600 text-white shadow-md shadow-indigo-600/30" : "border-gray-200 bg-white text-gray-700 hover:border-indigo-300"}`}>
            <span className="font-semibold">{x.time}</span> · {x.label}
          </button>
        ))}
      </div>
      <div key={i} className="lp-pop mt-6 grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-rose-100 bg-rose-50/60 p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-rose-700"><X size={16} /> The everyday headache</div>
          <p className="mt-3 text-lg font-medium text-gray-900">{d.pain}</p>
        </div>
        <div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-700"><Icon size={16} /> With {name}</div>
          <p className="mt-3 text-gray-800">{d.fix}</p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {d.points.map((p) => <li key={p} className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-emerald-800 ring-1 ring-emerald-200">{p}</li>)}
          </ul>
        </div>
      </div>
      <div className="mt-4 flex justify-center gap-1.5" aria-hidden>
        {DAY.map((x, k) => <span key={x.label} className={`h-1.5 rounded-full transition-all ${k === i ? "w-6 bg-indigo-600" : "w-1.5 bg-gray-300"}`} />)}
      </div>
    </div>
  );
}

function GstDemo({ rates, ewbLimit }: { rates: number[]; ewbLimit: number }) {
  const [amount, setAmount] = useState(48000);
  const [rate, setRate] = useState(rates.includes(18) ? 18 : rates[rates.length - 1] ?? 18);
  const [same, setSame] = useState(true);
  const tax = Math.round(amount * rate) / 100;
  const total = amount + tax;
  const ewb = total > ewbLimit;
  return (
    <div className="grid gap-6 rounded-3xl border border-indigo-100 bg-white p-6 shadow-xl shadow-indigo-100/60 md:grid-cols-2 md:p-8">
      <div className="space-y-5">
        <label className="block">
          <span className="text-sm font-medium text-gray-700">Taxable value of goods</span>
          <div className="mt-1 flex items-center gap-3">
            <input type="range" min={1000} max={150000} step={1000} value={amount} onChange={(e) => setAmount(Number(e.target.value))}
              className="w-full accent-indigo-600" aria-label="Taxable value" />
            <span className="w-24 text-right font-semibold tabular-nums text-gray-900">₹{amount.toLocaleString("en-IN")}</span>
          </div>
        </label>
        <div>
          <span className="text-sm font-medium text-gray-700">GST rate</span>
          <div className="mt-1 flex flex-wrap gap-2">
            {rates.filter((r) => r > 0).map((r) => (
              <button key={r} onClick={() => setRate(r)}
                className={`rounded-lg px-3 py-1.5 text-sm ${r === rate ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>{r}%</button>
            ))}
          </div>
        </div>
        <div>
          <span className="text-sm font-medium text-gray-700">Customer is in</span>
          <div className="mt-1 inline-flex rounded-lg bg-gray-100 p-1 text-sm">
            <button onClick={() => setSame(true)} className={`rounded-md px-3 py-1.5 ${same ? "bg-white shadow-sm" : "text-gray-600"}`}>Same state</button>
            <button onClick={() => setSame(false)} className={`rounded-md px-3 py-1.5 ${!same ? "bg-white shadow-sm" : "text-gray-600"}`}>Another state</button>
          </div>
        </div>
      </div>
      <div className="rounded-2xl bg-slate-950 p-6 text-white">
        <div className="text-xs tracking-wider text-indigo-300 uppercase">The bill works this out</div>
        <div className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-slate-400">Taxable value</span><span className="tabular-nums">{money(amount)}</span></div>
          {same ? (
            <>
              <div className="flex justify-between"><span className="text-slate-400">CGST {rate / 2}%</span><span className="tabular-nums">{money(tax / 2)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">SGST {rate / 2}%</span><span className="tabular-nums">{money(tax / 2)}</span></div>
            </>
          ) : (
            <div className="flex justify-between"><span className="text-slate-400">IGST {rate}%</span><span className="tabular-nums">{money(tax)}</span></div>
          )}
          <div className="flex justify-between border-t border-white/10 pt-2 text-lg font-semibold"><span>Total</span><span className="tabular-nums">{money(total)}</span></div>
        </div>
        <div className={`mt-5 flex items-start gap-2 rounded-xl px-3 py-2.5 text-sm transition-colors ${ewb ? "bg-amber-400 text-amber-950" : "bg-white/5 text-slate-300"}`}>
          <Truck size={18} className="mt-0.5 shrink-0" />
          {ewb ? `Over ₹${ewbLimit.toLocaleString("en-IN")}: the app reminds you that an e-way bill is generally needed to move these goods.`
            : `Under ₹${ewbLimit.toLocaleString("en-IN")}: usually no e-way bill. Slide the value up and watch.`}
        </div>
        <p className="mt-3 text-[11px] text-slate-500">Illustration only. Actual requirements depend on your goods, state rules and transaction.</p>
      </div>
    </div>
  );
}

function Features() {
  const [g, setG] = useState(FEATURE_GROUPS[0].key);
  const group = FEATURE_GROUPS.find((x) => x.key === g)!;
  return (
    <div>
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-2 sm:mx-0 sm:justify-center sm:px-0">
        {FEATURE_GROUPS.map((x) => (
          <button key={x.key} onClick={() => setG(x.key)}
            className={`shrink-0 rounded-xl px-4 py-2 text-sm font-medium transition ${x.key === g ? "bg-slate-900 text-white" : "bg-white text-gray-700 ring-1 ring-gray-200 hover:ring-indigo-300"}`}>
            {x.label}
          </button>
        ))}
      </div>
      <div key={g} className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {group.items.map(({ icon: Icon, title, text }, k) => (
          <div key={title} className="lp-pop group rounded-2xl border border-gray-200 bg-white p-5 transition hover:-translate-y-1 hover:border-indigo-200 hover:shadow-lg hover:shadow-indigo-100"
            style={{ animationDelay: `${k * 80}ms` }}>
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-md shadow-indigo-500/30 transition group-hover:scale-110">
              <Icon size={20} aria-hidden />
            </span>
            <h3 className="mt-4 font-semibold text-gray-900">{title}</h3>
            <p className="mt-1 text-sm text-gray-600">{text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="divide-y divide-gray-200 rounded-2xl border border-gray-200 bg-white">
      {FAQ.map((f, k) => (
        <div key={f.q}>
          <button onClick={() => setOpen(open === k ? null : k)} className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left font-medium text-gray-900" aria-expanded={open === k}>
            {f.q}
            <ChevronDown size={18} className={`shrink-0 text-gray-400 transition-transform ${open === k ? "rotate-180" : ""}`} />
          </button>
          <div className={`grid transition-all duration-300 ${open === k ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
            <p className="overflow-hidden px-5 text-sm text-gray-600"><span className="block pb-4">{f.a}</span></p>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Landing() {
  const { me, loading, business } = useAuth();
  const router = useRouter();
  const config = useConfig();
  const { data } = useFetch<PlansData>("/billing/plans");
  const [cycle, setCycle] = useState<string>("YEARLY");
  const name = config.brand?.app_name || "SmartHisab";
  const trial = data?.trial_days ?? config.trial_days ?? 14;
  const cheapest = data?.plans.filter((p) => p.yearly > 0).sort((a, b) => a.yearly - b.yearly)[0];
  const firstPack = data?.credit_packs?.[0];

  useEffect(() => {
    if (!loading && me) {
      router.replace(business ? "/dashboard" : me.platform_role === "SUPERADMIN" ? "/admin" : me.platform_role === "RESELLER" ? "/reseller" : me.practice_clients > 0 ? "/practice" : "/onboarding");
    }
  }, [me, loading, business, router]);

  if (loading || me) return <Loading />;

  return (
    <div className="overflow-x-hidden bg-white">
      <header className="sticky top-0 z-30 border-b border-gray-100 bg-white/80 backdrop-blur-lg">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <BrandLogo />
          <nav className="flex items-center gap-1 text-sm">
            <a href="#day" className="hidden px-3 py-2 text-gray-700 hover:text-gray-900 md:block">Why us</a>
            <a href="#features" className="hidden px-3 py-2 text-gray-700 hover:text-gray-900 md:block">Features</a>
            <a href="#pricing" className="hidden px-3 py-2 text-gray-700 hover:text-gray-900 sm:block">Pricing</a>
            <a href="#faq" className="hidden px-3 py-2 text-gray-700 hover:text-gray-900 md:block">FAQ</a>
            <Link href="/login" className="px-3 py-2 text-gray-700 hover:text-gray-900">Sign in</Link>
            <Link href="/register" className="rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white shadow-md shadow-indigo-600/30 hover:bg-indigo-700">Start free</Link>
          </nav>
        </div>
      </header>

      {/* ---------------- hero */}
      <section className="relative isolate overflow-hidden bg-slate-950 text-white">
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
          <div className="lp-blob absolute -top-24 -left-24 h-96 w-96 rounded-full bg-indigo-600/40 blur-3xl" />
          <div className="lp-blob absolute top-40 right-0 h-80 w-80 rounded-full bg-violet-600/30 blur-3xl" style={{ animationDelay: "-6s" }} />
          <div className="lp-blob absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-amber-500/20 blur-3xl" style={{ animationDelay: "-12s" }} />
          <div className="absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.07)_1px,transparent_1px)] [background-size:22px_22px]" />
        </div>
        <div className="mx-auto grid max-w-6xl items-center gap-14 px-4 pt-16 pb-24 lg:grid-cols-2 lg:pt-24">
          <div>
            <p className="lp-pop inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium text-indigo-200">
              <Sparkles size={14} className="text-amber-300" /> Billing · Stock · GST · Staff, all in one app
            </p>
            <h1 className="lp-pop mt-5 text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl" style={{ animationDelay: "0.1s" }}>
              Run your business,{" "}
              <span className="lp-shine bg-gradient-to-r from-amber-300 via-orange-300 to-amber-300 bg-clip-text text-transparent">not the paperwork.</span>
            </h1>
            <p className="lp-pop mt-6 max-w-xl text-lg text-slate-300" style={{ animationDelay: "0.2s" }}>
              GST bills in seconds. Stock, payments and staff salaries in one place. A reminder before every due date.
              On your phone, tablet or computer, even when the internet drops.
            </p>
            <div className="lp-pop mt-8 flex flex-wrap gap-3" style={{ animationDelay: "0.3s" }}>
              <Link href="/register" className="group inline-flex items-center gap-2 rounded-xl bg-amber-400 px-6 py-3 text-base font-semibold text-slate-950 shadow-lg shadow-amber-500/30 transition hover:bg-amber-300">
                Start {trial}-day free trial <ArrowRight size={18} className="transition group-hover:translate-x-1" />
              </Link>
              <a href="#day" className="rounded-xl border border-white/20 px-6 py-3 text-base font-medium text-white hover:bg-white/10">See how it helps</a>
            </div>
            <p className="lp-pop mt-4 text-sm text-slate-400" style={{ animationDelay: "0.4s" }}>
              No card needed · Free plan for small shops{cheapest ? ` · Paid plans from ${money(cheapest.yearly / 12).replace(/\.\d+$/, "")}/month` : ""}
            </p>
          </div>
          <div className="lp-pop pb-6" style={{ animationDelay: "0.3s" }}><HeroMock /></div>
        </div>
      </section>

      {/* ---------------- ticker */}
      <div className="border-y border-gray-100 bg-gray-50 py-4" aria-label="Included features">
        <div className="flex w-max lp-marquee gap-8 whitespace-nowrap text-sm font-medium text-gray-500">
          {[...TICKER, ...TICKER].map((t, k) => (
            <span key={k} className="flex items-center gap-2"><Check size={14} className="text-emerald-500" aria-hidden />{t}</span>
          ))}
        </div>
      </div>

      {/* ---------------- a day in your business */}
      <section id="day" className="scroll-mt-16 py-20">
        <div className="mx-auto max-w-5xl px-4">
          <Reveal className="text-center">
            <p className="text-sm font-semibold tracking-wider text-indigo-600 uppercase">Sound familiar?</p>
            <h2 className="mt-2 text-3xl font-bold text-gray-900 sm:text-4xl">A day in your business, made easier</h2>
            <p className="mx-auto mt-3 max-w-2xl text-gray-600">The same headaches come back every day. Here is how {name} takes them off your plate.</p>
          </Reveal>
          <Reveal className="mt-10" delay={100}><DayInBusiness name={name} /></Reveal>
        </div>
      </section>

      {/* ---------------- smart checks */}
      <section className="relative overflow-hidden bg-gradient-to-b from-indigo-50 to-white py-20">
        <div className="mx-auto max-w-6xl px-4">
          <Reveal className="mx-auto max-w-2xl text-center">
            <p className="inline-flex items-center gap-2 text-sm font-semibold tracking-wider text-indigo-600 uppercase"><Sparkles size={16} /> Smart checks</p>
            <h2 className="mt-2 text-3xl font-bold text-gray-900 sm:text-4xl">An assistant that checks while you work</h2>
            <p className="mt-3 text-gray-600">You focus on customers. The app watches tax, stock, dates and permissions in the background, and speaks up when something needs you.</p>
          </Reveal>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {CHECKS.map(({ icon: Icon, title, text }, k) => (
              <Reveal key={title} delay={(k % 4) * 90}>
                <div className="h-full rounded-2xl bg-white p-5 shadow-sm ring-1 ring-indigo-100 transition hover:-translate-y-1 hover:shadow-lg hover:shadow-indigo-100">
                  <Icon className="text-indigo-600" size={22} aria-hidden />
                  <h3 className="mt-3 font-semibold text-gray-900">{title}</h3>
                  <p className="mt-1 text-sm text-gray-600">{text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- try it */}
      <section className="py-20">
        <div className="mx-auto max-w-5xl px-4">
          <Reveal className="mb-10 text-center">
            <p className="text-sm font-semibold tracking-wider text-indigo-600 uppercase">Try it</p>
            <h2 className="mt-2 text-3xl font-bold text-gray-900 sm:text-4xl">Move the slider. Watch the bill think.</h2>
          </Reveal>
          <Reveal><GstDemo rates={config.gst_rates?.length ? config.gst_rates : [5, 12, 18, 28]} ewbLimit={config.ewb_threshold || 50000} /></Reveal>
        </div>
      </section>

      {/* ---------------- features */}
      <section id="features" className="scroll-mt-16 bg-gray-50 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <Reveal className="mb-10 text-center">
            <p className="text-sm font-semibold tracking-wider text-indigo-600 uppercase">One app</p>
            <h2 className="mt-2 text-3xl font-bold text-gray-900 sm:text-4xl">Everything for day-to-day hisab</h2>
            <p className="mx-auto mt-3 max-w-2xl text-gray-600">Billing, stock, accounts, GST and staff work together, so a bill made at the counter shows up in stock, books and returns without typing it twice.</p>
          </Reveal>
          <Features />
        </div>
      </section>

      {/* ---------------- pricing */}
      <section id="pricing" className="scroll-mt-16 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <Reveal className="mb-10 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-semibold tracking-wider text-indigo-600 uppercase">Pricing</p>
              <h2 className="mt-2 text-3xl font-bold text-gray-900 sm:text-4xl">Unlimited bills on every paid plan</h2>
              <p className="mt-2 text-gray-600">One plan covers your whole account. Upgrade or downgrade any time. Prices exclude GST.</p>
            </div>
            <CycleToggle cycles={data?.cycles} value={cycle} onChange={setCycle} />
          </Reveal>
          {data ? (
            <PlanCards plans={data.plans} cycle={cycle} cta={(p) => (
              <Link href="/register" className={`block w-full rounded-lg py-2 text-center text-sm font-medium ${p.code === "PROFESSIONAL" ? "bg-indigo-600 text-white hover:bg-indigo-700" : "border border-gray-300 text-gray-800 hover:bg-gray-50"}`}>
                {p.code === "FREE" ? "Start free" : "Start free trial"}
              </Link>
            )} />
          ) : <Loading />}
          {firstPack && (
            <Reveal className="mt-8">
              <div className="flex flex-wrap items-center justify-between gap-6 rounded-2xl bg-slate-950 p-6 text-white md:p-8">
                <div className="max-w-2xl">
                  <h3 className="flex items-center gap-2 text-lg font-semibold"><Coins size={20} className="text-amber-300" /> Direct e-invoice & e-way bill: pay only for what you use</h3>
                  <p className="mt-2 text-sm text-slate-300">
                    Every direct filing through the GST network uses API credits. Growth and Business include credits every month; on Starter, or when you need more,
                    buy a prepaid pack. Packs don&apos;t expire, failed calls aren&apos;t charged, and the JSON download is always free.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  {data?.credit_packs?.map((pk) => (
                    <div key={pk.credits} className="rounded-xl bg-white/5 px-4 py-3 text-center ring-1 ring-white/10">
                      <div className="text-lg font-semibold">{pk.credits.toLocaleString("en-IN")}</div>
                      <div className="text-xs text-slate-400">credits · {money(pk.price).replace(".00", "")}</div>
                    </div>
                  ))}
                </div>
              </div>
            </Reveal>
          )}
        </div>
      </section>

      {/* ---------------- FAQ */}
      <section id="faq" className="scroll-mt-16 bg-gray-50 py-20">
        <div className="mx-auto max-w-3xl px-4">
          <Reveal className="mb-8 text-center"><h2 className="text-3xl font-bold text-gray-900 sm:text-4xl">Questions business owners ask</h2></Reveal>
          <Reveal><Faq /></Reveal>
        </div>
      </section>

      {/* ---------------- final call */}
      <section className="px-4 py-20">
        <Reveal>
          <div className="relative mx-auto max-w-5xl overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 via-violet-600 to-indigo-700 px-6 py-14 text-center text-white shadow-2xl shadow-indigo-500/30">
            <div aria-hidden className="lp-blob absolute -top-20 -right-10 h-64 w-64 rounded-full bg-amber-400/30 blur-3xl" />
            <h2 className="relative text-3xl font-bold sm:text-4xl">Your first bill takes about a minute.</h2>
            <p className="relative mx-auto mt-3 max-w-xl text-indigo-100">Enter your GSTIN and your business details fill in. Add an item, pick a customer, save. That&apos;s it.</p>
            <Link href="/register" className="relative mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 font-semibold text-indigo-700 shadow-lg transition hover:scale-[1.03]">
              Start your {trial}-day free trial <ArrowRight size={18} />
            </Link>
            <p className="relative mt-3 text-sm text-indigo-200">No card needed. Keep the Free plan as long as you like.</p>
          </div>
        </Reveal>
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
              <Link href="/dpa" className="hover:underline">Data Processing</Link>
              <Link href="/security" className="hover:underline">Security</Link>
              <Link href="/refund" className="hover:underline">Refunds</Link>
              <Link href="/disclaimer" className="hover:underline">Disclaimer</Link>
              <Link href="/grievance" className="hover:underline">Grievance</Link>
              <Link href="/contact" className="hover:underline">Contact</Link>
            </nav>
          </div>
          <p className="mt-6 text-xs leading-relaxed text-gray-400">
            {name} is a software tool that helps businesses record transactions and prepare GST-related documents and reports from the data they enter.
            It does not provide tax, legal or accounting advice, and it does not file returns on your behalf. Please review all documents and returns
            — ideally with a qualified professional — before issuing or filing them. {name} is independent software and is not affiliated with,
            endorsed or certified by GSTN, CBIC or any Government authority. e-Invoice and e-way bill generation uses a third-party GST Suvidha
            Provider. GSTIN and HSN/SAC information is sourced from third parties and public records and may not always be current.
          </p>
          <p className="mt-3 text-xs">© {new Date().getFullYear()} {config.company.name}. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
