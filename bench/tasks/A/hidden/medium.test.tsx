import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { bodyRows, closeApp, openApp, SLOW } from "./helpers";

afterEach(closeApp);

function timesOf(table: HTMLElement): number[] {
  const headers = within(table).getAllByRole("columnheader");
  const col = headers.findIndex((h) => (h.textContent ?? "").replace(/[▲▼]/g, "").trim() === "Time");
  return bodyRows(table).map((row) => {
    const cell = row.cells[col];
    const attr = cell?.querySelector("time")?.getAttribute("datetime");
    const text = attr ?? (cell?.textContent ?? "").replace(/\s*UTC$/, "") + " UTC";
    return new Date(text).getTime();
  });
}

describe("bugs and refactor", () => {
  it("A7 a one-day date range lists that day's trades", async () => {
    const s = await openApp("/trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    fireEvent.change(s.getByLabelText("From"), { target: { value: "2026-10-27" } });
    fireEvent.change(s.getByLabelText("To"), { target: { value: "2026-10-27" } });
    expect(await s.findByText("Showing 1 to 17 of 17 trades", {}, SLOW)).toBeInTheDocument();
  });

  it("A7 the end date of a range is included", async () => {
    const s = await openApp("/trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    fireEvent.change(s.getByLabelText("From"), { target: { value: "2026-10-05" } });
    fireEvent.change(s.getByLabelText("To"), { target: { value: "2026-10-09" } });
    expect(await s.findByText("Showing 1 to 25 of 40 trades", {}, SLOW)).toBeInTheDocument();
  });

  it("A8 sorting by Time orders trades chronologically across days", async () => {
    const s = await openApp("/trades");
    const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    fireEvent.click(within(table).getByRole("button", { name: /^Time/ }));
    await waitFor(() => {
      const asc = timesOf(s.getByRole("table", { name: "Trade blotter" }));
      expect(asc).toEqual([...asc].sort((a, b) => a - b));
      expect(Math.max(...asc)).toBeLessThan(Date.parse("2026-10-08T00:00:00Z"));
    });
    fireEvent.click(within(s.getByRole("table", { name: "Trade blotter" })).getByRole("button", { name: /^Time/ }));
    await waitFor(() => {
      const desc = timesOf(s.getByRole("table", { name: "Trade blotter" }));
      expect(desc).toEqual([...desc].sort((a, b) => b - a));
      expect(Math.min(...desc)).toBeGreaterThanOrEqual(Date.parse("2026-10-26T00:00:00Z"));
    });
  });

  it("A9 the dashboard instruments table sorts with the shared arrows", async () => {
    const s = await openApp("/");
    const region = s.getByRole("region", { name: "Instruments" });
    const table = await within(region).findByRole("table", {}, SLOW);
    const instrument = within(table).getByRole("columnheader", { name: /^Instrument/ });
    expect(instrument).toHaveAttribute("aria-sort", "ascending");
    expect(instrument.textContent).toContain("▲");
    fireEvent.click(within(table).getByRole("button", { name: /^Price/ }));
    const price = within(table).getByRole("columnheader", { name: /^Price/ });
    expect(price).toHaveAttribute("aria-sort", "ascending");
    expect(price.textContent).toContain("▲");
    expect(within(table).getByRole("columnheader", { name: /^Instrument/ }).textContent).not.toMatch(/[▲▼]/);
    expect(bodyRows(table)[0]?.textContent).toMatch(/^EURUSD/);
    fireEvent.click(within(table).getByRole("button", { name: /^Price/ }));
    expect(within(table).getByRole("columnheader", { name: /^Price/ }).textContent).toContain("▼");
    expect(bodyRows(table)[0]?.textContent).toMatch(/^XAU/);
  });
});
