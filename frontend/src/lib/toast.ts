/**
 * Short confirmation messages ("Item saved") shown at the bottom of the screen.
 *
 * `toast(text)` can be called from anywhere. Saves through api() announce themselves: a successful
 * POST / PUT / DELETE on a known record type shows "<Record> saved / updated / deleted", so every form
 * confirms without extra code.
 */

export interface Toast { id: number; text: string; tone: "ok" | "error" }

const listeners = new Set<(t: Toast) => void>();
let seq = 0;

export function onToast(fn: (t: Toast) => void) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

export function toast(text: string, tone: Toast["tone"] = "ok") {
  const t = { id: ++seq, text, tone };
  listeners.forEach((fn) => fn(t));
}

const DOC_TITLES: Record<string, string> = {
  SALE: "Sale invoice", PURCHASE: "Purchase bill", ESTIMATE: "Estimate", SALE_ORDER: "Sale order", PURCHASE_ORDER: "Purchase order",
  DELIVERY_CHALLAN: "Delivery challan", SALE_RETURN: "Credit note", PURCHASE_RETURN: "Debit note", EXPENSE: "Expense",
};

// record path (collection or one record — never sub-actions like /vouchers/x/email) → what it is called
const RECORDS: [RegExp, string][] = [
  [/^\/items(\/[^/?]+)?$/, "Item"], [/^\/parties(\/[^/?]+)?$/, "Party"], [/^\/vouchers(\/[^/?]+)?$/, "Document"],
  [/^\/payments(\/[^/?]+)?$/, "Payment"], [/^\/accounts(\/[^/?]+)?$/, "Account"], [/^\/transfers(\/[^/?]+)?$/, "Transfer"],
  [/^\/capital(\/[^/?]+)?$/, "Capital entry"], [/^\/tax-payments(\/[^/?]+)?$/, "Tax payment"],
  [/^\/loans(\/[^/?]+)?$/, "Loan"], [/^\/loans\/[^/]+\/txns(\/[^/?]+)?$/, "Loan entry"], [/^\/godowns(\/[^/?]+)?$/, "Godown"],
  [/^\/price-lists(\/[^/?]+)?$/, "Price list"], [/^\/price-lists\/[^/]+\/items$/, "Price list rates"],
  [/^\/boms(\/[^/?]+)?$/, "Bill of materials"], [/^\/productions(\/[^/?]+)?$/, "Production entry"],
  [/^\/recurring(\/[^/?]+)?$/, "Recurring invoice"], [/^\/expenses\/categories(\/[^/?]+)?$/, "Expense category"],
  [/^\/expenses\/items(\/[^/?]+)?$/, "Expense item"], [/^\/businesses\/current$/, "Business details"],
  [/^\/reminders\/settings$/, "Reminder settings"], [/^\/compliance\/tasks(\/[^/?]+)?$/, "Compliance entry"],
  [/^\/businesses\/current\/modules$/, "Modules"],
];

export function announceSave(method: string, path: string, body: unknown) {
  if (method === "GET") return;
  const hit = RECORDS.find(([re]) => re.test(path.split("?")[0]));
  if (!hit) return;
  let name = hit[1];
  const type = (body as { type?: string } | null)?.type;
  if (name === "Document" && type && DOC_TITLES[type]) name = DOC_TITLES[type];
  toast(`${name} ${method === "DELETE" ? "deleted" : method === "POST" ? "saved" : "updated"}`);
}
