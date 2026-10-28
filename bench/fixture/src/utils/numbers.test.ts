import { describe, expect, it } from "vitest";
import {
  clamp,
  formatBasisPoints,
  formatMultiple,
  formatPrice,
  formatQuantity,
  formatSignedCurrency,
  percentOf,
  roundTo,
  sum,
  toUsd,
  toneOf,
} from "./numbers";

describe("arithmetic helpers", () => {
  it("sums, rounds, clamps and takes shares", () => {
    expect(sum([1.5, 2.5, -1])).toBe(3);
    expect(sum([])).toBe(0);
    expect(roundTo(1.23456, 2)).toBe(1.23);
    expect(clamp(12, 0, 10)).toBe(10);
    expect(clamp(-3, 0, 10)).toBe(0);
    expect(percentOf(25, 100)).toBe(0.25);
    expect(percentOf(5, 0)).toBe(0);
  });

  it("converts to USD and throws for an unknown currency", () => {
    const rates = { USD: 1, EUR: 1.1, JPY: 0.0067 };
    expect(toUsd(100, "EUR", rates)).toBeCloseTo(110);
    expect(toUsd(100, "USD", rates)).toBe(100);
    expect(() => toUsd(1, "CHF", rates)).toThrow("No FX rate for CHF");
  });
});

describe("number formatting", () => {
  it("formats prices, signed amounts, quantities and ratios", () => {
    expect(formatPrice(1.0842)).toBe("$1.0842");
    expect(formatPrice(227.48)).toBe("$227.48");
    expect(formatPrice(214.9, "EUR")).toBe("€214.90");
    expect(formatSignedCurrency(1520.4)).toBe("+$1,520");
    expect(formatSignedCurrency(-98)).toBe("-$98");
    expect(formatSignedCurrency(0)).toBe("$0");
    expect(formatQuantity(5000000)).toBe("5,000,000");
    expect(formatBasisPoints(0.0087)).toBe("87 bp");
    expect(formatMultiple(34.21)).toBe("34.2x");
    expect(formatMultiple(null)).toBe("n/a");
    expect([toneOf(0.01), toneOf(-2), toneOf(0)]).toEqual(["up", "down", "flat"]);
  });
});
