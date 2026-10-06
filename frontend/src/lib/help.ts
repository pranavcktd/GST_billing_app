/**
 * Plain-language help shown behind the ⓘ icon next to field labels.
 *
 * <Field> looks its label up here automatically, so most screens get help without extra code; pass
 * `info` to <Field> (or use <Info text=…/>) for anything else. Keys are labels in lower case, without
 * "(₹)", "(optional)" or "*".
 */

const HELP: Record<string, string> = {
  // ---- items
  "item name": "The name printed on bills. Keep it short and clear, e.g. “Basmati Rice 5 kg”.",
  "item code / sku": "Your own code for the item (stock keeping unit). Optional — also used for barcode labels and quick search.",
  "hsn code": "Harmonised System of Nomenclature code for goods. Printing it on invoices is mandatory: 4 digits up to ₹5 crore turnover, 6 digits above. Type a word or code to search the official list.",
  "sac code": "Services Accounting Code — the HSN equivalent for services (starts with 99). Type a word or code to search the official list.",
  "hsn/sac code": "HSN code for goods or SAC code for services (starts with 99). Used on invoices and in the HSN summary of GSTR-1.",
  "hsn/sac": "HSN code for goods or SAC code for services (starts with 99). Used on invoices and in the HSN summary of GSTR-1.",
  "unit": "How the item is counted — pieces, kg, litres, boxes… These are the GST portal's unit codes (UQC), reported in GSTR-1.",
  "category": "Your own grouping (e.g. Grocery, Spares). Helps filter lists and reports.",
  "sale price": "Default selling rate. Choose “With tax” if the price already includes GST — the app works out the taxable value.",
  "purchase price": "Default buying rate, used for purchase bills and to value stock.",
  "mrp": "Maximum retail price printed on the pack. Optional; can be shown on invoices and used for MRP-based price lists.",
  "gst rate": "GST % for this item. The rate comes from the HSN/SAC code — check the official rate list. 0% covers nil-rated and exempt supplies.",
  "gst %": "GST % for this item or line. CGST + SGST (same state) or IGST (other state) is split automatically.",
  "cess %": "Compensation cess — only for specific goods such as tobacco, aerated drinks and some cars. Leave 0 otherwise.",
  "opening stock": "Quantity in hand on the date you start using the app. It is valued at the purchase price.",
  "as of date": "The date the opening figure applies to — usually the first day you start recording in the app.",
  "low stock alert at": "When stock falls to this level, the item appears in Low stock on the dashboard.",
  // ---- parties
  "gstin": "15-character GST number. The first two digits are the state code and characters 3–12 are the PAN. A registered buyer's GSTIN makes the sale B2B (they can claim input tax credit).",
  "gstin (if registered)": "15-character GST number of the party. Leave blank for consumers and unregistered businesses.",
  "gst type": "Registered (regular), composition, unregistered, consumer, SEZ or overseas. Decides how the sale is reported in GSTR-1.",
  "party type": "Customer (you sell to them), supplier (you buy from them) or both.",
  "pan": "10-character Permanent Account Number. Filled from the GSTIN when there is one; needed for TDS.",
  "state": "Decides the place of supply: same state as you → CGST + SGST, another state → IGST.",
  "place of supply": "Where the supply is treated as made (usually the buyer's state). Same state as yours → CGST + SGST; different state → IGST.",
  "opening balance": "Amount already due on the day you start: positive = they owe you (receivable), negative = you owe them (payable).",
  "credit limit": "Maximum amount this customer may owe you. You are warned when a new bill would cross it.",
  "payment due after (days)": "Credit period. The due date on invoices is the bill date plus these days; reminders follow it.",
  "billing address": "Printed on invoices. For B2B sales it should match the buyer's GST registration.",
  "shipping address (if different)": "Where goods are delivered, if not the billing address. Printed as “Ship to”.",
  "price list": "Special rates for this party (dealer, wholesale…). Rates fill in automatically on their bills.",
  // ---- documents
  "due date": "Date by which the customer should pay. Used for overdue status and payment reminders.",
  "valid till": "Date until which this quotation's prices are valid.",
  "supplier bill no.": "The invoice number printed on the supplier's bill — needed to match your purchases with GSTR-2B.",
  "supplier bill date": "Date on the supplier's invoice (not the date you received it).",
  "vehicle no.": "Registration number of the vehicle carrying the goods — needed for the e-way bill.",
  "transporter id": "GSTIN or TRANSIN of the transporter, if a transport company moves the goods (for the e-way bill).",
  "transporter name": "Name of the transport company, printed on the invoice and e-way bill.",
  "distance (km)": "Approximate road distance from dispatch to delivery. It decides how long the e-way bill is valid.",
  "lr / transport doc no.": "Lorry receipt / railway receipt / airway bill number given by the transporter.",
  "e-way bill no. (12 digits)": "Number of the e-way bill generated on the portal for this movement of goods.",
  "foreign currency": "Currency of the export invoice. GST values are still calculated in rupees.",
  "exchange rate": "Rupees per unit of foreign currency on the invoice date.",
  "port code": "6-character code of the port of export, as given in the shipping bill.",
  "reason": "Why this entry is made. For credit / debit notes the reason is reported in GSTR-1.",
  // ---- payments
  "tds deducted": "Income-tax deducted at source on this payment. The bill is treated as settled for the full amount (payment + TDS).",
  "mode": "How the money moved — cash, bank transfer, UPI, cheque or card.",
  "deposit to": "Cash or bank account where the money went in.",
  "paid from": "Cash or bank account the money came out of.",
  "reference": "UTR / transaction ID / cheque number, so the payment can be matched with the bank statement.",
  "cheque date": "Date written on the cheque. A cheque affects the bank balance only after you mark it cleared.",
  // ---- business
  "business name": "Trade name printed on your invoices.",
  "legal name (as per gst)": "Name exactly as on your GST registration certificate.",
  "type of business (constitution)": "Proprietorship, partnership, LLP, company… It decides which filings apply to you (for example MCA returns for companies and LLPs).",
  "gst registration": "Regular — tax invoices and GST credit; Composition — tax on turnover at a fixed rate, bill of supply, no credit; Not registered — no GST on bills.",
  "category (decides the cmp-08 tax rate)": "Composition category: traders and manufacturers pay 1%, restaurants 5% and service providers 6% of turnover (rates are kept up to date by the admin).",
  "lut arn / reference number": "Letter of Undertaking — lets you export or supply to SEZ without paying IGST. File it on the GST portal every financial year.",
  "valid until": "Last date the LUT covers (normally 31 March).",
  "upi id": "Your UPI address. A scan-to-pay QR for the balance due is printed on invoices.",
  "ifsc": "11-character bank branch code (e.g. HDFC0001234). Printed with your bank details.",
  "invoice title": "Optional heading in place of “Tax Invoice”, e.g. “Tax Invoice cum Delivery Challan”.",
  "terms & conditions": "Printed at the bottom of invoices — payment terms, jurisdiction, return policy.",
  "default terms & conditions": "Printed at the bottom of invoices — payment terms, jurisdiction, return policy.",
  // ---- cash & bank, expenses, misc
  "display name": "Short name shown in lists, e.g. “HDFC Current A/c”.",
  "as of": "The date the opening balance applies to.",
  "cin / challan no.": "Challan Identification Number from the bank / portal receipt for the tax paid.",
  "period": "Tax period the challan is for, e.g. Aug-2026 or Q2.",
  "interest rate % p.a.": "Yearly interest rate on the loan — used to split EMIs into principal and interest.",
  "batch no.": "Manufacturer's batch / lot number, for items where you track batches and expiry.",
  "godown": "Location the stock is kept at. Add more locations under Godowns.",
  "labour / overheads per batch": "Other costs of making one batch (wages, power…). Added to the cost of the finished goods.",
  "expense category": "Head of expense such as rent or electricity. Categories marked “ITC blocked” never claim input tax credit (section 17(5)).",
  "show filings due from": "Filings due before this date are not listed. Set an older date to also track past returns.",
  "gst returns": "Monthly: GSTR-1 and GSTR-3B every month. Quarterly (QRMP): returns every quarter, tax paid monthly — available up to ₹5 crore turnover.",
};

const normalize = (label: string) =>
  label.toLowerCase().replace(/\(₹[^)]*\)|\(optional\)|\*/g, "").replace(/\s+/g, " ").trim();

/** Help for a field label, if there is any. */
export function helpFor(label: string): string | undefined {
  const key = normalize(label);
  if (HELP[key]) return HELP[key];
  if (/ no\.$/.test(key) && /invoice|note|estimate|order|challan|bill|expense/.test(key)) {
    return "Document number. Leave blank to use the next number in your series; numbers must be unique within the financial year (up to 16 characters for GST invoices).";
  }
  return undefined;
}

/** Help for terms used outside form fields (table headings, check boxes). */
export const TERMS = {
  reverseCharge: "Reverse charge (RCM): for some purchases (e.g. from unregistered suppliers of notified services, GTA, legal fees) the buyer pays the GST instead of the supplier, and can then claim it as input tax credit.",
  tcs: "Tax collected at source — only when the law requires you to collect it (e.g. certain sales above limits). It is added to the bill total.",
  roundOff: "Rounds the bill total to the nearest rupee. The difference is shown separately on the invoice.",
  discount: "Discount % on this line before GST. GST is charged on the price after discount.",
  hsn: "HSN code for goods or SAC code for services (starts with 99).",
  gst: "GST % for the line: CGST + SGST within the state, IGST across states.",
  supplierCharged: "Untick if the supplier did not charge GST (unregistered or composition supplier, or exempt goods).",
} as const;
