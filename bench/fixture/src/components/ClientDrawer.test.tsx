import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";
import { latency } from "../api";
import { ClientDrawer } from "./ClientDrawer";

beforeAll(() => {
  latency.ms = 0;
});

describe("ClientDrawer", () => {
  it("loads and shows the client", async () => {
    render(<ClientDrawer clientId="c-001" onClose={() => undefined} />);
    expect(await screen.findByRole("heading", { name: "Northwind Capital" })).toBeInTheDocument();
    expect(screen.getByText("Ines Vogel", { exact: false })).toBeInTheDocument();
  });


});
