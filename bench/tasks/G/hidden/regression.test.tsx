// Regression guard: existing behaviour the asks must not break. Passes on the unmodified fixture.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import trades from "../data/trades.json";
import { bodyRows, closeApp, isTest, openApp, read, readBlob, SLOW, sourceFiles } from "./helpers";

beforeEach(() => {
  localStorage.clear();
  // Signed in the way the prompt describes it; the unmodified app ignores this key.
  localStorage.setItem("pulse.session", JSON.stringify("dana@pulse.test"));
});
afterEach(() => {
  closeApp();
  vi.restoreAllMocks();
});

describe("regression", () => {
  it("dashboard shows key figures, instruments, watchlist and recent activity", async () => {
    const s = await openApp("/");
    expect(await s.findByRole("article", { name: "Assets under management" }, SLOW)).toBeInTheDocument();
    const instruments = s.getByRole("region", { name: "Instruments" });
    expect(await within(instruments).findByRole("link", { name: "AAPL" }, SLOW)).toBeInTheDocument();
    fireEvent.click(within(instruments).getByRole("button", { name: "FX" }));
    await waitFor(() => expect(within(instruments).queryByRole("link", { name: "AAPL" })).not.toBeInTheDocument(), SLOW);
    expect(within(instruments).getByRole("link", { name: "EURUSD" })).toBeInTheDocument();
    expect(await s.findByRole("table", { name: "Latest trades" }, SLOW)).toBeInTheDocument();
  });

  it("portfolio lists holdings with a totals row and an allocation chart", async () => {
    const s = await openApp("/portfolio");
    const table = await s.findByRole("table", { name: "Holdings" }, SLOW);
    expect(within(table).getByText("Total (11 positions)")).toBeInTheDocument();
    expect(s.getByRole("img", { name: /Allocation by asset class/ })).toBeInTheDocument();
  });

  it("trades page pages, filters and opens a trade", async () => {
    const s = await openApp("/trades");
    const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    expect(bodyRows(table)).toHaveLength(25);
    expect(s.getByText("Showing 1 to 25 of 150 trades")).toBeInTheDocument();
    fireEvent.change(s.getByLabelText("Instrument"), { target: { value: "AAPL" } });
    expect(await s.findByText("Showing 1 to 15 of 15 trades", {}, SLOW)).toBeInTheDocument();
    fireEvent.click(within(s.getByRole("table", { name: "Trade blotter" })).getAllByRole("row")[1]!);
    expect(await s.findByRole("dialog", { name: "Trade details" }, SLOW)).toBeInTheDocument();
  });

  it("instrument page shows quote, stats and recent trades", async () => {
    const s = await openApp("/instruments/AAPL");
    expect(await s.findByRole("heading", { name: "Apple Inc." }, SLOW)).toBeInTheDocument();
    expect(s.getByLabelText("Last price")).toHaveTextContent("$227.48");
    expect(await s.findByRole("table", { name: "Recent AAPL trades" }, SLOW)).toBeInTheDocument();
  });

  it("clients page searches and opens the drawer", async () => {
    const s = await openApp("/clients");
    fireEvent.click(await s.findByText("Harbor Pension Trust", {}, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    expect(await within(drawer).findByRole("heading", { name: "Harbor Pension Trust" }, SLOW)).toBeInTheDocument();
  });

  it("reports page shows status badges", async () => {
    const s = await openApp("/reports");
    await s.findByText("Daily market wrap", {}, SLOW);
    expect(s.getAllByText("Published").length).toBeGreaterThanOrEqual(4);
  });

  it("settings toggles the dark theme and unknown addresses say Page not found.", async () => {
    const s = await openApp("/settings");
    fireEvent.click(await s.findByRole("switch", { name: "Dark theme" }, SLOW));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(s.getByRole("switch", { name: "Email alerts" })).toBeInTheDocument();
    closeApp();
    const missing = await openApp("/nowhere");
    expect(await missing.findByText("Page not found.", {}, SLOW)).toBeInTheDocument();
  });

  it("G14 no debug flags and no test-only or dev-only routes are left in the source", () => {
    const files = sourceFiles().filter((f) => !isTest(f) && /\.(tsx?|css|html)$/.test(f));
    expect(files.filter((f) => /debug/i.test(read(f)))).toEqual([]);
    const routes = files.flatMap((f) => Array.from(read(f).matchAll(/path=["']([^"']*)["']/g)).map((m) => m[1] ?? ""));
    expect(routes.length).toBeGreaterThan(5);
    expect(routes.filter((r) => /test|dev|debug|__|claim/i.test(r))).toEqual([]);
  });

  describe("G20 Export CSV on the Trades page behaves as before", () => {
    const header =
      "Trade,Executed (UTC),Instrument,Side,Quantity,Filled,Price,Currency,Notional,Client,Trader,Venue,Status";

    async function exportCsv(prepare?: (s: Awaited<ReturnType<typeof openApp>>) => void) {
      const blobs: Blob[] = [];
      const names: string[] = [];
      URL.createObjectURL = vi.fn((blob: Blob) => {
        blobs.push(blob);
        return "blob:pulse";
      });
      URL.revokeObjectURL = vi.fn();
      vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
        names.push(this.download);
      });
      const s = await openApp("/trades");
      await s.findByRole("table", { name: "Trade blotter" }, SLOW);
      prepare?.(s);
      fireEvent.click(s.getByRole("button", { name: "Export CSV" }));
      await waitFor(() => expect(blobs).toHaveLength(1));
      return { lines: (await readBlob(blobs[0]!)).split("\r\n"), name: names[0] ?? "" };
    }

    it("exports every trade, newest first, with the raw status codes", async () => {
      const { lines, name } = await exportCsv();
      expect(name).toMatch(/^pulse-trades-\d{4}-\d{2}-\d{2}\.csv$/);
      expect(lines[0]).toBe(header);
      expect(lines).toHaveLength(trades.length + 1);
      expect(lines[1]).toMatch(/^T-10150,2026-10-27T/);
      expect(lines.filter((l) => l.endsWith(",partial")).length).toBe(trades.filter((t) => t.status === "partial").length);
      expect(lines.some((l) => l.endsWith(",cancelled"))).toBe(true);
    });

    it("exports in the order the blotter is sorted", async () => {
      const { lines } = await exportCsv((s) => {
        const table = s.getByRole("table", { name: "Trade blotter" });
        fireEvent.click(within(table).getByRole("button", { name: /^Trade/ }));
      });
      expect(lines[1]).toMatch(/^T-10001,/);
      expect(lines.at(-1)).toMatch(/^T-10150,/);
    });
  });
});
