"use client";

import { FileDown, Loader2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui";
import { apiBlob } from "@/lib/api";

/** Opens the server-made PDF of a document in a new tab (from there it can be saved, printed or shared). */
export function PdfButton({ id }: { id: string }) {
  const [busy, setBusy] = useState(false);
  async function open() {
    const win = window.open("", "_blank"); // opened right away so pop-up blockers allow it
    setBusy(true);
    try {
      const { blob } = await apiBlob(`/vouchers/${id}/pdf`);
      const url = URL.createObjectURL(blob);
      if (win) win.location.href = url;
      else window.location.href = url;
    } catch (e) {
      win?.close();
      alert((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Button variant="secondary" onClick={open} disabled={busy} title="Open the PDF — save, print or share it">
      {busy ? <Loader2 size={16} className="animate-spin" /> : <FileDown size={16} />} PDF
    </Button>
  );
}
