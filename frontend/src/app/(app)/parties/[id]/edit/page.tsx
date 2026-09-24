"use client";

import { useParams, useRouter } from "next/navigation";
import { PartyForm } from "@/components/PartyForm";
import { ErrorBox, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Party } from "@/lib/types";

export default function EditPartyPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data, error, loading } = useFetch<Party>(`/parties/${id}`);

  if (loading) return <Loading />;
  if (!data) return <ErrorBox message={error} />;

  return (
    <div className="max-w-4xl">
      <PageHeader title={`Edit ${data.name}`} />
      <PartyForm
        initial={data}
        onSubmit={async (p) => {
          await api(`/parties/${id}`, { method: "PUT", body: p });
          router.push(`/parties/${id}`);
        }}
      />
    </div>
  );
}
