import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { closeApp, openApp, pick, pickReady, SLOW } from "./helpers";

afterEach(closeApp);

type Screen = Awaited<ReturnType<typeof openApp>>;

async function addAlert(s: Screen, symbol: string, condition: "goes above" | "goes below", price: string) {
  await pickReady(await s.findByLabelText("Instrument", {}, SLOW), new RegExp(`^${symbol}\\b`));
  pick(s.getByLabelText("Condition"), new RegExp(`^${condition}$`));
  fireEvent.change(s.getByLabelText("Price"), { target: { value: price } });
  fireEvent.click(s.getByRole("button", { name: "Add alert" }));
}

// The innermost list item whose whole text contains the alert sentence (markup inside it is free).
function alertItem(_s: Screen, text: string): HTMLElement {
  const li = Array.from(document.querySelectorAll("li"))
    .filter((el) => (el.textContent ?? "").replace(/\s+/g, " ").includes(text))
    .pop();
  if (!li) throw new Error(`alert ${text} is not in a list item`);
  return li;
}

describe("C10 price alerts", () => {
  it("C10 alerts page is in the sidebar and starts empty", async () => {
    const s = await openApp("/");
    fireEvent.click(within(s.getByRole("navigation", { name: "Primary" })).getByRole("link", { name: "Alerts" }));
    expect(await s.findByRole("heading", { level: 1, name: "Alerts" }, SLOW)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/alerts");
    expect(await s.findByText("No alerts yet.", {}, SLOW)).toBeInTheDocument();
  });

  it("C10 a triggered alert is listed and posts an unread notification to the bell", async () => {
    const s = await openApp("/alerts");
    await s.findByRole("button", { name: "Notifications, 3 unread" }, SLOW);
    await addAlert(s, "AAPL", "goes above", "200");
    expect(await waitFor(() => alertItem(s, "AAPL goes above $200.00"), SLOW)).toBeInTheDocument();
    expect(within(alertItem(s, "AAPL goes above $200.00")).getByText("Triggered")).toBeInTheDocument();
    expect(await s.findByRole("button", { name: "Notifications, 4 unread" }, SLOW)).toBeInTheDocument();
    await addAlert(s, "MSFT", "goes above", "500");
    expect(await waitFor(() => alertItem(s, "MSFT goes above $500.00"), SLOW)).toBeInTheDocument();
    expect(within(alertItem(s, "MSFT goes above $500.00")).getByText("Watching")).toBeInTheDocument();
    expect(s.getByRole("button", { name: "Notifications, 4 unread" })).toBeInTheDocument();
    fireEvent.click(s.getByRole("button", { name: "Notifications, 4 unread" }));
    const panel = s.getByRole("region", { name: "Notification list" });
    expect(within(panel).getByText("AAPL is above $200.00")).toBeInTheDocument();
    expect(within(panel).queryByText(/MSFT is above/)).not.toBeInTheDocument();
  }, 10000);

  it("C10 below alerts and prices use the instrument's usual digits", async () => {
    const s = await openApp("/alerts");
    await addAlert(s, "EURUSD", "goes below", "1.1");
    expect(await waitFor(() => alertItem(s, "EURUSD goes below $1.1000"), SLOW)).toBeInTheDocument();
    expect(within(alertItem(s, "EURUSD goes below $1.1000")).getByText("Triggered")).toBeInTheDocument();
    await addAlert(s, "AAPL", "goes below", "100");
    expect(await waitFor(() => alertItem(s, "AAPL goes below $100.00"), SLOW)).toBeInTheDocument();
    expect(within(alertItem(s, "AAPL goes below $100.00")).getByText("Watching")).toBeInTheDocument();
  }, 10000);

  it("C10 rejects an empty or zero price", async () => {
    const s = await openApp("/alerts");
    await addAlert(s, "AAPL", "goes above", "");
    expect(await s.findByText("Enter a price above zero", {}, SLOW)).toBeInTheDocument();
    await addAlert(s, "AAPL", "goes above", "0");
    expect(s.getByText("Enter a price above zero")).toBeInTheDocument();
    expect(s.getByText("No alerts yet.")).toBeInTheDocument();
  }, 10000);

  it("C10 alerts and their notification survive a reload without duplicates", async () => {
    let s = await openApp("/alerts");
    await addAlert(s, "AAPL", "goes above", "200");
    await s.findByRole("button", { name: "Notifications, 4 unread" }, SLOW);
    closeApp();
    s = await openApp("/alerts");
    expect(await waitFor(() => alertItem(s, "AAPL goes above $200.00"), SLOW)).toBeInTheDocument();
    fireEvent.click(await s.findByRole("button", { name: "Notifications, 4 unread" }, SLOW));
    expect(within(s.getByRole("region", { name: "Notification list" })).getAllByText("AAPL is above $200.00")).toHaveLength(1);
  }, 10000);

  it("C10 removing an alert empties the list", async () => {
    const s = await openApp("/alerts");
    await addAlert(s, "MSFT", "goes above", "500");
    const item = await waitFor(() => alertItem(s, "MSFT goes above $500.00"), SLOW);
    fireEvent.click(within(item).getByRole("button", { name: /Remove/ }));
    expect(await s.findByText("No alerts yet.", {}, SLOW)).toBeInTheDocument();
  }, 10000);

  it("C10 mark all read also clears alert notifications", async () => {
    const s = await openApp("/alerts");
    await addAlert(s, "AAPL", "goes above", "200");
    fireEvent.click(await s.findByRole("button", { name: "Notifications, 4 unread" }, SLOW));
    fireEvent.click(within(s.getByRole("region", { name: "Notification list" })).getByRole("button", { name: /^Mark all( as)? read$/ }));
    await waitFor(() => expect(s.getByRole("button", { name: "Notifications" })).toBeInTheDocument());
  }, 10000);
});

function watchRow(table: HTMLElement, symbol: string): HTMLTableRowElement {
  // The first cell starts with the symbol (no symbol in the fixture is a prefix of another).
  const row = Array.from(table.querySelectorAll<HTMLTableRowElement>("tbody tr")).find((r) =>
    (r.cells[0]?.textContent ?? "").trim().startsWith(symbol),
  );
  if (!row) throw new Error(`no watchlist row for ${symbol}`);
  return row;
}

describe("C11 watchlist page", () => {
  it("C11 watchlist page lists the watched instruments with prices", async () => {
    const s = await openApp("/");
    fireEvent.click(within(s.getByRole("navigation", { name: "Primary" })).getByRole("link", { name: "Watchlist" }));
    expect(await s.findByRole("heading", { level: 1, name: "Watchlist" }, SLOW)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/watchlist");
    const table = await s.findByRole("table", { name: "Watched instruments" }, SLOW);
    expect(table.querySelectorAll("tbody tr")).toHaveLength(3);
    expect(watchRow(table, "AAPL").textContent).toContain("$227.48");
    expect(watchRow(table, "EURUSD").textContent).toContain("$1.0842");
    expect(watchRow(table, "XAU").textContent).toContain("$2,641.50");
    expect(await s.findByRole("img", { name: "AAPL 1 month trend" }, SLOW)).toBeInTheDocument();
  }, 10000);

  it("C11 adds an instrument that the rest of the app then shows as watched", async () => {
    let s = await openApp("/watchlist");
    const select = await s.findByLabelText("Add instrument", {}, SLOW);
    await pickReady(select, /^MSFT\b/);
    fireEvent.click(s.getByRole("button", { name: "Add" }));
    const table = await s.findByRole("table", { name: "Watched instruments" }, SLOW);
    await waitFor(() => expect(watchRow(table, "MSFT").textContent).toContain("$431.20"));
    const options = Array.from((s.getByLabelText("Add instrument") as HTMLSelectElement).options).map((o) => o.textContent ?? "");
    expect(options.some((o) => /^MSFT\b/.test(o))).toBe(false);
    expect(options.some((o) => /^AAPL\b/.test(o))).toBe(false);
    closeApp();
    s = await openApp("/instruments/MSFT");
    await s.findByRole("heading", { name: "Microsoft Corp." }, SLOW);
    expect(s.getByRole("button", { pressed: true })).toBeInTheDocument();
  }, 10000);

  it("C11 removing everything shows the empty message", async () => {
    const s = await openApp("/watchlist");
    const table = await s.findByRole("table", { name: "Watched instruments" }, SLOW);
    for (const symbol of ["AAPL", "EURUSD", "XAU"]) {
      fireEvent.click(within(watchRow(table, symbol)).getByRole("button", { name: /Remove/ }));
    }
    expect(await s.findByText("Your watchlist is empty.", {}, SLOW)).toBeInTheDocument();
  }, 10000);

  it("C11 clicking a row opens instrument details in a drawer", async () => {
    const s = await openApp("/watchlist");
    const table = await s.findByRole("table", { name: "Watched instruments" }, SLOW);
    fireEvent.click(watchRow(table, "AAPL"));
    const drawer = await s.findByRole("dialog", { name: "Instrument details" }, SLOW);
    expect(await within(drawer).findByRole("heading", { name: "Apple Inc." }, SLOW)).toBeInTheDocument();
    expect(await within(drawer).findByText("Previous close", {}, SLOW)).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "Open instrument page" })).toHaveAttribute("href", "/instruments/AAPL");
  }, 10000);

  it("C11 the drawer uses the watch button with its new label", async () => {
    const s = await openApp("/watchlist");
    const table = await s.findByRole("table", { name: "Watched instruments" }, SLOW);
    fireEvent.click(watchRow(table, "XAU"));
    const drawer = await s.findByRole("dialog", { name: "Instrument details" }, SLOW);
    expect(await within(drawer).findByRole("button", { name: "On watchlist" }, SLOW)).toHaveAttribute("aria-pressed", "true");
  }, 10000);

  it("C11 trend lines point the way the price moved", async () => {
    const s = await openApp("/watchlist");
    const up = await s.findByRole("img", { name: "AAPL 1 month trend" }, SLOW);
    const down = s.getByRole("img", { name: "EURUSD 1 month trend" });
    const ends = (chart: Element) => {
      const pts = (chart.querySelector("polyline")?.getAttribute("points") ?? "").trim().split(/\s+/);
      return [Number(pts[0]?.split(",")[1]), Number(pts[pts.length - 1]?.split(",")[1])] as const;
    };
    const [upFirst, upLast] = ends(up);
    const [downFirst, downLast] = ends(down);
    expect(upLast).toBeLessThan(upFirst);
    expect(downLast).toBeGreaterThan(downFirst);
  }, 10000);
});
