import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { bodyRows, closeApp, figure, freezeDate, openApp, pickReady, setTimeZone, SLOW } from "./helpers";

const zone = process.env.TZ;

afterEach(() => {
  closeApp();
  vi.useRealTimers();
  if (zone === undefined) delete process.env.TZ;
  else process.env.TZ = zone;
});

async function blotter(route = "/trades") {
  const s = await openApp(route);
  await s.findByRole("table", { name: "Trade blotter" }, SLOW);
  return s;
}

describe("filters, links and paging", () => {
  it("E7 the blotter filters by status", async () => {
    const s = await blotter();
    const status = s.getByLabelText("Status") as HTMLSelectElement;
    expect(Array.from(status.options).map((o) => o.textContent)).toEqual([
      "All statuses",
      "Filled",
      "Partially filled",
      "Cancelled",
      "Pending",
    ]);
    await pickReady(status, /^Cancelled$/);
    expect(await s.findByText("Showing 1 to 10 of 10 trades", {}, SLOW)).toBeInTheDocument();
    expect(s.getByRole("button", { name: "Reset filters" })).toBeEnabled();
    await pickReady(status, /^Partially filled$/);
    await waitFor(() => {
      const table = s.getByRole("table", { name: "Trade blotter" });
      expect(within(table).getByRole("row", { name: "Trade T-10120" })).toBeInTheDocument();
      expect(table.textContent).not.toContain("Cancelled");
    }, SLOW);
    expect(s.getByText("Showing 1 to 10 of 10 trades")).toBeInTheDocument();
    await pickReady(status, /^Pending$/);
    expect(await s.findByText("No trades match these filters.", {}, SLOW)).toBeInTheDocument();
    fireEvent.click(s.getByRole("button", { name: "Reset filters" }));
    expect(await s.findByText("Showing 1 to 25 of 150 trades", {}, SLOW)).toBeInTheDocument();
  });

  it("E9 a trade link opens its drawer and the address follows the drawer", async () => {
    const s = await openApp("/trades?trade=T-10120");
    const drawer = await s.findByRole("dialog", { name: "Trade details" }, SLOW);
    expect(await within(drawer).findByRole("heading", { name: "Trade T-10120" }, SLOW)).toBeInTheDocument();
    fireEvent.click(within(drawer).getByRole("button", { name: "Close trade details" }));
    await waitFor(() => expect(s.queryByRole("dialog", { name: "Trade details" })).not.toBeInTheDocument());
    expect(new URLSearchParams(window.location.search).get("trade")).toBeNull();
    const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    fireEvent.click(within(table).getByRole("row", { name: "Trade T-10150" }));
    await waitFor(() => expect(new URLSearchParams(window.location.search).get("trade")).toBe("T-10150"));
    expect(await s.findByRole("heading", { name: "Trade T-10150" }, SLOW)).toBeInTheDocument();
  });

  it("E9 a link to an unknown trade says it was not found", async () => {
    const s = await openApp("/trades?trade=T-1");
    const drawer = await s.findByRole("dialog", { name: "Trade details" }, SLOW);
    expect(await within(drawer).findByText(/Trade T-1 not found/, {}, SLOW)).toBeInTheDocument();
  });

  it("E11 rows per page offers all trades on one page", async () => {
    const s = await blotter();
    const size = s.getByLabelText("Rows per page") as HTMLSelectElement;
    expect(Array.from(size.options).map((o) => o.textContent?.trim())).toEqual(["25", "50", "100", "All"]);
    await pickReady(size, /^50$/);
    expect(await s.findByText("Showing 1 to 50 of 150 trades", {}, SLOW)).toBeInTheDocument();
    expect(bodyRows(s.getByRole("table", { name: "Trade blotter" }))).toHaveLength(50);
    await pickReady(s.getByLabelText("Rows per page"), /^All$/);
    expect(await s.findByText("Showing all 150 trades", {}, SLOW)).toBeInTheDocument();
    const table = s.getByRole("table", { name: "Trade blotter" });
    expect(bodyRows(table)).toHaveLength(150);
    fireEvent.click(within(table).getByRole("row", { name: "Trade T-10001" }));
    expect(await s.findByRole("heading", { name: "Trade T-10001" }, SLOW)).toBeInTheDocument();
  });
});

describe("E12 today's figures follow the UTC day", () => {
  it("E12 a minute before midnight UTC still counts that day, even east of UTC", async () => {
    setTimeZone("Asia/Tokyo");
    freezeDate("2026-10-27T23:59:00Z");
    const s = await openApp("/trades");
    const today = await s.findByRole("region", { name: "Today" }, SLOW);
    await waitFor(() => expect(figure(today, "Trades")).toBe("17"), SLOW);
    expect(figure(today, "Filled")).toBe("14");
    expect(figure(today, "Partially filled")).toBe("0");
    expect(figure(today, "Cancelled")).toBe("3");
    expect(figure(today, "Pending")).toBe("0");
  });

  it("E12 a minute after midnight UTC starts a new day, even west of UTC", async () => {
    setTimeZone("America/New_York");
    freezeDate("2026-10-28T00:01:00Z");
    const s = await openApp("/trades");
    const today = await s.findByRole("region", { name: "Today" }, SLOW);
    await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    await waitFor(() => expect(figure(today, "Trades")).toBe("0"), SLOW);
    expect(figure(today, "Cancelled")).toBe("0");
  });
});
