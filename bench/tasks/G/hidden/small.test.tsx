// Task G, small asks. Test names start with the ask id.
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { fireEvent, within } from "@testing-library/react";
import { ACCOUNTS, closeApp, navLink, onPage, openApp, primaryNav, seedSession, SETTINGS_STORAGE_KEY, SLOW } from "./helpers";

beforeEach(() => localStorage.clear());
afterEach(closeApp);

describe("small", () => {
  it("G9 the user menu shows the name of whoever is signed in", async () => {
    seedSession(ACCOUNTS.marc.email);
    const s = await openApp("/");
    expect(await s.findByRole("button", { name: "Marc Ellery" }, SLOW)).toBeInTheDocument();
    expect(s.queryByRole("button", { name: "Dana Whitaker" })).not.toBeInTheDocument();
  });

  it("G10 the sign-in page is standalone, in a main area, with its own tab title", async () => {
    const s = await openApp("/sign-in");
    expect(await s.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(s.getByRole("main")).toBeInTheDocument();
    expect(s.queryByRole("navigation", { name: "Primary" })).not.toBeInTheDocument();
    expect(s.queryByRole("banner")).not.toBeInTheDocument();
    expect(document.title).toBe("Sign in | Pulse");
    expect(s.getByLabelText("Password")).toHaveAttribute("type", "password");
  });

  it("G11 Settings has an Account panel with the signed-in email", async () => {
    seedSession(ACCOUNTS.marc.email);
    const s = await openApp("/settings");
    const panel = await s.findByRole("region", { name: "Account" }, SLOW);
    expect(within(panel).getByText("Signed in as marc@pulse.test")).toBeInTheDocument();
  });

  it("G13 the dead Push alerts switch is gone and nothing about push is stored", async () => {
    seedSession(ACCOUNTS.dana.email);
    const s = await openApp("/settings");
    await s.findByRole("region", { name: "Notifications" }, SLOW);
    expect(s.queryByRole("switch", { name: "Push alerts" })).not.toBeInTheDocument();
    expect(s.getByRole("switch", { name: "Email alerts" })).toBeInTheDocument();
    expect(s.getByRole("switch", { name: "Weekly digest" })).toBeInTheDocument();
    fireEvent.click(s.getByRole("switch", { name: "Email alerts" }));
    const stored = localStorage.getItem(SETTINGS_STORAGE_KEY) ?? "";
    expect(JSON.parse(stored).alerts.email).toBe(false);
    expect(stored).not.toMatch(/push/i);
  });

  it("G17 every link in the navigation gives the page the same title, Venues included", async () => {
    seedSession(ACCOUNTS.dana.email);
    const s = await openApp("/");
    await onPage("Dashboard");
    const names = within(primaryNav()).getAllByRole("link").map((a) => a.textContent?.trim() ?? "");
    expect(names).toEqual(expect.arrayContaining(["Dashboard", "Portfolio", "Trades", "Venues", "Clients", "Reports", "Settings"]));
    for (const name of ["Portfolio", "Trades", "Venues", "Clients", "Reports", "Settings", "Dashboard"]) {
      fireEvent.click(navLink(name));
      await onPage(name);
    }
    expect(s.getByRole("main")).toBeInTheDocument();
  });
});
