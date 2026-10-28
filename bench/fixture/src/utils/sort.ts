import type { SortDirection, SortState } from "../types";

export type SortValue = string | number | null | undefined;

/** Compares numbers numerically and strings with locale rules; empty values sort last. */
export function compareValues(a: SortValue, b: SortValue): number {
  const aEmpty = a === null || a === undefined || a === "";
  const bEmpty = b === null || b === undefined || b === "";
  if (aEmpty && bEmpty) return 0;
  if (aEmpty) return 1;
  if (bEmpty) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), "en-US", { sensitivity: "base" });
}

export function sortBy<T>(rows: readonly T[], value: (row: T) => SortValue, direction: SortDirection = "asc"): T[] {
  const sign = direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => sign * compareValues(value(left), value(right)));
}

/** Clicking the active column flips direction; a new column starts ascending. */
export function nextSort(current: SortState | null, key: string): SortState {
  if (current && current.key === key) {
    return { key, direction: current.direction === "asc" ? "desc" : "asc" };
  }
  return { key, direction: "asc" };
}

export function ariaSort(current: SortState | null, key: string): "ascending" | "descending" | "none" {
  if (!current || current.key !== key) return "none";
  return current.direction === "asc" ? "ascending" : "descending";
}
