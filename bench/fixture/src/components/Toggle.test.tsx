import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Toggle } from "./Toggle";

describe("Toggle", () => {
  it("reports the new value when clicked", () => {
    const onChange = vi.fn();
    render(<Toggle label="Email alerts" checked={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole("switch", { name: "Email alerts" }));
    expect(onChange).toHaveBeenCalledWith(true);
  });

});
