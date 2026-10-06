"use client";

import { ExternalLink, FileDown, Loader2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui";
import { apiBlob, saveBlob } from "@/lib/api";

/** Downloads the server-made PDF with a clear file name (Tax-Invoice_INV-0012_Karan-Stores_06-10-2026.pdf);
 *  the small button next to it opens it in a new tab instead. */
export function PdfButton({ id }: { id: string }) {
  const [busy, setBusy] = useState(false);
  async function download() {
    setBusy(true);
    try {
      const { blob, filename } = await apiBlob(`/vouchers/${id}/pdf`);
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
      <Button variant="secondary" className="rounded-r-none" onClick={download} disabled={busy} title="Download the PDF">
        {busy ? <Loader2 size={16} className="animate-spin" /> : <FileDown size={16} />} PDF
      </Button>
      <Button variant="secondary" className="-ml-px rounded-l-none !px-2" onClick={open} title="Open the PDF in a new tab">
        <ExternalLink size={14} />
      </Button>
    </span>
  );
}
