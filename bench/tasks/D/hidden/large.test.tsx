import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { bodyRows, itemTexts, openApp, pickReady, resetApp, rowByLabel, SLOW } from "./helpers";

afterEach(() => {
  resetApp();
  vi.restoreAllMocks();
});

async function portfolio() {
  const s = await openApp("/portfolio");
  const table = await s.findByRole("table", { name: "Holdings" }, SLOW);
  return { s, table };
}

describe("D14 portfolio currency", () => {
  it("D14 shows every portfolio value in euros while prices stay in their own currency", async () => {
    const { s, table } = await portfolio();
    const select = s.getByLabelText("Show values in");
    expect(select).toHaveDisplayValue(/USD/);
    await pickReady(select, /EUR/);
    await waitFor(() => expect(s.getByRole("article", { name: "Market value" }).textContent).toContain("€28.8M"));
    expect(s.getByRole("article", { name: "Unrealized P&L" }).textContent).toContain("+€2M");
    expect(s.getByRole("article", { name: "Day change" }).textContent).toContain("+€112.2K");
    expect(within(table).getByRole("columnheader", { name: /Market value \(EUR\)/ })).toBeInTheDocument();
    const total = within(table).getByText("Total (11 positions)").closest("tr");
    expect(total?.textContent).toContain("€28,786,217.91");
    const aapl = within(table).getByRole("link", { name: "AAPL" }).closest("tr");
    expect(aapl?.textContent).toContain("$227.48");
    expect(aapl?.textContent).toContain("€2,517,764.25");
    expect(itemTexts(s.getByRole("region", { name: "Allocation" }))).toContain("Equities: €10.9M (38.0%)");
  });

  it("D14 switches to pounds and back to dollars", async () => {
    const { s, table } = await portfolio();
    await pickReady(s.getByLabelText("Show values in"), /GBP/);
    await waitFor(() => expect(s.getByRole("article", { name: "Market value" }).textContent).toContain("£24.1M"));
    expect(within(table).getByRole("columnheader", { name: /Market value \(GBP\)/ })).toBeInTheDocument();
    await pickReady(s.getByLabelText("Show values in"), /USD/);
    await waitFor(() => expect(s.getByRole("article", { name: "Market value" }).textContent).toContain("$31.2M"));
    expect(within(table).getByText("Total (11 positions)").closest("tr")?.textContent).toContain("$31,210,017.46");
  });
});

describe("D16 P&L by book", () => {
  it("D16 lists every book, largest market value first, in whole dollars", async () => {
    const { s } = await portfolio();
    const books = await s.findByRole("table", { name: "P&L by book" }, SLOW);
    const names = bodyRows(books).map((row) => (row.cells[0]?.textContent ?? "").trim());
    expect(names).toEqual(["Macro overlay", "Rates", "Core equity", "Growth", "Real assets"]);
    const core = rowByLabel("Core equity", books);
    expect(core.textContent).toContain("$6,464,538");
    expect(core.textContent).not.toContain("$6,464,538.");
    expect(core.textContent).toContain("+$797,864");
    expect(Array.from(core.cells).some((cell) => (cell.textContent ?? "").trim() === "3")).toBe(true);
    expect(rowByLabel("Macro overlay", books).textContent).toContain("-$73,661");
  });

  it("D16 follows the currency but not the book filter", async () => {
    const { s } = await portfolio();
    await pickReady(s.getByLabelText("Book"), /^Growth$/);
    await pickReady(s.getByLabelText("Show values in"), /EUR/);
    await waitFor(() => expect(rowByLabel("Core equity", s.getByRole("table", { name: "P&L by book" })).textContent).toContain("+€735,901"));
    expect(bodyRows(s.getByRole("table", { name: "P&L by book" }))).toHaveLength(5);
  });
});

describe("D17 export holdings", () => {
  it("D17 Export holdings produces a file or a print view", async () => {
    const created = vi.fn((_blob: Blob) => "blob:holdings");
    Object.defineProperty(URL, "createObjectURL", { value: created, configurable: true, writable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), configurable: true, writable: true });
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    // A download link's click would make jsdom try to navigate; the file itself is what counts.
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const { s } = await portfolio();
    const control =
      s.queryByRole("button", { name: "Export holdings" }) ?? s.getByRole("link", { name: "Export holdings" });
    const before = window.location.pathname + window.location.search;
    fireEvent.click(control);
    await waitFor(
      () => {
        const moved = window.location.pathname + window.location.search !== before;
        expect(created.mock.calls.length + print.mock.calls.length + (moved ? 1 : 0)).toBeGreaterThan(0);
      },
      SLOW,
    );
  });
});
