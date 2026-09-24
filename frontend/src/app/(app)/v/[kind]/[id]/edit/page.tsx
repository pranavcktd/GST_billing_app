"use client";

import { useParams } from "next/navigation";
import { ExpenseForm } from "@/components/ExpenseForm";
import { VoucherForm } from "@/components/VoucherForm";
import { ErrorBox, Loading, PageHeader } from "@/components/ui";
import { KINDS, kindOf } from "@/lib/constants";
import { useFetch } from "@/lib/useFetch";
import type { VoucherDetail } from "@/lib/types";

export default function EditVoucherPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, loading } = useFetch<VoucherDetail>(`/vouchers/${id}`);
  if (loading) return <Loading />;
  if (!data) return <ErrorBox message={error} />;
  if (data.cancelled) return <ErrorBox message="A cancelled document cannot be edited." />;
  const kind = kindOf(data.type);
  return (
    <>
      <PageHeader title={`Edit ${KINDS[kind].label} ${data.number}`} />
      {kind === "expenses" ? <ExpenseForm existing={data} /> : <VoucherForm kind={kind} existing={data} />}
    </>
  );
}
