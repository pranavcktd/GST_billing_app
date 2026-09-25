"use client";

import { LogOut, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { QR } from "@/components/QR";
import { Button, Card, ErrorBox, Field, Input } from "@/components/ui";
import { api, session } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Password, two-factor sign-in, sign out everywhere, and (for managers) the approval PIN. */
export function SecuritySettings({ canApprove }: { canApprove: boolean }) {
  const { me, refresh } = useAuth();
  const [pin, setPin] = useState("");
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [setup, setSetup] = useState<{ secret: string; otpauth_url: string } | null>(null);
  const [code, setCode] = useState("");
  const [disablePw, setDisablePw] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setErr(null); setMsg(null);
    try { await fn(); setMsg(ok); await refresh(); } catch (e) { setErr((e as Error).message); }
  };
  const withToken = async (p: Promise<{ token?: string }>) => {
    const r = await p;
    if (r.token) session.setToken(r.token);
  };

  return (
    <div className="grid max-w-5xl gap-5 md:grid-cols-2">
      <div className="md:col-span-2">
        <ErrorBox message={err} />
        {msg && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}
      </div>

      <Card className="space-y-3 p-5">
        <h2 className="flex items-center gap-2 font-semibold text-gray-900"><ShieldCheck size={17} /> Two-factor sign-in</h2>
        {me?.totp_enabled ? (
          <>
            <p className="text-sm text-emerald-700">On — a code from your authenticator app is needed at every sign-in.</p>
            <Field label="Password"><Input type="password" value={disablePw} onChange={(e) => setDisablePw(e.target.value)} /></Field>
            <Field label="Current 6-digit code"><Input inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></Field>
            <Button variant="danger" disabled={!disablePw || code.length < 6} onClick={() => run(() => api("/auth/2fa/disable", { body: { code, password: disablePw } }), "Two-factor sign-in turned off")}>Turn off</Button>
          </>
        ) : setup ? (
          <>
            <p className="text-sm text-gray-600">Scan with Google Authenticator, Microsoft Authenticator or Authy, then enter the code it shows.</p>
            <div className="flex items-center gap-4">
              <QR value={setup.otpauth_url} size={140} />
              <div className="text-xs text-gray-500">Can&apos;t scan? Enter this key:<div className="mt-1 font-mono text-sm break-all text-gray-800">{setup.secret}</div></div>
            </div>
            <Field label="6-digit code"><Input inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></Field>
            <Button disabled={code.length < 6} onClick={() => run(async () => { await api("/auth/2fa/enable", { body: { code } }); setSetup(null); setCode(""); }, "Two-factor sign-in is on")}>Verify & turn on</Button>
          </>
        ) : (
          <>
            <p className="text-sm text-gray-600">Protect your account even if someone learns your password. Strongly recommended for owners and administrators.</p>
            <Button onClick={() => run(async () => setSetup(await api("/auth/2fa/setup", { body: {} })), "Scan the QR code to continue")}>Set up two-factor sign-in</Button>
          </>
        )}
      </Card>

      <Card className="space-y-3 p-5">
        <h2 className="font-semibold text-gray-900">Change password</h2>
        <Field label="Current password"><Input type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
        <Field label="New password" hint="At least 8 characters"><Input type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
        <div className="flex justify-end">
          <Button disabled={pw.new_password.length < 8 || !pw.current_password} onClick={() => run(async () => {
            await withToken(api("/auth/password", { method: "PUT", body: pw }));
            setPw({ current_password: "", new_password: "" });
          }, "Password changed — other devices were signed out")}>Change password</Button>
        </div>
      </Card>

      <Card className="space-y-3 p-5">
        <h2 className="flex items-center gap-2 font-semibold text-gray-900"><LogOut size={17} /> Sessions</h2>
        <p className="text-sm text-gray-600">Lost a phone or used a shared computer? Sign out of every device except this one.</p>
        <Button variant="secondary" onClick={() => run(() => withToken(api("/auth/logout-all", { body: {} })), "Signed out of all other devices")}>Sign out everywhere else</Button>
      </Card>

      {canApprove && (
        <Card className="space-y-3 p-5">
          <h2 className="font-semibold text-gray-900">My approval PIN</h2>
          <p className="text-sm text-gray-600">Staff without the “edit past entries” right need a manager&apos;s PIN to change or cancel an older bill.</p>
          <Input type="password" inputMode="numeric" maxLength={6} placeholder="New 4–6 digit PIN" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => run(() => api("/me/approval-pin", { method: "PUT", body: { pin: null } }), "PIN removed")}>Remove PIN</Button>
            <Button disabled={pin.length < 4} onClick={() => run(async () => { await api("/me/approval-pin", { method: "PUT", body: { pin } }); setPin(""); }, "Approval PIN saved")}>Save PIN</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
