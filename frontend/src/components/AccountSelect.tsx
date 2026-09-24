"use client";

import { Select } from "@/components/ui";
import { money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Account } from "@/lib/types";

/** Cash / bank account picker. Empty value = Cash in Hand. */
export function AccountSelect({ value, onChange, showBalance = true }: {
  value: string; onChange: (id: string) => void; showBalance?: boolean;
}) {
  const { data } = useFetch<Account[]>("/accounts");
  const cash = data?.find((a) => a.is_default_cash);
  return (
    <Select value={value || cash?.id || ""} onChange={(e) => onChange(e.target.value)}>
      {data?.filter((a) => a.is_active).map((a) => (
        <option key={a.id} value={a.id}>
          {a.name}{showBalance ? ` (${money(a.balance)})` : ""}
        </option>
      ))}
    </Select>
  );
}
