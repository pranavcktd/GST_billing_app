"use client";

import { useEffect } from "react";
import { GlobalDialogs } from "@/components/GlobalDialogs";
import { Toaster } from "@/components/Toaster";
import { AuthProvider } from "@/lib/auth";
import { ConfigProvider } from "@/lib/config";
import { LegalConsentGate } from "@/components/LegalConsentGate";
import { SiteExtras } from "@/components/SiteExtras";

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    if (process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    } else {
      // development: a worker left over from a production run would keep serving old pages and scripts
      navigator.serviceWorker.getRegistrations().then(async (regs) => {
        if (!regs.length) return;
        await Promise.all(regs.map((r) => r.unregister()));
        if ("caches" in window) await Promise.all((await caches.keys()).map((k) => caches.delete(k)));
        location.reload();
      }).catch(() => {});
    }
  }, []);
  return (
    <ConfigProvider>
      <AuthProvider>
        {children}
        <GlobalDialogs />
        <LegalConsentGate />
        <Toaster />
        <SiteExtras />
      </AuthProvider>
    </ConfigProvider>
  );
}
