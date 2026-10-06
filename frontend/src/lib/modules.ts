/**
 * Optional menus a business can hide to keep the app simple ("lite"): a services business rarely needs stock,
 * godowns or e-way bills; a trader rarely needs recurring invoices. Hiding only removes menus and shortcuts —
 * data is never deleted and everything comes back when the module is switched on again.
 */
import type { MyBusiness } from "@/lib/types";

export type BusinessMode = "BOTH" | "GOODS" | "SERVICES";
export interface ModuleDef { key: string; label: string; hint: string; hrefs: string[]; kind: "goods" | "services" | "general" }

export const MODULES: ModuleDef[] = [
  // used mostly by businesses that sell goods
  { key: "pos", label: "POS / counter billing", hint: "Fast billing at a shop counter with barcode scanning", hrefs: ["/pos"], kind: "goods" },
  { key: "delivery_challans", label: "Delivery challans", hint: "Send goods without a bill — job work, approval, branch transfer", hrefs: ["/v/delivery-challans"], kind: "goods" },
  { key: "ewaybills", label: "E-way bills", hint: "Needed when goods worth over ₹50,000 move by road", hrefs: ["/ewaybills"], kind: "goods" },
  { key: "godowns", label: "Godowns & stock transfers", hint: "Stock kept at more than one place", hrefs: ["/godowns"], kind: "goods" },
  { key: "manufacturing", label: "Manufacturing", hint: "Make finished goods from raw material (bill of materials)", hrefs: ["/manufacturing"], kind: "goods" },
  { key: "barcode", label: "Barcode labels", hint: "Print price / barcode stickers for products", hrefs: ["/items/labels"], kind: "goods" },
  // used mostly by service providers
  { key: "recurring", label: "Recurring invoices", hint: "Bill the same amount every month — retainers, rent, AMC, subscriptions", hrefs: ["/recurring"], kind: "services" },
  // optional for anyone
  { key: "estimates", label: "Estimates / quotations", hint: "Send a quote before the sale", hrefs: ["/v/estimates"], kind: "general" },
  { key: "sale_orders", label: "Sale orders", hint: "Record confirmed orders before billing", hrefs: ["/v/sale-orders"], kind: "general" },
  { key: "purchase_orders", label: "Purchase orders", hint: "Send orders to suppliers", hrefs: ["/v/purchase-orders"], kind: "general" },
  { key: "price_lists", label: "Price lists", hint: "Different rates for dealers, wholesale or special customers", hrefs: ["/price-lists"], kind: "general" },
  { key: "reminders", label: "Collect payments (reminders)", hint: "Automatic payment reminders by e-mail / WhatsApp", hrefs: ["/reminders"], kind: "general" },
  { key: "cheques", label: "Cheques", hint: "Track cheques received and issued until they clear", hrefs: ["/cash-bank/cheques"], kind: "general" },
  { key: "compliance", label: "Compliance calendar", hint: "GST, income-tax, TDS, MCA / LLP and PF due dates — what is pending and what is filed", hrefs: ["/compliance"], kind: "general" },
  { key: "documents", label: "Document vault", hint: "Store ITRs, financial statements, certificates and licences; share by e-mail or WhatsApp", hrefs: ["/documents"], kind: "general" },
  { key: "loans", label: "Loan accounts", hint: "Business loans and EMIs", hrefs: ["/loans"], kind: "general" },
];

/** Modules hidden by default for each kind of business (they can be switched back on individually). */
export function presetHidden(mode: BusinessMode): string[] {
  if (mode === "SERVICES") return MODULES.filter((m) => m.kind === "goods").map((m) => m.key);
  if (mode === "GOODS") return MODULES.filter((m) => m.kind === "services").map((m) => m.key);
  return [];
}

export const businessMode = (b: MyBusiness | null | undefined): BusinessMode => (b?.modules?.mode as BusinessMode) ?? "BOTH";

/** Pages hidden for this business (a hidden page also hides its sub-pages, e.g. /pos/...). */
export function hiddenHrefs(b: MyBusiness | null | undefined): string[] {
  const hidden = new Set(b?.modules?.hidden ?? []);
  return MODULES.filter((m) => hidden.has(m.key)).flatMap((m) => m.hrefs);
}

export const isHiddenHref = (href: string, hidden: string[]) => hidden.some((h) => href === h || href.startsWith(h + "/") || href.startsWith(h + "?"));
