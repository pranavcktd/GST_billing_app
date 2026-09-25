"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState<{ message: string; dev_temp_password?: string } | null>(null);
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
    <AuthCard title="Forgot password" sub="We'll e-mail you a temporary password">
      {done ? (
        <div className="space-y-4 text-sm">
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">{done.message}</p>
          <ul className="list-disc space-y-1 pl-5 text-gray-600">
            <li>The temporary password works once and expires in 60 minutes.</li>
            <li>Your current password keeps working until you sign in with the temporary one.</li>
            <li>Not in your inbox? Check spam, or ask your administrator.</li>
          </ul>
          {done.dev_temp_password && (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Development mode (e-mail not set up) — temporary password: <b className="font-mono text-sm">{done.dev_temp_password}</b>
            </p>
          )}
          <Link href="/login" className="block rounded-lg bg-brand-600 py-2 text-center font-medium text-white hover:bg-brand-700">Go to sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <ErrorBox message={error} />
          <Field label="Registered e-mail"><Input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <Button type="submit" disabled={busy} className="w-full">{busy ? "Sending…" : "E-mail me a temporary password"}</Button>
          <Link href="/login" className="block text-center text-sm text-gray-600 hover:underline">Back to sign in</Link>
        </form>
      )}
    </AuthCard>
  );
}
