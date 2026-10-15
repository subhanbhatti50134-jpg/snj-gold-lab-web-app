// Pure cart helpers for the POS checkout screen. Every monetary value is
// rounded half-up to 2 decimals to match the backend's Decimal quantize.

import type { MetalRate } from "./types";

export type MakingChargeType = "" | "per_gram" | "percent" | "fixed";

export interface CartLine {
  key: string;
  product_id: number;
  sku: string;
  name: string;
  metal: string;
  purity: number;
  quantity_grams: number;
  rate_per_gram: number;
  making_charge_type: MakingChargeType;
  making_charge_value: number;
}

export function money2(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function metalOf(line: CartLine): number {
  return line.quantity_grams * line.rate_per_gram * (line.purity / 100);
}

// Ujra: per gram of net weight, percent of metal value, or flat amount.
export function makingOf(line: CartLine): number {
  const value = Number(line.making_charge_value || 0);
  if (!line.making_charge_type) return 0;
  if (line.making_charge_type === "per_gram") {
    return money2(line.quantity_grams * value);
  }
  if (line.making_charge_type === "percent") {
    return money2((metalOf(line) * value) / 100);
  }
  return money2(value);
}

export function lineTotal(line: CartLine): number {
  return money2(metalOf(line) + makingOf(line));
}

export function cartTotal(lines: CartLine[]): number {
  return money2(lines.reduce((sum, line) => sum + lineTotal(line), 0));
}

export function validateLine(line: CartLine): string | null {
  if (!(line.quantity_grams > 0)) return "Weight must be greater than zero";
  if (!(line.rate_per_gram > 0)) return "Rate must be greater than zero";
  if (line.purity <= 0 || line.purity > 100) return "Purity must be 1–100";
  if (line.making_charge_type && !(line.making_charge_value > 0)) {
    return "Making charge must be greater than zero";
  }
  if (!line.making_charge_type && Number(line.making_charge_value)) {
    return "Pick a making charge type or clear the value";
  }
  return null;
}

export function validateCart(lines: CartLine[]): string | null {
  if (!lines.length) return "Cart is empty";
  for (const line of lines) {
    const error = validateLine(line);
    if (error) return `${line.name || line.sku}: ${error}`;
  }
  return null;
}

export interface PaymentAllocation {
  paidPerLine: number[];
  totalPaid: number;
  change: number;
  due: number;
}

// Cash received is applied to cart lines in order (FIFO): earlier lines
// are paid first, the last one may be partial, the rest stays due.
export function allocatePayment(
  lines: CartLine[],
  received: number
): PaymentAllocation {
  const target = money2(Math.max(0, received));
  const grand = cartTotal(lines);

  const totalPaid = money2(Math.min(target, grand));
  const due = money2(Math.max(0, grand - totalPaid));
  const change = money2(Math.max(0, target - totalPaid));

  const paidPerLine: number[] = [];
  let remaining = totalPaid;
  for (const line of lines) {
    const pay = money2(Math.min(remaining, lineTotal(line)));
    paidPerLine.push(pay);
    remaining = money2(remaining - pay);
  }

  return { paidPerLine, totalPaid, change, due };
}

// Best default rate for a product: exact metal+purity match first,
// otherwise the most recently verified active rate for the metal.
export function defaultRate(
  rates: MetalRate[],
  metal: string,
  purity: number
): number | null {
  const active = rates.filter(r => r.active && r.metal === metal);
  if (!active.length) return null;

  const exact = active.filter(r => Number(r.purity) === Number(purity));
  const pool = exact.length ? exact : active;

  const sorted = [...pool].sort((a, b) => {
    const ta = a.verified_at ? Date.parse(a.verified_at) : 0;
    const tb = b.verified_at ? Date.parse(b.verified_at) : 0;
    return tb - ta;
  });

  const value = Number(sorted[0].rate_per_gram);
  return Number.isFinite(value) && value > 0 ? value : null;
}
