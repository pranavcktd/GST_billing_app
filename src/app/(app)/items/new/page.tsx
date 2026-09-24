"use client";

import { useRouter } from "next/navigation";
import { ItemForm, emptyItem } from "@/components/ItemForm";
import { PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import type { Item } from "@/lib/types";

export default function NewItemPage() {
  const router = useRouter();
  return (
    <div className="max-w-4xl">
      <PageHeader title="Add item" />
      <ItemForm
        initial={emptyItem}
        isNew
        onSubmit={async (i) => {
          const created = await api<Item>("/items", { body: i });
          router.push(`/items/${created.id}`);
        }}
      />
    </div>
  );
}
