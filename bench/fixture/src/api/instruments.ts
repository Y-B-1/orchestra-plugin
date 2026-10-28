import data from "../data/instruments.json";
import statsData from "../data/instrument-stats.json";
import type { AssetClass, Instrument, InstrumentStats } from "../types";
import { delay, NotFoundError } from "./client";

const instruments = data as Instrument[];
const stats = statsData as InstrumentStats[];

export async function fetchInstruments(assetClass?: AssetClass): Promise<Instrument[]> {
  const rows = assetClass ? instruments.filter((i) => i.assetClass === assetClass) : instruments;
  return delay(rows.map((row) => ({ ...row })));
}

export async function fetchInstrument(symbol: string): Promise<Instrument> {
  const found = instruments.find((i) => i.symbol === symbol);
  if (!found) throw new NotFoundError("Instrument", symbol);
  return delay({ ...found });
}

export async function fetchInstrumentStats(symbol: string): Promise<InstrumentStats> {
  const found = stats.find((s) => s.symbol === symbol);
  if (!found) throw new NotFoundError("Instrument", symbol);
  return delay({ ...found });
}
