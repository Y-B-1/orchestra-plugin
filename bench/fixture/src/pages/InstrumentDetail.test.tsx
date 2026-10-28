import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeAll, describe, expect, it } from "vitest";
import { latency } from "../api";
import { InstrumentDetail } from "./InstrumentDetail";

beforeAll(() => {
  latency.ms = 0;
});

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/instruments/:symbol" element={<InstrumentDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Instrument detail page", () => {
  it("shows the quote, key stats, price history and recent trades", async () => {
    renderAt("/instruments/AAPL");
    expect(await screen.findByRole("heading", { name: "Apple Inc." })).toBeInTheDocument();
    expect(screen.getByLabelText("Last price")).toHaveTextContent("$227.48");
    expect(screen.getByText("Previous close")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /AAPL daily closes over 3 months/ })).toBeInTheDocument();
    cleanup();
    renderAt("/instruments/AAPL");
    expect(await screen.findByRole("table", { name: "Recent AAPL trades" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "All AAPL trades" })).toHaveAttribute("href", "/trades?symbol=AAPL");
  });

  it("explains an unknown symbol", async () => {
    renderAt("/instruments/NOPE");
    expect(await screen.findByRole("alert")).toHaveTextContent("Instrument NOPE not found");
  });
});
