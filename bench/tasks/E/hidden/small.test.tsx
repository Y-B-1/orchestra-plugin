import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { closeApp, figure, headers, openApp, SLOW, themeBlocks, token } from "./helpers";

afterEach(() => {
  closeApp();
  vi.restoreAllMocks();
});

async function blotter(route = "/trades") {
  const s = await openApp(route);
  const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
  return { s, table };
}

describe("small asks", () => {
  it("E1 partly filled trades say Partially filled", async () => {
    const { s } = await blotter();
    fireEvent.click(s.getByRole("button", { name: "Page 2" }));
    const row = await s.findByRole("row", { name: "Trade T-10120" }, SLOW);
    expect(within(row).getByText("Partially filled")).toBeInTheDocument();
    expect(within(row).queryByText("Partial")).not.toBeInTheDocument();
  });

  it("E2 the blotter has a Trader column right before Status", async () => {
    const { table } = await blotter();
    const names = headers(table);
    expect(names).toContain("Trader");
    expect(names.indexOf("Trader")).toBe(names.indexOf("Status") - 1);
    const row = within(table).getByRole("row", { name: "Trade T-10147" });
    expect(within(row).getByText("A. Moreau")).toBeInTheDocument();
  });

  it("E3 the trade drawer shows the remaining quantity", async () => {
    const { s } = await blotter();
    fireEvent.click(s.getByRole("button", { name: "Page 2" }));
    fireEvent.click(await s.findByRole("row", { name: "Trade T-10120" }, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Trade details" }, SLOW);
    await within(drawer).findByText("Remaining", {}, SLOW);
    expect(figure(drawer, "Remaining")).toBe("3,154");
  });

  it("E4 pending has its own color token", () => {
    const { light, dark } = themeBlocks();
    expect(token(light, "--color-pending")).toBe("#b54708");
    expect(token(dark, "--color-pending")).toBe("#fdb022");
  });

  it("E5 the CSV export uses the same status words as the badge", async () => {
    let blob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((value: Blob | MediaSource) => {
      blob = value as Blob;
      return "blob:bench";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const { s } = await blotter();
    fireEvent.click(s.getByRole("button", { name: "Export CSV" }));
    await waitFor(() => expect(blob).not.toBeNull());
    const csv = await (blob as unknown as Blob).text();
    const lines = csv.split(/\r?\n/);
    const status = lines[0]!.split(",").indexOf("Status");
    expect(status).toBeGreaterThanOrEqual(0);
    const values = new Set(lines.slice(1).map((line) => line.split(",")[status]));
    expect(values).toEqual(new Set(["Filled", "Partially filled", "Cancelled"]));
  });

  it("E6 the not found page links back to the dashboard", async () => {
    const s = await openApp("/no-such-page");
    const link = await s.findByRole("link", { name: "Back to the dashboard" }, SLOW);
    expect(link).toHaveAttribute("href", "/");
  });

  it("E18 settings groups the alert options under Alerts", async () => {
    const s = await openApp("/settings");
    const alerts = s.getByRole("region", { name: "Alerts" });
    expect(within(alerts).getByRole("heading", { name: "Alerts" })).toBeInTheDocument();
    expect(within(alerts).getByRole("switch", { name: "Email alerts" })).toBeInTheDocument();
    expect(within(alerts).getByLabelText("Large trade alert (USD)")).toHaveValue(1000000);
  });
});
