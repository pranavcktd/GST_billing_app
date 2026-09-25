"use client";

import { useEffect } from "react";
import { GlobalDialogs } from "@/components/GlobalDialogs";
import { AuthProvider } from "@/lib/auth";

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return (
    <AuthProvider>
      {children}
      <GlobalDialogs />
    </AuthProvider>
  );
}
