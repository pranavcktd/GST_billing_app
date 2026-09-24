"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ErrorBox, Loading } from "@/components/ui";
import { kindOf } from "@/lib/constants";
import { useFetch } from "@/lib/useFetch";
import type { Voucher } from "@/lib/types";

/** Resolves a document id to its typed URL (used by ledgers and reports). */
export default function DocRedirect() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data, error } = useFetch<Voucher>(`/vouchers/${id}`);
  useEffect(() => {
    if (data) router.replace(`/v/${kindOf(data.type)}/${data.id}`);
  }, [data, router]);
  return error ? <ErrorBox message={error} /> : <Loading />;
}
