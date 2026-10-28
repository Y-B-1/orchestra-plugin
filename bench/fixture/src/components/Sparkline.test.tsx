import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sparkline, sparklinePoints } from "./Sparkline";

describe("sparklinePoints", () => {
  it("maps values to points inside the box", () => {
    const points = sparklinePoints([1, 2, 3, 4], 100, 40, 2);
    expect(points).toHaveLength(4);
    expect(points[0]?.[0]).toBe(2);
    expect(points[3]?.[0]).toBe(98);
    const flat = sparklinePoints([5, 5, 5], 60, 20, 2);
    expect(flat.every(([, y]) => y >= 0 && y <= 20)).toBe(true);
    expect(sparklinePoints([], 60, 20)).toEqual([]);
  });
});

describe("Sparkline", () => {
  it("renders an accessible chart", () => {
    render(<Sparkline values={[1, 3, 2]} label="AAPL closes" tone="up" />);
    expect(screen.getByRole("img", { name: "AAPL closes" })).toHaveClass("sparkline--up");
  });
});
