"use client";

import { Mail, MessageCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { GoogleButton } from "@/components/GoogleButton";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useConfig } from "@/lib/config";
import type { Me } from "@/lib/types";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const wa = useConfig().whatsapp;
  const waLogin = !!wa?.login;
  const sandboxMode = !!wa?.sandbox;
  const [mode, setMode] = useState<"email" | "whatsapp">("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [sandboxCode, setSandboxCode] = useState<string | null>(null);
  const [wait, setWait] = useState(0);
  const [otp, setOtp] = useState("");
  const [needOtp, setNeedOtp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  function done(res: Me & { token: string }) {
    login(res.token, res);
    if (res.must_change_password) router.replace("/change-password");
    else if (res.businesses.length) router.replace("/dashboard");
    else router.replace(res.platform_role === "SUPERADMIN" ? "/admin" : res.platform_role === "RESELLER" ? "/reseller" : "/onboarding");
  }

  async function sendCode() {
    setBusy(true); setError(null);
    try {
      const r = await api<{ to: string; resend_in: number; sandbox_code?: string }>("/auth/otp/send", { body: { phone, purpose: "LOGIN" } });
      setSentTo(r.to); setWait(r.resend_in); setCode(""); setSandboxCode(r.sandbox_code ?? null);
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "whatsapp" && !sentTo) return sendCode();
    setBusy(true);
    setError(null);
    try {
      const otpPart = needOtp ? otp : undefined;
      done(mode === "email"
        ? await api<Me & { token: string }>("/auth/login", { body: { email, password, otp: otpPart } })
        : await api<Me & { token: string }>("/auth/otp/login", { body: { phone, code, otp: otpPart } }));
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

  const tab = (m: typeof mode, icon: React.ReactNode, label: string) => (
    <button type="button" onClick={() => { setMode(m); setError(null); setNeedOtp(false); }}
      className={`flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 text-sm font-medium ${mode === m ? "bg-white text-gray-900 shadow-sm" : "text-gray-600"}`}>
      {icon}{label}
    </button>
  );

  return (
    <AuthCard title="Welcome back" sub="Sign in to manage your billing">
      {!needOtp && <GoogleButton text="signin_with" />}
      <form onSubmit={submit} className="space-y-4">
        {waLogin && !needOtp && (
          <div className="flex rounded-lg bg-gray-100 p-1">
            {tab("email", <Mail size={15} />, "E-mail")}
            {tab("whatsapp", <MessageCircle size={15} className="text-emerald-600" />, "WhatsApp")}
          </div>
        )}
        <ErrorBox message={error} />
        {needOtp ? (
          <Field label="Authenticator code" hint="Open Google Authenticator / Microsoft Authenticator and enter the 6-digit code">
            <Input autoFocus inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} className="text-center text-lg tracking-widest" />
          </Field>
        ) : mode === "email" ? (
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
          <>
            <Field label="Mobile number" hint={sentTo ? undefined : "We'll send a 6-digit code to this number on WhatsApp"}>
              <div className="flex">
                <span className="inline-flex items-center rounded-l-lg border border-r-0 border-gray-300 bg-gray-50 px-3 text-sm text-gray-600">+91</span>
                <Input type="tel" inputMode="numeric" autoComplete="tel-national" required maxLength={10} className="rounded-l-none"
                  value={phone} onChange={(e) => { setPhone(e.target.value.replace(/\D/g, "")); setSentTo(null); }} />
              </div>
            </Field>
            {sentTo && (
              <>
                {sandboxCode && <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900"><b>Sandbox</b> — no WhatsApp message was sent. Your code is <b className="font-mono text-sm tracking-widest">{sandboxCode}</b></p>}
                <Field label="Code from WhatsApp" hint={`If ${sentTo} is linked to an account, the code is on its way. It works for 5 minutes.`}>
                  <Input autoFocus inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} className="text-center text-lg tracking-widest" />
                </Field>
                <div className="text-right text-sm">
                  <button type="button" disabled={wait > 0 || busy} onClick={sendCode} className="text-brand-600 hover:underline disabled:text-gray-400 disabled:no-underline">
                    {wait > 0 ? `Send again in ${wait}s` : "Send again"}
                  </button>
                </div>
              </>
            )}
            <p className="text-xs text-gray-500">No code? Sign in with e-mail once and link your mobile in Settings → Security.</p>
            {sandboxMode && !sentTo && <p className="text-xs text-amber-700">Sandbox mode: codes are shown here instead of being sent on WhatsApp.</p>}
          </>
        )}
        <Button type="submit" className="w-full"
          disabled={busy || (needOtp && otp.length < 6) || (mode === "whatsapp" && !needOtp && (phone.length !== 10 || (!!sentTo && code.length < 6)))}>
          {busy ? "Please wait…" : needOtp ? "Verify & sign in" : mode === "whatsapp" && !sentTo ? "Send code on WhatsApp" : "Sign in"}
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
