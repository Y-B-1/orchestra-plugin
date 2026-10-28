import { describe, expect, it } from "vitest";
import {
  formatCurrency,
  formatDate,
  formatPercent,
  formatSignedPercent,
  formatVolume,
} from "./format";

describe("formatCurrency", () => {
  it("formats US dollars", () => {
    expect(formatCurrency(1234.5)).toBe("$1,234.50");
  });


  it("formats US dollars with grouping", () => {
    expect(formatCurrency(1234.5)).toBe("$1,234.50");
  });
});

describe("formatPercent", () => {
  it("formats a fraction as a percent", () => {
    expect(formatPercent(0.1234)).toBe("12.34%");
  });

  it("adds a plus sign to gains and a minus sign to losses", () => {
    expect(formatSignedPercent(0.0124)).toBe("+1.24%");
    expect(formatSignedPercent(-0.0036)).toBe("-0.36%");
  });
});

describe("formatVolume", () => {
  it("abbreviates large counts", () => {
    expect(formatVolume(51230000)).toBe("51.2M");
    expect(formatVolume(1840000)).toBe("1.8M");
  });
});

describe("formatDate", () => {
  it("formats an ISO date in UTC", () => {
    expect(formatDate("2026-10-27")).toBe("Oct 27, 2026");
  });

  it("flags invalid input", () => {
    expect(formatDate("not-a-date")).toBe("Invalid date");
  });
});

