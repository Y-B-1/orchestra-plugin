import { describe, expect, it } from "vitest";
import {
  addDays,
  daysBetween,
  formatRelative,
  formatShortDate,
  formatTime,
  isInvertedRange,
  isWithinRange,
  parseIsoDay,
} from "./dates";

describe("day arithmetic", () => {
  it("parses days as midnight UTC and counts across month boundaries", () => {
    expect(parseIsoDay("2026-10-27")?.toISOString()).toBe("2026-10-27T00:00:00.000Z");
    expect(parseIsoDay("10/27/2026")).toBeNull();
    expect(parseIsoDay("")).toBeNull();
    expect(addDays("2026-10-30", 3)).toBe("2026-11-02");
    expect(addDays("2026-10-01", -1)).toBe("2026-09-30");
    expect(daysBetween("2026-10-01", "2026-10-27")).toBe(26);
  });
});

describe("isWithinRange", () => {
  it("keeps a timestamp inside the range and treats empty bounds as open", () => {
    expect(isWithinRange("2026-10-15T10:30:00Z", "2026-10-10", "2026-10-20")).toBe(true);
    expect(isWithinRange("2026-01-01T00:00:00Z", "", "")).toBe(true);
    expect(isWithinRange("2026-10-05T08:00:00Z", "2026-10-01", "")).toBe(true);
  });

  it("drops timestamps before the start, invalid input and inverted ranges", () => {
    expect(isWithinRange("2026-10-09T23:59:00Z", "2026-10-10", "2026-10-20")).toBe(false);
    expect(isWithinRange("yesterday", "", "")).toBe(false);
    expect(isInvertedRange("2026-10-20", "2026-10-10")).toBe(true);
    expect(isInvertedRange("2026-10-10", "2026-10-10")).toBe(false);
    expect(isInvertedRange("", "2026-10-10")).toBe(false);
  });
});

describe("formatting", () => {
  it("formats short dates and 24-hour times in UTC, and relative times", () => {
    expect(formatShortDate("2026-10-27T19:42:00Z")).toBe("Oct 27");
    expect(formatTime("2026-10-27T09:05:00Z")).toBe("09:05");
    const now = new Date("2026-10-27T20:00:00Z");
    expect(formatRelative("2026-10-27T19:58:00Z", now)).toBe("2 minutes ago");
    expect(formatRelative("2026-10-27T16:00:00Z", now)).toBe("4 hours ago");
    expect(formatRelative("2026-10-26T18:00:00Z", now)).toBe("yesterday");
    expect(formatRelative("2026-10-27T19:59:40Z", now)).toBe("just now");
  });
});
