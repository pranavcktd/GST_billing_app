import { useEffect } from "react";

/** File names for saved documents — same rule as the server (services/invoice_pdf.filename):
 *  Tax-Invoice_INV-0012_Karan-Stores_06-10-2026 */

function slug(text: string, limit: number): string {
  return text.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, limit).replace(/-+$/, "");
}

export function shortParty(name: string | null | undefined): string {
  const words = (name ?? "").replace(/&/g, " ").split(/\s+/).filter((w) => /[A-Za-z0-9]/.test(w));
  while (words.length && ["m/s", "ms", "messrs", "mr", "mrs", "shri", "smt"].includes(words[0].toLowerCase().replace(/\.+$/, ""))) words.shift();
  return slug(words.slice(0, 2).join(" "), 20) || "Party";
}

export function docFileName(v: { title: string; number: string; party_name: string | null; date: string }): string {
  const [y, m, d] = v.date.split("-");
  return `${slug(v.title.split("/")[0], 30)}_${slug(v.number, 30) || "draft"}_${shortParty(v.party_name)}_${d}-${m}-${y}`;
}

/** Browsers name a "Save as PDF" file after the page title — set it while a document is shown. */
export function useDocTitle(name: string | null) {
  useEffect(() => {
    if (!name) return;
    const before = document.title;
    document.title = name;
    return () => { document.title = before; };
  }, [name]);
}
