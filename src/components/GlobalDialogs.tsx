"use client";

import { Crown, KeyRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Input } from "@/components/ui";
import { uiHooks } from "@/lib/api";

const PLAN_NAMES: Record<string, string> = { STARTER: "Starter", PROFESSIONAL: "Professional", ENTERPRISE: "Enterprise" };

/** App-wide prompts triggered by API responses: manager approval PIN and plan upgrade. */
export function GlobalDialogs() {
  const [pinAsk, setPinAsk] = useState<{ message: string } | null>(null);
  const [pin, setPin] = useState("");
  const resolver = useRef<((v: string | null) => void) | null>(null);
  const [upgrade, setUpgrade] = useState<{ message: string; plan?: string } | null>(null);

  useEffect(() => {
    uiHooks.askApprovalPin = (message) =>
      new Promise((resolve) => {
        resolver.current = resolve;
        setPin("");
        setPinAsk({ message });
      });
    uiHooks.showUpgrade = (message, plan) => setUpgrade({ message, plan });
    return () => {
      uiHooks.askApprovalPin = undefined;
      uiHooks.showUpgrade = undefined;
    };
  }, []);

  const answer = (v: string | null) => {
    resolver.current?.(v);
    resolver.current = null;
    setPinAsk(null);
  };

  return (
    <>
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
