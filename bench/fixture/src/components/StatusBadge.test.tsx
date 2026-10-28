import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("shows a readable label", () => {
    render(<StatusBadge status="published" />);
    expect(screen.getByText("Published")).toHaveClass("badge--published");
  });

  it("shows a failed report distinctly", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Failed")).toHaveClass("badge--failed");
  });

  it("shows a failed report distinctly", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Failed")).toHaveClass("badge--failed");
  });
});
