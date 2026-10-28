import type { AllocationSlice, AssetClass, FxRates, Holding, Instrument, PortfolioTotals, Position } from "../types";
import { percentOf, sum, toUsd } from "./numbers";

export const assetClassLabels: Record<AssetClass, string> = {
  equity: "Equities",
  fx: "FX",
  commodity: "Commodities",
  bond: "Bonds",
};

const assetClassOrder: AssetClass[] = ["equity", "bond", "commodity", "fx"];

/**
 * Joins holdings with live instrument prices and converts every value to USD.
 * Holdings whose instrument is missing are skipped.
 */
export function buildPositions(holdings: readonly Holding[], instruments: readonly Instrument[], rates: FxRates): Position[] {
  const bySymbol = new Map(instruments.map((instrument) => [instrument.symbol, instrument]));
  const rows: Omit<Position, "weight">[] = [];
  for (const holding of holdings) {
    const instrument = bySymbol.get(holding.symbol);
    if (!instrument) continue;
    const marketValueUsd = toUsd(holding.quantity * instrument.price, instrument.currency, rates);
    const costBasisUsd = toUsd(holding.quantity * holding.avgCost, instrument.currency, rates);
    const previousValueUsd = marketValueUsd / (1 + instrument.changePct);
    rows.push({
      ...holding,
      name: instrument.name,
      assetClass: instrument.assetClass,
      currency: instrument.currency,
      price: instrument.price,
      changePct: instrument.changePct,
      marketValueUsd,
      costBasisUsd,
      unrealizedPnlUsd: marketValueUsd - costBasisUsd,
      unrealizedPnlPct: percentOf(marketValueUsd - costBasisUsd, costBasisUsd),
      dayChangeUsd: marketValueUsd - previousValueUsd,
    });
  }
  const total = sum(rows.map((row) => row.marketValueUsd));
  return rows.map((row) => ({ ...row, weight: percentOf(row.marketValueUsd, total) }));
}

export function portfolioTotals(positions: readonly Position[]): PortfolioTotals {
  const marketValueUsd = sum(positions.map((p) => p.marketValueUsd));
  const costBasisUsd = sum(positions.map((p) => p.costBasisUsd));
  return {
    marketValueUsd,
    costBasisUsd,
    unrealizedPnlUsd: marketValueUsd - costBasisUsd,
    unrealizedPnlPct: percentOf(marketValueUsd - costBasisUsd, costBasisUsd),
    dayChangeUsd: sum(positions.map((p) => p.dayChangeUsd)),
    positions: positions.length,
  };
}

/** Market value per asset class, largest first, skipping empty classes. */
export function allocationByClass(positions: readonly Position[]): AllocationSlice[] {
  const total = sum(positions.map((p) => p.marketValueUsd));
  const slices = assetClassOrder.map((assetClass) => {
    const valueUsd = sum(positions.filter((p) => p.assetClass === assetClass).map((p) => p.marketValueUsd));
    return { assetClass, valueUsd, weight: percentOf(valueUsd, total) };
  });
  return slices.filter((slice) => slice.valueUsd > 0).sort((a, b) => b.valueUsd - a.valueUsd);
}
