export type Role = "OWNER" | "ADMIN" | "STAFF" | "ACCOUNTANT";
export type BusinessGstType = "REGULAR" | "COMPOSITION" | "UNREGISTERED";
export type PartyType = "CUSTOMER" | "SUPPLIER" | "BOTH";
export type PartyGstType = "REGISTERED" | "COMPOSITION" | "UNREGISTERED" | "CONSUMER" | "SEZ" | "OVERSEAS";
export type ItemType = "GOODS" | "SERVICE";
export type VoucherType =
  | "SALE" | "SALE_RETURN" | "PURCHASE" | "PURCHASE_RETURN" | "ESTIMATE"
  | "DELIVERY_CHALLAN" | "SALE_ORDER" | "PURCHASE_ORDER" | "EXPENSE";
export type PaymentType = "IN" | "OUT";
export type PaymentMode = "CASH" | "BANK" | "UPI" | "CHEQUE" | "CARD" | "OTHER";

export interface User { id: string; name: string; email: string; phone: string | null }
export interface MyBusiness { id: string; name: string; gstin: string | null; gst_type: BusinessGstType; role: Role }
export interface Me { user: User; businesses: MyBusiness[] }

export interface Business {
  id: string; name: string; legal_name: string | null; gst_type: BusinessGstType; gstin: string | null;
  pan: string | null; state_code: string; address: string | null; city: string | null; pincode: string | null;
  phone: string | null; email: string | null; logo_url: string | null; signature_url: string | null;
  bank_name: string | null; bank_account_no: string | null; bank_ifsc: string | null; bank_branch: string | null;
  upi_id: string | null; invoice_prefix: string; credit_note_prefix: string; debit_note_prefix: string;
  estimate_prefix: string; purchase_prefix: string; receipt_prefix: string; payment_prefix: string;
  challan_prefix: string; sale_order_prefix: string; purchase_order_prefix: string; expense_prefix: string;
  invoice_terms: string | null; auto_backup: boolean; backup_email: string | null;
}

export interface Party {
  id: string; type: PartyType; name: string; gst_type: PartyGstType; gstin: string | null; pan: string | null;
  phone: string | null; email: string | null; state_code: string | null; billing_address: string | null;
  city: string | null; pincode: string | null; shipping_address: string | null; opening_balance: number;
  credit_limit: number | null; is_active: boolean; balance: number;
}

export interface Item {
  id: string; type: ItemType; name: string; code: string | null; hsn_sac: string | null; unit: string;
  category: string | null; description: string | null; image_url: string | null; sale_price: number;
  sale_price_tax_inclusive: boolean; purchase_price: number; purchase_price_tax_inclusive: boolean;
  mrp: number | null; gst_rate: number; cess_rate: number; low_stock_level: number | null; is_active: boolean;
  track_batch: boolean; track_serial: boolean; stock: number;
}

export interface VoucherLine {
  id?: string; item_id: string | null; expense_item_id?: string | null; batch_no?: string | null;
  mfg_date?: string | null; expiry_date?: string | null; serial_nos?: string | null; name: string; description: string | null; hsn_sac: string | null;
  unit: string | null; qty: number; rate: number; tax_inclusive: boolean; discount_pct: number;
  gst_rate: number; cess_rate: number; amount?: number; discount?: number; taxable?: number;
  cgst?: number; sgst?: number; igst?: number; cess?: number; total?: number;
}

export interface Voucher {
  id: string; type: VoucherType; number: string; date: string; due_date: string | null;
  party_id: string | null; party_name: string; party_gstin: string | null; party_state_code: string | null;
  party_address: string | null; party_phone: string | null; place_of_supply: string; inter_state: boolean;
  tax_applicable: boolean; reverse_charge: boolean; supplier_invoice_no: string | null;
  supplier_invoice_date: string | null; original_voucher_id: string | null; reason: string | null;
  sub_total: number; discount: number; taxable: number; cgst: number; sgst: number; igst: number; cess: number;
  tcs_rate: number; tcs_amount: number; round_off: number; grand_total: number; notes: string | null;
  terms: string | null; cancelled: boolean; converted_to_id: string | null; source_voucher_id: string | null;
  expense_category_id: string | null; paid: number; balance: number; status: string; title: string;
}

export interface TaxBucket { rate: number; taxable: number; cgst: number; sgst: number; igst: number; cess: number }

export interface VoucherDetail extends Voucher {
  lines: VoucherLine[]; tax_breakup: TaxBucket[]; amount_in_words: string; original_number: string | null;
}

export interface Payment {
  id: string; type: PaymentType; number: string; date: string; party_id: string | null; party_name: string | null;
  amount: number; tds_amount: number; account_id: string; account_name: string | null; mode: PaymentMode;
  reference: string | null; notes: string | null; allocated: number;
  cheque_status: "OPEN" | "CLEARED" | "BOUNCED" | null; cheque_date: string | null; cleared_on: string | null;
  allocations: { voucher_id: string; voucher_number: string; amount: number }[];
}

export interface Account {
  id: string; type: "CASH" | "BANK"; name: string; bank_name: string | null; account_no: string | null;
  ifsc: string | null; opening_balance: number; opening_date: string | null; is_default_cash: boolean;
  is_active: boolean; balance: number;
}

export interface ExpenseCategory { id: string; name: string; kind: "DIRECT" | "INDIRECT"; is_active: boolean; total: number }
export interface ExpenseItem {
  id: string; name: string; category_id: string | null; hsn_sac: string | null; rate: number; gst_rate: number; is_active: boolean;
}

export interface Loan {
  id: string; name: string; lender: string | null; account_no: string | null; interest_rate: number | null;
  opening_balance: number; opening_date: string | null; notes: string | null; is_active: boolean; outstanding: number;
}

/** Generic report shape returned by /reports/run/{slug}. */
export type ColType = "text" | "money" | "qty" | "date" | "pct" | "int";
export interface ReportColumn { key: string; label: string; type: ColType }
export type ReportRow = Record<string, string | number | null | undefined> & { _style?: string; _link?: string | null };
export interface ReportSection {
  title: string | null; columns: ReportColumn[]; rows: ReportRow[]; total: ReportRow | null; note: string | null;
}
export interface ReportResult {
  title: string; subtitle: string | null; summary: { label: string; value: number; type: ColType }[]; sections: ReportSection[];
}
export interface ReportMeta {
  slug: string; category: string; title: string; description: string; filters: string[]; href: string | null;
}
