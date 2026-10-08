"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { useConfig } from "@/lib/config";
import { useAuth } from "@/lib/auth";
import type { Me } from "@/lib/types";

export default function RegisterPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const verify = !!useConfig().whatsapp?.signup_verify;
  const [code, setCode] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [sandboxCode, setSandboxCode] = useState<string | null>(null);

  async function sendCode() {
    setError(null);
    try {
      const r = await api<{ to: string; sandbox_code?: string }>("/auth/otp/send", { body: { phone: form.phone, purpose: "SIGNUP" } });
      setSent(r.to); setSandboxCode(r.sandbox_code ?? null);
    } catch (err) { setError((err as Error).message); }
  }
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<Me & { token: string }>("/auth/register", { body: { ...form, phone_code: verify ? code : undefined } });
      login(res.token, res);
      router.replace("/onboarding");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Create your account" sub="Start billing in under two minutes">
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox message={error} />
        <Field label="Your name" required>
          <Input required minLength={2} value={form.name} onChange={set("name")} />
        </Field>
        <Field label="Email" required>
          <Input type="email" required autoComplete="email" value={form.email} onChange={set("email")} />
        </Field>
        {verify ? (
          <>
            <Field label="Mobile number (WhatsApp)" required hint={sent ? `Code sent to ${sent} on WhatsApp` : "We'll verify it with a code on WhatsApp"}>
              <div className="flex gap-2">
                <Input type="tel" inputMode="numeric" maxLength={10} required value={form.phone}
                  onChange={(e) => { setForm({ ...form, phone: e.target.value.replace(/\D/g, "") }); setSent(null); }} />
                <Button type="button" variant="secondary" disabled={form.phone.length !== 10} onClick={sendCode}>{sent ? "Resend" : "Send code"}</Button>
              </div>
            </Field>
            {sent && sandboxCode && <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900"><b>Sandbox</b> — no WhatsApp message was sent. Your code is <b className="font-mono text-sm tracking-widest">{sandboxCode}</b></p>}
            {sent && (
              <Field label="Code from WhatsApp" required>
                <Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
              </Field>
            )}
          </>
        ) : (
          <Field label="Mobile number">
            <Input type="tel" value={form.phone} onChange={set("phone")} />
          </Field>
        )}
        <Field label="Password" hint="At least 8 characters" required>
          <Input type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={set("password")} />
        </Field>
        <Button type="submit" disabled={busy || (verify && code.length !== 6)} className="w-full">
          {busy ? "Creating account…" : "Create account"}
        </Button>
        <p className="text-center text-xs text-gray-500">
          By creating an account you agree to the <Link href="/terms" className="underline">Terms of Service</Link>,{" "}
          <Link href="/privacy" className="underline">Privacy Policy</Link> and <Link href="/disclaimer" className="underline">Disclaimer</Link>.
        </p>
        <p className="text-center text-sm text-gray-600">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-brand-600 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </AuthCard>
  );
}
