import type { Instrument, InstrumentStats } from "../../types";
import { formatCompactCurrency, formatPercent, formatVolume } from "../../utils/format";
import { formatMultiple, formatPrice } from "../../utils/numbers";
import { StatList, type Stat } from "../StatList";

export function KeyStats({ instrument, stats }: { instrument: Instrument; stats: InstrumentStats }) {
  const price = (value: number) => formatPrice(value, instrument.currency);
  const rows: Stat[] = [
    { label: "Open", value: price(stats.open) },
    { label: "Previous close", value: price(stats.prevClose) },
    { label: "Day range", value: `${price(stats.dayLow)} to ${price(stats.dayHigh)}` },
    { label: "3 month range", value: `${price(stats.rangeLow)} to ${price(stats.rangeHigh)}` },
    { label: "Average volume", value: formatVolume(stats.avgVolume), hint: "Average daily volume over 3 months" },
    { label: "Exchange", value: stats.exchange },
    { label: "Sector", value: stats.sector },
  ];
  if (stats.marketCap !== null) rows.push({ label: "Market cap", value: formatCompactCurrency(stats.marketCap) });
  if (stats.peRatio !== null) rows.push({ label: "P/E ratio", value: formatMultiple(stats.peRatio) });
  if (stats.dividendYield !== null) {
    rows.push({ label: instrument.assetClass === "bond" ? "Yield" : "Dividend yield", value: formatPercent(stats.dividendYield) });
  }
  return <StatList stats={rows} columns={2} />;
}
