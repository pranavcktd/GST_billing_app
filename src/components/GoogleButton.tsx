"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useConfig } from "@/lib/config";
import type { Me } from "@/lib/types";

declare global {
  interface Window {
    google?: { accounts: { id: {
      initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: string }) => void;
      renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
    } } };
  }
}

function loadGis(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const existing = document.getElementById("gis-script");
    if (existing) { existing.addEventListener("load", () => resolve()); return; }
    const s = document.createElement("script");
    s.id = "gis-script";
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Could not load Google sign-in"));
    document.head.appendChild(s);
  });
}

/** "Continue with Google" — shown only when the super admin has switched it on. New users go straight to business details. */
export function GoogleButton({ text = "continue_with" }: { text?: "continue_with" | "signup_with" | "signin_with" }) {
  const clientId = useConfig().signup?.google_client_id;
  const { login } = useAuth();
  const router = useRouter();
  const box = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null); // credential waiting for the 2FA code
  const [otp, setOtp] = useState("");

  async function finish(credential: string, code?: string) {
    setErr(null);
    try {
      const res = await api<Me & { token: string }>("/auth/google", { body: { credential, otp: code } });
      login(res.token, res);
      router.replace(res.businesses.length ? "/dashboard" : res.platform_role === "SUPERADMIN" || res.platform_role === "TEAM" ? "/admin" : "/onboarding");
    } catch (e) {
      if (e instanceof ApiError && e.code === "OTP_REQUIRED") { setPending(credential); if (code) setErr(e.message); }
      else setErr((e as Error).message);
    }
  }

  useEffect(() => {
    if (!clientId || !box.current) return;
    let alive = true;
    loadGis().then(() => {
      if (!alive || !box.current || !window.google) return;
      window.google.accounts.id.initialize({ client_id: clientId, callback: (r) => finish(r.credential) });
      window.google.accounts.id.renderButton(box.current, { theme: "outline", size: "large", width: box.current.offsetWidth || 320, text, shape: "rectangular" });
    }).catch((e) => setErr((e as Error).message));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, text]);

  if (!clientId) return null;
  return (
    <div className="space-y-3">
      <div ref={box} className="flex min-h-10 w-full justify-center" />
      <p className="text-center text-[11px] text-gray-500">By continuing with Google you agree to the{" "}
        <a href="/terms" target="_blank" className="underline">Terms</a>, <a href="/privacy" target="_blank" className="underline">Privacy Policy</a> and{" "}
        <a href="/dpa" target="_blank" className="underline">Data Processing Addendum</a>.</p>
      <ErrorBox message={err} />
      {pending && (
        <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); finish(pending, otp); }}>
          <Field label="Authenticator code"><Input autoFocus inputMode="numeric" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} /></Field>
          <Button type="submit" className="w-full" disabled={otp.length < 6}>Verify & continue</Button>
        </form>
      )}
      <div className="flex items-center gap-3 text-xs text-gray-400"><span className="h-px flex-1 bg-gray-200" />or<span className="h-px flex-1 bg-gray-200" /></div>
    </div>
  );
}
