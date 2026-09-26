/**
 * Everything the global search (Ctrl + K) can jump to, besides data records and reports.
 * `k` = extra keywords, including common Hindi / Hinglish words users type.
 * `perm` hides entries the user's role cannot use.
 */
import type { Action, Module } from "@/lib/types";

export type Group = "Create" | "Go to" | "GST" | "Settings" | "Utilities" | "Account";
export interface SearchEntry {
  title: string; href: string; group: Group; k?: string; perm?: [Module, Action]; platform?: "SUPERADMIN" | "RESELLER";
}

export const ENTRIES: SearchEntry[] = [
  // ---- create
  { group: "Create", title: "New sale invoice", href: "/v/sales/new", k: "add create bill tax invoice sell bikri becha customer", perm: ["sales", "create"] },
  { group: "Create", title: "POS / counter billing", href: "/pos", k: "retail counter scan barcode quick bill cash sale", perm: ["sales", "create"] },
  { group: "Create", title: "New estimate / quotation", href: "/v/estimates/new", k: "add create quote proforma", perm: ["sales", "create"] },
  { group: "Create", title: "New sale order", href: "/v/sale-orders/new", k: "add create order booking", perm: ["sales", "create"] },
  { group: "Create", title: "New delivery challan", href: "/v/delivery-challans/new", k: "add create dc dispatch job work", perm: ["sales", "create"] },
  { group: "Create", title: "New credit note (sale return)", href: "/v/credit-notes/new", k: "add create sales return cn wapas", perm: ["sales", "create"] },
  { group: "Create", title: "New purchase bill", href: "/v/purchases/new", k: "add create buy supplier bill khareed kharida", perm: ["purchases", "create"] },
  { group: "Create", title: "New purchase order", href: "/v/purchase-orders/new", k: "add create po", perm: ["purchases", "create"] },
  { group: "Create", title: "New debit note (purchase return)", href: "/v/debit-notes/new", k: "add create purchase return dn", perm: ["purchases", "create"] },
  { group: "Create", title: "New expense", href: "/v/expenses/new", k: "add create kharcha kharch spend rent salary petrol", perm: ["expenses", "create"] },
  { group: "Create", title: "Receive payment (payment in)", href: "/payments/in/new", k: "add receipt collect money received jama aaya paisa udhar", perm: ["payments_in", "create"] },
  { group: "Create", title: "Make payment (payment out)", href: "/payments/out/new", k: "add pay supplier paid diya paisa", perm: ["payments_out", "create"] },
  { group: "Create", title: "Add party", href: "/parties/new", k: "new create customer supplier vendor client grahak contact", perm: ["parties", "create"] },
  { group: "Create", title: "Add item / product", href: "/items/new", k: "new create product service stock maal saman sku", perm: ["items", "create"] },

  // ---- go to
  { group: "Go to", title: "Dashboard", href: "/dashboard", k: "home summary overview" },
  { group: "Go to", title: "Sale invoices", href: "/v/sales", k: "sales list bills bikri", perm: ["sales", "view"] },
  { group: "Go to", title: "Estimates / quotations", href: "/v/estimates", k: "quotes", perm: ["sales", "view"] },
  { group: "Go to", title: "Sale orders", href: "/v/sale-orders", perm: ["sales", "view"] },
  { group: "Go to", title: "Delivery challans", href: "/v/delivery-challans", k: "dc", perm: ["sales", "view"] },
  { group: "Go to", title: "Credit notes", href: "/v/credit-notes", k: "sale returns", perm: ["sales", "view"] },
  { group: "Go to", title: "Purchase bills", href: "/v/purchases", k: "purchases khareed", perm: ["purchases", "view"] },
  { group: "Go to", title: "Purchase orders", href: "/v/purchase-orders", k: "po", perm: ["purchases", "view"] },
  { group: "Go to", title: "Debit notes", href: "/v/debit-notes", k: "purchase returns", perm: ["purchases", "view"] },
  { group: "Go to", title: "Expenses", href: "/v/expenses", k: "kharcha", perm: ["expenses", "view"] },
  { group: "Go to", title: "Expense categories & items", href: "/expenses/categories", k: "itc blocked", perm: ["expenses", "view"] },
  { group: "Go to", title: "Payments received", href: "/payments/in", k: "payment in receipts", perm: ["payments_in", "view"] },
  { group: "Go to", title: "Payments made", href: "/payments/out", k: "payment out", perm: ["payments_out", "view"] },
  { group: "Go to", title: "Parties", href: "/parties", k: "customers suppliers ledger grahak", perm: ["parties", "view"] },
  { group: "Go to", title: "Items & stock", href: "/items", k: "inventory products maal stock", perm: ["items", "view"] },
  { group: "Go to", title: "Godowns & stock transfers", href: "/godowns", k: "warehouse location branch", perm: ["items", "view"] },
  { group: "Go to", title: "Barcode labels", href: "/items/labels", k: "print sticker", perm: ["items", "view"] },
  { group: "Go to", title: "Bank & cash", href: "/cash-bank", k: "accounts bank statement cash in hand", perm: ["cashbank", "view"] },
  { group: "Go to", title: "Cheques", href: "/cash-bank/cheques", k: "pdc bounce clear", perm: ["cashbank", "view"] },
  { group: "Go to", title: "Loan accounts", href: "/loans", k: "emi borrow karz", perm: ["cashbank", "view"] },
  { group: "Go to", title: "Capital / drawings", href: "/cash-bank/capital", k: "owner investment", perm: ["cashbank", "view"] },
  { group: "Go to", title: "Tax payments", href: "/cash-bank/tax-payments", k: "gst challan pmt tds paid", perm: ["cashbank", "view"] },
  { group: "Go to", title: "All reports", href: "/reports", k: "report list" },
  { group: "Go to", title: "Receivables & payables (outstanding)", href: "/reports/outstanding", k: "udhar due collect aging", perm: ["reports_financial", "view"] },

  // ---- GST
  { group: "GST", title: "GSTR-1 (with portal JSON)", href: "/reports/gstr1", k: "gst return outward sales json", perm: ["reports_gst", "view"] },
  { group: "GST", title: "GSTR-3B (with portal JSON)", href: "/reports/gstr3b", k: "gst return summary itc payable", perm: ["reports_gst", "view"] },
  { group: "GST", title: "GSTR-2B matching", href: "/reports/gstr2b", k: "itc reconcile purchase", perm: ["reports_gst", "view"] },
  { group: "GST", title: "HSN / SAC codes", href: "/utilities/hsn", k: "hsn sac code rate master", perm: ["settings", "view"] },
  { group: "GST", title: "GST calculator", href: "/utilities/gst-calculator", k: "calculate tax inclusive exclusive" },
  { group: "GST", title: "Update tax slab on items", href: "/utilities/tax-slab", k: "rate change gst rate", perm: ["items", "edit"] },
  { group: "GST", title: "e-Invoice settings", href: "/settings?tab=einvoice", k: "irn einvoice gsp credentials", perm: ["settings", "view"] },

  // ---- settings
  { group: "Settings", title: "Business details", href: "/settings?tab=business", k: "company profile gstin address logo bank upi lut", perm: ["settings", "view"] },
  { group: "Settings", title: "Invoice design & print", href: "/settings?tab=print", k: "theme template format thermal print settings", perm: ["settings", "view"] },
  { group: "Settings", title: "E-mail settings", href: "/settings?tab=email", k: "smtp mail", perm: ["settings", "view"] },
  { group: "Settings", title: "Security, 2FA & sessions", href: "/settings?tab=security", k: "password two factor otp login devices" },
  { group: "Settings", title: "Staff & roles / manage companies", href: "/utilities/companies", k: "users team employee permission business add company" },
  { group: "Settings", title: "Subscription & plan", href: "/billing", k: "upgrade pay plan renew razorpay" },

  // ---- utilities
  { group: "Utilities", title: "Import data (Excel)", href: "/utilities/import", k: "bulk upload excel template" },
  { group: "Utilities", title: "Backup & restore", href: "/utilities/backup", k: "export data download restore" },
  { group: "Utilities", title: "Export to Tally", href: "/utilities/tally", k: "xml tally prime" },
  { group: "Utilities", title: "Audit trail", href: "/utilities/audit", k: "log history changes who", perm: ["audit", "view"] },
  { group: "Utilities", title: "All utilities", href: "/utilities" },

  // ---- account
  { group: "Account", title: "Change password", href: "/change-password", k: "reset password" },
  { group: "Account", title: "Super Admin", href: "/admin", k: "platform admin", platform: "SUPERADMIN" },
  { group: "Account", title: "Reseller portal", href: "/reseller", k: "licences", platform: "RESELLER" },
];

const words = (s: string) => s.toLowerCase().split(/[^a-z0-9ऀ-ॿ-]+/).filter(Boolean);

/** Every query word must start one of the entry's words; titles score higher than keywords. */
export function score(query: string, title: string, keywords = ""): number {
  const q = words(query);
  if (!q.length) return 0;
  const t = words(title);
  const k = words(keywords);
  let total = 0;
  for (const w of q) {
    if (t.some((x) => x === w)) total += 6;
    else if (t.some((x) => x.startsWith(w))) total += 4;
    else if (k.some((x) => x === w)) total += 3;
    else if (k.some((x) => x.startsWith(w))) total += 2;
    else if (w.length > 2 && (title + " " + keywords).toLowerCase().includes(w)) total += 1;
    else return 0;
  }
  return total + (title.toLowerCase().startsWith(query.toLowerCase().trim()) ? 3 : 0);
}
