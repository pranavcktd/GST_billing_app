"use client";

import { ExternalLink, FileDown, Loader2, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui";
import { apiBlob, saveBlob } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { DscStatus } from "@/components/DscSettings";

/** Downloads the server-made PDF with a clear file name (Tax-Invoice_INV-0012_Karan-Stores_06-10-2026.pdf);
 *  the small button next to it opens it in a new tab instead. */
export function PdfButton({ id }: { id: string }) {
  const [busy, setBusy] = useState(false);
  const { data: dsc } = useFetch<DscStatus>("/dsc");
  const signable = !!dsc?.configured && !dsc.expired;
  async function download(sign?: boolean) {
    setBusy(true);
    try {
      const { blob, filename } = await apiBlob(`/vouchers/${id}/pdf${sign ? "?sign=true" : ""}`);
      saveBlob(blob, filename);
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function open() {
    const win = window.open("", "_blank"); // opened right away so pop-up blockers allow it
    try {
      const { blob } = await apiBlob(`/vouchers/${id}/pdf`);
      const url = URL.createObjectURL(blob);
      if (win) win.location.href = url;
      else window.location.href = url;
    } catch (e) {
      win?.close();
      alert((e as Error).message);
    }
  }
  return (
    <span className="inline-flex">
      <Button variant="secondary" className="rounded-r-none" onClick={() => download()} disabled={busy}
        title={signable && dsc?.mode === "AUTO" ? `Download the PDF (digitally signed by ${dsc.subject})` : "Download the PDF"}>
        {busy ? <Loader2 size={16} className="animate-spin" /> : signable && dsc?.mode === "AUTO" ? <ShieldCheck size={16} className="text-emerald-600" /> : <FileDown size={16} />} PDF
      </Button>
      {signable && dsc?.mode === "ON_REQUEST" && (
        <Button variant="secondary" className="-ml-px rounded-none" onClick={() => download(true)} disabled={busy} title={`Digitally signed by ${dsc.subject}`}>
          <ShieldCheck size={15} className="text-emerald-600" /> Signed PDF
        </Button>
      )}
      <Button variant="secondary" className="-ml-px rounded-l-none !px-2" onClick={open} title="Open the PDF in a new tab">
        <ExternalLink size={14} />
      </Button>
    </span>
  );
}
