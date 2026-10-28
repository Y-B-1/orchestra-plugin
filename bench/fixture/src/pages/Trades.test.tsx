import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, describe, expect, it } from "vitest";
import { latency } from "../api";
import { Trades } from "./Trades";

beforeAll(() => {
  latency.ms = 0;
});

function renderTrades(path = "/trades") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Trades />
    </MemoryRouter>,
  );
}

function bodyRows() {
  const table = screen.getByRole("table", { name: "Trade blotter" });
  return within(table).getAllByRole("row").slice(1);
}

describe("Trades page", () => {
  it("shows 25 trades per page, newest first", async () => {
    renderTrades();
    await screen.findByRole("table", { name: "Trade blotter" });
    expect(bodyRows()).toHaveLength(25);
    expect(bodyRows()[0]).toHaveAccessibleName("Trade T-10150");
    expect(screen.getByText("Showing 1 to 25 of 150 trades")).toBeInTheDocument();
    cleanup();
    renderTrades();
    await screen.findByRole("table", { name: "Trade blotter" });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Showing 26 to 50 of 150 trades")).toBeInTheDocument();
    expect(bodyRows()[0]).toHaveAccessibleName("Trade T-10125");
  });

  it("filters by side and returns to the first page", async () => {
    renderTrades();
    await screen.findByRole("table", { name: "Trade blotter" });
    fireEvent.click(screen.getByRole("button", { name: "Page 2" }));
    fireEvent.click(screen.getByRole("button", { name: "Buy" }));
    await waitFor(() => expect(screen.getByText(/^Showing 1 to 25 of \d+ trades$/)).toBeInTheDocument());
    expect(screen.queryByText(/of 150 trades/)).not.toBeInTheDocument();
  });

  it("starts filtered by the symbol in the address", async () => {
    renderTrades("/trades?symbol=AAPL");
    await screen.findByRole("table", { name: "Trade blotter" });
    await waitFor(() => expect(screen.getByText(/of 15 trades/)).toBeInTheDocument());
  });

  it("opens the trade detail drawer", async () => {
    renderTrades();
    await screen.findByRole("table", { name: "Trade blotter" });
    fireEvent.click(screen.getByRole("row", { name: "Trade T-10150" }));
    const drawer = await screen.findByRole("dialog", { name: "Trade details" });
    expect(await within(drawer).findByText("Venue")).toBeInTheDocument();
  });
});
