"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { api, session } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Shown after signing in with a temporary password. */
export default function ChangePassword() {
  const { refresh } = useAuth();
  const router = useRouter();
  const [f, setF] = useState({ current_password: "", new_password: "", repeat: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (f.new_password !== f.repeat) return setError("The two new passwords do not match");
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ token: string }>("/auth/password", { method: "PUT", body: { current_password: f.current_password, new_password: f.new_password } });
      session.setToken(r.token);
      const me = await refresh();
      router.replace(me?.businesses.length ? "/dashboard" : me?.platform_role === "SUPERADMIN" ? "/admin" : me?.platform_role === "RESELLER" ? "/reseller" : "/onboarding");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Choose your own password" sub="You signed in with a temporary password — please replace it">
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox message={error} />
        <Field label="Temporary / current password"><Input type="password" required value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} /></Field>
        <Field label="New password" hint="At least 8 characters"><Input type="password" required minLength={8} autoComplete="new-password" value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} /></Field>
        <Field label="Repeat new password"><Input type="password" required minLength={8} autoComplete="new-password" value={f.repeat} onChange={(e) => setF({ ...f, repeat: e.target.value })} /></Field>
        <Button type="submit" disabled={busy} className="w-full">{busy ? "Saving…" : "Save password"}</Button>
      </form>
    </AuthCard>
  );
}
