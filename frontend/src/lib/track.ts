/**
 * First-party analytics (Admin → Analytics). A random id kept in this browser — no IP address, nothing sent to a third
 * party. Every call is fire-and-forget and never shows an error.
 */

import { API_URL, authHeaders } from "@/lib/api";

const VID = "sh-visitor";
let enabled = true;
let respectDnt = true;

export function configureTracking(opts: { enabled: boolean; respect_dnt: boolean } | undefined) {
  if (!opts) return;
  enabled = opts.enabled;
  respectDnt = opts.respect_dnt;
}

function allowed(): boolean {
  if (!enabled || typeof window === "undefined") return false;
  const dnt = navigator.doNotTrack === "1" || (window as unknown as { doNotTrack?: string }).doNotTrack === "1";
  return !(respectDnt && dnt);
}

export function visitorId(): string | null {
  try {
    let v = localStorage.getItem(VID);
    if (!v) {
      v = (crypto.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`).slice(0, 40);
      localStorage.setItem(VID, v);
    }
    return v;
  } catch {
    return null;
  }
}

function send(path: string, body: Record<string, unknown>, auth = false) {
  fetch(`${API_URL}/api${path}`, {
    method: "POST", keepalive: true,
    headers: { "Content-Type": "application/json", ...(auth ? authHeaders() : {}) },
    body: JSON.stringify(body),
  }).catch(() => {});
}

/** A page of the public website was opened. */
export function trackVisit(path: string) {
  const visitor = allowed() ? visitorId() : null;
  if (!visitor) return;
  const q = new URLSearchParams(window.location.search);
  send("/track/visit", { visitor, path, referrer: document.referrer || null, utm_source: q.get("utm_source"), utm_campaign: q.get("utm_campaign") }, true);
}

/** Plan interest: pricing seen, a plan clicked, the billing cycle changed. Signed-in users are counted as users. */
export function trackEvent(kind: "PRICING_VIEW" | "PLAN_CLICK" | "CYCLE", data: { plan?: string; cycle?: string } = {}) {
  const signedIn = Boolean(authHeaders().Authorization);
  if (!signedIn && !allowed()) return;
  send("/track/event", { visitor: allowed() ? visitorId() : null, kind, page: window.location.pathname, ...data }, true);
}

let lastModule = "";
let lastAt = 0;
/** A signed-in person opened a module of the app (repeat opens within 20 seconds count once). */
export function trackUsage(module: string | undefined) {
  if (!module || !enabled || typeof window === "undefined") return;
  const now = Date.now();
  if (module === lastModule && now - lastAt < 20000) return;
  lastModule = module;
  lastAt = now;
  send("/track/usage", { module }, true);
}
