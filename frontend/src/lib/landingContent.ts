/**
 * Home page texts. These are the built-in defaults; the super admin edits them in Admin → Website → Home page and
 * the saved version (GET /api/site/landing) is merged over these. Icons are fixed by position.
 * Placeholders: {brand} = product name, {trial} = free-trial days.
 *
 * Wording note: describe what the software helps with, never promise outcomes. Avoid "100% compliant",
 * "guaranteed", "error-free", "certified", "government approved" or "files your returns".
 */

import {
  AlarmClock, BadgeCheck, BarChart3, Bell, Boxes, Coins, FileBadge, FolderLock, IndianRupee, Landmark, Lock,
  ReceiptIndianRupee, ScanLine, ShieldCheck, Smartphone, Truck, UserCheck, Users, WifiOff,
} from "lucide-react";

export interface DayItem { time: string; label: string; pain: string; fix: string; points: string[] }
export interface Card { title: string; text: string }
export interface FeatureGroup { label: string; items: Card[] }
export interface Faq { q: string; a: string }
export interface Section { eyebrow: string; title: string; subtitle: string }

export interface LandingContent {
  hero: { badge: string; title: string; highlight: string; subtitle: string; cta_primary: string; cta_secondary: string; note: string };
  ticker: string[];
  day: Section & { items: DayItem[] };
  checks: Section & { items: Card[] };
  demo: { eyebrow: string; title: string };
  features: Section & { groups: FeatureGroup[] };
  pricing: Section & { credits_title: string; credits_text: string };
  faq: { title: string; items: Faq[] };
  final: { title: string; text: string; cta: string; note: string };
  footer_note: string;
}

export const DAY_ICONS = [Boxes, ScanLine, Truck, IndianRupee, AlarmClock];
export const CHECK_ICONS = [BadgeCheck, ReceiptIndianRupee, Truck, Boxes, Bell, BarChart3, Lock, ShieldCheck];
export const FEATURE_ICONS = [
  [ReceiptIndianRupee, ScanLine, WifiOff, FileBadge], [Boxes, BarChart3, ScanLine, Truck], [FileBadge, BarChart3, AlarmClock, BadgeCheck],
  [Landmark, IndianRupee, BarChart3, FolderLock], [Users, UserCheck, Coins, Smartphone],
];
export const icon = <T,>(list: T[], i: number): T => list[i % list.length];

export const DEFAULT_LANDING: LandingContent = {
  hero: {
    badge: "Billing · Stock · GST · Staff, all in one app",
    title: "Run your business,",
    highlight: "not the paperwork.",
    subtitle: "GST bills in seconds. Stock, payments and staff salaries in one place. A reminder before every due date. On your phone, tablet or computer, even when the internet drops.",
    cta_primary: "Start {trial}-day free trial",
    cta_secondary: "See how it helps",
    note: "No card needed · Free plan for small shops",
  },
  ticker: ["GST invoices", "e-Invoice (IRN)", "e-Way bill", "GSTR-1 & 3B JSON", "GSTR-2B matching", "Stock & godowns",
    "Barcode billing", "Offline billing", "Staff attendance", "Payroll with PF / ESI", "Document vault", "Compliance calendar",
    "Cheques & bank", "Profit & loss", "Tally export", "Role-based staff access"],
  day: {
    eyebrow: "Sound familiar?", title: "A day in your business, made easier",
    subtitle: "The same headaches come back every day. Here is how {brand} takes them off your plate.",
    items: [
      { time: "9 AM", label: "Opening", pain: "\"Do we still have that item, or is the register wrong again?\"",
        fix: "Live stock shows on every bill line. You choose whether the app warns you or stops a sale of stock you don't have.",
        points: ["Stock by godown, batch & expiry", "Low-stock alerts", "Stock transfers between godowns"] },
      { time: "11 AM", label: "Counter rush", pain: "Customers queue while you work out CGST, SGST and IGST by hand.",
        fix: "Scan or search an item and the tax is split from the place of supply. Print a thermal receipt or A4 bill, or share it as a PDF.",
        points: ["Barcode & quick counter billing", "UPI QR on the bill", "Keeps billing when the internet drops"] },
      { time: "2 PM", label: "Big dispatch", pain: "A ₹75,000 order is leaving. Does it need an e-way bill? An IRN?",
        fix: "The app flags it the moment you save the bill and, on plans with direct filing, generates the IRN and e-way bill for you to print.",
        points: ["e-Invoice (IRN) & e-way bill", "Goods-only e-way bill value", "Printable e-way bill"] },
      { time: "6 PM", label: "Collections", pain: "Who owes what? Which cheque is due? Does the cash drawer match?",
        fix: "Party ledgers, payment reminders, a cheque register and cash & bank books, all from the bills you already made.",
        points: ["Outstanding & ageing", "Cheque register", "Day book & cash book"] },
      { time: "Month end", label: "Returns & salaries", pain: "Return deadlines, CA calls, attendance registers and salary sheets.",
        fix: "A compliance calendar built from your registration date, GSTR-1 / 3B data ready to review, attendance & payroll with PF, ESI and PT, and every document in one vault.",
        points: ["Due-date reminders", "Payslips & salary register", "Share access with your CA"] },
    ],
  },
  checks: {
    eyebrow: "Smart checks", title: "An assistant that checks while you work",
    subtitle: "You focus on customers. The app watches tax, stock, dates and permissions in the background, and speaks up when something needs you.",
    items: [
      { title: "GSTIN auto-fill", text: "Type a GSTIN and the party's name, address and state come in from public records." },
      { title: "Tax split for you", text: "CGST + SGST or IGST chosen from the place of supply, every time." },
      { title: "e-Way bill alerts", text: "Bills that may need an e-way bill or IRN are flagged as soon as they are saved." },
      { title: "Stock guard", text: "A warning, or a stop, when a bill sells more than is in stock." },
      { title: "Due-date reminders", text: "GST, TDS, PF / ESI and other dates, worked out from your own registration." },
      { title: "GSTR-2B matching", text: "Purchases checked against GSTR-2B so input credit at risk stands out." },
      { title: "Manager approval", text: "Edits to old or locked entries need an approval PIN from the owner or manager." },
      { title: "Audit trail", text: "Who changed what, and when, is recorded for every entry — with the values before and after." },
    ],
  },
  demo: { eyebrow: "Try it", title: "Move the slider. Watch the bill think." },
  features: {
    eyebrow: "One app", title: "Everything for your day-to-day accounts",
    subtitle: "Billing, stock, accounts, GST and staff work together, so a bill made at the counter shows up in stock, books and returns without typing it twice.",
    groups: [
      { label: "Billing", items: [
        { title: "GST invoices & bills of supply", text: "B2B, B2C, export and service bills with HSN / SAC, discounts and your own invoice themes." },
        { title: "Counter billing (POS)", text: "Barcode scanning, 80 / 58 mm thermal receipts and quick payment entry." },
        { title: "Offline billing", text: "Keep making bills when the internet drops; they are saved when you are back online." },
        { title: "Quotations, challans & returns", text: "Estimates, delivery challans, credit / debit notes and recurring bills." },
      ] },
      { label: "Stock", items: [
        { title: "Godowns, batches & serials", text: "Track stock in many places, with batch, expiry and serial numbers." },
        { title: "Stock reports", text: "Stock summary, movement and valuation, low-stock and expiry alerts." },
        { title: "Barcode labels", text: "Print labels for your items and scan them at the counter." },
        { title: "Purchases & transfers", text: "Purchase bills, returns and transfers that update stock as you go." },
      ] },
      { label: "GST & compliance", items: [
        { title: "e-Invoice & e-way bill", text: "Generate IRN and e-way bills directly through a licensed GSP connection, or download the JSON." },
        { title: "Return-ready data", text: "GSTR-1 and GSTR-3B summaries and JSON files to review before you upload." },
        { title: "Compliance calendar", text: "GST, income tax, TDS, PF / ESI and labour-law dates, with what is done and what is due." },
        { title: "Filing status", text: "Fetch which GST returns are already filed so the calendar stays up to date." },
      ] },
      { label: "Money & books", items: [
        { title: "Cash, bank & cheques", text: "Bank accounts, cheque register, loans and expenses in one place." },
        { title: "Receivables & payables", text: "Party ledgers, ageing and payment reminders." },
        { title: "Profit & loss, balance sheet", text: "Built on double-entry from the bills you make, with Tally export." },
        { title: "Document vault", text: "Registration certificates, licences and bills stored and found in seconds." },
      ] },
      { label: "Team & payroll", items: [
        { title: "Staff logins", text: "Invite billing staff, store managers and your CA, each with the access you choose." },
        { title: "Attendance", text: "Daily attendance, half days, leave and overtime for every employee." },
        { title: "Payroll", text: "Monthly salary with PF, ESI, professional tax and advances, plus payslips." },
        { title: "Any device", text: "Phone, tablet or computer. Install it like an app, no download store needed." },
      ] },
    ],
  },
  pricing: {
    eyebrow: "Pricing", title: "Unlimited bills on every paid plan",
    subtitle: "One plan covers your whole account. Upgrade or downgrade any time. Prices exclude GST.",
    credits_title: "Direct e-invoice & e-way bill: pay only for what you use",
    credits_text: "Every direct filing through the GST network uses API credits. Paid plans include credits every month; when you need more, buy a prepaid pack. Packs don't expire, failed calls aren't charged, and the JSON download is always free.",
  },
  faq: {
    title: "Questions business owners ask",
    items: [
      { q: "Do I need GST registration to use it?", a: "No. Unregistered and composition businesses can bill, track stock and keep accounts. GST features switch on when you add a GSTIN." },
      { q: "Is there a mobile app?", a: "It works in the browser on any phone, tablet or computer, and you can install it to your home screen like an app. One login, all devices." },
      { q: "What if the internet goes down?", a: "You can keep making bills. They are kept on the device and saved to your account when the connection returns." },
      { q: "What are API credits?", a: "Direct e-invoice (IRN), e-way bill, cancellations and filing-status checks go through a licensed GSP and cost us per call. Paid plans include credits every month; if you need more, buy a prepaid pack. Failed calls are not charged." },
      { q: "Does it file my GST returns?", a: "It prepares return data and JSON files from your entries so you or your CA can review and upload them. e-Invoices and e-way bills can be generated directly." },
      { q: "Can my CA or accountant work on my books?", a: "Yes. Invite them with their own login and choose what they can see and change." },
      { q: "Is my data safe?", a: "Data is backed up automatically, every change is logged, and you can export everything (or send it to Tally) whenever you like." },
    ],
  },
  final: {
    title: "Your first bill takes about a minute.",
    text: "Enter your GSTIN and your business details fill in. Add an item, pick a customer, save. That's it.",
    cta: "Start your {trial}-day free trial",
    note: "No card needed. Keep the Free plan as long as you like.",
  },
  footer_note: "{brand} is a software tool that helps businesses record transactions and prepare GST-related documents and reports from the data they enter. It does not provide tax, legal or accounting advice, and it does not file returns on your behalf. Please review all documents and returns — ideally with a qualified professional — before issuing or filing them. {brand} is independent software and is not affiliated with, endorsed or certified by GSTN, CBIC or any Government authority. e-Invoice and e-way bill generation uses a third-party GST Suvidha Provider. GSTIN and HSN/SAC information is sourced from third parties and public records and may not always be current.",
};

/** Saved content over the defaults (each section / list replaced as a whole when present). */
export function mergeLanding(saved: unknown): LandingContent {
  const s = (saved && typeof saved === "object" ? saved : {}) as Partial<Record<keyof LandingContent, unknown>>;
  const out = { ...DEFAULT_LANDING } as Record<string, unknown>;
  for (const k of Object.keys(DEFAULT_LANDING) as (keyof LandingContent)[]) {
    const v = s[k];
    if (v === undefined || v === null) continue;
    const d = DEFAULT_LANDING[k];
    out[k] = Array.isArray(d) || typeof d !== "object" ? v : { ...(d as object), ...(v as object) };
  }
  return out as unknown as LandingContent;
}

export const fillLanding = (text: string, vars: { brand: string; trial: number }) =>
  text.replace(/\{brand\}/g, vars.brand).replace(/\{trial\}/g, String(vars.trial));
