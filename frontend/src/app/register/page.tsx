"use client";

import { Mail, MessageCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { GoogleButton } from "@/components/GoogleButton";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useConfig } from "@/lib/config";
import type { Me } from "@/lib/types";

type Way = "WHATSAPP" | "EMAIL";

function SandboxNote({ code }: { code: string }) {
  return (
    <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
      <b>Sandbox</b> — no message was sent. Your code is <b className="font-mono text-sm tracking-widest">{code}</b>
    </p>
  );
}

export default function RegisterPage() {
  const { login } = useAuth();
  const router = useRouter();
  const cfg = useConfig();
  // verification channels chosen by the platform (older servers: WhatsApp's switch)
  const ways: Way[] = (cfg.signup?.verify as Way[] | undefined) ?? (cfg.whatsapp?.signup_verify ? ["WHATSAPP"] : []);
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "" });
  const [way, setWay] = useState<Way | null>(null);
  const [code, setCode] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [sandboxCode, setSandboxCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const active: Way | null = ways.length ? (way && ways.includes(way) ? way : ways[0]) : null;
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  async function sendCode() {
    setError(null);
    try {
      const r = active === "EMAIL"
        ? await api<{ to: string; sandbox_code?: string }>("/auth/email-code", { body: { email: form.email } })
        : await api<{ to: string; sandbox_code?: string }>("/auth/otp/send", { body: { phone: form.phone, purpose: "SIGNUP" } });
      setSent(r.to); setSandboxCode(r.sandbox_code ?? null); setCode("");
    } catch (err) { setError((err as Error).message); }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<Me & { token: string }>("/auth/register", {
        body: { ...form, phone_code: active === "WHATSAPP" ? code : undefined, email_code: active === "EMAIL" ? code : undefined },
      });
      login(res.token, res);
      router.replace("/onboarding");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const pickWay = (w: Way) => { setWay(w); setSent(null); setCode(""); setSandboxCode(null); };

  return (
    <AuthCard title="Create your account" sub="Start billing in under two minutes">
      <GoogleButton text="signup_with" />
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox message={error} />
        <Field label="Your name" required>
          <Input required minLength={2} value={form.name} onChange={set("name")} />
        </Field>

        {ways.length > 1 && (
          <div>
            <div className="mb-1 text-xs font-medium text-gray-600">Verify with</div>
            <div className="flex rounded-lg bg-gray-100 p-1">
              {ways.map((w) => (
                <button key={w} type="button" onClick={() => pickWay(w)}
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 text-sm font-medium ${active === w ? "bg-white text-gray-900 shadow-sm" : "text-gray-600"}`}>
                  {w === "WHATSAPP" ? <><MessageCircle size={15} className="text-emerald-600" /> WhatsApp</> : <><Mail size={15} /> E-mail</>}
                </button>
              ))}
            </div>
          </div>
        )}

        <Field label="Email" required hint={active === "EMAIL" ? (sent ? `Code sent to ${sent}` : "We'll send a code to confirm it") : undefined}>
          <div className="flex gap-2">
            <Input type="email" required autoComplete="email" value={form.email}
              onChange={(e) => { setForm({ ...form, email: e.target.value }); if (active === "EMAIL") setSent(null); }} />
            {active === "EMAIL" && <Button type="button" variant="secondary" className="shrink-0 whitespace-nowrap" disabled={!/^\S+@\S+\.\S+$/.test(form.email)} onClick={sendCode}>{sent ? "Resend" : "Send code"}</Button>}
          </div>
        </Field>

        <Field label={active === "WHATSAPP" ? "Mobile number (WhatsApp)" : "Mobile number"} required={active === "WHATSAPP"}
          hint={active === "WHATSAPP" ? (sent ? `Code sent to ${sent} on WhatsApp` : "We'll verify it with a code on WhatsApp") : undefined}>
          <div className="flex gap-2">
            <Input type="tel" inputMode="numeric" maxLength={active === "WHATSAPP" ? 10 : 15} required={active === "WHATSAPP"} value={form.phone}
              onChange={(e) => { setForm({ ...form, phone: active === "WHATSAPP" ? e.target.value.replace(/\D/g, "") : e.target.value }); if (active === "WHATSAPP") setSent(null); }} />
            {active === "WHATSAPP" && <Button type="button" variant="secondary" className="shrink-0 whitespace-nowrap" disabled={form.phone.length !== 10} onClick={sendCode}>{sent ? "Resend" : "Send code"}</Button>}
          </div>
        </Field>

        {active && sent && (
          <>
            {sandboxCode && <SandboxNote code={sandboxCode} />}
            <Field label={active === "EMAIL" ? "Code from your e-mail" : "Code from WhatsApp"} required>
              <Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
            </Field>
          </>
        )}

        <Field label="Password" hint="At least 8 characters" required>
          <Input type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={set("password")} />
        </Field>
        <Button type="submit" disabled={busy || (!!active && code.length !== 6)} className="w-full">
          {busy ? "Creating account…" : "Create account"}
        </Button>
        <p className="text-center text-xs text-gray-500">
          By creating an account you agree to the <Link href="/terms" className="underline">Terms of Service</Link>,{" "}
          <Link href="/privacy" className="underline">Privacy Policy</Link> and <Link href="/disclaimer" className="underline">Disclaimer</Link>.
        </p>
        <p className="text-center text-sm text-gray-600">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-brand-600 hover:underline">Sign in</Link>
        </p>
      </form>
    </AuthCard>
  );
}
