import type { Instrument } from "../types";

export interface Movers {
  gainers: Instrument[];
  losers: Instrument[];
}

/** The biggest risers and fallers by daily change; flat instruments are left out. */
export function topMovers(instruments: readonly Instrument[], count = 3): Movers {
  const byChange = [...instruments].sort((a, b) => b.changePct - a.changePct);
  return {
    gainers: byChange.filter((i) => i.changePct > 0).slice(0, count),
    losers: byChange
      .filter((i) => i.changePct < 0)
      .reverse()
      .slice(0, count),
  };
}

/** Turnover proxy used to rank activity: price times volume, in the quote currency. */
export function turnover(instrument: Instrument): number {
  return instrument.price * instrument.volume;
}
