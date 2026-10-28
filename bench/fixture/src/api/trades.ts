import data from "../data/trades.json";
import type { Trade, TradeFilters } from "../types";
import { isInvertedRange, isWithinRange } from "../utils/dates";
import { delay, NotFoundError, ValidationError } from "./client";

const trades = data as Trade[];

export const emptyTradeFilters: TradeFilters = {
  side: "all",
  assetClass: "all",
  from: "",
  to: "",
  symbol: "",
};

export function matchesTradeFilters(trade: Trade, filters: TradeFilters): boolean {
  if (filters.side !== "all" && trade.side !== filters.side) return false;
  if (filters.assetClass !== "all" && trade.assetClass !== filters.assetClass) return false;
  if (filters.symbol && !trade.symbol.toLowerCase().includes(filters.symbol.trim().toLowerCase())) return false;
  return isWithinRange(trade.executedAt, filters.from, filters.to);
}

/** Trades matching `filters`, newest first. */
export async function fetchTrades(filters: Partial<TradeFilters> = {}): Promise<Trade[]> {
  const merged = { ...emptyTradeFilters, ...filters };
  if (isInvertedRange(merged.from, merged.to)) {
    throw new ValidationError("The start date must be on or before the end date.");
  }
  const rows = trades
    .filter((trade) => matchesTradeFilters(trade, merged))
    .sort((a, b) => b.executedAt.localeCompare(a.executedAt));
  return delay(rows.map((row) => ({ ...row })));
}

export async function fetchTrade(id: string): Promise<Trade> {
  const found = trades.find((t) => t.id === id);
  if (!found) throw new NotFoundError("Trade", id);
  return delay({ ...found });
}

/** The most recent trades in one instrument. */
export async function fetchRecentTrades(symbol: string, limit = 10): Promise<Trade[]> {
  const rows = trades
    .filter((trade) => trade.symbol === symbol)
    .sort((a, b) => b.executedAt.localeCompare(a.executedAt))
    .slice(0, limit);
  return delay(rows.map((row) => ({ ...row })));
}
