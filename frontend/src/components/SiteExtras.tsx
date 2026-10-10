"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useConfig } from "@/lib/config";
import { configureTracking, trackVisit } from "@/lib/track";

/** Pages of the public website (the rest is the app). */
const WEBSITE = ["/", "/terms", "/privacy", "/dpa", "/security", "/refund", "/disclaimer", "/grievance", "/contact", "/login", "/register", "/forgot-password"];
const NO_CHAT = ["/print", "/receipt", "/i/"]; // printable pages and shared invoices

type Tawk = {
  visitor?: { name?: string; email?: string; hash?: string };
  customStyle?: unknown;
  onLoad?: () => void;
  hideWidget?: () => void;
  showWidget?: () => void;
  setAttributes?: (a: Record<string, string>, cb?: (e?: unknown) => void) => void;
};
declare global {
  interface Window { Tawk_API?: Tawk; Tawk_LoadStart?: Date }
}

let loaded = false;
let identified = "";

async function identity(): Promise<{ name: string | null; email: string | null; hash: string | null } | null> {
  try { return await api("/track/chat-identity"); } catch { return null; }
}

/** First-party page views of the website, and the tawk.to live chat when the super admin switches it on. */
export function SiteExtras() {
  const pathname = usePathname();
  const config = useConfig();
  const { me } = useAuth();
  const chat = config.live_chat;
  const isWebsite = WEBSITE.includes(pathname);

  useEffect(() => { configureTracking(config.analytics); }, [config.analytics]);
  useEffect(() => { if (isWebsite) trackVisit(pathname); }, [pathname, isWebsite]);

  const show = Boolean(chat?.enabled && chat.property_id) && !NO_CHAT.some((p) => pathname.startsWith(p))
    && (chat!.show_on === "BOTH" || (chat!.show_on === "WEBSITE" ? isWebsite : !isWebsite));

  useEffect(() => {
    if (!chat?.enabled || !chat.property_id) return;
    const api_ = window.Tawk_API;
    if (loaded) {
      if (show) api_?.showWidget?.(); else api_?.hideWidget?.();
      return;
    }
    if (!show) return;
    loaded = true;
    (async () => {
      const t: Tawk = (window.Tawk_API = window.Tawk_API || {});
      window.Tawk_LoadStart = new Date();
      // keep clear of the Help button and the phone menu bar
      t.customStyle = { visibility: { desktop: { position: "br", xOffset: 20, yOffset: 80 }, mobile: { position: "br", xOffset: 12, yOffset: 140 } } };
      if (me && chat.pass_user) {
        const who = await identity();
        if (who?.email) {
          t.visitor = { name: who.name ?? undefined, email: who.email, ...(who.hash ? { hash: who.hash } : {}) };
          identified = who.email;
        }
      }
      const s = document.createElement("script");
      s.async = true;
      s.src = `https://embed.tawk.to/${encodeURIComponent(chat.property_id)}/${encodeURIComponent(chat.widget_id || "default")}`;
      s.charset = "UTF-8";
      s.setAttribute("crossorigin", "*");
      document.body.appendChild(s);
    })();
  }, [show, chat, me]);

  // signed in after the chat was already open: tell tawk.to who this is
  useEffect(() => {
    if (!loaded || !me || !chat?.pass_user || identified === me.user.email) return;
    identified = me.user.email;
    identity().then((who) => {
      if (who?.email) window.Tawk_API?.setAttributes?.({ name: who.name ?? "", email: who.email, ...(who.hash ? { hash: who.hash } : {}) });
    });
  }, [me, chat?.pass_user]);

  return null;
}
