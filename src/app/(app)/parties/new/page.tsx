"use client";

import { useRouter } from "next/navigation";
import { PartyForm, emptyParty } from "@/components/PartyForm";
import { PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import type { Party } from "@/lib/types";

export default function NewPartyPage() {
  const router = useRouter();
  return (
    <div className="max-w-4xl">
      <PageHeader title="Add party" />
      <PartyForm
        initial={emptyParty()}
        onSubmit={async (p) => {
          const created = await api<Party>("/parties", { body: p });
          router.push(`/parties/${created.id}`);
        }}
      />
    </div>
  );
}
