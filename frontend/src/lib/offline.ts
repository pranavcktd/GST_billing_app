/**
 * Offline billing.
 *
 * - Read cache: answers of a few GET endpoints needed to make a bill (items, parties, rates, godowns,
 *   accounts, your profile) are kept per business and served when the server can't be reached.
 * - Queue: a new document saved while offline is stored on this device with a unique client_ref and
 *   uploaded when the connection returns. The server ignores a repeated upload of the same client_ref,
 *   so a retry can never create a duplicate. The invoice number is given at upload.
 */

export interface QueuedDoc {
  id: string;            // client_ref
  business_id: string;
  path: string;
  body: Record<string, unknown>;
  label: string;         // "Sale Invoice · Karan Stores · ₹1,180"
  created_at: string;
  error?: string;        // server refused it (needs attention)
}

const QUEUE_KEY = "offline-queue";
const CACHE_PREFIX = "offline-cache:";
const CACHEABLE: RegExp[] = [
  /^\/auth\/me$/, /^\/businesses\/current$/, /^\/items(\?|$)/, /^\/parties(\?|$)/, /^\/parties\/[^/]+\/rates$/,
  /^\/godowns$/, /^\/items\/stock(\?|$)/, /^\/accounts$/, /^\/expenses\/categories$/, /^\/expenses\/items(\?|$)/, /^\/price-lists$/,
];
const QUEUEABLE = /^\/vouchers$/;

export class OfflineQueuedError extends Error {
  constructor(public doc: QueuedDoc) {
    super("Saved on this device — it will be uploaded automatically when you are back online.");
  }
}

const listeners = new Set<() => void>();
export const onQueueChange = (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn); }; };
const notify = () => listeners.forEach((fn) => fn());

function safeGet(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function safeSet(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch { /* storage full or blocked — offline features degrade quietly */ }
}

export const isNetworkError = (e: unknown) => e instanceof TypeError || (typeof navigator !== "undefined" && !navigator.onLine);
export const cacheable = (path: string) => CACHEABLE.some((r) => r.test(path));
export const queueable = (method: string, path: string) => method === "POST" && QUEUEABLE.test(path);

export function cachePut(bid: string | null, path: string, data: unknown): void {
  const text = JSON.stringify(data);
  if (text.length < 3_000_000) safeSet(`${CACHE_PREFIX}${bid ?? "-"}:${path}`, text);
}
export function cacheGet<T>(bid: string | null, path: string): T | undefined {
  const raw = safeGet(`${CACHE_PREFIX}${bid ?? "-"}:${path}`);
  if (raw === null) return undefined;
  try { return JSON.parse(raw) as T; } catch { return undefined; }
}

export function queue(): QueuedDoc[] {
  try { return JSON.parse(safeGet(QUEUE_KEY) ?? "[]") as QueuedDoc[]; } catch { return []; }
}
function saveQueue(q: QueuedDoc[]) {
  safeSet(QUEUE_KEY, JSON.stringify(q));
  notify();
}

export function newClientRef(): string {
  const rnd = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID().replace(/-/g, "") : Math.random().toString(36).slice(2) + Date.now().toString(36);
  return `off_${rnd.slice(0, 24)}`;
}

const TITLES: Record<string, string> = { SALE: "Sale Invoice", PURCHASE: "Purchase Bill", ESTIMATE: "Estimate", SALE_ORDER: "Sale Order",
  PURCHASE_ORDER: "Purchase Order", DELIVERY_CHALLAN: "Delivery Challan", SALE_RETURN: "Credit Note", PURCHASE_RETURN: "Debit Note", EXPENSE: "Expense" };

export function enqueue(bid: string, path: string, body: Record<string, unknown>, partyName?: string): QueuedDoc {
  const lines = (body.lines as { qty?: number; rate?: number }[] | undefined) ?? [];
  const approx = lines.reduce((s, l) => s + (Number(l.qty) || 0) * (Number(l.rate) || 0), 0);
  const doc: QueuedDoc = {
    id: (body.client_ref as string) || newClientRef(), business_id: bid, path, body: { ...body },
    label: `${TITLES[String(body.type)] ?? "Document"} · ${partyName || (body.party_name as string) || "Cash sale"} · ₹${approx.toLocaleString("en-IN")} before tax`,
    created_at: new Date().toISOString(),
  };
  doc.body.client_ref = doc.id;
  doc.body.allow_negative = true; // billed offline: the goods are already gone; the server still applies "Block"
  saveQueue([...queue().filter((d) => d.id !== doc.id), doc]);
  return doc;
}

export function removeQueued(id: string): void {
  saveQueue(queue().filter((d) => d.id !== id));
}

let syncing = false;

/** Upload queued documents one by one. `send` performs the real POST (it throws on failure). */
export async function syncQueue(send: (doc: QueuedDoc) => Promise<void>): Promise<{ sent: number; failed: number }> {
  if (syncing || (typeof navigator !== "undefined" && !navigator.onLine)) return { sent: 0, failed: 0 };
  syncing = true;
  let sent = 0, failed = 0;
  try {
    for (const doc of queue()) {
      if (doc.error) continue;
      try {
        await send(doc);
        removeQueued(doc.id);
        sent++;
      } catch (e) {
        if (isNetworkError(e)) break; // still offline — try later
        failed++;
        saveQueue(queue().map((d) => (d.id === doc.id ? { ...d, error: (e as Error).message } : d)));
      }
    }
  } finally {
    syncing = false;
  }
  return { sent, failed };
}

export function retryQueued(id: string): void {
  saveQueue(queue().map((d) => (d.id === id ? { ...d, error: undefined } : d)));
}
