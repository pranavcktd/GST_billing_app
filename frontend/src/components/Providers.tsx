"use client";

import { useEffect } from "react";
import { GlobalDialogs } from "@/components/GlobalDialogs";
import { AuthProvider } from "@/lib/auth";
import { ConfigProvider } from "@/lib/config";

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return (
    <ConfigProvider>
      <AuthProvider>
        {children}
        <GlobalDialogs />
      </AuthProvider>
    </ConfigProvider>
  );
}
