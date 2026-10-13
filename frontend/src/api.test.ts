import { describe, expect, it } from "vitest";
import { atLeast, errorText, money, qty } from "./api";
import type { CurrentUser } from "./api";

function user(role: CurrentUser["role"]): CurrentUser {
  return {
    id: 1,
    username: "u",
    role,
    active: true
  };
}

describe("atLeast", () => {
  it("returns false without a user", () => {
    expect(atLeast(null, "viewer")).toBe(false);
  });

  it("ranks viewer < operator < manager < admin", () => {
    expect(atLeast(user("viewer"), "viewer")).toBe(true);
    expect(atLeast(user("viewer"), "operator")).toBe(false);
    expect(atLeast(user("operator"), "operator")).toBe(true);
    expect(atLeast(user("operator"), "manager")).toBe(false);
    expect(atLeast(user("manager"), "manager")).toBe(true);
    expect(atLeast(user("manager"), "admin")).toBe(false);
    expect(atLeast(user("admin"), "admin")).toBe(true);
    expect(atLeast(user("admin"), "viewer")).toBe(true);
  });
});

describe("money", () => {
  it("formats a number as PKR currency", () => {
    expect(money(1500)).toContain("1,500");
  });

  it("treats null and undefined as zero", () => {
    expect(money(null)).toBe(money(0));
    expect(money(undefined)).toBe(money(0));
  });

  it("handles numeric strings from the API", () => {
    expect(money("1234.5")).toContain("1,234.5");
  });
});

describe("qty", () => {
  it("formats grams with up to 3 decimals", () => {
    expect(qty(588.5)).toContain("588.5");
  });

  it("treats nullish as zero", () => {
    expect(qty(null)).toBe(qty(0));
    expect(qty(undefined)).toBe(qty(0));
  });
});

describe("errorText", () => {
  it("extracts the message from an Error", () => {
    expect(errorText(new Error("boom"))).toBe("boom");
  });

  it("falls back to a generic message", () => {
    expect(errorText("a string")).toBe("Unknown error");
    expect(errorText(undefined)).toBe("Unknown error");
  });
});
