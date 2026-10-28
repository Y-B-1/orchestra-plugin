import { formatSignedPercent } from "../utils/format";
import { formatSignedCurrency, toneOf } from "../utils/numbers";

interface PriceChangeProps {
  /** Change as a fraction, e.g. 0.0124 for +1.24%. */
  pct?: number;
  /** Absolute change in `currency`. */
  amount?: number;
  currency?: string;
  className?: string;
}

/** A signed change colored by direction: green up, red down, muted when flat. */
export function PriceChange({ pct, amount, currency = "USD", className }: PriceChangeProps) {
  const basis = pct ?? amount ?? 0;
  const tone = toneOf(basis);
  const parts: string[] = [];
  if (amount !== undefined) parts.push(formatSignedCurrency(amount, currency));
  if (pct !== undefined) parts.push(amount !== undefined ? `(${formatSignedPercent(pct)})` : formatSignedPercent(pct));
  return <span className={`price-change price-change--${tone}${className ? ` ${className}` : ""}`}>{parts.join(" ")}</span>;
}
