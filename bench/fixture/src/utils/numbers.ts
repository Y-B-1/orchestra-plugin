import type { FxRates } from "../types";

const quantityFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });

export function sum(values: readonly number[]): number {
  return values.reduce((total, value) => total + value, 0);
}

export function roundTo(value: number, digits: number): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Share of `part` in `total` as a fraction; zero when the total is zero. */
export function percentOf(part: number, total: number): number {
  if (total === 0) return 0;
  return part / total;
}

/** Converts an amount in `currency` to US dollars. Unknown currencies throw. */
export function toUsd(amount: number, currency: string, rates: FxRates): number {
  const rate = rates[currency];
  if (rate === undefined) throw new Error(`No FX rate for ${currency}`);
  return amount * rate;
}

export function formatQuantity(value: number): string {
  return quantityFormatter.format(value);
}

/** Number of decimals a price needs: FX pairs quote to 4 or 5 places. */
export function priceDigits(price: number): number {
  if (price < 2) return 4;
  if (price < 20) return 3;
  return 2;
}

export function formatPrice(price: number, currency = "USD"): string {
  const digits = priceDigits(price);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(price);
}

export function formatSignedCurrency(value: number, currency = "USD"): string {
  const text = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Math.abs(value));
  if (value > 0) return `+${text}`;
  if (value < 0) return `-${text}`;
  return text;
}

export function formatBasisPoints(fraction: number): string {
  return `${roundTo(fraction * 10000, 1)} bp`;
}

export function formatMultiple(value: number | null): string {
  if (value === null) return "n/a";
  return `${value.toFixed(1)}x`;
}

export function toneOf(value: number): "up" | "down" | "flat" {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}
