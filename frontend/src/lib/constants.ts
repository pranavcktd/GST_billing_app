import type { PartyGstType, PaymentMode, VoucherType } from "./types";

export const STATES: Record<string, string> = {
  "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand",
  "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
  "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura",
  "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
  "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat", "26": "Dadra and Nagar Haveli and Daman and Diu",
  "27": "Maharashtra", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
  "34": "Puducherry", "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
  "38": "Ladakh", "96": "Foreign Country", "97": "Other Territory",
};

export const stateLabel = (code?: string | null) => (code && STATES[code] ? `${code}-${STATES[code]}` : "");

export const GST_RATES = [0, 0.25, 3, 5, 12, 18, 28, 40];

export const UNITS: Record<string, string> = {
  NOS: "Numbers", PCS: "Pieces", KGS: "Kilograms", GMS: "Grams", LTR: "Litres", MLT: "Millilitre",
  MTR: "Metres", CMS: "Centimetres", SQF: "Square Feet", SQM: "Square Metres", BOX: "Box", PAC: "Packs",
  SET: "Sets", DOZ: "Dozens", BAG: "Bags", BTL: "Bottles", CTN: "Cartons", QTL: "Quintal", TON: "Tonnes",
  UNT: "Units", OTH: "Others",
};

export const PARTY_GST_TYPES: Record<PartyGstType, string> = {
  REGISTERED: "Registered (Regular)",
  COMPOSITION: "Registered (Composition)",
  UNREGISTERED: "Unregistered business",
  CONSUMER: "Consumer",
  SEZ: "SEZ",
  OVERSEAS: "Overseas",
};

export const PAYMENT_MODES: Record<PaymentMode, string> = {
  CASH: "Cash", BANK: "Bank transfer", UPI: "UPI", CHEQUE: "Cheque", CARD: "Card", OTHER: "Other",
};

/** URL slug <-> voucher type, plus UI wording. */
export const KINDS = {
  sales: { type: "SALE", label: "Sale Invoice", plural: "Sale Invoices", partyLabel: "Customer", party: "CUSTOMER" },
  estimates: { type: "ESTIMATE", label: "Estimate", plural: "Estimates / Quotations", partyLabel: "Customer", party: "CUSTOMER" },
  "sale-orders": { type: "SALE_ORDER", label: "Sale Order", plural: "Sale Orders", partyLabel: "Customer", party: "CUSTOMER" },
  "delivery-challans": { type: "DELIVERY_CHALLAN", label: "Delivery Challan", plural: "Delivery Challans", partyLabel: "Customer", party: "CUSTOMER" },
  "credit-notes": { type: "SALE_RETURN", label: "Credit Note", plural: "Credit Notes (Sale Return)", partyLabel: "Customer", party: "CUSTOMER" },
  purchases: { type: "PURCHASE", label: "Purchase Bill", plural: "Purchase Bills", partyLabel: "Supplier", party: "SUPPLIER" },
  "purchase-orders": { type: "PURCHASE_ORDER", label: "Purchase Order", plural: "Purchase Orders", partyLabel: "Supplier", party: "SUPPLIER" },
  "debit-notes": { type: "PURCHASE_RETURN", label: "Debit Note", plural: "Debit Notes (Purchase Return)", partyLabel: "Supplier", party: "SUPPLIER" },
  expenses: { type: "EXPENSE", label: "Expense", plural: "Expenses", partyLabel: "Paid to", party: "SUPPLIER" },
} as const satisfies Record<string, { type: VoucherType; label: string; plural: string; partyLabel: string; party: "CUSTOMER" | "SUPPLIER" }>;

export type Kind = keyof typeof KINDS;

export const kindOf = (type: VoucherType): Kind =>
  (Object.keys(KINDS) as Kind[]).find((k) => KINDS[k].type === type) ?? "sales";

export const isOutward = (t: VoucherType) =>
  t === "SALE" || t === "SALE_RETURN" || t === "ESTIMATE" || t === "SALE_ORDER" || t === "DELIVERY_CHALLAN";

/** Documents with no money / ledger effect (can be converted into a bill). */
export const NON_LEDGER: VoucherType[] = ["ESTIMATE", "SALE_ORDER", "PURCHASE_ORDER", "DELIVERY_CHALLAN"];

/** kind -> kind it converts into */
export const CONVERTS_TO: Partial<Record<Kind, Kind>> = {
  estimates: "sales", "sale-orders": "sales", "delivery-challans": "sales", "purchase-orders": "purchases",
};

/** kind -> bulk import entity */
export const IMPORT_ENTITY: Record<Kind, string> = {
  sales: "sales", estimates: "estimates", "sale-orders": "sale-orders", "delivery-challans": "delivery-challans",
  "credit-notes": "credit-notes", purchases: "purchases", "purchase-orders": "purchase-orders",
  "debit-notes": "debit-notes", expenses: "expenses",
};
