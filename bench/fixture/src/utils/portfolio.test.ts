import { describe, expect, it } from "vitest";
import type { Holding, Instrument } from "../types";
import { allocationByClass, buildPositions, portfolioTotals } from "./portfolio";

const instruments: Instrument[] = [
  { symbol: "AAA", name: "Alpha", assetClass: "equity", price: 110, changePct: 0.1, volume: 1, currency: "USD" },
  { symbol: "BBB", name: "Beta", assetClass: "bond", price: 50, changePct: 0, volume: 1, currency: "EUR" },
];

const holdings: Holding[] = [
  { id: "h1", symbol: "AAA", quantity: 10, avgCost: 100, openedAt: "2026-01-01", book: "Core" },
  { id: "h2", symbol: "BBB", quantity: 20, avgCost: 50, openedAt: "2026-01-01", book: "Rates" },
  { id: "h3", symbol: "ZZZ", quantity: 5, avgCost: 1, openedAt: "2026-01-01", book: "Core" },
];

const rates = { USD: 1, EUR: 2 };

describe("buildPositions", () => {
  it("prices holdings in USD, weights them and skips unknown instruments", () => {
    const positions = buildPositions(holdings, instruments, rates);
    expect(positions.map((p) => p.symbol)).toEqual(["AAA", "BBB"]);
    expect(positions[0]).toMatchObject({ marketValueUsd: 1100, costBasisUsd: 1000, unrealizedPnlUsd: 100 });
    expect(positions[1]?.marketValueUsd).toBe(2000);
    expect(positions[0]?.dayChangeUsd).toBeCloseTo(100);
    expect(positions[0]?.weight).toBeCloseTo(1100 / 3100);
    expect(positions.reduce((total, p) => total + p.weight, 0)).toBeCloseTo(1);
  });
});

describe("portfolioTotals and allocationByClass", () => {
  it("adds up positions and groups value by asset class, largest first", () => {
    const totals = portfolioTotals(buildPositions(holdings, instruments, rates));
    expect(totals).toMatchObject({ marketValueUsd: 3100, costBasisUsd: 3000, unrealizedPnlUsd: 100, positions: 2 });
    const slices = allocationByClass(buildPositions(holdings, instruments, rates));
    expect(slices.map((s) => s.assetClass)).toEqual(["bond", "equity"]);
    expect(slices[0]?.weight).toBeCloseTo(2000 / 3100);
  });
});
