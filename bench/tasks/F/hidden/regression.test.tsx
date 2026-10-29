// Regression guard: existing pages still render and work. Passes on the unmodified fixture.
import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { bodyRows, closeApp, openApp, SLOW } from "./helpers";

afterEach(closeApp);

describe("regression", () => {
  it("dashboard shows key figures, instruments, watchlist and recent activity", async () => {
    const s = await openApp("/");
    expect(await s.findByRole("article", { name: "Assets under management" }, SLOW)).toBeInTheDocument();
    const instruments = s.getByRole("region", { name: "Instruments" });
    expect(await within(instruments).findByRole("link", { name: "AAPL" }, SLOW)).toBeInTheDocument();
    fireEvent.click(within(instruments).getByRole("button", { name: "FX" }));
    await waitFor(() => expect(within(instruments).queryByRole("link", { name: "AAPL" })).not.toBeInTheDocument(), SLOW);
    expect(await s.findByRole("table", { name: "Latest trades" }, SLOW)).toBeInTheDocument();
  });

  it("portfolio keeps compact summary cards, the holdings table and the allocation chart", async () => {
    const s = await openApp("/portfolio");
    const table = await s.findByRole("table", { name: "Holdings" }, SLOW);
    expect(within(table).getByText("Total (11 positions)")).toBeInTheDocument();
    expect(s.getByRole("img", { name: /Allocation by asset class/ })).toBeInTheDocument();
    const card = s.getByRole("article", { name: "Market value" });
    expect(card).toHaveTextContent(/^Market value\$31\.2M/);
    expect(within(table).getAllByRole("rowheader")[0]).toHaveTextContent("EURUSD");
  });

  it("trades page pages, filters and keeps the trade-currency Notional column", async () => {
    const s = await openApp("/trades");
    const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    expect(bodyRows(table)).toHaveLength(25);
    expect(s.getByText("Showing 1 to 25 of 150 trades")).toBeInTheDocument();
    expect(within(table).getByRole("button", { name: /Notional/ })).toBeInTheDocument();
    fireEvent.change(s.getByLabelText("Instrument"), { target: { value: "AAPL" } });
    expect(await s.findByText("Showing 1 to 15 of 15 trades", {}, SLOW)).toBeInTheDocument();
    fireEvent.click(within(s.getByRole("table", { name: "Trade blotter" })).getAllByRole("row")[1]!);
    expect(await s.findByRole("dialog", { name: "Trade details" }, SLOW)).toBeInTheDocument();
  });

  it("instrument page keeps quote, price history tabs, key stats and recent trades", async () => {
    const s = await openApp("/instruments/AAPL");
    expect(await s.findByRole("heading", { name: "Apple Inc." }, SLOW)).toBeInTheDocument();
    expect(s.getByLabelText("Last price")).toHaveTextContent("$227.48");
    expect(s.getByRole("tab", { name: "1 month" })).toBeInTheDocument();
    expect(s.getByText("Previous close")).toBeInTheDocument();
    expect(await s.findByRole("table", { name: "Recent AAPL trades" }, SLOW)).toBeInTheDocument();
  });

  it("clients page searches, keeps compact AUM in the list and opens the drawer", async () => {
    const s = await openApp("/clients");
    const harbor = await s.findByText("Harbor Pension Trust", {}, SLOW);
    expect(harbor.closest("button")).toHaveTextContent("$3.4B");
    fireEvent.change(s.getByLabelText("Search clients"), { target: { value: "quill" } });
    await waitFor(() => expect(s.queryByText("Harbor Pension Trust")).not.toBeInTheDocument(), SLOW);
    expect(s.getAllByText(/Quill Software/).length).toBeGreaterThanOrEqual(1);
    fireEvent.change(s.getByLabelText("Search clients"), { target: { value: "" } });
    fireEvent.click(await s.findByText("Harbor Pension Trust", {}, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    expect(await within(drawer).findByRole("heading", { name: "Harbor Pension Trust" }, SLOW)).toBeInTheDocument();
  });

  it("reports page filters by status", async () => {
    const s = await openApp("/reports");
    await s.findByText("Daily market wrap", {}, SLOW);
    expect(s.getAllByText("Published").length).toBeGreaterThanOrEqual(4);
    fireEvent.click(s.getByRole("tab", { name: "Failed" }));
    await waitFor(() => expect(s.queryByText("Daily market wrap")).not.toBeInTheDocument(), SLOW);
    expect(s.getByText("Rates desk summary")).toBeInTheDocument();
  });

  it("settings toggles the dark theme and the bell shows unread notifications", async () => {
    const s = await openApp("/settings");
    fireEvent.click(s.getByRole("switch", { name: "Dark theme" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(await s.findByRole("button", { name: "Notifications, 3 unread" }, SLOW)).toBeInTheDocument();
  });
});
