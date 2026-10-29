// Medium asks: the data migration, the client panels, the daily trend window and the money format.
import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { join } from "node:path";
import { closeApp, openApp, read, SLOW, SRC, WHOLE_DOLLARS } from "./helpers";

afterEach(closeApp);

interface ClientRecord {
  id: string;
  name: string;
}
interface TradeRecord {
  clientId: string;
}

describe("medium", () => {
  it("F1 the migration added the new Quill account and Tidewater, and moved the late Quill trades", async () => {
    const clients = JSON.parse(read(join(SRC, "data", "clients.json"))) as ClientRecord[];
    const trades = JSON.parse(read(join(SRC, "data", "trades.json"))) as TradeRecord[];
    expect(clients).toHaveLength(12);
    expect(clients.find((c) => c.id === "c-011")?.name).toBe("Quill Software");
    expect(clients.find((c) => c.id === "c-012")?.name).toBe("Tidewater Metals");
    expect(trades).toHaveLength(150);
    expect(trades.filter((t) => t.clientId === "c-011")).toHaveLength(8);
    expect(trades.filter((t) => t.clientId === "c-009")).toHaveLength(13);
    const s = await openApp("/clients");
    const region = await s.findByRole("region", { name: "Clients" });
    await within(region).findByText("Tidewater Metals", {}, SLOW);
    expect(within(region).getAllByRole("listitem")).toHaveLength(12);
  });

  it("F3 New clients this month lists Tidewater and not Quill", async () => {
    const s = await openApp("/");
    const region = await s.findByRole("region", { name: "New clients this month" });
    await within(region).findByText("Tidewater Metals", {}, SLOW);
    const items = within(region).getAllByRole("listitem");
    expect(items.map((li) => li.textContent?.trim())).toEqual(["Tidewater Metals"]);
  });

  it("F4 Trades by client has one aggregated row per client, biggest first, ties by name", async () => {
    const s = await openApp("/");
    const region = await s.findByRole("region", { name: "Trades by client" });
    await within(region).findByText(/Tidewater Metals/, {}, SLOW);
    const rows = within(region)
      .getAllByRole("listitem")
      .map((li) => {
        const text = li.textContent ?? "";
        const m = /^\s*(\D+?)\s*(\d+)\s+trades/.exec(text);
        return { text, name: m?.[1] ?? "", trades: Number(m?.[2]) };
      });
    expect(rows).toHaveLength(11);
    expect(new Set(rows.map((r) => r.name)).size).toBe(11);
    const quill = rows.filter((r) => r.name === "Quill Software");
    expect(quill).toHaveLength(1);
    expect(quill[0]!.trades).toBe(21);
    expect(quill[0]!.text).toContain("$41,000,000");
    expect(quill[0]!.text).not.toContain("$79,000,000");
    expect(rows.find((r) => r.name === "Tidewater Metals")!.trades).toBe(0);
    expect(rows.reduce((total, r) => total + r.trades, 0)).toBe(150);
    for (let i = 1; i < rows.length; i++) {
      const a = rows[i - 1]!;
      const b = rows[i]!;
      expect(a.trades >= b.trades).toBe(true);
      if (a.trades === b.trades) expect(a.name.localeCompare(b.name)).toBeLessThan(0);
    }
    for (const r of rows) expect(r.text.match(/\$[\d,.]+[A-Za-z]?/)?.[0]).toMatch(WHOLE_DOLLARS);
  });

  describe("F6 Daily trend", () => {
    async function openTrend(symbol = "AAPL") {
      const s = await openApp(`/instruments/${symbol}`);
      const region = await s.findByRole("region", { name: "Daily trend" }, SLOW);
      await within(region).findAllByRole("row", {}, SLOW);
      const rows = () => within(region).getAllByRole("row").slice(1);
      return { s, region, rows };
    }

    it("shows the latest 30 days, oldest first", async () => {
      const { rows } = await openTrend();
      await waitFor(() => expect(rows()).toHaveLength(30), SLOW);
      expect(rows()[0]).toHaveTextContent("Sep 16, 2026");
      expect(rows()[29]).toHaveTextContent(/Oct 27, 2026.*\$227\.48/);
    });

    it("still stops at 30 when the range asks for more", async () => {
      const { region, rows } = await openTrend();
      fireEvent.change(within(region).getByLabelText("From"), { target: { value: "2026-07-01" } });
      await waitFor(() => expect(rows()[0]).toHaveTextContent("Sep 16, 2026"), SLOW);
      expect(rows()).toHaveLength(30);
      fireEvent.change(within(region).getByLabelText("To"), { target: { value: "2026-08-31" } });
      await waitFor(() => expect(rows()[rows().length - 1]).toHaveTextContent("Aug 31, 2026"), SLOW);
      expect(rows()).toHaveLength(30);
    });

    it("shows a short range in full, both end days included", async () => {
      const { region, rows } = await openTrend("MSFT");
      fireEvent.change(within(region).getByLabelText("From"), { target: { value: "2026-10-20" } });
      fireEvent.change(within(region).getByLabelText("To"), { target: { value: "2026-10-22" } });
      await waitFor(() => expect(rows()).toHaveLength(3), SLOW);
      expect(rows()[0]).toHaveTextContent("Oct 20, 2026");
      expect(rows()[2]).toHaveTextContent("Oct 22, 2026");
    });

    it("says so when the range is empty", async () => {
      const { region, rows } = await openTrend();
      fireEvent.change(within(region).getByLabelText("From"), { target: { value: "2026-11-01" } });
      expect(await within(region).findByText("No daily data in this range.", {}, SLOW)).toBeInTheDocument();
      expect(rows()).toHaveLength(0);
    });
  });

  it("F9 holdings market values and the Total row are whole dollars with separators", async () => {
    const s = await openApp("/portfolio");
    const table = await s.findByRole("table", { name: "Holdings" }, SLOW);
    const headers = within(table).getAllByRole("columnheader").map((h) => h.textContent?.replace(/[▲▼]/g, "").trim());
    const col = headers.indexOf("Market value (USD)");
    expect(col).toBeGreaterThan(-1);
    const rows = within(table).getAllByRole("row").slice(1, -1);
    expect(rows).toHaveLength(11);
    // The Instrument cell is a row header, so the data cells start one column later.
    for (const row of rows) expect(within(row).getAllByRole("cell")[col - 1]?.textContent).toMatch(WHOLE_DOLLARS);
    const aapl = rows.find((r) => within(r).queryByRole("link", { name: "AAPL" }));
    expect(aapl).toHaveTextContent("$2,729,760");
    expect(s.getByTestId("total-market-value")).toHaveTextContent(/^\$31,210,017$/);
  });

  it("F9 the client drawer shows AUM as whole dollars", async () => {
    const s = await openApp("/clients");
    fireEvent.click(await s.findByText("Harbor Pension Trust", {}, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    expect(await within(drawer).findByText("$3,400,000,000", {}, SLOW)).toBeInTheDocument();
  });
});
