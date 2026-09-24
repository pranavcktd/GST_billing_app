"use client";

import { Download, Upload } from "lucide-react";
import { useState } from "react";
import { ImportDialog } from "@/components/ImportDialog";
import { Button, Card, Loading, PageHeader } from "@/components/ui";
import { downloadFile } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

const GROUPS: { title: string; entities: string[] }[] = [
  { title: "Masters", entities: ["parties", "items", "stock", "hsn", "expense-items"] },
  { title: "Sales", entities: ["sales", "estimates", "sale-orders", "delivery-challans", "credit-notes", "payments-in"] },
  { title: "Purchases & expenses", entities: ["purchases", "purchase-orders", "debit-notes", "payments-out", "expenses"] },
];

export default function ImportHub() {
  const { data } = useFetch<{ entity: string; title: string }[]>("/import/types");
  const [open, setOpen] = useState<{ entity: string; title: string } | null>(null);
  if (!data) return <Loading />;
  const title = (e: string) => data.find((d) => d.entity === e)?.title ?? e;

  return (
    <>
      <PageHeader title="Import data" sub="Download the template, fill it in Excel, then upload. Each file is checked fully before anything is saved." />
      <div className="grid gap-5 lg:grid-cols-3">
        {GROUPS.map((g) => (
          <Card key={g.title} className="p-4">
            <h2 className="mb-2 text-xs font-semibold tracking-wider text-gray-500 uppercase">{g.title}</h2>
            <ul className="divide-y divide-gray-100">
              {g.entities.map((e) => (
                <li key={e} className="flex items-center justify-between gap-2 py-2">
                  <span className="text-sm text-gray-900">{title(e)}</span>
                  <span className="flex gap-1">
                    <Button variant="ghost" className="!px-2 !py-1" title="Download template" onClick={() => downloadFile(`/import/${e}/template`)}><Download size={15} /></Button>
                    <Button variant="secondary" className="!py-1" onClick={() => setOpen({ entity: e, title: title(e) })}><Upload size={15} /> Import</Button>
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
      <p className="mt-4 text-xs text-gray-500">
        Parties and items are matched by GSTIN / item code / name and updated if they already exist, so the same import also works for bulk updates.
        Missing parties and items in bill imports are created automatically.
      </p>
      {open && <ImportDialog entity={open.entity} title={open.title} onClose={() => setOpen(null)} />}
    </>
  );
}
