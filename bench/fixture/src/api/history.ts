import data from "../data/price-history.json";
import type { PricePoint } from "../types";
import { delay, NotFoundError, ValidationError } from "./client";

const history = data as Record<string, PricePoint[]>;

export type HistoryRange = "1M" | "3M";

const pointsPerRange: Record<HistoryRange, number> = {
  "1M": 21,
  "3M": 63,
};

/** Daily closes for `symbol`, oldest first, covering the requested range. */
export async function fetchPriceHistory(symbol: string, range: HistoryRange = "3M"): Promise<PricePoint[]> {
  const points = history[symbol];
  if (!points) throw new NotFoundError("Price history for", symbol);
  const count = pointsPerRange[range];
  if (count === undefined) throw new ValidationError(`Unknown range ${range}`);
  return delay(points.slice(-count).map((point) => ({ ...point })));
}
