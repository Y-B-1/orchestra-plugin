import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import fxRates from "../data/fx-rates.json";
import holdings from "../data/holdings.json";
import instruments from "../data/instruments.json";
import { bodyRows, closeApp, openApp, rowByLabel, SLOW, usd0 } from "./helpers";

afterEach(closeApp);

describe("B11 client page", () => {
  it("B11 the client drawer links to a full client page", async () => {
    const s = await openApp("/clients");
    fireEvent.click(await s.findByText("Harbor Pension Trust", {}, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    const link = await within(drawer).findByRole("link", { name: "Open client page" }, SLOW);
    expect(link).toHaveAttribute("href", "/clients/c-002");
    fireEvent.click(link);
    expect(await s.findByRole("heading", { name: "Harbor Pension Trust" }, SLOW)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/clients/c-002");
    expect(s.getByRole("heading", { level: 1 })).toHaveTextContent("Clients");
  }, 10000);

  it("B11 lists the client's trades newest first and opens one", async () => {
    const s = await openApp("/clients/c-002");
    const table = await s.findByRole("table", { name: "Trades for Harbor Pension Trust" }, SLOW);
    expect(bodyRows(table)).toHaveLength(17);
    expect(s.getByText(/^Showing 1 to 17 of 17\b/)).toBeInTheDocument();
    const headers = within(table).getAllByRole("columnheader").map((h) => (h.textContent ?? "").replace(/[▲▼]/g, "").trim());
    expect(headers).not.toContain("Client");
    expect(bodyRows(table)[0]?.textContent).toContain("T-10150");
    fireEvent.click(bodyRows(table)[0]!);
    expect(await s.findByRole("dialog", { name: "Trade details" }, SLOW)).toBeInTheDocument();
  }, 10000);

  it("B11 has notes, a way back and the capitalized tier", async () => {
    const s = await openApp("/clients/c-009");
    expect(await s.findByRole("heading", { name: "Quill Software" }, SLOW)).toBeInTheDocument();
    expect(await s.findByLabelText("New note", {}, SLOW)).toBeInTheDocument();
    expect(s.getByRole("link", { name: "All clients" })).toHaveAttribute("href", "/clients");
    expect(s.getByText("AMER · Corporate")).toBeInTheDocument();
    expect(await s.findByText(/^Showing 1 to 21 of 21\b/, {}, SLOW)).toBeInTheDocument();
  }, 10000);

  it("B11 explains an unknown client", async () => {
    const s = await openApp("/clients/c-999");
    expect(await s.findByRole("alert", {}, SLOW)).toHaveTextContent("Client c-999 not found");
  }, 10000);
});

const classes = [
  ["equity", "Equities"],
  ["bond", "Bonds"],
  ["commodity", "Commodities"],
  ["fx", "FX"],
] as const;

function currentValues(): Record<string, number> {
  const rates = fxRates as Record<string, number>;
  const out: Record<string, number> = { equity: 0, bond: 0, commodity: 0, fx: 0 };
  for (const h of holdings) {
    const i = instruments.find((row) => row.symbol === h.symbol)!;
    out[i.assetClass] = (out[i.assetClass] ?? 0) + h.quantity * i.price * (rates[i.currency] ?? 0);
  }
  return out;
}

async function rebalance(s: Awaited<ReturnType<typeof openApp>>) {
  const region = await s.findByRole("region", { name: "Rebalance" }, SLOW);
  await within(region).findByLabelText("Equities target %", {}, SLOW);
  return region;
}

function setTargets(region: HTMLElement, targets: Record<string, number>) {
  for (const [, label] of classes) {
    fireEvent.change(within(region).getByLabelText(`${label} target %`), { target: { value: String(targets[label]) } });
  }
}

describe("B12 rebalancing calculator", () => {
  it("B12 starts at today's weights rounded to whole percents", async () => {
    const s = await openApp("/portfolio");
    const region = await rebalance(s);
    const values = currentValues();
    const total = Object.values(values).reduce((a, b) => a + b, 0);
    for (const [key, label] of classes) {
      expect(within(region).getByLabelText(`${label} target %`)).toHaveValue(Math.round((values[key]! / total) * 100));
    }
    const table = within(region).getByRole("table", { name: "Rebalancing trades" });
    const equityTarget = (Math.round((values.equity! / total) * 100) / 100) * total;
    // Either the exact difference rounded, or the difference of the two rounded values shown.
    const exact = usd0(values.equity! - equityTarget);
    const display = usd0(Math.round(values.equity!) - Math.round(equityTarget));
    expect(rowByLabel("Equities", table).textContent).toMatch(new RegExp(`Sell (${exact}|${display})`.replace(/\$/g, "\\$")));
  }, 10000);

  it("B12 shows the trades to reach the targets in whole dollars", async () => {
    const s = await openApp("/portfolio");
    const region = await rebalance(s);
    setTargets(region, { Equities: 100, Bonds: 0, Commodities: 0, FX: 0 });
    const values = currentValues();
    const total = Object.values(values).reduce((a, b) => a + b, 0);
    const table = await within(region).findByRole("table", { name: "Rebalancing trades" }, SLOW);
    const equities = rowByLabel("Equities", table).textContent ?? "";
    expect(equities).toContain(usd0(values.equity!));
    expect(equities).toContain(usd0(total));
    expect(equities).toContain(`Buy ${usd0(total - values.equity!)}`);
    expect(rowByLabel("Bonds", table).textContent).toContain(`Sell ${usd0(values.bond!)}`);
    expect(rowByLabel("Commodities", table).textContent).toContain(`Sell ${usd0(values.commodity!)}`);
    expect(rowByLabel("FX", table).textContent).toContain(`Sell ${usd0(values.fx!)}`);
  }, 10000);

  it("B12 refuses targets that do not add up and resets to current", async () => {
    const s = await openApp("/portfolio");
    const region = await rebalance(s);
    setTargets(region, { Equities: 50, Bonds: 0, Commodities: 0, FX: 0 });
    expect(await within(region).findByText("Targets must add up to 100% (now 50%)", {}, SLOW)).toBeInTheDocument();
    expect(within(region).queryByRole("table", { name: "Rebalancing trades" })).not.toBeInTheDocument();
    fireEvent.click(within(region).getByRole("button", { name: "Reset to current" }));
    await waitFor(() => expect(within(region).queryByText(/Targets must add up/)).not.toBeInTheDocument());
    expect(within(region).getByRole("table", { name: "Rebalancing trades" })).toBeInTheDocument();
  }, 10000);
});
