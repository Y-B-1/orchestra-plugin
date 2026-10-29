// Small asks: copy changes, the closed badge and the switch colors.
import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, within } from "@testing-library/react";
import { closeApp, openApp, read, SLOW, SRC, themeBlocks, token } from "./helpers";
import { join } from "node:path";

afterEach(closeApp);

describe("small", () => {
  it("F2 closed accounts carry a Closed badge in the client list", async () => {
    const s = await openApp("/clients");
    const region = await s.findByRole("region", { name: "Clients" });
    await within(region).findAllByText(/Quill Software/, {}, SLOW);
    const closed = within(region).getAllByText("Closed");
    expect(closed).toHaveLength(1);
    const items = within(region).getAllByRole("listitem");
    expect(items.filter((li) => /Quill Software/.test(li.textContent ?? ""))).toHaveLength(2);
    expect(items.filter((li) => /Closed/.test(li.textContent ?? "")).map((li) => li.textContent)).toEqual([
      expect.stringContaining("Quill Software"),
    ]);
  });

  it("F12 the holdings hint says whole USD", async () => {
    const s = await openApp("/portfolio");
    await s.findByRole("table", { name: "Holdings" }, SLOW);
    expect(s.getByText("Values in whole USD at today's FX rates")).toBeInTheDocument();
  });

  it("F13 the client search placeholder mentions contacts", async () => {
    const s = await openApp("/clients");
    expect(await s.findByPlaceholderText("Search clients or contacts", {}, SLOW)).toBeInTheDocument();
    expect(s.getByLabelText("Search clients")).toBeInTheDocument();
  });

  it("F14 the reports tab is called Draft", async () => {
    const s = await openApp("/reports");
    expect(await s.findByRole("tab", { name: "Draft" }, SLOW)).toBeInTheDocument();
    expect(s.queryByRole("tab", { name: "Drafts" })).not.toBeInTheDocument();
  });

  it("F15 the trades export button says what it exports", async () => {
    const s = await openApp("/trades");
    expect(await s.findByRole("button", { name: "Export trades CSV" }, SLOW)).toBeInTheDocument();
    expect(s.queryByRole("button", { name: "Export CSV" })).not.toBeInTheDocument();
  });

  it("F16 the client drawer labels AUM in USD", async () => {
    const s = await openApp("/clients");
    fireEvent.click(await s.findByText("Northwind Capital", {}, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    expect(await within(drawer).findByText("Assets under management (USD)", {}, SLOW)).toBeInTheDocument();
  });

  it("F17 the dark theme description says everywhere", async () => {
    const s = await openApp("/settings");
    expect(await s.findByText("Use the dark color scheme everywhere.")).toBeInTheDocument();
  });

  it("F8 the switch on-color is a theme token with its own value in each theme", () => {
    const { light, dark } = themeBlocks();
    expect(token(light, "--color-switch-on")).toBe("#2f5bea");
    expect(token(dark, "--color-switch-on")).toBe("#8fa8ff");
    const css = read(join(SRC, "styles", "global.css"));
    expect(css).toContain("var(--color-switch-on)");
    const toggleRules = Array.from(css.matchAll(/[^{}]*\.toggle[^{]*\{([^}]*)\}/g)).map((m) => m[1] ?? "");
    for (const body of toggleRules) expect(body).not.toMatch(/#[0-9a-fA-F]{3,8}\b|rgba?\(/);
  });

  it("F8 switches that are on carry the on class, in light and in dark", async () => {
    const s = await openApp("/settings");
    const email = await s.findByRole("switch", { name: "Email alerts" });
    const push = s.getByRole("switch", { name: "Push alerts" });
    for (const theme of ["light", "dark"] as const) {
      const dark = s.getByRole("switch", { name: "Dark theme" }) as HTMLInputElement;
      if (dark.checked !== (theme === "dark")) fireEvent.click(dark);
      expect(document.documentElement.dataset.theme).toBe(theme);
      expect(email.closest(".toggle--on")).not.toBeNull();
      expect(push.closest(".toggle--on")).toBeNull();
      fireEvent.click(push);
      expect(push.closest(".toggle--on")).not.toBeNull();
      fireEvent.click(push);
      expect(push.closest(".toggle--on")).toBeNull();
    }
  });
});
