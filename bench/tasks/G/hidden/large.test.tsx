// Task G, large asks: the preference migration, the navigation variants and the Venues page.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import trades from "../data/trades.json";
import {
  ACCOUNTS,
  bodyRows,
  closeApp,
  navLink,
  onPage,
  openApp,
  primaryNav,
  seedSession,
  SETTINGS_STORAGE_KEY,
  SLOW,
} from "./helpers";

beforeEach(() => {
  localStorage.clear();
  seedSession(ACCOUNTS.dana.email);
});
afterEach(() => {
  closeApp();
  vi.restoreAllMocks();
});

const stored = () => JSON.parse(localStorage.getItem(SETTINGS_STORAGE_KEY) ?? "null");

describe("large: saved preferences", () => {
  it("G12 the old flat shape is migrated on load, quietly, and written back", async () => {
    localStorage.setItem(
      SETTINGS_STORAGE_KEY,
      JSON.stringify({ theme: "dark", emailAlerts: false, pushAlerts: true, weeklyDigest: false }),
    );
    const dialogs = [vi.spyOn(window, "confirm"), vi.spyOn(window, "prompt"), vi.spyOn(window, "alert")];
    const s = await openApp("/settings");
    await s.findByRole("region", { name: "Notifications" }, SLOW);
    expect(s.getByRole("switch", { name: "Email alerts" })).not.toBeChecked();
    expect(s.getByRole("switch", { name: "Weekly digest" })).not.toBeChecked();
    expect(s.getByRole("switch", { name: "Dark theme" })).toBeChecked();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(stored()).toEqual({ theme: "dark", alerts: { email: false, digest: false }, navbar: "sidebar" });
    for (const spy of dialogs) expect(spy).not.toHaveBeenCalled();
  });

  it("G12 missing old values get the defaults", async () => {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify({ theme: "dark", emailAlerts: false }));
    const s = await openApp("/settings");
    await s.findByRole("region", { name: "Notifications" }, SLOW);
    expect(s.getByRole("switch", { name: "Weekly digest" })).toBeChecked();
    expect(stored()).toEqual({ theme: "dark", alerts: { email: false, digest: true }, navbar: "sidebar" });
  });

  it("G12 the new shape is left alone, and nothing stored means the defaults", async () => {
    const current = { theme: "light", alerts: { email: false, digest: true }, navbar: "compact" };
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(current));
    await openApp("/settings");
    await onPage("Settings");
    expect(stored()).toEqual(current);
    closeApp();
    localStorage.removeItem(SETTINGS_STORAGE_KEY);
    await openApp("/settings");
    await onPage("Settings");
    expect(stored()).toEqual({ theme: "light", alerts: { email: true, digest: true }, navbar: "sidebar" });
  });
});

describe("large: navigation variants", () => {
  it("G15 starts as the sidebar and the Navigation style group has three buttons", async () => {
    const s = await openApp("/settings");
    await onPage("Settings");
    expect(primaryNav()).toHaveAttribute("data-variant", "sidebar");
    const group = s.getByRole("group", { name: "Navigation style" });
    expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["Sidebar", "Compact", "Top bar"]);
    expect(within(group).getByRole("button", { name: "Sidebar" })).toHaveAttribute("aria-pressed", "true");
  });

  it("G15 the three variants are distinct and each keeps every link, the current page and Venues", async () => {
    const s = await openApp("/settings");
    await onPage("Settings");
    const seen = new Set<string>();
    const inHeader: boolean[] = [];
    for (const [button, variant] of [["Sidebar", "sidebar"], ["Compact", "compact"], ["Top bar", "top"]] as const) {
      fireEvent.click(within(s.getByRole("group", { name: "Navigation style" })).getByRole("button", { name: button }));
      await waitFor(() => expect(primaryNav()).toHaveAttribute("data-variant", variant), SLOW);
      seen.add(primaryNav().getAttribute("data-variant") ?? "");
      inHeader.push(primaryNav().closest("header") !== null);
      for (const name of ["Dashboard", "Portfolio", "Trades", "Venues", "Clients", "Reports", "Settings"]) {
        expect(navLink(name)).toBeInTheDocument();
      }
      expect(navLink("Settings")).toHaveAttribute("aria-current", "page");
      expect(navLink("Trades")).not.toHaveAttribute("aria-current");
      expect(s.getAllByRole("navigation", { name: "Primary" })).toHaveLength(1);
    }
    expect(seen.size).toBe(3);
    expect(inHeader).toEqual([false, false, true]);
  });

  it("G15 the compact variant keeps the full page name as the tooltip and the accessible name", async () => {
    localStorage.setItem(
      SETTINGS_STORAGE_KEY,
      JSON.stringify({ theme: "light", alerts: { email: true, digest: true }, navbar: "compact" }),
    );
    const s = await openApp("/portfolio");
    await onPage("Portfolio");
    expect(primaryNav()).toHaveAttribute("data-variant", "compact");
    for (const name of ["Dashboard", "Portfolio", "Trades", "Venues", "Clients", "Reports", "Settings"]) {
      expect(navLink(name)).toHaveAttribute("title", name);
    }
    expect(navLink("Portfolio")).toHaveAttribute("aria-current", "page");
    fireEvent.click(navLink("Venues"));
    await onPage("Venues");
    expect(s.getByRole("banner")).not.toContainElement(primaryNav());
  });

  it("G15 the choice is saved as navbar and survives a reload; the top variant sits inside the header", async () => {
    const s = await openApp("/settings");
    await onPage("Settings");
    fireEvent.click(within(s.getByRole("group", { name: "Navigation style" })).getByRole("button", { name: "Top bar" }));
    await waitFor(() => expect(stored().navbar).toBe("top"), SLOW);
    closeApp();
    const again = await openApp("/");
    await onPage("Dashboard");
    expect(primaryNav()).toHaveAttribute("data-variant", "top");
    expect(again.getByRole("banner")).toContainElement(primaryNav());
    fireEvent.click(navLink("Trades"));
    await onPage("Trades");
  });
});

function chrome(s: typeof import("@testing-library/react").screen) {
  const title = s.getByRole("heading", { level: 2 });
  const header = title.parentElement!;
  const panel = header.parentElement!;
  const page = panel.parentElement!;
  const wrap = panel.querySelector(".table-wrap");
  return {
    page: page.className,
    panel: [panel.tagName, panel.className],
    header: header.className,
    title: title.className,
    wrap: wrap?.className ?? null,
  };
}

describe("large: Venues page", () => {
  it("G16 has the title, the tab title, the panel and the table names", async () => {
    const s = await openApp("/venues");
    await onPage("Venues");
    expect(document.title).toBe("Venues | Pulse");
    expect(await s.findByRole("region", { name: "Venues" }, SLOW)).toBeInTheDocument();
    expect(s.getByRole("heading", { level: 2, name: "Venue summary" })).toBeInTheDocument();
    const table = await s.findByRole("table", { name: "Venue summary" }, SLOW);
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent?.replace(/[▲▼]/g, "").trim())).toEqual([
      "Venue",
      "Trades",
      "Filled",
      "Partially filled",
      "Cancelled",
    ]);
  });

  it("G16 counts every venue's trades and statuses from the trade data", async () => {
    const s = await openApp("/venues");
    const table = await s.findByRole("table", { name: "Venue summary" }, SLOW);
    const expected = new Map<string, number[]>();
    for (const t of trades) {
      const row = expected.get(t.venue) ?? [0, 0, 0, 0];
      row[0] += 1;
      if (t.status === "filled") row[1] += 1;
      if (t.status === "partial") row[2] += 1;
      if (t.status === "cancelled") row[3] += 1;
      expected.set(t.venue, row);
    }
    const rows = bodyRows(table);
    expect(rows).toHaveLength(expected.size);
    for (const row of rows) {
      const cells = Array.from(row.cells).map((c) => c.textContent?.trim() ?? "");
      expect(cells.slice(1).map(Number)).toEqual(expected.get(cells[0]!));
    }
  });

  it("G16 starts sorted by Trades, biggest first, with the arrow; Venue sorts A to Z", async () => {
    const s = await openApp("/venues");
    const table = await s.findByRole("table", { name: "Venue summary" }, SLOW);
    const header = within(table).getByRole("columnheader", { name: /Trades/ });
    expect(header).toHaveAttribute("aria-sort", "descending");
    expect(header).toHaveTextContent("▼");
    expect(bodyRows(table)[0]!.cells[0]).toHaveTextContent("NYSE");
    expect(bodyRows(table)[1]!.cells[0]).toHaveTextContent("NASDAQ");
    expect(bodyRows(table).at(-1)!.cells[0]).toHaveTextContent("CME Globex");
    fireEvent.click(within(table).getByRole("button", { name: /^Venue/ }));
    expect(within(table).getByRole("columnheader", { name: /^Venue/ })).toHaveAttribute("aria-sort", "ascending");
    expect(bodyRows(table)[0]!.cells[0]).toHaveTextContent("CME Globex");
  });

  it("G16 looks like the Trades page: same wrapper, panel, header, title and table classes", async () => {
    const s = await openApp("/trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    const trades = chrome(s);
    closeApp();
    const v = await openApp("/venues");
    const table = await v.findByRole("table", { name: "Venue summary" }, SLOW);
    const venues = chrome(v);
    expect(venues).toEqual(trades);
    expect(venues.page).toContain("page");
    expect(venues.panel[1]).toContain("panel");
    expect(venues.header).toContain("panel__header");
    expect(venues.title).toContain("panel__title");
    expect(table.className).toContain("table");
    const numeric = within(table).getByRole("columnheader", { name: /^Trades/ });
    expect(numeric.className).toContain("table__num");
    expect(bodyRows(table)[0]!.cells[1]!.className).toContain("table__num");
  });
});
