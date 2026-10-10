"use client";

import { AlarmClock, ArrowRight, Boxes, Check, ChevronDown, Coins, Sparkles, Truck, X } from "lucide-react";
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
import {
  type Card as CardText, type DayItem, type Faq as FaqItem, type FeatureGroup, CHECK_ICONS, DAY_ICONS, FEATURE_ICONS, fillLanding,
  mergeLanding,
} from "@/lib/landingContent";

/* Texts: src/lib/landingContent.ts (defaults) + Admin → Website → Home page (edits). */

interface PlansData {
  plans: PlanOut[]; cycles?: Cycle[]; trial_days: number;
  credit_packs?: { credits: number; price: number }[]; credit_costs?: Record<string, number>;
}

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

function DayInBusiness({ name, items }: { name: string; items: DayItem[] }) {
  const [i, setI] = useState(0);
  const [auto, setAuto] = useState(true);
  useEffect(() => {
    if (!auto) return;
    const t = setInterval(() => setI((x) => (x + 1) % Math.max(items.length, 1)), 6000);
    return () => clearInterval(t);
  }, [auto, items.length]);
  if (!items.length) return null;
  const d = items[i % items.length];
  const Icon = DAY_ICONS[i % DAY_ICONS.length];
  return (
    <div>
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-2 sm:mx-0 sm:flex-wrap sm:justify-center sm:px-0">
        {items.map((x, k) => (
          <button key={`${x.label}${k}`} onClick={() => { setI(k); setAuto(false); }}
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
            {(d.points ?? []).map((p) => <li key={p} className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-emerald-800 ring-1 ring-emerald-200">{p}</li>)}
          </ul>
        </div>
      </div>
      <div className="mt-4 flex justify-center gap-1.5" aria-hidden>
        {items.map((x, k) => <span key={`${x.label}${k}`} className={`h-1.5 rounded-full transition-all ${k === i ? "w-6 bg-indigo-600" : "w-1.5 bg-gray-300"}`} />)}
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

function Features({ groups }: { groups: FeatureGroup[] }) {
  const [g, setG] = useState(0);
  const gi = g < groups.length ? g : 0;
  const group = groups[gi];
  if (!group) return null;
  return (
    <div>
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-2 sm:mx-0 sm:justify-center sm:px-0">
        {groups.map((x, k) => (
          <button key={`${x.label}${k}`} onClick={() => setG(k)}
            className={`shrink-0 rounded-xl px-4 py-2 text-sm font-medium transition ${k === gi ? "bg-slate-900 text-white" : "bg-white text-gray-700 ring-1 ring-gray-200 hover:ring-indigo-300"}`}>
            {x.label}
          </button>
        ))}
      </div>
      <div key={gi} className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {group.items.map(({ title, text }: CardText, k) => {
          const Icon = FEATURE_ICONS[gi % FEATURE_ICONS.length][k % 4];
          return (
          <div key={`${title}${k}`} className="lp-pop group rounded-2xl border border-gray-200 bg-white p-5 transition hover:-translate-y-1 hover:border-indigo-200 hover:shadow-lg hover:shadow-indigo-100"
            style={{ animationDelay: `${k * 80}ms` }}>
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-md shadow-indigo-500/30 transition group-hover:scale-110">
              <Icon size={20} aria-hidden />
            </span>
            <h3 className="mt-4 font-semibold text-gray-900">{title}</h3>
            <p className="mt-1 text-sm text-gray-600">{text}</p>
          </div>
          );
        })}
      </div>
    </div>
  );
}

function Faq({ items }: { items: FaqItem[] }) {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="divide-y divide-gray-200 rounded-2xl border border-gray-200 bg-white">
      {items.map((f, k) => (
        <div key={`${f.q}${k}`}>
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
  const { data: site } = useFetch<{ body: string | null }>("/site/landing");
  let saved: unknown = null;
  try { saved = site?.body ? JSON.parse(site.body) : null; } catch { saved = null; }
  const c = mergeLanding(saved);
  const t = (x: string) => fillLanding(x, { brand: name, trial });

  useEffect(() => {
    if (!loading && me) {
      router.replace(business ? "/dashboard" : me.platform_role === "SUPERADMIN" || me.platform_role === "TEAM" ? "/admin" : me.platform_role === "RESELLER" ? "/reseller" : me.practice_clients > 0 ? "/practice" : "/onboarding");
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
              <Sparkles size={14} className="text-amber-300" /> {t(c.hero.badge)}
            </p>
            <h1 className="lp-pop mt-5 text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl" style={{ animationDelay: "0.1s" }}>
              {t(c.hero.title)}{" "}
              <span className="lp-shine bg-gradient-to-r from-amber-300 via-orange-300 to-amber-300 bg-clip-text text-transparent">{t(c.hero.highlight)}</span>
            </h1>
            <p className="lp-pop mt-6 max-w-xl text-lg text-slate-300" style={{ animationDelay: "0.2s" }}>
              {t(c.hero.subtitle)}
            </p>
            <div className="lp-pop mt-8 flex flex-wrap gap-3" style={{ animationDelay: "0.3s" }}>
              <Link href="/register" className="group inline-flex items-center gap-2 rounded-xl bg-amber-400 px-6 py-3 text-base font-semibold text-slate-950 shadow-lg shadow-amber-500/30 transition hover:bg-amber-300">
                {t(c.hero.cta_primary)} <ArrowRight size={18} className="transition group-hover:translate-x-1" />
              </Link>
              <a href="#day" className="rounded-xl border border-white/20 px-6 py-3 text-base font-medium text-white hover:bg-white/10">{t(c.hero.cta_secondary)}</a>
            </div>
            <p className="lp-pop mt-4 text-sm text-slate-400" style={{ animationDelay: "0.4s" }}>
              {t(c.hero.note)}{cheapest ? ` · Paid plans from ${money(cheapest.yearly / 12).replace(/\.\d+$/, "")}/month` : ""}
            </p>
          </div>
          <div className="lp-pop pb-6" style={{ animationDelay: "0.3s" }}><HeroMock /></div>
        </div>
      </section>

      {/* ---------------- ticker */}
      <div className="border-y border-gray-100 bg-gray-50 py-4" aria-label="Included features">
        <div className="flex w-max lp-marquee gap-8 whitespace-nowrap text-sm font-medium text-gray-500">
          {[...c.ticker, ...c.ticker].map((x, k) => (
            <span key={k} className="flex items-center gap-2"><Check size={14} className="text-emerald-500" aria-hidden />{t(x)}</span>
          ))}
        </div>
      </div>

      {/* ---------------- a day in your business */}
      <section id="day" className="scroll-mt-16 py-20">
        <div className="mx-auto max-w-5xl px-4">
          <Reveal className="text-center">
            <p className="text-sm font-semibold tracking-wider text-indigo-600 uppercase">{t(c.day.eyebrow)}</p>
            <h2 className="mt-2 text-3xl font-bold text-gray-900 sm:text-4xl">{t(c.day.title)}</h2>
            <p className="mx-auto mt-3 max-w-2xl text-gray-600">{t(c.day.subtitle)}</p>
          </Reveal>
          <Reveal className="mt-10" delay={100}><DayInBusiness name={name} items={c.day.items} /></Reveal>
        </div>
      </section>

      {/* ---------------- smart checks */}
      <section className="relative overflow-hidden bg-gradient-to-b from-indigo-50 to-white py-20">
        <div className="mx-auto max-w-6xl px-4">
          <Reveal className="mx-auto max-w-2xl text-center">
            <p className="inline-flex items-center gap-2 text-sm font-semibold tracking-wider text-indigo-600 uppercase"><Sparkles size={16} /> {t(c.checks.eyebrow)}</p>
            <h2 className="mt-2 text-3xl font-bold text-gray-900 sm:text-4xl">{t(c.checks.title)}</h2>
            <p className="mt-3 text-gray-600">{t(c.checks.subtitle)}</p>
          </Reveal>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {c.checks.items.map(({ title, text }, k) => { const Icon = CHECK_ICONS[k % CHECK_ICONS.length]; return (
              <Reveal key={`${title}${k}`} delay={(k % 4) * 90}>
                <div className="h-full rounded-2xl bg-white p-5 shadow-sm ring-1 ring-indigo-100 transition hover:-translate-y-1 hover:shadow-lg hover:shadow-indigo-100">
                  <Icon className="text-indigo-600" size={22} aria-hidden />
                  <h3 className="mt-3 font-semibold text-gray-900">{t(title)}</h3>
                  <p className="mt-1 text-sm text-gray-600">{t(text)}</p>
                </div>
              </Reveal>
            ); })}
          </div>
        </div>
      </section>

      {/* ---------------- try it */}
      <section className="py-20">
        <div className="mx-auto max-w-5xl px-4">
          <Reveal className="mb-10 text-center">
            <p className="text-sm font-semibold tracking-wider text-indigo-600 uppercase">{t(c.demo.eyebrow)}</p>
            <h2 className="mt-2 text-3xl font-bold text-gray-900 sm:text-4xl">{t(c.demo.title)}</h2>
          </Reveal>
          <Reveal><GstDemo rates={config.gst_rates?.length ? config.gst_rates : [5, 12, 18, 28]} ewbLimit={config.ewb_threshold || 50000} /></Reveal>
        </div>
      </section>

      {/* ---------------- features */}
      <section id="features" className="scroll-mt-16 bg-gray-50 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <Reveal className="mb-10 text-center">
            <p className="text-sm font-semibold tracking-wider text-indigo-600 uppercase">{t(c.features.eyebrow)}</p>
            <h2 className="mt-2 text-3xl font-bold text-gray-900 sm:text-4xl">{t(c.features.title)}</h2>
            <p className="mx-auto mt-3 max-w-2xl text-gray-600">{t(c.features.subtitle)}</p>
          </Reveal>
          <Features groups={c.features.groups} />
        </div>
      </section>

      {/* ---------------- pricing */}
      <section id="pricing" className="scroll-mt-16 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <Reveal className="mb-10 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-semibold tracking-wider text-indigo-600 uppercase">{t(c.pricing.eyebrow)}</p>
              <h2 className="mt-2 text-3xl font-bold text-gray-900 sm:text-4xl">{t(c.pricing.title)}</h2>
              <p className="mt-2 text-gray-600">{t(c.pricing.subtitle)}</p>
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
                  <h3 className="flex items-center gap-2 text-lg font-semibold"><Coins size={20} className="text-amber-300" /> {t(c.pricing.credits_title)}</h3>
                  <p className="mt-2 text-sm text-slate-300">{t(c.pricing.credits_text)}</p>
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
          <Reveal className="mb-8 text-center"><h2 className="text-3xl font-bold text-gray-900 sm:text-4xl">{t(c.faq.title)}</h2></Reveal>
          <Reveal><Faq items={c.faq.items} /></Reveal>
        </div>
      </section>

      {/* ---------------- final call */}
      <section className="px-4 py-20">
        <Reveal>
          <div className="relative mx-auto max-w-5xl overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 via-violet-600 to-indigo-700 px-6 py-14 text-center text-white shadow-2xl shadow-indigo-500/30">
            <div aria-hidden className="lp-blob absolute -top-20 -right-10 h-64 w-64 rounded-full bg-amber-400/30 blur-3xl" />
            <h2 className="relative text-3xl font-bold sm:text-4xl">{t(c.final.title)}</h2>
            <p className="relative mx-auto mt-3 max-w-xl text-indigo-100">{t(c.final.text)}</p>
            <Link href="/register" className="relative mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 font-semibold text-indigo-700 shadow-lg transition hover:scale-[1.03]">
              {t(c.final.cta)} <ArrowRight size={18} />
            </Link>
            <p className="relative mt-3 text-sm text-indigo-200">{t(c.final.note)}</p>
          </div>
        </Reveal>
      </section>

      <footer className="border-t border-gray-100 bg-gray-50 py-10 text-sm text-gray-500">
        <div className="mx-auto max-w-6xl px-4">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div className="max-w-sm">
              <BrandLogo size="sm" />
              <p className="mt-2 text-xs">{config.brand?.tagline}</p>
              <p className="mt-3 text-xs text-gray-600">
                {config.company.email && <a href={`mailto:${config.company.email}`} className="hover:underline">{config.company.email}</a>}
                {/^\+?[\d\s-]{8,}$/.test(config.company.phone ?? "") && <> · <a href={`tel:${config.company.phone.replace(/[\s-]/g, "")}`} className="hover:underline">{config.company.phone}</a></>}
              </p>
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
          <p className="mt-6 text-xs leading-relaxed text-gray-400">{t(c.footer_note)}</p>
          <p className="mt-3 text-xs">© {new Date().getFullYear()} {config.company.name}. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
