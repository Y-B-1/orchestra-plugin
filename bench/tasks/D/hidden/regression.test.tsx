// Regression guard: existing pages and existing money formats still work. Passes on the unmodified fixture.
import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { bodyRows, openApp, resetApp, SLOW } from "./helpers";

afterEach(resetApp);

describe("regression", () => {
  it("dashboard shows key figures, instruments, watchlist and recent activity", async () => {
    const s = await openApp("/");
    const aum = await s.findByRole("article", { name: "Assets under management" }, SLOW);
    expect(aum.textContent).toContain("$48.2B");
    expect(aum.textContent).not.toContain("+$48.2B");
    const instruments = s.getByRole("region", { name: "Instruments" });
    expect(await within(instruments).findByRole("link", { name: "AAPL" }, SLOW)).toBeInTheDocument();
    fireEvent.click(within(instruments).getByRole("button", { name: "FX" }));
    await waitFor(() => expect(within(instruments).queryByRole("link", { name: "AAPL" })).not.toBeInTheDocument(), SLOW);
    expect(within(instruments).getByRole("link", { name: "EURUSD" })).toBeInTheDocument();
    expect(await s.findByRole("table", { name: "Latest trades" }, SLOW)).toBeInTheDocument();
  });

  it("portfolio lists holdings in US dollars with cents, a totals row and an allocation chart", async () => {
    const s = await openApp("/portfolio");
    const table = await s.findByRole("table", { name: "Holdings" }, SLOW);
    expect(within(table).getByText("Total (11 positions)")).toBeInTheDocument();
    const aapl = within(table).getByRole("link", { name: "AAPL" }).closest("tr");
    expect(aapl?.textContent).toContain("$2,729,760.00");
    expect(aapl?.textContent).toContain("$227.48");
    expect(aapl?.textContent).toContain("+$468,960");
    expect(s.getByRole("img", { name: /Allocation by asset class/ })).toBeInTheDocument();
  });

  it("trades page pages, filters and opens a trade with fees and notional in cents", async () => {
    const s = await openApp("/trades");
    const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    expect(bodyRows(table)).toHaveLength(25);
    expect(s.getByText("Showing 1 to 25 of 150 trades")).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: "Trade T-10145" }).textContent).toContain("$7,039,565.00");
    fireEvent.click(within(table).getByRole("row", { name: "Trade T-10150" }));
    const drawer = await s.findByRole("dialog", { name: "Trade details" }, SLOW);
    await waitFor(() => expect(drawer.textContent).toContain("$2.10"), SLOW);
    expect(drawer.textContent).toContain("$71.91");
    fireEvent.change(s.getByLabelText("Instrument"), { target: { value: "AAPL" } });
    expect(await s.findByText("Showing 1 to 15 of 15 trades", {}, SLOW)).toBeInTheDocument();
  });

  it("instrument pages keep their prices and market cap", async () => {
    const s = await openApp("/instruments/SAP");
    expect(await s.findByRole("heading", { name: "SAP SE" }, SLOW)).toBeInTheDocument();
    expect(s.getByLabelText("Last price")).toHaveTextContent("€214.90");
  });

  it("instrument page shows the market cap in compact dollars and recent trades", async () => {
    const s = await openApp("/instruments/AAPL");
    expect(await s.findByText("$3.5T", {}, SLOW)).toBeInTheDocument();
    expect(await s.findByRole("table", { name: "Recent AAPL trades" }, SLOW)).toBeInTheDocument();
  });

  it("clients page searches and opens the drawer", async () => {
    const s = await openApp("/clients");
    fireEvent.change(s.getByLabelText("Search clients"), { target: { value: "quill" } });
    await waitFor(() => expect(s.queryByText("Northwind Capital")).not.toBeInTheDocument(), SLOW);
    expect(await s.findByText("Quill Software", {}, SLOW)).toBeInTheDocument();
    fireEvent.change(s.getByLabelText("Search clients"), { target: { value: "" } });
    fireEvent.click(await s.findByText("Harbor Pension Trust", {}, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    expect(await within(drawer).findByRole("heading", { name: "Harbor Pension Trust" }, SLOW)).toBeInTheDocument();
  });

  it("client notes are added and deleted", async () => {
    const s = await openApp("/clients");
    fireEvent.click(await s.findByText("Lumen Robotics", {}, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    fireEvent.click(await within(drawer).findByRole("tab", { name: /Notes/ }, SLOW));
    fireEvent.change(within(drawer).getByLabelText("New note"), { target: { value: "Plain note" } });
    fireEvent.click(within(drawer).getByRole("button", { name: "Add note" }));
    expect(await within(drawer).findByText("Plain note")).toBeInTheDocument();
    fireEvent.click(within(drawer).getByRole("button", { name: /Delete note/ }));
    expect(await within(drawer).findByText("No notes yet.")).toBeInTheDocument();
  });

  it("reports page shows status badges", async () => {
    const s = await openApp("/reports");
    await s.findByText("Daily market wrap", {}, SLOW);
    expect(s.getAllByText("Published").length).toBeGreaterThanOrEqual(4);
    expect(s.getByText("Rates desk summary")).toBeInTheDocument();
  });

  it("settings toggles the dark theme and saves the alert switches", async () => {
    const s = await openApp("/settings");
    fireEvent.click(s.getByRole("switch", { name: "Dark theme" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    fireEvent.click(s.getByRole("switch", { name: "Push alerts" }));
    await waitFor(() => expect(JSON.parse(localStorage.getItem("pulse.settings") ?? "{}").pushAlerts).toBe(true));
    expect(await s.findByRole("button", { name: "Notifications, 3 unread" }, SLOW)).toBeInTheDocument();
  });
});
