"use client";

import { BadgeCheck, Loader2 } from "lucide-react";
import { useState } from "react";
import { Input } from "@/components/ui";
import { api } from "@/lib/api";

export interface IfscInfo {
  ifsc: string; bank: string | null; branch: string | null; address: string | null; city: string | null;
  district: string | null; state: string | null; upi: boolean; neft: boolean; rtgs: boolean; imps: boolean;
}

const VALID = /^[A-Z]{4}0[A-Z0-9]{6}$/;
const title = (s: string | null) => (s ?? "").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()).trim();

/** "Laxmi Road, Pune" from the branch and city the IFSC service returned. */
export function branchText(i: IfscInfo): string {
  const b = title(i.branch), c = title(i.city);
  return c && !b.toLowerCase().includes(c.toLowerCase()) ? `${b}, ${c}` : b;
}

/**
 * IFSC box: when 11 valid characters are typed it looks the branch up and calls `onFound`, so the form can fill the bank
 * name / branch. Everything stays editable; if the lookup fails the user simply types the details.
 */
export function IfscInput({ value, onChange, onFound }: { value: string; onChange: (v: string) => void; onFound?: (i: IfscInfo) => void }) {
  const [state, setState] = useState<{ busy?: boolean; info?: IfscInfo; error?: string; code?: string }>({});

  async function look(code: string) {
    if (!VALID.test(code) || state.code === code) return;
    setState({ busy: true, code });
    try {
      const info = await api<IfscInfo>(`/ifsc/${code}`);
      setState({ info, code });
      onFound?.(info);
    } catch (e) {
      setState({ error: (e as Error).message, code });
    }
  }

  return (
    <div>
      <div className="relative">
        <Input value={value} maxLength={11} className="pr-8 uppercase" placeholder="e.g. HDFC0001234" autoComplete="off"
          onChange={(e) => { const v = e.target.value.toUpperCase().replace(/\s/g, ""); onChange(v); if (v.length === 11) look(v); else setState({}); }}
          onBlur={() => look(value)} />
        {state.busy && <Loader2 size={15} className="absolute top-1/2 right-2.5 -translate-y-1/2 animate-spin text-gray-400" />}
        {state.info && <BadgeCheck size={15} className="absolute top-1/2 right-2.5 -translate-y-1/2 text-emerald-600" />}
      </div>
      {state.info && (
        <p className="mt-1 text-xs text-emerald-700">
          {state.info.bank} · {branchText(state.info)}{state.info.state ? `, ${title(state.info.state)}` : ""}
          <span className="text-gray-400"> — filled in, you can still edit</span>
        </p>
      )}
      {state.error && <p className="mt-1 text-xs text-amber-700">{state.error}</p>}
      {value && value.length === 11 && !VALID.test(value) && !state.busy && !state.error && (
        <p className="mt-1 text-xs text-amber-700">IFSC looks wrong: 4 letters, a zero, then 6 letters or digits</p>
      )}
    </div>
  );
}
