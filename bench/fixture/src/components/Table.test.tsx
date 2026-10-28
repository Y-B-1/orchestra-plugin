import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Table, type Column } from "./Table";

interface Row {
  id: string;
  name: string;
  price: number;
}

const rows: Row[] = [
  { id: "1", name: "Beta", price: 20 },
  { id: "2", name: "Alpha", price: 300 },
  { id: "3", name: "Gamma", price: 5 },
];

const columns: Column<Row>[] = [
  { key: "name", header: "Name", rowHeader: true, render: (r) => r.name, sortValue: (r) => r.name },
  { key: "price", header: "Price", align: "right", render: (r) => r.price.toFixed(2), sortValue: (r) => r.price },
  { key: "note", header: "Note", render: () => "-" },
];

function names() {
  return screen.getAllByRole("rowheader").map((cell) => cell.textContent);
}

describe("Table", () => {
  it("keeps the input order, then sorts ascending and descending on header clicks", () => {
    render(<Table columns={columns} rows={rows} rowKey={(r) => r.id} />);
    expect(names()).toEqual(["Beta", "Alpha", "Gamma"]);
    fireEvent.click(screen.getByRole("button", { name: "Price" }));
    expect(names()).toEqual(["Gamma", "Beta", "Alpha"]);
    expect(screen.getByRole("columnheader", { name: /Price/ })).toHaveAttribute("aria-sort", "ascending");
    fireEvent.click(screen.getByRole("button", { name: /Price/ }));
    expect(names()).toEqual(["Alpha", "Beta", "Gamma"]);
    const header = screen.getByRole("columnheader", { name: "Note" });
    expect(within(header).queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows the empty message when there are no rows", () => {
    render(<Table columns={columns} rows={[]} rowKey={(r) => r.id} emptyMessage="No rows here." />);
    expect(screen.getByText("No rows here.")).toBeInTheDocument();
  });

  it("reports sort changes instead of sorting when controlled", () => {
    const onSortChange = vi.fn();
    render(<Table columns={columns} rows={rows} rowKey={(r) => r.id} sort={null} onSortChange={onSortChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Name" }));
    expect(onSortChange).toHaveBeenCalledWith({ key: "name", direction: "asc" });
    expect(names()).toEqual(["Beta", "Alpha", "Gamma"]);
  });

  it("opens a row with the keyboard", () => {
    const onRowClick = vi.fn();
    render(<Table columns={columns} rows={rows} rowKey={(r) => r.id} onRowClick={onRowClick} rowLabel={(r) => r.name} />);
    fireEvent.keyDown(screen.getByRole("row", { name: "Alpha" }), { key: "Enter" });
    expect(onRowClick).toHaveBeenCalledWith(rows[1]);
  });
});
