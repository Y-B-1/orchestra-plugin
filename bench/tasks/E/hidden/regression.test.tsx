// Regression guard: existing pages still render and work. Passes on the unmodified fixture.
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { bodyRows, closeApp, openApp, sleep, SLOW } from "./helpers";

// Counts trade list responses the mock API sends, to see how often the blotter asks for trades.
const calls = vi.hoisted(() => ({ tradeLists: 0 }));
vi.mock("../api/client", async (importOriginal) => {
  const mod = await importOriginal<typeof import("../api/client")>();
  const isTradeList = (value: unknown) =>
    Array.isArray(value) && (value.length === 0 || (typeof value[0] === "object" && value[0] !== null && "executedAt" in value[0]));
  return {
    ...mod,
    delay: <T,>(value: T, ms?: number) => {
      if (isTradeList(value)) calls.tradeLists += 1;
      return mod.delay(value, ms);
    },
  };
});

afterEach(closeApp);

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
    expect(s.getByText("Previous close")).toBeInTheDocument();
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
    expect(s.getByText("Rates desk summary")).toBeInTheDocument();
  });

  it("settings toggles the dark theme and the bell shows unread notifications", async () => {
    const s = await openApp("/settings");
    fireEvent.click(s.getByRole("switch", { name: "Dark theme" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(await s.findByRole("button", { name: "Notifications, 3 unread" }, SLOW)).toBeInTheDocument();
  });

  it("typing in the instrument filter asks for trades once per pause, not per keystroke", async () => {
    const s = await openApp("/trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    await sleep(400);
    const before = calls.tradeLists;
    const box = s.getByLabelText("Instrument");
    for (const value of ["A", "AA", "AAP", "AAPL"]) fireEvent.change(box, { target: { value } });
    expect(await s.findByText("Showing 1 to 15 of 15 trades", {}, SLOW)).toBeInTheDocument();
    await sleep(600);
    expect(calls.tradeLists - before).toBeLessThanOrEqual(2);
  });
});
