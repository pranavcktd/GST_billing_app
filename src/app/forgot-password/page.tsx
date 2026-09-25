"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState<{ message: string; dev_link?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setDone(await api("/auth/forgot", { body: { email } }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Forgot password" sub="We'll e-mail you a link to set a new password">
      {done ? (
        <div className="space-y-4 text-sm">
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">{done.message} The link is valid for 30 minutes.</p>
          {done.dev_link && (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Development mode (e-mail not set up): <Link href={done.dev_link.replace(/^https?:\/\/[^/]+/, "")} className="font-medium underline">open the reset link</Link>
            </p>
          )}
          <Link href="/login" className="block text-center text-brand-600 hover:underline">Back to sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <ErrorBox message={error} />
          <Field label="Email"><Input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <Button type="submit" disabled={busy} className="w-full">{busy ? "Sending…" : "Send reset link"}</Button>
          <Link href="/login" className="block text-center text-sm text-gray-600 hover:underline">Back to sign in</Link>
        </form>
      )}
    </AuthCard>
  );
}
