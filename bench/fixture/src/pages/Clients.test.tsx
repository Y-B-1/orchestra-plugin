import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, describe, expect, it } from "vitest";
import { latency } from "../api";
import { Clients } from "./Clients";

beforeAll(() => {
  latency.ms = 0;
});

describe("Clients page", () => {
  it("filters the list as you type", async () => {
    render(
      <MemoryRouter>
        <Clients />
      </MemoryRouter>,
    );
    await screen.findByText("Northwind Capital");
    fireEvent.change(screen.getByLabelText("Search clients"), { target: { value: "quill" } });
    await waitFor(() => expect(screen.queryByText("Northwind Capital")).not.toBeInTheDocument());
    expect(screen.getByText("Quill Software")).toBeInTheDocument();
  });

  it("opens the detail drawer for a client", async () => {
    render(
      <MemoryRouter>
        <Clients />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByText("Harbor Pension Trust"));
    expect(await screen.findByRole("dialog", { name: "Client details" })).toBeInTheDocument();
  });
});
