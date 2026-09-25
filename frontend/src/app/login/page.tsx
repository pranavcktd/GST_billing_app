"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me } from "@/lib/types";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [needOtp, setNeedOtp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<Me & { token: string }>("/auth/login", { body: { email, password, otp: needOtp ? otp : undefined } });
      login(res.token, res);
      if (res.must_change_password) router.replace("/change-password");
      else if (res.businesses.length) router.replace("/dashboard");
      else router.replace(res.platform_role === "SUPERADMIN" ? "/admin" : res.platform_role === "RESELLER" ? "/reseller" : "/onboarding");
    } catch (err) {
      if (err instanceof ApiError && err.code === "OTP_REQUIRED") {
        if (needOtp) setError(err.message);
        setNeedOtp(true);
      } else {
        setError((err as Error).message);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Welcome back" sub="Sign in to manage your billing">
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox message={error} />
        {!needOtp ? (
          <>
            <Field label="Email">
              <Input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Field label="Password">
              <Input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <div className="text-right text-sm">
              <Link href="/forgot-password" className="text-brand-600 hover:underline">Forgot password?</Link>
            </div>
          </>
        ) : (
          <Field label="Authenticator code" hint="Open Google Authenticator / Microsoft Authenticator and enter the 6-digit code">
            <Input autoFocus inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} className="text-center text-lg tracking-widest" />
          </Field>
        )}
        <Button type="submit" disabled={busy || (needOtp && otp.length < 6)} className="w-full">
          {busy ? "Signing in…" : needOtp ? "Verify & sign in" : "Sign in"}
        </Button>
        {needOtp && (
          <button type="button" className="w-full text-center text-sm text-gray-500 hover:underline" onClick={() => { setNeedOtp(false); setOtp(""); }}>
            Back
          </button>
        )}
        <p className="text-center text-sm text-gray-600">
          New here?{" "}
          <Link href="/register" className="font-medium text-brand-600 hover:underline">Create an account</Link>
        </p>
      </form>
    </AuthCard>
  );
}
