import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AsyncContent } from "./AsyncContent";

describe("AsyncContent", () => {
  it("shows the loading label and then an error with a retry button", () => {
    render(
      <AsyncContent state={{ data: null, loading: true, error: null }} loadingLabel="Loading trades">
        {(data: string[]) => data.join(",")}
      </AsyncContent>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading trades...");
    const reload = vi.fn();
    cleanup();
    render(
      <AsyncContent state={{ data: null, loading: false, error: new Error("offline"), reload }} loadingLabel="Loading">
        {(data: string[]) => data.join(",")}
      </AsyncContent>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong: offline");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reload).toHaveBeenCalledOnce();
  });

  it("shows the empty message or the content", () => {
    const { rerender } = render(
      <AsyncContent
        state={{ data: [], loading: false, error: null }}
        loadingLabel="Loading"
        isEmpty={(rows: string[]) => rows.length === 0}
        emptyMessage="Nothing here."
      >
        {(rows) => rows.join(",")}
      </AsyncContent>,
    );
    expect(screen.getByText("Nothing here.")).toBeInTheDocument();
    rerender(
      <AsyncContent
        state={{ data: ["a", "b"], loading: false, error: null }}
        loadingLabel="Loading"
        isEmpty={(rows: string[]) => rows.length === 0}
        emptyMessage="Nothing here."
      >
        {(rows) => rows.join(",")}
      </AsyncContent>,
    );
    expect(screen.getByText("a,b")).toBeInTheDocument();
  });
});
