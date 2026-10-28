import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { closeApp, openApp, sleep, SLOW, testBugs } from "./helpers";

afterEach(closeApp);

describe("bugs, refactor and test cleanup", () => {
  it("B7 the trade pager stops at the last full page", async () => {
    const s = await openApp("/trades");
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    const pager = s.getByRole("navigation", { name: "Pagination" });
    expect(within(pager).queryByRole("button", { name: "Page 7" })).not.toBeInTheDocument();
    fireEvent.click(within(pager).getByRole("button", { name: "Page 6" }));
    expect(await s.findByText("Showing 126 to 150 of 150 trades", {}, SLOW)).toBeInTheDocument();
    expect(within(s.getByRole("navigation", { name: "Pagination" })).getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("B8 client search shows the results for what is in the box after fast typing", async () => {
    const s = await openApp("/clients");
    await s.findByText("Northwind Capital", {}, SLOW);
    const box = s.getByLabelText("Search clients");
    fireEvent.change(box, { target: { value: "h" } });
    await sleep(200);
    fireEvent.change(box, { target: { value: "harbor" } });
    await sleep(1200);
    expect(s.getByText("Harbor Pension Trust")).toBeInTheDocument();
    expect(s.queryByText("Northwind Capital")).not.toBeInTheDocument();
    fireEvent.change(box, { target: { value: "m" } });
    await sleep(200);
    fireEvent.change(box, { target: { value: "meridian" } });
    await sleep(1200);
    expect(s.getByText("Meridian Endowment")).toBeInTheDocument();
    expect(s.queryByText("Harbor Pension Trust")).not.toBeInTheDocument();
  }, 10000);

  it("B9 top bar title and browser tab title agree on every page", async () => {
    const pages: [string, string][] = [
      ["/", "Dashboard"],
      ["/portfolio", "Portfolio"],
      ["/trades", "Trades"],
      ["/clients", "Clients"],
      ["/reports", "Reports"],
      ["/settings", "Settings"],
    ];
    for (const [route, name] of pages) {
      const s = await openApp(route);
      expect(s.getByRole("heading", { level: 1 })).toHaveTextContent(name);
      await waitFor(() => expect(document.title).toBe(`${name} | Pulse`));
      expect(within(s.getByRole("navigation", { name: "Primary" })).getByRole("link", { name })).toBeInTheDocument();
      closeApp();
    }
  });

  it("B9 the instrument page shows its symbol in the top bar and the tab", async () => {
    const s = await openApp("/instruments/AAPL");
    expect(s.getByRole("heading", { level: 1 })).toHaveTextContent(/^AAPL$/);
    await waitFor(() => expect(document.title).toBe("AAPL | Pulse"));
  });

  describe("B10 test suite cleanup", () => {
    const bugs = testBugs();
    it("B10 no skipped or todo tests remain", () => {
      expect(bugs.skipped).toEqual([]);
    });
    it("B10 no snapshot tests or snapshot files remain", () => {
      expect(bugs.snapshots).toEqual([]);
    });
    it("B10 no test body is duplicated inside a test file", () => {
      expect(bugs.duplicates).toEqual([]);
    });
    it("B10 no eslint-disable comment remains in the async hook", () => {
      expect(bugs.suppressions.filter((f) => f.endsWith("useAsync.ts"))).toEqual([]);
    });
  });
});
