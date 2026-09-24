/**
 * Live preview of invoice totals while typing. Mirrors backend/app/gst/calc.py —
 * the server recomputes everything on save and its numbers are the ones stored.
 */

const r2 = (x: number) => Math.sign(x) * Math.round((Math.abs(x) + Number.EPSILON) * 100) / 100;

export interface CalcLine {
  qty: number; rate: number; gst_rate: number; cess_rate: number; discount_pct: number; tax_inclusive: boolean;
}

export interface CalcLineOut {
  amount: number; discount: number; taxable: number; cgst: number; sgst: number; igst: number; cess: number; total: number;
}

export interface CalcTotals {
  lines: CalcLineOut[]; sub_total: number; discount: number; taxable: number; cgst: number; sgst: number;
  igst: number; cess: number; round_off: number; grand_total: number; tcs: number;
}

export function calcLine(l: CalcLine, taxApplicable: boolean, interState: boolean): CalcLineOut {
  const amount = r2((l.qty || 0) * (l.rate || 0));
  const discount = r2((amount * (l.discount_pct || 0)) / 100);
  const net = amount - discount;
  const g = taxApplicable ? l.gst_rate || 0 : 0;
  const c = taxApplicable ? l.cess_rate || 0 : 0;
  const taxable = l.tax_inclusive && (g || c) ? r2((net * 100) / (100 + g + c)) : r2(net);
  let cgst = 0, sgst = 0, igst = 0;
  if (g) {
    if (interState) igst = r2((taxable * g) / 100);
    else cgst = sgst = r2((taxable * g) / 200);
  }
  const cess = r2((taxable * c) / 100);
  return { amount, discount, taxable, cgst, sgst, igst, cess, total: r2(taxable + cgst + sgst + igst + cess) };
}

export function calcInvoice(
  lines: CalcLine[], taxApplicable: boolean, interState: boolean, roundOff = true, reverseCharge = false, tcsRate = 0,
): CalcTotals {
  const outs = lines.map((l) => calcLine(l, taxApplicable, interState));
  const sum = (k: keyof CalcLineOut) => r2(outs.reduce((s, o) => s + o[k], 0));
  const base = reverseCharge ? sum("taxable") : sum("total");
  const tcs = tcsRate ? r2((base * tcsRate) / 100) : 0;
  const raw = r2(base + tcs);
  const grand = roundOff ? Math.round(raw) : raw;
  return {
    lines: outs, sub_total: sum("amount"), discount: sum("discount"), taxable: sum("taxable"),
    cgst: sum("cgst"), sgst: sum("sgst"), igst: sum("igst"), cess: sum("cess"),
    round_off: r2(grand - raw), grand_total: grand, tcs,
  };
}

/** GSTIN format + checksum (same algorithm as the backend). */
const CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
export function gstinError(g: string): string | null {
  const v = g.trim().toUpperCase();
  if (!/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/.test(v)) return "Format should be like 27AAPFU0939F1ZV";
  let sum = 0;
  for (let i = 0; i < 14; i++) {
    const p = CHARS.indexOf(v[i]) * (i % 2 === 0 ? 1 : 2);
    sum += Math.floor(p / 36) + (p % 36);
  }
  return CHARS[(36 - (sum % 36)) % 36] === v[14] ? null : "Checksum mismatch — please re-check the GSTIN";
}
