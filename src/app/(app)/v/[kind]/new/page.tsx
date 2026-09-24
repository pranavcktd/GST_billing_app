"use client";

import { notFound, useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ExpenseForm } from "@/components/ExpenseForm";
import { VoucherForm } from "@/components/VoucherForm";
import { Loading, PageHeader } from "@/components/ui";
import { KINDS, type Kind } from "@/lib/constants";

function NewVoucher({ kind }: { kind: Kind }) {
  const sp = useSearchParams();
  if (kind === "expenses") return <ExpenseForm />;
  return (
    <VoucherForm
      kind={kind}
      presetPartyId={sp.get("party")}
      sourceId={sp.get("from")}
      originalId={sp.get("original")}
    />
  );
}

export default function NewVoucherPage() {
  const { kind } = useParams<{ kind: string }>();
  if (!(kind in KINDS)) notFound();
  return (
    <>
      <PageHeader title={`New ${KINDS[kind as Kind].label}`} />
      <Suspense fallback={<Loading />}>
        <NewVoucher kind={kind as Kind} />
      </Suspense>
    </>
  );
}
