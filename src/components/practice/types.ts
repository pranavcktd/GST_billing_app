import type { ReportSection } from "@/lib/types";

export type Entity = "PROPRIETORSHIP" | "PARTNERSHIP";

export interface PClient {
  id: string; name: string; entity_type: Entity; pan: string | null; gstin: string | null; address: string | null;
  phone: string | null; email: string | null; nature_of_business: string | null; linked_business_id: string | null;
  notes: string | null; created_at: string; updated_at: string;
  files: { id: string; fy: string; status: "DRAFT" | "FINAL"; version: number; updated_at: string }[] | null;
}

export interface Ledger { id: string; name: string; group: string | null; head: string | null; partner: string | null; cy: string; py: string }
export interface Asset {
  description?: string; block?: string; opening?: string | null; addition?: string | null; addition_date?: string | null; sale?: string | null;
  cost?: string | null; opening_acc_dep?: string | null; put_to_use?: string | null; life?: string | null; ca_method?: "SLM" | "WDV";
}
export interface Partner { id: string; name: string; pan?: string; share: string; interest_rate: string; remuneration: string }
export interface FileData {
  entity_type: Entity; ledgers: Ledger[]; closing_stock: { cy: string; py: string };
  depreciation: { method: "IT" | "CA"; assets: Asset[]; py_amount: string };
  partners: Partner[]; py: { ppe?: string };
}
export interface PFile {
  id: string; fy: string; status: "DRAFT" | "FINAL"; source: string | null; version: number; data: FileData;
  finalized_at: string | null; finalized_by: string | null; updated_at: string; client: PClient;
}
export interface Head { code: string; section: string; label: string; nature: "Dr" | "Cr"; help: string }
export interface Check { level: "error" | "warn" | "info" | "ok"; text: string }
export interface Statements {
  doc: { title: string; subtitle: string; sections: (ReportSection & { rows: (Record<string, unknown> & { _key?: string | null })[] })[] };
  checks: Check[];
  explain: Record<string, { title: string; text: string; items: { name: string; amount: number }[] }>;
  summary: Record<string, number>;
  status: string;
}

export const fyOptions = (): string[] => {
  const now = new Date();
  const start = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  return Array.from({ length: 6 }, (_, i) => {
    const y = start - i;
    return `${y}-${String((y + 1) % 100).padStart(2, "0")}`;
  });
};

export const toNum = (s: string | null | undefined) => {
  const n = Number(String(s ?? "").replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
};
