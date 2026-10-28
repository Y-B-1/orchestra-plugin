import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { bodyRows, closeApp, figure, freezeDate, headers, openApp, pickReady, sleep, SLOW } from "./helpers";

// Requests started while `slow` is on take much longer, the way a busy backend answers out of order.
const net = vi.hoisted(() => ({ slow: false }));
vi.mock("../api/client", async (importOriginal) => {
  const mod = await importOriginal<typeof import("../api/client")>();
  return { ...mod, delay: <T,>(value: T, ms?: number) => mod.delay(value, net.slow ? 900 : ms) };
});

afterEach(() => {
  net.slow = false;
  closeApp();
  vi.useRealTimers();
});

type App = Awaited<ReturnType<typeof openApp>>;

async function openBooking(s: App) {
  fireEvent.click(await s.findByRole("button", { name: "Book trade" }, SLOW));
  return s.findByRole("dialog", { name: "Book trade" }, SLOW);
}

async function book(s: App, quantity: string, client = /^Harbor Pension Trust$/) {
  const dialog = await openBooking(s);
  await pickReady(await within(dialog).findByLabelText("Client", {}, SLOW), client);
  await pickReady(within(dialog).getByLabelText("Instrument"), /^AAPL\b/);
  await pickReady(within(dialog).getByLabelText("Side"), /^Buy$/);
  fireEvent.change(within(dialog).getByLabelText("Quantity"), { target: { value: quantity } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Book" }));
  await waitFor(() => expect(s.queryByRole("dialog", { name: "Book trade" })).not.toBeInTheDocument(), SLOW);
}

const nav = (s: App, name: string) => fireEvent.click(within(s.getByRole("navigation", { name: "Primary" })).getByRole("link", { name }));

describe("E13 booking a trade", () => {
  it("E13 the booking dialog works from the keyboard", async () => {
    const s = await openApp("/trades");
    const button = await s.findByRole("button", { name: "Book trade" }, SLOW);
    button.focus();
    fireEvent.click(button);
    const dialog = await s.findByRole("dialog", { name: "Book trade" }, SLOW);
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
    fireEvent.keyDown(document.activeElement ?? dialog, { key: "Escape", code: "Escape" });
    await waitFor(() => expect(s.queryByRole("dialog", { name: "Book trade" })).not.toBeInTheDocument());
    await waitFor(() => expect(document.activeElement).toBe(s.getByRole("button", { name: "Book trade" })));
  });

  it("E13 a booked trade is pending everywhere trade statuses show", async () => {
    freezeDate("2026-10-27T20:00:00Z");
    const s = await openApp("/trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    const dialog = await openBooking(s);
    await pickReady(await within(dialog).findByLabelText("Instrument", {}, SLOW), /^AAPL\b/);
    expect(Number((within(dialog).getByLabelText("Price") as HTMLInputElement).value)).toBe(227.48);
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await book(s, "500");
    expect(await s.findByText("Trade T-10151 booked.", {}, SLOW)).toBeInTheDocument();
    const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    const row = await within(table).findByRole("row", { name: "Trade T-10151" }, SLOW);
    expect(bodyRows(table)[0]).toBe(row);
    expect(row.textContent).toContain("Pending");
    expect(row.textContent).toContain("Harbor Pension Trust");
    expect(row.textContent).toContain("D. Whitaker");
    const today = s.getByRole("region", { name: "Today" });
    await waitFor(() => expect(figure(today, "Trades")).toBe("18"), SLOW);
    expect(figure(today, "Pending")).toBe("1");
    expect(s.getByRole("button", { name: "Notifications, 3 unread" })).toBeInTheDocument();
    await pickReady(s.getByLabelText("Status"), /^Pending$/);
    expect(await s.findByText("Showing 1 to 1 of 1 trades", {}, SLOW)).toBeInTheDocument();
    fireEvent.click(within(s.getByRole("table", { name: "Trade blotter" })).getByRole("row", { name: "Trade T-10151" }));
    const drawer = await s.findByRole("dialog", { name: "Trade details" }, SLOW);
    await within(drawer).findByText("Remaining", {}, SLOW);
    expect(within(drawer).getByText("Pending")).toBeInTheDocument();
    expect(figure(drawer, "Remaining")).toBe("500");
    expect(figure(drawer, "Venue")).toBe("Pulse");
  });

  it("E13 the ticket refuses a missing quantity or a zero price", async () => {
    const s = await openApp("/trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    const dialog = await openBooking(s);
    await within(dialog).findByLabelText("Quantity", {}, SLOW);
    fireEvent.click(within(dialog).getByRole("button", { name: "Book" }));
    expect(await within(dialog).findByText("Enter a quantity above zero")).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText("Quantity"), { target: { value: "10" } });
    fireEvent.change(within(dialog).getByLabelText("Price"), { target: { value: "0" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Book" }));
    expect(await within(dialog).findByText("Enter a price above zero")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(s.queryByRole("dialog", { name: "Book trade" })).not.toBeInTheDocument());
    await sleep(300);
    expect(s.getByText("Showing 1 to 25 of 150 trades")).toBeInTheDocument();
  });

  it("E14 only a pending trade can be cancelled from its drawer", async () => {
    const s = await openApp("/trades?trade=T-10150");
    const filled = await s.findByRole("dialog", { name: "Trade details" }, SLOW);
    await within(filled).findByText("Remaining", {}, SLOW);
    expect(within(filled).queryByRole("button", { name: "Cancel trade" })).not.toBeInTheDocument();
    fireEvent.click(within(filled).getByRole("button", { name: "Close trade details" }));
    await book(s, "500");
    const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    fireEvent.click(await within(table).findByRole("row", { name: "Trade T-10151" }, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Trade details" }, SLOW);
    fireEvent.click(await within(drawer).findByRole("button", { name: "Cancel trade" }, SLOW));
    expect(await within(drawer).findByText("Cancelled", {}, SLOW)).toBeInTheDocument();
    expect(within(drawer).queryByRole("button", { name: "Cancel trade" })).not.toBeInTheDocument();
    await waitFor(() => {
      const row = within(s.getByRole("table", { name: "Trade blotter" })).getByRole("row", { name: "Trade T-10151" });
      expect(row.textContent).toContain("Cancelled");
    }, SLOW);
  });
});

describe("E16 large trade alerts", () => {
  it("E16 a large booking raises a notification that opens the trade", async () => {
    const s = await openApp("/trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    await s.findByRole("button", { name: "Notifications, 3 unread" }, SLOW);
    await book(s, "10000");
    const bell = await s.findByRole("button", { name: "Notifications, 4 unread" }, SLOW);
    fireEvent.click(bell);
    const list = await s.findByRole("region", { name: "Notification list" }, SLOW);
    fireEvent.click(within(list).getByRole("link", { name: "Large trade booked: T-10151" }));
    expect(await s.findByRole("heading", { name: "Trade T-10151" }, SLOW)).toBeInTheDocument();
    expect(new URLSearchParams(window.location.search).get("trade")).toBe("T-10151");
  });

  it("E16 the threshold comes from Settings", async () => {
    const s = await openApp("/settings");
    fireEvent.change(s.getByLabelText("Large trade alert (USD)"), { target: { value: "5000000" } });
    nav(s, "Trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    await book(s, "10000");
    expect(await s.findByText("Trade T-10151 booked.", {}, SLOW)).toBeInTheDocument();
    await sleep(300);
    expect(s.getByRole("button", { name: "Notifications, 3 unread" })).toBeInTheDocument();
  });
});

describe("E15 client exposure", () => {
  function exposureRow(symbol: string) {
    const table = document.querySelector("table");
    const row = Array.from(table?.querySelectorAll("tbody tr") ?? []).find((r) => (r.firstElementChild?.textContent ?? "").trim() === symbol);
    return row ? Array.from(row.children).map((cell) => (cell.textContent ?? "").trim()) : null;
  }

  it("E15 exposure page lists a client's position per instrument", async () => {
    const s = await openApp("/");
    nav(s, "Exposure");
    expect(await s.findByRole("heading", { level: 1, name: "Exposure" }, SLOW)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/exposure");
    expect(s.getByText("Pick a client to see their exposure.")).toBeInTheDocument();
    await pickReady(s.getByLabelText("Client"), /^Harbor Pension Trust$/);
    expect(await s.findByRole("heading", { name: "Exposure for Harbor Pension Trust" }, SLOW)).toBeInTheDocument();
    await waitFor(() => expect(new URLSearchParams(window.location.search).get("client")).toBe("c-002"));
    const table = await s.findByRole("table", { name: "Exposure by instrument" }, SLOW);
    expect(headers(table)).toEqual(["Instrument", "Bought", "Sold", "Net", "Trades"]);
    expect(exposureRow("AAPL")).toEqual(["AAPL", "0", "3,950", expect.stringMatching(/^[-−]3,950$/), "2"]);
    expect(exposureRow("NVDA")).toEqual(["NVDA", "11,550", "0", "11,550", "3"]);
    const symbols = bodyRows(table).map((r) => (r.firstElementChild?.textContent ?? "").trim());
    expect(symbols).toEqual([...symbols].sort());
  });

  it("E15 the client drawer links to that client's exposure", async () => {
    const s = await openApp("/clients");
    fireEvent.click(await s.findByText("Harbor Pension Trust", {}, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    fireEvent.click(await within(drawer).findByRole("link", { name: "View exposure" }, SLOW));
    expect(await s.findByRole("heading", { name: "Exposure for Harbor Pension Trust" }, SLOW)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/exposure");
    expect(new URLSearchParams(window.location.search).get("client")).toBe("c-002");
  });

  it("E15 switching clients quickly never shows one client's positions under another's name", async () => {
    const s = await openApp("/exposure?client=c-001");
    await s.findByRole("heading", { name: "Exposure for Northwind Capital" }, SLOW);
    const select = s.getByLabelText("Client");
    await pickReady(select, /^Northwind Capital$/);
    net.slow = true;
    await pickReady(select, /^Harbor Pension Trust$/);
    await sleep(100);
    net.slow = false;
    await pickReady(s.getByLabelText("Client"), /^Sable Insurance$/);
    await s.findByRole("heading", { name: "Exposure for Sable Insurance" }, SLOW);
    await waitFor(() => expect(exposureRow("XAU")).not.toBeNull(), SLOW);
    await sleep(1300);
    expect(s.getByRole("heading", { name: "Exposure for Sable Insurance" })).toBeInTheDocument();
    expect(s.queryByRole("heading", { name: "Exposure for Harbor Pension Trust" })).not.toBeInTheDocument();
    expect(exposureRow("XAU")).toEqual(["XAU", "363", "422", expect.stringMatching(/^[-−]59$/), "2"]);
    expect(exposureRow("EURUSD")).toBeNull();
  });

  it("E15 a trade booked after a client was viewed shows when you come back", async () => {
    const s = await openApp("/exposure?client=c-002");
    await s.findByRole("heading", { name: "Exposure for Harbor Pension Trust" }, SLOW);
    await waitFor(() => expect(exposureRow("AAPL")?.[4]).toBe("2"), SLOW);
    nav(s, "Trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    await book(s, "500");
    await s.findByText("Trade T-10151 booked.", {}, SLOW);
    nav(s, "Exposure");
    await pickReady(await s.findByLabelText("Client", {}, SLOW), /^Harbor Pension Trust$/);
    await s.findByRole("heading", { name: "Exposure for Harbor Pension Trust" }, SLOW);
    await waitFor(() => expect(exposureRow("AAPL")?.[4]).toBe("3"), SLOW);
    expect(exposureRow("AAPL")?.[2]).toBe("3,950");
  });
});
