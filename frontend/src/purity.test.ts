import { describe, expect, it } from "vitest";
import {
  formatPurity,
  fromKarat,
  prettyKarat,
  toKarat
} from "./purity";

describe("karat conversion", () => {
  it("converts percent to karat", () => {
    expect(toKarat(100)).toBe(24);
    expect(toKarat(75)).toBe(18);
    expect(toKarat("91.6667")).toBe(22);
  });

  it("converts karat to percent", () => {
    expect(fromKarat(24)).toBe(100);
    expect(fromKarat(18)).toBe(75);
    expect(fromKarat(22)).toBe(91.6667);
  });

  it("round-trips common purities", () => {
    for (const k of [24, 22, 21, 18, 14]) {
      expect(fromKarat(toKarat(fromKarat(k)))).toBeCloseTo(
        fromKarat(k),
        3
      );
    }
  });

  it("treats junk input as zero", () => {
    expect(toKarat("abc")).toBe(0);
    expect(fromKarat("")).toBe(0);
  });
});

describe("prettyKarat", () => {
  it("rounds to whole karats within tolerance", () => {
    expect(prettyKarat(100)).toBe("24K");
    expect(prettyKarat(99.99)).toBe("24K");
    expect(prettyKarat(91.6667)).toBe("22K");
    expect(prettyKarat(75)).toBe("18K");
    expect(prettyKarat(58.3333)).toBe("14K");
    expect(prettyKarat(99.9)).toBe("24K");
  });

  it("keeps one decimal for odd purities", () => {
    expect(prettyKarat(88.5)).toBe("21.2K");
    expect(prettyKarat(66)).toBe("15.8K");
  });

  it("hides karat for zero or invalid purity", () => {
    expect(prettyKarat(0)).toBe("");
    expect(prettyKarat("x")).toBe("");
  });
});

describe("formatPurity", () => {
  it("joins percent and karat", () => {
    expect(formatPurity(75)).toBe("75% · 18K");
    expect(formatPurity(91.6667)).toBe("91.6667% · 22K");
  });

  it("falls back to percent alone when karat is meaningless", () => {
    expect(formatPurity(0)).toBe("0%");
    expect(formatPurity("nope")).toBe("—");
  });
});
