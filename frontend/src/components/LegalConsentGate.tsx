"use client";

import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, ErrorBox } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** When the Terms / Privacy Policy change, every signed-in user accepts the new version before continuing. */
export function LegalConsentGate() {
  const { me, refresh, logout } = useAuth();
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (!me || me.legal_ok !== false) return null;
  return (
    <Modal title="Updated terms and privacy policy" onClose={() => {}}>
      <div className="space-y-3 text-sm">
        <p className="flex items-start gap-2 text-gray-700"><ShieldCheck size={18} className="mt-0.5 shrink-0 text-brand-600" />
          We have updated our policies. Please read and accept them to continue using your account.</p>
        <ul className="ml-5 list-disc text-gray-700">
          <li><Link href="/terms" target="_blank" className="text-brand-600 underline">Terms of Service</Link></li>
          <li><Link href="/privacy" target="_blank" className="text-brand-600 underline">Privacy Policy</Link></li>
          <li><Link href="/dpa" target="_blank" className="text-brand-600 underline">Data Processing Addendum</Link></li>
        </ul>
        <label className="flex items-start gap-2"><input type="checkbox" className="mt-1" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          <span>I have read and agree to the updated Terms of Service, Privacy Policy and Data Processing Addendum.</span></label>
        <ErrorBox message={err} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={logout}>Sign out</Button>
          <Button disabled={!agree || busy} onClick={async () => {
            setBusy(true); setErr(null);
            try { await api("/auth/legal/accept", { body: {} }); await refresh(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
          }}>Accept and continue</Button>
        </div>
      </div>
    </Modal>
  );
}
