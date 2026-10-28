import holdingsData from "../data/holdings.json";
import ratesData from "../data/fx-rates.json";
import instrumentData from "../data/instruments.json";
import type { FxRates, Holding, Instrument, Position } from "../types";
import { buildPositions } from "../utils/portfolio";
import { delay } from "./client";

const holdings = holdingsData as Holding[];
const rates = ratesData as FxRates;
const instruments = instrumentData as Instrument[];

export async function fetchHoldings(): Promise<Holding[]> {
  return delay(holdings.map((row) => ({ ...row })));
}

export async function fetchFxRates(): Promise<FxRates> {
  return delay({ ...rates });
}

/** Holdings priced at the latest instrument prices, in USD. */
export async function fetchPositions(): Promise<Position[]> {
  return delay(buildPositions(holdings, instruments, rates));
}
