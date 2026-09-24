"use client";

import { useParams, useRouter } from "next/navigation";
import { ItemForm } from "@/components/ItemForm";
import { ErrorBox, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Item } from "@/lib/types";

export default function EditItemPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data, error, loading } = useFetch<Item>(`/items/${id}`);

  if (loading) return <Loading />;
  if (!data) return <ErrorBox message={error} />;

  return (
    <div className="max-w-4xl">
      <PageHeader title={`Edit ${data.name}`} />
      <ItemForm
        initial={data}
        isNew={false}
        onSubmit={async (i) => {
          await api(`/items/${id}`, { method: "PUT", body: i });
          router.push(`/items/${id}`);
        }}
      />
    </div>
  );
}
