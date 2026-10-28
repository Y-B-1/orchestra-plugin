import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { closeApp, openApp, SLOW, themeBlocks, token } from "./helpers";

afterEach(closeApp);

describe("small asks", () => {
  it("A1 every sidebar link has a decorative icon and keeps its name", async () => {
    const s = await openApp("/settings");
    const nav = s.getByRole("navigation", { name: "Primary" });
    for (const name of ["Dashboard", "Portfolio", "Trades", "Clients", "Reports", "Settings"]) {
      expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    }
    for (const link of within(nav).getAllByRole("link")) {
      const svg = link.querySelector("svg");
      expect(svg, `icon in ${link.textContent}`).not.toBeNull();
      expect(svg?.closest('[aria-hidden="true"], [role="presentation"], [role="none"]')).not.toBeNull();
    }
  });

  it("A2 price moves show an up or down arrow in front", async () => {
    const s = await openApp("/");
    const movers = await s.findByRole("region", { name: "Top movers" }, SLOW);
    const nvda = (await within(movers).findByRole("link", { name: "NVDA" }, SLOW)).closest("li");
    const tsla = within(movers).getByRole("link", { name: "TSLA" }).closest("li");
    expect(nvda?.textContent).toMatch(/▲\s*\+2\.81%/);
    expect(tsla?.textContent).toMatch(/▼\s*-2\.13%/);
    const watch = s.getByRole("region", { name: "Watchlist" });
    const eurusd = within(watch).getByRole("link", { name: "EURUSD" }).closest("li");
    expect(eurusd?.textContent).toMatch(/▼\s*-0\.11%/);
    expect(eurusd?.textContent).not.toContain("▲");
  });

  it("A3 the trade blotter has a Venue column right after Client", async () => {
    const s = await openApp("/trades");
    const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => (h.textContent ?? "").replace(/[▲▼]/g, "").trim());
    expect(headers).toContain("Venue");
    expect(headers.indexOf("Venue")).toBe(headers.indexOf("Client") + 1);
    const row = within(table).getByRole("row", { name: "Trade T-10150" });
    expect(within(row).getByText("ICE")).toBeInTheDocument();
  });

  it("A4 trade times end in UTC", async () => {
    const s = await openApp("/trades");
    const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    const row = within(table).getByRole("row", { name: "Trade T-10150" });
    expect(row.textContent).toContain("Oct 27, 2026, 18:31 UTC");
  });

  it("A5 up and down colors have the requested values", () => {
    const { light, dark } = themeBlocks();
    expect(token(light, "--color-up")).toBe("#15803d");
    expect(token(light, "--color-down")).toBe("#b91c1c");
    expect(token(dark, "--color-up")).toBe("#4ade80");
    expect(token(dark, "--color-down")).toBe("#f87171");
  });

  it("A6 the reset button on the trade filters says Clear filters", async () => {
    const s = await openApp("/trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    const clear = s.getByRole("button", { name: "Clear filters" });
    expect(clear).toBeDisabled();
    expect(s.queryByRole("button", { name: "Reset filters" })).not.toBeInTheDocument();
    fireEvent.click(s.getByRole("button", { name: "Buy" }));
    await waitFor(() => expect(clear).toBeEnabled());
    fireEvent.click(clear);
    await waitFor(() => expect(s.getByRole("button", { name: "Clear filters" })).toBeDisabled());
  });
});
