import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, describe, expect, it } from "vitest";
import { fetchPositions, latency } from "../api";
import { formatCurrency } from "../utils/format";
import { Portfolio } from "./Portfolio";

beforeAll(() => {
  latency.ms = 0;
});

function renderPortfolio() {
  return render(
    <MemoryRouter>
      <Portfolio />
    </MemoryRouter>,
  );
}

describe("Portfolio page", () => {
  it("shows holdings largest first with a totals row", async () => {
    renderPortfolio();
    const table = await screen.findByRole("table", { name: "Holdings" });
    const rowHeaders = within(table).getAllByRole("rowheader");
    expect(rowHeaders[0]).toHaveTextContent("EURUSD");
    expect(rowHeaders[rowHeaders.length - 1]).toHaveTextContent("Total (11 positions)");
    const positions = await fetchPositions();
    const total = positions.reduce((sum, p) => sum + p.marketValueUsd, 0);
    expect(screen.getByTestId("total-market-value")).toHaveTextContent(formatCurrency(total));
  });

  it("re-sorts holdings and charts the allocation", async () => {
    renderPortfolio();
    const table = await screen.findByRole("table", { name: "Holdings" });
    fireEvent.click(within(table).getByRole("button", { name: "Instrument" }));
    expect(within(table).getAllByRole("rowheader")[0]).toHaveTextContent("AAPL");
    cleanup();
    renderPortfolio();
    expect(await screen.findByRole("img", { name: /Allocation by asset class/ })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Portfolio summary" })).toBeInTheDocument();
  });
});
