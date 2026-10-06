"use client";

import { Crown, Hourglass, KeyRound, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Input } from "@/components/ui";
import { api, type ApiError, session, uiHooks } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const PLAN_NAMES: Record<string, string> = { STARTER: "Starter", PROFESSIONAL: "Professional", ENTERPRISE: "Enterprise" };

/** App-wide prompts triggered by API responses: manager approval PIN and plan upgrade. */
export function GlobalDialogs() {
  const [pinAsk, setPinAsk] = useState<{ message: string } | null>(null);
  const [pin, setPin] = useState("");
  const resolver = useRef<((v: string | null) => void) | null>(null);
  const [upgrade, setUpgrade] = useState<{ message: string; plan?: string } | null>(null);
  const [blocked, setBlocked] = useState<{ code: string; message: string } | null>(null);

  useEffect(() => {
    uiHooks.askApprovalPin = (message) =>
      new Promise((resolve) => {
        resolver.current = resolve;
        setPin("");
        setPinAsk({ message });
      });
    uiHooks.showUpgrade = (message, plan) => setUpgrade({ message, plan });
    uiHooks.accessBlocked = (code, message) => setBlocked({ code, message });
    return () => {
      uiHooks.askApprovalPin = undefined;
      uiHooks.showUpgrade = undefined;
      uiHooks.accessBlocked = undefined;
    };
  }, []);

  const answer = (v: string | null) => {
    resolver.current?.(v);
    resolver.current = null;
    setPinAsk(null);
  };

  return (
    <>
      {blocked && <AccessBlocked code={blocked.code} message={blocked.message} />}
      {pinAsk && (
        <Modal title="Manager approval needed" onClose={() => answer(null)}>
          <form onSubmit={(e) => { e.preventDefault(); answer(pin); }} className="space-y-4">
            <p className="flex items-start gap-2 text-sm text-gray-600"><KeyRound size={16} className="mt-0.5 shrink-0" /> {pinAsk.message}. Ask the owner or a store manager to enter their approval PIN.</p>
            <Input type="password" inputMode="numeric" autoFocus maxLength={6} placeholder="4–6 digit PIN" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => answer(null)}>Cancel</Button>
              <Button type="submit" disabled={pin.length < 4}>Approve</Button>
            </div>
          </form>
        </Modal>
      )}
      {upgrade && (
        <Modal title="Upgrade your plan" onClose={() => setUpgrade(null)}>
          <div className="space-y-4 text-sm">
            <p className="flex items-start gap-2 text-gray-700"><Crown size={18} className="mt-0.5 shrink-0 text-amber-500" /> {upgrade.message}</p>
            <p className="text-gray-500">Upgrading takes a minute — pay by UPI, card or net banking and continue right where you left off.</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setUpgrade(null)}>Later</Button>
              <Link href={`/billing${upgrade.plan ? `?plan=${upgrade.plan}` : ""}`} onClick={() => setUpgrade(null)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-brand-700">
                <Crown size={15} /> See {upgrade.plan ? PLAN_NAMES[upgrade.plan] ?? "" : ""} plan
              </Link>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

/** Full-screen notice while a staff sign-in waits for approval or is outside the allowed network / hours. */
function AccessBlocked({ code, message }: { code: string; message: string }) {
  const { logout, me, switchBusiness } = useAuth();
  const waiting = code === "ACCESS_PENDING";
  // while waiting, check again every 10 seconds — the page reloads once the owner approves
  useEffect(() => {
    if (!waiting) return;
    const t = setInterval(() => {
      api("/staff/policy").then(() => window.location.reload(), (e: ApiError) => { if (e.code !== "ACCESS_PENDING") window.location.reload(); });
    }, 10000);
    return () => clearInterval(t);
  }, [waiting]);
  const others = (me?.businesses ?? []).filter((b) => b.id !== session.businessId());
  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-gray-900/60 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 text-center shadow-xl">
        {waiting ? <Hourglass size={36} className="mx-auto text-amber-500" /> : <ShieldAlert size={36} className="mx-auto text-red-600" />}
        <h2 className="mt-3 text-lg font-semibold text-gray-900">{waiting ? "Waiting for approval" : "Sign-in not allowed"}</h2>
        <p className="mt-1 text-sm text-gray-600">{message}</p>
        {waiting && <p className="mt-2 text-xs text-gray-500">This page continues by itself once approved.</p>}
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {others.length > 0 && <Button variant="secondary" onClick={() => switchBusiness(others[0].id)}>Open {others[0].name}</Button>}
          <Button variant="secondary" onClick={() => window.location.reload()}>Check again</Button>
          <Button variant="danger" onClick={logout}>Sign out</Button>
        </div>
      </div>
    </div>
  );
}
