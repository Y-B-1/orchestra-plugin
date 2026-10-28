import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Tabs } from "./Tabs";

const tabs = [
  { id: "one", label: "One", render: () => <p>First panel</p> },
  { id: "two", label: "Two", render: () => <p>Second panel</p> },
  { id: "three", label: "Three", badge: 4, render: () => <p>Third panel</p> },
];

describe("Tabs", () => {
  it("shows the first panel by default", () => {
    render(<Tabs label="Sections" tabs={tabs} />);
    expect(screen.getByRole("tab", { name: "One" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("First panel");
  });

  it("switches panels on click and with arrow keys", () => {
    const onChange = vi.fn();
    render(<Tabs label="Sections" tabs={tabs} onChange={onChange} />);
    fireEvent.click(screen.getByRole("tab", { name: "Two" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Second panel");
    expect(onChange).toHaveBeenCalledWith("two");
    cleanup();
    render(<Tabs label="Sections" tabs={tabs} />);
    fireEvent.keyDown(screen.getByRole("tab", { name: "One" }), { key: "ArrowLeft" });
    const last = screen.getByRole("tab", { name: /Three/ });
    expect(last).toHaveAttribute("aria-selected", "true");
    expect(last).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Third panel");
  });
});
