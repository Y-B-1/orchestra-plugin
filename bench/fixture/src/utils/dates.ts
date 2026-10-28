export const DAY_MS = 24 * 60 * 60 * 1000;

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

const shortDateFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

const relativeFormatter = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });

/** Parses a `YYYY-MM-DD` string as midnight UTC. Returns null for anything else. */
export function parseIsoDay(value: string): Date | null {
  if (!ISO_DAY.test(value)) return null;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Formats a date as `YYYY-MM-DD` in UTC, the format date inputs use. */
export function toIsoDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(day: string, amount: number): string {
  const date = parseIsoDay(day);
  if (!date) throw new Error(`Invalid day: ${day}`);
  return toIsoDay(new Date(date.getTime() + amount * DAY_MS));
}

export function daysBetween(from: string, to: string): number {
  const start = parseIsoDay(from);
  const end = parseIsoDay(to);
  if (!start || !end) return Number.NaN;
  return Math.round((end.getTime() - start.getTime()) / DAY_MS);
}

/**
 * True when the timestamp falls inside the day range. Either bound may be an
 * empty string, which leaves that side of the range open.
 */
export function isWithinRange(iso: string, from: string, to: string): boolean {
  const time = new Date(iso).getTime();
  if (Number.isNaN(time)) return false;
  const start = from ? parseIsoDay(from) : null;
  const end = to ? parseIsoDay(to) : null;
  if (start && time < start.getTime()) return false;
  if (end && time > end.getTime()) return false;
  return true;
}

/** True when `from` is after `to`; an open bound never conflicts. */
export function isInvertedRange(from: string, to: string): boolean {
  if (!from || !to) return false;
  return from > to;
}

export function formatShortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Invalid date";
  return shortDateFormatter.format(date);
}

export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Invalid time";
  return timeFormatter.format(date);
}

const relativeSteps: { unit: Intl.RelativeTimeFormatUnit; ms: number }[] = [
  { unit: "day", ms: DAY_MS },
  { unit: "hour", ms: 60 * 60 * 1000 },
  { unit: "minute", ms: 60 * 1000 },
];

/** "5 minutes ago", "yesterday", "3 days ago". Anything under a minute is "just now". */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const time = new Date(iso).getTime();
  if (Number.isNaN(time)) return "Invalid date";
  const diff = time - now.getTime();
  for (const step of relativeSteps) {
    if (Math.abs(diff) >= step.ms) {
      return relativeFormatter.format(Math.round(diff / step.ms), step.unit);
    }
  }
  return "just now";
}

export function compareIso(a: string, b: string): number {
  return new Date(a).getTime() - new Date(b).getTime();
}
