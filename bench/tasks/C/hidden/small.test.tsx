import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, within } from "@testing-library/react";
import { closeApp, openApp, read, SLOW, sourceFiles, themeBlocks, token } from "./helpers";

afterEach(closeApp);

describe("small asks", () => {
  it("C1 the watch button says Add to watchlist and On watchlist", async () => {
    const s = await openApp("/instruments/MSFT");
    const add = await s.findByRole("button", { name: "Add to watchlist" }, SLOW);
    expect(add).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(add);
    const on = await s.findByRole("button", { name: "On watchlist" }, SLOW);
    expect(on).toHaveAttribute("aria-pressed", "true");
    expect(s.queryByRole("button", { name: "Watch" })).not.toBeInTheDocument();
  });

  it("C2 every notification shows a decorative icon for its kind", async () => {
    const s = await openApp("/settings");
    fireEvent.click(await s.findByRole("button", { name: /^Notifications/ }, SLOW));
    const panel = s.getByRole("region", { name: "Notification list" });
    await within(panel).findByText("Large fill on NVDA", {}, SLOW);
    const items = within(panel).getAllByRole("listitem");
    expect(items.length).toBe(8);
    for (const item of items) {
      const svg = item.querySelector("svg");
      expect(svg, item.textContent ?? "").not.toBeNull();
      expect(svg?.closest('[aria-hidden="true"], [role="presentation"], [role="none"]')).not.toBeNull();
    }
  });

  it("C3 the bell's bulk action says Mark all read", async () => {
    const s = await openApp("/settings");
    fireEvent.click(await s.findByRole("button", { name: /^Notifications/ }, SLOW));
    expect(s.getByRole("button", { name: "Mark all read" })).toBeInTheDocument();
    expect(s.queryByRole("button", { name: "Mark all as read" })).not.toBeInTheDocument();
  });

  it("C4 the unread bubble uses its own color token", () => {
    const { light, dark } = themeBlocks();
    expect(token(light, "--color-badge")).toBe("#d92d20");
    expect(token(dark, "--color-badge")).toBe("#ff6b61");
    const css = sourceFiles().filter((f) => f.endsWith(".css")).map(read).join("\n");
    expect(css).toContain("var(--color-badge)");
  });

  it("C5 the dashboard watchlist shows each instrument's name", async () => {
    const s = await openApp("/");
    const watch = await s.findByRole("region", { name: "Watchlist" }, SLOW);
    expect(await within(watch).findByText("Apple Inc.", {}, SLOW)).toBeInTheDocument();
    expect(within(watch).getByText("Euro / US dollar")).toBeInTheDocument();
    expect(within(watch).getByText("Gold spot")).toBeInTheDocument();
  });

  it("C6 the email alerts setting describes price alerts", async () => {
    const s = await openApp("/settings");
    expect(s.getByText("When one of your price alerts goes off.")).toBeInTheDocument();
    expect(s.queryByText("Price moves above your thresholds.")).not.toBeInTheDocument();
  });
});
