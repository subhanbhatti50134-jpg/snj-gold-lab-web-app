// Karat conversion: 24K is pure, so karat = purity% × 24 / 100.
// One scale for gold and silver; the backend always stores percent.

export type PurityUnit = "%" | "K";

export function toKarat(purity: number | string): number {
  const n = Number(purity);
  if (!Number.isFinite(n)) return 0;
  return Math.round(((n * 24) / 100) * 10000) / 10000;
}

export function fromKarat(karat: number | string): number {
  const n = Number(karat);
  if (!Number.isFinite(n)) return 0;
  return Math.round((n / 24) * 100 * 10000) / 10000;
}

/** "22K" when it rounds cleanly, otherwise one decimal: "21.2K". */
export function prettyKarat(purity: number | string): string {
  const n = Number(purity);
  if (!Number.isFinite(n) || n <= 0) return "";
  const k = (n * 24) / 100;
  const nearest = Math.round(k);
  if (Math.abs(k - nearest) <= 0.05) return `${nearest}K`;
  return `${k.toFixed(1)}K`;
}

/** "91.67% · 22K" for tables, receipts and cards. */
export function formatPurity(purity: number | string): string {
  const n = Number(purity);
  if (!Number.isFinite(n)) return "—";
  const karat = prettyKarat(n);
  return karat ? `${n}% · ${karat}` : `${n}%`;
}
