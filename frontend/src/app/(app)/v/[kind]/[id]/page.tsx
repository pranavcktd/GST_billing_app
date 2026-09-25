"use client";

import { ArrowRightLeft, Ban, MessageCircle, Pencil, Printer, Receipt, Undo2, Wallet } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { EInvoicePanel } from "@/components/EInvoicePanel";
import { InvoiceDocument } from "@/components/InvoiceDocument";
import { Button, ErrorBox, LinkButton, Loading, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { usePerms } from "@/lib/auth";
import { CONVERTS_TO, KINDS, kindOf } from "@/lib/constants";
import { fmtDate, money } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import type { Business, VoucherDetail } from "@/lib/types";

export default function VoucherViewPage() {
  const { id } = useParams<{ id: string }>();
  const { can } = usePerms();
  const { data: v, error, setData } = useFetch<VoucherDetail>(`/vouchers/${id}`);
  const { data: business } = useFetch<Business>("/businesses/current");
  const [actionError, setActionError] = useState<string | null>(null);

  if (error) return <ErrorBox message={error} />;
  if (!v || !business) return <Loading />;

  const kind = kindOf(v.type);
  const meta = KINDS[kind];
  const docModule = kind === "expenses" ? "expenses" : ["purchases", "purchase-orders", "debit-notes"].includes(kind) ? "purchases" : "sales";
  const canEdit = can(docModule, "edit");
  const canDelete = can(docModule, "delete");
  const payDir = v.type === "SALE" || v.type === "PURCHASE_RETURN" ? "in" : "out";
  const convertTo = CONVERTS_TO[kind];

  async function cancel() {
    if (!confirm(`Cancel ${v!.number}? The number stays used (as GST requires), stock is reversed, and any payment becomes an advance for the party.`)) return;
    try {
      setData(await api<VoucherDetail>(`/vouchers/${id}/cancel`, { method: "POST" }));
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  function share() {
    const phone = (v!.party_phone ?? "").replace(/\D/g, "").slice(-10);
    const text =
      `${v!.title} ${v!.number} dated ${fmtDate(v!.date)} from ${business!.name}\n` +
      `Amount: ${money(v!.grand_total)}` + (v!.balance > 0 ? `\nBalance due: ${money(v!.balance)}` : "") +
      (business!.upi_id ? `\nPay via UPI: ${business!.upi_id}` : "");
    window.open(`https://wa.me/${phone ? "91" + phone : ""}?text=${encodeURIComponent(text)}`, "_blank");
  }

  return (
    <>
      <PageHeader
        title={`${meta.label} ${v.number}`}
        sub={`${v.party_name} · ${fmtDate(v.date)}`}
        actions={
          <>
            <LinkButton href={`/print/${v.id}`} variant="secondary"><Printer size={16} /> Print / PDF</LinkButton>
            {v.type === "SALE" && <LinkButton href={`/print/${v.id}?format=THERMAL_80`} variant="secondary"><Receipt size={16} /> Thermal</LinkButton>}
            <Button variant="secondary" onClick={share}><MessageCircle size={16} /> WhatsApp</Button>
            {!v.cancelled && convertTo && !v.converted_to_id && can(convertTo === "purchases" ? "purchases" : "sales", "create") && (
              <LinkButton href={`/v/${convertTo}/new?from=${v.id}`} variant="secondary">
                <ArrowRightLeft size={16} /> Convert to {KINDS[convertTo].label.toLowerCase()}
              </LinkButton>
            )}
            {!v.cancelled && v.balance > 0 && v.party_id && can(payDir === "in" ? "payments_in" : "payments_out", "create") && (
              <LinkButton href={`/payments/${payDir}/new?party=${v.party_id}&voucher=${v.id}`} variant="secondary"><Wallet size={16} /> Record payment</LinkButton>
            )}
            {!v.cancelled && (v.type === "SALE" || v.type === "PURCHASE") && v.party_id && can(docModule, "create") && (
              <LinkButton href={`/v/${v.type === "SALE" ? "credit-notes" : "debit-notes"}/new?party=${v.party_id}&original=${v.id}`} variant="secondary">
                <Undo2 size={16} /> {v.type === "SALE" ? "Credit note" : "Debit note"}
              </LinkButton>
            )}
            {!v.cancelled && canEdit && v.einvoice_status !== "GENERATED" && <LinkButton href={`/v/${kind}/${v.id}/edit`} variant="secondary"><Pencil size={16} /> Edit</LinkButton>}
            {!v.cancelled && canDelete && v.einvoice_status !== "GENERATED" && <Button variant="danger" onClick={cancel}><Ban size={16} /> Cancel</Button>}
          </>
        }
      />
      <ErrorBox message={actionError} />
      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        <StatusBadge status={v.status} />
        {v.type !== "ESTIMATE" && !v.cancelled && (
          <span className="text-gray-600">Paid {money(v.paid)} · Balance {money(v.balance)}</span>
        )}
        {v.converted_to_id && (
          <Link href={`/doc/${v.converted_to_id}`} className="text-brand-600 hover:underline">View converted bill →</Link>
        )}
        {v.source_voucher_id && (
          <Link href={`/doc/${v.source_voucher_id}`} className="text-brand-600 hover:underline">Created from → view source</Link>
        )}
      </div>
      <EInvoicePanel v={v} business={business} onChange={setData} canEdit={canEdit} />
      <div className="overflow-x-auto">
        <div className="min-w-[760px]">
          <InvoiceDocument v={v} business={business} />
        </div>
      </div>
    </>
  );
}
