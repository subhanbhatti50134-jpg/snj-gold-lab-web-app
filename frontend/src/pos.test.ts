import { describe, expect, it } from "vitest";
import {
  allocatePayment,
  cartTotal,
  defaultRate,
  lineTotal,
  money2,
  validateCart,
  validateLine,
  type CartLine
} from "./pos";
import type { MetalRate } from "./types";

function line(overrides: Partial<CartLine> = {}): CartLine {
  return {
    key: "k1",
    product_id: 1,
    sku: "GOLD-24K",
    name: "Gold 24K",
    metal: "gold",
    purity: 100,
    quantity_grams: 10,
    rate_per_gram: 3000,
    ...overrides
  };
}

describe("money2", () => {
  it("rounds half up to two decimals", () => {
    expect(money2(10.005)).toBe(10.01);
    expect(money2(10.004)).toBe(10);
    expect(money2(10)).toBe(10);
  });

  it("treats non-finite values as zero", () => {
    expect(money2(NaN)).toBe(0);
    expect(money2(Infinity)).toBe(0);
  });
});

describe("lineTotal / cartTotal", () => {
  it("computes weight x rate x purity/100", () => {
    expect(lineTotal(line())).toBe(30000);
    expect(lineTotal(line({ purity: 91.6, quantity_grams: 11.6638 }))).toBe(
      32052.12
    );
  });

  it("sums lines", () => {
    expect(
      cartTotal([line(), line({ key: "k2", quantity_grams: 5 })])
    ).toBe(45000);
  });
});

describe("validation", () => {
  it("rejects zero weight, zero rate and bad purity", () => {
    expect(validateLine(line({ quantity_grams: 0 }))).toContain("Weight");
    expect(validateLine(line({ rate_per_gram: 0 }))).toContain("Rate");
    expect(validateLine(line({ purity: 0 }))).toContain("Purity");
    expect(validateLine(line())).toBeNull();
  });

  it("rejects an empty cart and names the first bad line", () => {
    expect(validateCart([])).toContain("empty");
    expect(
      validateCart([line(), line({ key: "k2", quantity_grams: 0, name: "Bad" })])
    ).toContain("Bad");
  });
});

describe("allocatePayment", () => {
  const lines = [
    line({ key: "a", quantity_grams: 10 }), // 30000
    line({ key: "b", quantity_grams: 4 }) // 12000
  ];

  it("pays everything when cash covers the total", () => {
    const result = allocatePayment(lines, 50000);
    expect(result.totalPaid).toBe(42000);
    expect(result.change).toBe(8000);
    expect(result.due).toBe(0);
    expect(result.paidPerLine).toEqual([30000, 12000]);
  });

  it("applies cash FIFO with a partial last line", () => {
    const result = allocatePayment(lines, 35000);
    expect(result.totalPaid).toBe(35000);
    expect(result.paidPerLine).toEqual([30000, 5000]);
    expect(result.due).toBe(7000);
    expect(result.change).toBe(0);
  });

  it("handles underpayment of the first line only", () => {
    const result = allocatePayment(lines, 10000);
    expect(result.paidPerLine).toEqual([10000, 0]);
    expect(result.due).toBe(32000);
  });

  it("treats no cash as nothing paid", () => {
    const result = allocatePayment(lines, 0);
    expect(result.totalPaid).toBe(0);
    expect(result.due).toBe(42000);
    expect(result.change).toBe(0);
  });
});

describe("defaultRate", () => {
  const rates: MetalRate[] = [
    {
      id: 1,
      metal: "gold",
      purity: 99.99,
      rate_per_gram: 24000,
      unit: "gram",
      entered_rate: 24000,
      active: true,
      verified_at: "2026-10-01T00:00:00"
    },
    {
      id: 2,
      metal: "gold",
      purity: 99.99,
      rate_per_gram: 25000,
      unit: "gram",
      entered_rate: 25000,
      active: true,
      verified_at: "2026-10-10T00:00:00"
    },
    {
      id: 3,
      metal: "gold",
      purity: 91.6,
      rate_per_gram: 23000,
      unit: "gram",
      entered_rate: 23000,
      active: true,
      verified_at: "2026-10-12T00:00:00"
    },
    {
      id: 4,
      metal: "silver",
      purity: 99.9,
      rate_per_gram: 300,
      unit: "gram",
      entered_rate: 300,
      active: false,
      verified_at: "2026-10-12T00:00:00"
    }
  ];

  it("prefers an exact purity match with the latest verification", () => {
    expect(defaultRate(rates, "gold", 99.99)).toBe(25000);
  });

  it("falls back to the same metal when no exact purity exists", () => {
    expect(defaultRate(rates, "gold", 95)).toBe(23000);
  });

  it("returns null for unknown metal or inactive-only rates", () => {
    expect(defaultRate(rates, "platinum", 100)).toBeNull();
    expect(defaultRate(rates, "silver", 99.9)).toBeNull();
  });
});
