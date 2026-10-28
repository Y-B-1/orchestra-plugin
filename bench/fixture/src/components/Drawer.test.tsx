import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Drawer } from "./Drawer";

describe("Drawer", () => {
  it("renders a labelled dialog and focuses its close button", () => {
    render(
      <Drawer label="Trade details" title="Trade T-1" onClose={() => undefined}>
        Body
      </Drawer>,
    );
    expect(screen.getByRole("dialog", { name: "Trade details" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Trade T-1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
  });

  it("closes on Escape and on the close button", () => {
    const onClose = vi.fn();
    render(
      <Drawer label="Details" title="Title" onClose={onClose} closeLabel="Close details">
        Body
      </Drawer>,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.click(screen.getByRole("button", { name: "Close details" }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
