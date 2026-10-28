import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { itemTexts, openApp, resetApp, SLOW } from "./helpers";

afterEach(resetApp);

describe("small asks", () => {
  it("D1 the P&L and day change cards show a sign", async () => {
    const s = await openApp("/portfolio");
    const pnl = await s.findByRole("article", { name: "Unrealized P&L" }, SLOW);
    expect(pnl.textContent).toContain("+$2.2M");
    expect(s.getByRole("article", { name: "Day change" }).textContent).toContain("+$121.6K");
    const value = s.getByRole("article", { name: "Market value" }).textContent ?? "";
    expect(value).toContain("$31.2M");
    expect(value).not.toContain("+");
  });

  it("D2 the allocation legend shows each share next to the amount", async () => {
    const s = await openApp("/portfolio");
    await s.findByRole("img", { name: /Allocation by asset class/ }, SLOW);
    const legend = itemTexts(s.getByRole("region", { name: "Allocation" }));
    expect(legend).toContain("Equities: $11.9M (38.0%)");
    expect(legend).toContain("FX: $8.4M (27.0%)");
    expect(legend).toContain("Commodities: $4.2M (13.6%)");
  });

  it("D3 the client drawer shows AUM in whole dollars", async () => {
    const s = await openApp("/clients");
    fireEvent.click(await s.findByText("Northwind Capital", {}, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    await waitFor(() => expect(drawer.textContent).toContain("$1,250,000,000"), SLOW);
    expect(drawer.textContent).not.toContain("$1,250,000,000.00");
  });

  it("D5 the client search says what it searches", async () => {
    const s = await openApp("/clients");
    const box = s.getByPlaceholderText("Search by name, contact or region");
    expect(box).toBe(s.getByLabelText("Search clients"));
  });

  it("D6 D7 report lines use dots and scheduled reports show when they are due", async () => {
    const s = await openApp("/reports");
    await s.findByText("Daily market wrap", {}, SLOW);
    expect(s.getByText("Oct 27, 2026 · A. Moreau · 6 pages")).toBeInTheDocument();
    expect(s.getByText("Oct 25, 2026 · L. Duarte")).toBeInTheDocument();
    expect(s.getByText("Due Oct 30, 2026 · L. Duarte")).toBeInTheDocument();
    expect(s.getByText("Due Oct 31, 2026 · J. Ortiz")).toBeInTheDocument();
  });

  it("D15 the client list is in A to Z order", async () => {
    const s = await openApp("/clients");
    const region = s.getByRole("region", { name: "Clients" });
    await within(region).findByText("Northwind Capital", {}, SLOW);
    const expected = [
      "Baltic Shipping Fund",
      "Granite Family Office",
      "Harbor Pension Trust",
      "Lumen Robotics",
      "Meridian Endowment",
      "Northwind Capital",
      "Orchid Wealth",
      "Pinecrest Logistics",
      "Quill Software",
      "Sable Insurance",
    ];
    const items = itemTexts(region);
    expect(items).toHaveLength(expected.length);
    items.forEach((text, index) => expect(text.startsWith(expected[index]!)).toBe(true));
  });
});
