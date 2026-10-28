import { beforeAll, describe, expect, it } from "vitest";
import { fetchRecentTrades, fetchTrade, fetchTrades, latency, NotFoundError, ValidationError } from "./index";

beforeAll(() => {
  latency.ms = 0;
});

describe("fetchTrades", () => {
  it("returns every trade, newest first", async () => {
    const trades = await fetchTrades();
    expect(trades).toHaveLength(150);
    const times = trades.map((t) => t.executedAt);
    expect(times).toEqual([...times].sort().reverse());
  });

  it("filters by symbol, side and asset class", async () => {
    const trades = await fetchTrades({ symbol: "aapl" });
    expect(trades.length).toBeGreaterThan(0);
    expect(new Set(trades.map((t) => t.symbol))).toEqual(new Set(["AAPL"]));
    const fx = await fetchTrades({ side: "sell", assetClass: "fx" });
    expect(fx.length).toBeGreaterThan(0);
    expect(fx.every((t) => t.side === "sell" && t.assetClass === "fx")).toBe(true);
  });

  it("filters by a date range and rejects an inverted one", async () => {
    const trades = await fetchTrades({ from: "2026-10-05", to: "2026-10-09" });
    expect(trades.length).toBeGreaterThan(0);
    expect(trades.every((t) => t.executedAt >= "2026-10-05" && t.executedAt < "2026-10-10")).toBe(true);
    await expect(fetchTrades({ from: "2026-10-20", to: "2026-10-10" })).rejects.toBeInstanceOf(ValidationError);
  });
});

describe("single trades", () => {
  it("finds a trade by id and rejects an unknown one", async () => {
    expect((await fetchTrade("T-10001")).symbol).toBe("UST10");
    await expect(fetchTrade("T-1")).rejects.toBeInstanceOf(NotFoundError);
  });

  it("lists recent trades for one instrument", async () => {
    const trades = await fetchRecentTrades("AAPL", 5);
    expect(trades).toHaveLength(5);
    expect(trades.every((t) => t.symbol === "AAPL")).toBe(true);
  });
});
