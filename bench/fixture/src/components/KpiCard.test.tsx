import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Kpi } from "../types";
import { KpiCard } from "./KpiCard";

const kpi: Kpi = { id: "trades", label: "Trades today", value: 18342, format: "number", deltaPct: -0.0311 };

describe("KpiCard", () => {
  it("shows the label, value and signed delta", () => {
    render(<KpiCard kpi={kpi} />);
    expect(screen.getByText("Trades today")).toBeInTheDocument();
    expect(screen.getByText("18,342")).toBeInTheDocument();
    expect(screen.getByText("-3.11%")).toHaveClass("kpi-card__delta--down");
  });

  it("matches the recorded markup", () => {
    const { container } = render(<KpiCard kpi={kpi} />);
    expect(container.innerHTML).toMatchSnapshot();
  });

  it.skip("renders a sparkline (blocked on charting library upgrade to v2)", () => {
    render(<KpiCard kpi={kpi} />);
    expect(screen.getByTestId("sparkline")).toBeInTheDocument();
  });
});
