import * as offline from "./offline";
import { announceSave } from "./toast";

// Empty = same origin (/api is proxied by Next.js, see next.config.ts). Set only to call the API directly.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

const TOKEN_KEY = "gb_token";
const BUSINESS_KEY = "gb_business";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}

export const session = {
  token: () => read(TOKEN_KEY),
  setToken: (t: string | null) => write(TOKEN_KEY, t),
  businessId: () => read(BUSINESS_KEY),
  setBusinessId: (id: string | null) => write(BUSINESS_KEY, id),
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string, public plan?: string, public detail?: unknown) {
    super(message);
  }
}

type Structured = { message: string; code?: string; plan?: string; plan_name?: string };

/** Hooks the UI registers: ask a manager for the approval PIN, and show the upgrade prompt. */
export const uiHooks: {
  askApprovalPin?: (message: string) => Promise<string | null>;
  showUpgrade?: (message: string, plan?: string) => void;
  accessBlocked?: (code: string, message: string) => void;
} = {};

/** Staff sign-in rules of a business (approval / office network / hours) — see GlobalDialogs. */
export const ACCESS_CODES = ["ACCESS_PENDING", "ACCESS_DENIED", "IP_NOT_ALLOWED", "OUTSIDE_HOURS"];

function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in (detail as object)) return (detail as Structured).message;
  if (Array.isArray(detail) && detail.length) {
    // FastAPI validation errors: [{loc, msg}]
    return detail
      .map((d: { loc?: (string | number)[]; msg?: string }) => {
        const field = d.loc?.filter((x) => x !== "body").join(" › ");
        const msg = (d.msg ?? "").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join("\n");
  }
  return `Request failed (${status})`;
}

export async function api<T = unknown>(
  path: string,
  opts: { method?: string; body?: unknown; form?: FormData; approvalPin?: string } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.approvalPin) headers["X-Approval-Pin"] = opts.approvalPin;
  const token = session.token();
  const bid = session.businessId();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (bid) headers["X-Business-Id"] = bid;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const method = opts.method ?? (opts.body !== undefined || opts.form ? "POST" : "GET");

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api${path}`, {
      method,
      headers,
      body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
    });
  } catch (e) {
    // the server can't be reached: answer from this device where possible (see lib/offline.ts)
    if (method === "GET" && offline.cacheable(path)) {
      const cached = offline.cacheGet<T>(bid, path);
      if (cached !== undefined) return cached;
    }
    if (offline.queueable(method, path) && bid && opts.body && typeof opts.body === "object") {
      throw new offline.OfflineQueuedError(offline.enqueue(bid, path, opts.body as Record<string, unknown>));
    }
    throw new ApiError(0, "You are offline or the server can't be reached — check your internet connection.");
  }
  if (res.status === 204) {
    if (res.ok) announceSave(method, path, opts.body);
    return undefined as T;
  }
  const body = await res.json().catch(() => null);
  if (res.ok) announceSave(method, path, opts.body);
  if (res.ok && method === "GET" && offline.cacheable(path)) offline.cachePut(bid, path, body);
  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/")) {
      session.setToken(null);
      window.location.href = "/login";
    }
    // planned downtime: everyone but super admins is signed out until the platform is live again
    const md = (body as { detail?: { code?: string } })?.detail;
    if (res.status === 503 && md?.code === "MAINTENANCE" && typeof window !== "undefined" && !path.startsWith("/auth/")) {
      session.setToken(null);
      if (!window.location.pathname.startsWith("/login")) window.location.href = "/login?maintenance=1";
    }
    const detail = (body as { detail?: unknown })?.detail as Structured | undefined;
    const structured = detail && typeof detail === "object" ? detail : undefined;
    // an older entry needs a manager's approval: ask for the PIN and retry once
    if (res.status === 403 && structured?.code === "APPROVAL_REQUIRED" && uiHooks.askApprovalPin && !opts.approvalPin) {
      const pin = await uiHooks.askApprovalPin(structured.message);
      if (pin) return api<T>(path, { ...opts, approvalPin: pin });
    }
    if (res.status === 403 && structured?.code && ACCESS_CODES.includes(structured.code)) uiHooks.accessBlocked?.(structured.code, structured.message);
    if (res.status === 402 && (structured?.code === "UPGRADE" || structured?.code === "CREDITS")) uiHooks.showUpgrade?.(structured.message, structured.plan);
    throw new ApiError(res.status, errorMessage(body, res.status), structured?.code, structured?.plan, structured);
  }
  return body as T;
}

export function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  const token = session.token();
  const bid = session.businessId();
  if (token) h.Authorization = `Bearer ${token}`;
  if (bid) h["X-Business-Id"] = bid;
  return h;
}

/** Fetch a file from the API (with auth) and return it as a Blob + suggested name. */
export async function apiBlob(path: string, init?: RequestInit): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${API_URL}/api${path}`, { ...init, headers: authHeaders() });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, errorMessage(body, res.status));
  }
  const cd = res.headers.get("Content-Disposition") ?? "";
  const filename = /filename="?([^"]+)"?/.exec(cd)?.[1] ?? "download";
  return { blob: await res.blob(), filename };
}

export function saveBlob(blob: Blob, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export async function downloadFile(path: string) {
  const { blob, filename } = await apiBlob(path);
  saveBlob(blob, filename);
}

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}
