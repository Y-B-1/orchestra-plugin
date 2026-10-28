import { describe, expect, it } from "vitest";
import data from "../data/instruments.json";
import type { Instrument } from "../types";
import { topMovers, turnover } from "./markets";

describe("topMovers", () => {
  it("ranks the biggest gainers and losers", () => {
    const { gainers, losers } = topMovers(data as Instrument[]);
    expect(gainers.map((i) => i.symbol)).toEqual(["NVDA", "AAPL", "XAU"]);
    expect(losers.map((i) => i.symbol)).toEqual(["TSLA", "WTI", "MSFT"]);
    expect(turnover({ ...(data as Instrument[])[0]!, price: 2, volume: 10 })).toBe(20);
  });
});
