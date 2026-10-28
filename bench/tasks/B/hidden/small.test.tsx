import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, within } from "@testing-library/react";
import fxRates from "../data/fx-rates.json";
import holdings from "../data/holdings.json";
import instruments from "../data/instruments.json";
import { closeApp, openApp, SLOW, themeBlocks, token } from "./helpers";

afterEach(closeApp);

const signedUsd0 = (value: number) =>
  `${value > 0 ? "+" : value < 0 ? "-" : ""}${new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Math.abs(value))}`;

function dayChangeUsd(symbol?: string): number {
  const rates = fxRates as Record<string, number>;
  let total = 0;
  for (const h of holdings) {
    if (symbol && h.symbol !== symbol) continue;
    const i = instruments.find((row) => row.symbol === h.symbol)!;
    const value = h.quantity * i.price * (rates[i.currency] ?? 0);
    total += value - value / (1 + i.changePct);
  }
  return total;
}

function headerTexts(table: HTMLElement): string[] {
  return within(table)
    .getAllByRole("columnheader")
    .map((h) => (h.textContent ?? "").replace(/[▲▼]/g, "").trim());
}

describe("small asks", () => {
  it("B1 unrealized P&L is called Open P&L on the portfolio page", async () => {
    const s = await openApp("/portfolio");
    const table = await s.findByRole("table", { name: "Holdings" }, SLOW);
    expect(headerTexts(table)).toContain("Open P&L");
    expect(s.getByRole("article", { name: "Open P&L" })).toBeInTheDocument();
    expect(s.queryByText("Unrealized P&L")).not.toBeInTheDocument();
  });

  it("B2 holdings have a Day change column after Price with a total", async () => {
    const s = await openApp("/portfolio");
    const table = await s.findByRole("table", { name: "Holdings" }, SLOW);
    const headers = headerTexts(table);
    expect(headers.indexOf("Day change")).toBe(headers.indexOf("Price") + 1);
    const aapl = within(table).getByRole("rowheader", { name: /^AAPL/ }).closest("tr")!;
    const col = headers.indexOf("Day change");
    expect(aapl.cells[col]?.textContent).toContain(signedUsd0(dayChangeUsd("AAPL")));
    const totals = within(table).getByText("Total (11 positions)").closest("tr")!;
    let start = 0;
    let dayCell: HTMLTableCellElement | undefined;
    for (const cell of Array.from(totals.cells)) {
      if (start === col) dayCell = cell;
      start += cell.colSpan;
    }
    expect(start).toBe(headers.length);
    expect(dayCell?.textContent).toContain(signedUsd0(dayChangeUsd()));
  });

  it("B3 client rows show AUM with two decimals", async () => {
    const s = await openApp("/clients");
    expect(await s.findByRole("button", { name: /Northwind Capital/ }, SLOW)).toHaveTextContent("AUM $1.25B");
    expect(s.getByRole("button", { name: /Harbor Pension Trust/ })).toHaveTextContent("AUM $3.4B");
    expect(s.getByRole("button", { name: /Lumen Robotics/ })).toHaveTextContent("AUM $86M");
  });

  it("B4 client tier is capitalized in the list and the drawer", async () => {
    const s = await openApp("/clients");
    expect((await s.findAllByText("EMEA · Institutional", {}, SLOW)).length).toBe(3);
    expect(s.getByText("APAC · Corporate")).toBeInTheDocument();
    expect(s.queryByText(/\/ institutional/)).not.toBeInTheDocument();
    fireEvent.click(s.getByText("Granite Family Office"));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    const tier = (await within(drawer).findByText("Tier", {}, SLOW)).nextElementSibling;
    expect(tier?.textContent).toBe("Private");
  });

  it("B5 corner radius and drawer width tokens have the requested values", () => {
    const { light } = themeBlocks();
    expect(token(light, "--radius")).toBe("6px");
    expect(token(light, "--drawer-width")).toBe("480px");
  });

  it("B6 report tabs show how many reports each has", async () => {
    const s = await openApp("/reports");
    await s.findByText("Daily market wrap", {}, SLOW);
    const expected: [string, number][] = [
      ["All", 8],
      ["Published", 4],
      ["Scheduled", 2],
      ["Drafts", 1],
      ["Failed", 1],
    ];
    for (const [label, count] of expected) {
      expect(await s.findByRole("tab", { name: new RegExp(`^${label}\\s*${count}$`) }, SLOW)).toBeInTheDocument();
    }
  });
});
