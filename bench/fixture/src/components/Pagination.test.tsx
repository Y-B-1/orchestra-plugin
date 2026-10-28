import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Pagination } from "./Pagination";

describe("Pagination", () => {
  it("summarises the visible range and disables Previous and Next at the ends", () => {
    render(<Pagination total={60} page={2} pageSize={25} onPageChange={() => undefined} noun="trades" />);
    expect(screen.getByText("Showing 26 to 50 of 60 trades")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 2" })).toHaveAttribute("aria-current", "page");
    cleanup();
    const { rerender } = render(<Pagination total={60} page={1} pageSize={25} onPageChange={() => undefined} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    rerender(<Pagination total={60} page={3} pageSize={25} onPageChange={() => undefined} />);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("requests the chosen page", () => {
    const onPageChange = vi.fn();
    render(<Pagination total={60} page={1} pageSize={25} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Page 3" }));
    expect(onPageChange.mock.calls).toEqual([[2], [3]]);
  });
});
