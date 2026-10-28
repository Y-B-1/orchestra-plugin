import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClientNotes, notesKey } from "./ClientNotes";

const fixedNow = () => new Date("2026-10-27T14:30:00Z");

describe("ClientNotes", () => {
  it("starts with an empty state", () => {
    render(<ClientNotes clientId="c-001" now={fixedNow} />);
    expect(screen.getByText("No notes yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add note" })).toBeDisabled();
  });

  it("adds a note with a timestamp and stores it", () => {
    render(<ClientNotes clientId="c-001" now={fixedNow} />);
    fireEvent.change(screen.getByLabelText("New note"), { target: { value: "  Called about FX overlay.  " } });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    const item = screen.getByRole("listitem");
    expect(within(item).getByText("Called about FX overlay.")).toBeInTheDocument();
    expect(within(item).getByText("Oct 27, 2026, 14:30 UTC")).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(notesKey("c-001")) ?? "[]")).toHaveLength(1);
  });

  it("lists stored notes newest first, keeps clients apart and deletes notes", () => {
    localStorage.setItem(
      notesKey("c-002"),
      JSON.stringify([
        { id: "n2", text: "Second", author: "Dana Whitaker", createdAt: "2026-10-26T10:00:00Z" },
        { id: "n1", text: "First", author: "Dana Whitaker", createdAt: "2026-10-25T10:00:00Z" },
      ]),
    );
    render(<ClientNotes clientId="c-002" now={fixedNow} />);
    expect(screen.getAllByRole("listitem").map((li) => li.querySelector("p")?.textContent)).toEqual(["Second", "First"]);
    expect(localStorage.getItem(notesKey("c-001"))).toBeNull();
    cleanup();
    render(<ClientNotes clientId="c-003" now={fixedNow} />);
    fireEvent.change(screen.getByLabelText("New note"), { target: { value: "Temporary" } });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    fireEvent.click(screen.getByRole("button", { name: /Delete note/ }));
    expect(screen.getByText("No notes yet.")).toBeInTheDocument();
  });
});
