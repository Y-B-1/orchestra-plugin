import { beforeAll, describe, expect, it } from "vitest";
import { fetchFxRates, fetchHoldings, fetchInstrumentStats, fetchPositions, fetchPriceHistory, latency, NotFoundError } from "./index";

beforeAll(() => {
  latency.ms = 0;
});

describe("holdings", () => {
  it("lists the house book and prices positions in USD", async () => {
    expect(await fetchHoldings()).toHaveLength(11);
    const positions = await fetchPositions();
    const aapl = positions.find((p) => p.symbol === "AAPL");
    expect(aapl?.marketValueUsd).toBeCloseTo(12000 * 227.48);
    const sap = positions.find((p) => p.symbol === "SAP");
    const rates = await fetchFxRates();
    expect(sap?.marketValueUsd).toBeCloseTo(4000 * 214.9 * (rates.EUR ?? 0));
  });
});

describe("price history and stats", () => {
  it("returns the requested range, oldest first", async () => {
    const points = await fetchPriceHistory("AAPL", "1M");
    expect(points).toHaveLength(21);
    expect(points[points.length - 1]).toEqual({ date: "2026-10-27", close: 227.48 });
    expect(points[0]!.date < points[1]!.date).toBe(true);
  });

  it("returns key stats and rejects an unknown symbol", async () => {
    await expect(fetchPriceHistory("NOPE")).rejects.toBeInstanceOf(NotFoundError);
    await expect(fetchInstrumentStats("NOPE")).rejects.toBeInstanceOf(NotFoundError);
    const stats = await fetchInstrumentStats("MSFT");
    expect(stats.exchange).toBe("NASDAQ");
    expect(stats.dayLow).toBeLessThanOrEqual(stats.dayHigh);
  });
});
