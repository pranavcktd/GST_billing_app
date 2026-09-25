"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me } from "@/lib/types";

export default function RegisterPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<Me & { token: string }>("/auth/register", { body: form });
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
        <Field label="Mobile number">
          <Input type="tel" value={form.phone} onChange={set("phone")} />
        </Field>
        <Field label="Password" hint="At least 8 characters" required>
          <Input type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={set("password")} />
        </Field>
        <Button type="submit" disabled={busy} className="w-full">
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
