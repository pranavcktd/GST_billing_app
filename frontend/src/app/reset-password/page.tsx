"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { Button, ErrorBox, Field, Input, Loading } from "@/components/ui";
import { api } from "@/lib/api";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (pw !== pw2) return setError("The two passwords do not match");
    setBusy(true);
    setError(null);
    try {
      await api("/auth/reset", { body: { token, new_password: pw } });
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!token) return <ErrorBox message="This link is incomplete — request a new one from the sign-in page." />;
  if (done) {
    return (
      <div className="space-y-4 text-sm">
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">Your password has been changed. All other devices have been signed out.</p>
        <Link href="/login" className="block text-center font-medium text-brand-600 hover:underline">Sign in</Link>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      <ErrorBox message={error} />
      <Field label="New password" hint="At least 8 characters"><Input type="password" required minLength={8} autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
      <Field label="Repeat new password"><Input type="password" required minLength={8} autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} /></Field>
      <Button type="submit" disabled={busy} className="w-full">{busy ? "Saving…" : "Set new password"}</Button>
    </form>
  );
}

export default function ResetPassword() {
  return (
    <AuthCard title="Set a new password" sub="Choose a password you don't use anywhere else">
      <Suspense fallback={<Loading />}><ResetForm /></Suspense>
    </AuthCard>
  );
}
