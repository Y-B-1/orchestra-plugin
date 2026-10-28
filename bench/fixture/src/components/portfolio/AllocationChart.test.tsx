import { cleanup, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AllocationChart } from "./AllocationChart";

describe("AllocationChart", () => {
  const slices = [
    { assetClass: "equity" as const, valueUsd: 600, weight: 0.6 },
    { assetClass: "bond" as const, valueUsd: 400, weight: 0.4 },
  ];

  it("describes every slice to assistive technology", () => {
    render(<AllocationChart slices={slices} />);
    const chart = screen.getByRole("img", { name: /Allocation by asset class/ });
    expect(chart).toHaveAccessibleName("Allocation by asset class Equities 60.0%, Bonds 40.0%");
  });

  it("scales bars to the largest slice and explains an empty portfolio", () => {
    const { container } = render(<AllocationChart slices={slices} />);
    const bars = container.querySelectorAll("rect.allocation__bar");
    expect(bars).toHaveLength(2);
    const [equity, bond] = Array.from(bars).map((bar) => Number(bar.getAttribute("width")));
    expect(equity).toBe(300);
    expect(bond).toBeCloseTo(200);
    cleanup();
    render(<AllocationChart slices={[]} />);
    expect(screen.getByText("No holdings to allocate.")).toBeInTheDocument();
  });
});
