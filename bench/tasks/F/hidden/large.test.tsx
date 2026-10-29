// Large asks: health score, contributors, the CSV export and the print view.
import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import {
  captureDownload,
  closeApp,
  holding,
  mockHoldings,
  openApp,
  parseCsv,
  SLOW,
  unmockHoldings,
  WHOLE_DOLLARS,
} from "./helpers";

afterEach(() => {
  closeApp();
  unmockHoldings();
});

async function health(s: Awaited<ReturnType<typeof openApp>>) {
  const region = await s.findByRole("region", { name: "Portfolio health" }, SLOW);
  const label = await within(region).findByText(/Health score: -?\d+ \/ 100/, {}, SLOW);
  const bar = within(region).getByRole("progressbar", { name: "Health score" });
  return {
    shown: Number(/Health score: (-?\d+) \/ 100/.exec(label.textContent ?? "")?.[1]),
    width: bar.getAttribute("width"),
    now: bar.getAttribute("aria-valuenow"),
  };
}

describe("F5 Portfolio health", () => {
  it("scores the house portfolio and the label, bar width and aria value agree", async () => {
    const h = await health(await openApp("/portfolio"));
    expect(h).toEqual({ shown: 65, width: "65%", now: "65" });
  });

  it("holds a raw score above 100 at 100 everywhere", async () => {
    mockHoldings([holding("h-01", "AAPL", 1000, 100), holding("h-02", "AAPL", 1000, 100)]);
    const h = await health(await openApp("/portfolio"));
    expect(h).toEqual({ shown: 100, width: "100%", now: "100" });
  });

  it("holds a raw score below 0 at 0 everywhere", async () => {
    mockHoldings([holding("h-01", "MSFT", 100, 900)]);
    const h = await health(await openApp("/portfolio"));
    expect(h).toEqual({ shown: 0, width: "0%", now: "0" });
  });

  it("rounds each part first and then adds them", async () => {
    // Diversification 29.4 and performance 30.4: parts round to 29 + 30, the sum would round to 60.
    mockHoldings([holding("h-01", "AAPL", 51, 197.4652777777778), holding("h-02", "AAPL", 49, 197.4652777777778)]);
    const h = await health(await openApp("/portfolio"));
    expect(h).toEqual({ shown: 59, width: "59%", now: "59" });
  });
});

describe("F7 Top contributors", () => {
  async function names(s: Awaited<ReturnType<typeof openApp>>) {
    const list = await s.findByRole("list", { name: "Top contributors" }, SLOW);
    return within(list).getAllByRole("listitem").map((li) => li.textContent ?? "");
  }

  it("lists the top 10 by dollars made, biggest first, with the signed amount", async () => {
    const items = await names(await openApp("/portfolio"));
    expect(items).toHaveLength(10);
    const order = ["NVIDIA Corp.", "Apple Inc.", "Gold spot", "Microsoft Corp.", "SAP SE", "German Bund 10Y", "US Treasury 10Y", "Euro / US dollar", "US dollar / Yen", "WTI crude"];
    order.forEach((name, i) => expect(items[i]).toContain(name));
    expect(items[0]).toContain("+$1,256,100");
    expect(items[6]).toContain("-$27,200");
    expect(items.join(" ")).not.toContain("Tesla");
  });

  it("ranks a bigger dollar contributor above a smaller one and breaks ties by name", async () => {
    mockHoldings([
      holding("h-01", "NVDA", 100, 128.07),
      holding("h-02", "MSFT", 100, 421.2),
      holding("h-03", "XAU", 1, 1),
      holding("h-04", "AAPL", 1000, 200),
    ]);
    const items = await names(await openApp("/portfolio"));
    expect(items).toHaveLength(4);
    ["Apple Inc.", "Gold spot", "Microsoft Corp.", "NVIDIA Corp."].forEach((name, i) => expect(items[i]).toContain(name));
    expect(items[0]).toContain("+$27,480");
    expect(items[2]).toContain("+$1,000");
    expect(items[3]).toContain("+$1,000");
  });

  it("puts the biggest loss last", async () => {
    mockHoldings([holding("h-01", "AAPL", 100, 300), holding("h-02", "MSFT", 100, 500), holding("h-03", "NVDA", 100, 138)]);
    const items = await names(await openApp("/portfolio"));
    expect(items[0]).toContain("NVIDIA Corp.");
    expect(items[1]).toContain("Microsoft Corp.");
    expect(items[2]).toContain("Apple Inc.");
    expect(items[2]).toContain("-$7,252");
  });
});

describe("F10 Portfolio CSV", () => {
  it("exports the holdings with money as whole dollars, as on screen", async () => {
    const download = captureDownload();
    try {
      const s = await openApp("/portfolio");
      await s.findByRole("table", { name: "Holdings" }, SLOW);
      fireEvent.click(s.getByRole("button", { name: "Export portfolio CSV" }));
      const rows = parseCsv(await download.text());
      expect(rows[0]).toEqual(["Instrument", "Name", "Book", "Market value (USD)", "Unrealized P&L (USD)", "Weight"]);
      expect(rows).toHaveLength(12);
      expect(rows[1]).toEqual(["EURUSD", "Euro / US dollar", "Macro overlay", "$5,421,000", "-$36,500", "17.4%"]);
      const aapl = rows.find((r) => r[0] === "AAPL");
      expect(aapl).toEqual(["AAPL", "Apple Inc.", "Core equity", "$2,729,760", "+$468,960", "8.7%"]);
      for (const row of rows.slice(1)) {
        expect(row[3]).toMatch(WHOLE_DOLLARS);
        expect(row[4]).toMatch(/^[+-]\$\d{1,3}(,\d{3})*$/);
      }
    } finally {
      download.restore();
    }
  });
});

describe("F11 Print view", () => {
  it("the Portfolio page links to the print view", async () => {
    const s = await openApp("/portfolio");
    const link = await s.findByRole("link", { name: "Print view" }, SLOW);
    expect(link).toHaveAttribute("href", "/portfolio/print");
  });

  it("shows the statement alone, with whole-dollar values and a Total row", async () => {
    const s = await openApp("/portfolio/print");
    expect(await s.findByRole("heading", { level: 1, name: "Portfolio statement" }, SLOW)).toBeInTheDocument();
    const table = await s.findByRole("table", {}, SLOW);
    const headers = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual(["Instrument", "Market value (USD)"]);
    const rows = within(table).getAllByRole("row");
    const aapl = rows.find((r) => /^AAPL/.test(r.textContent ?? ""));
    expect(aapl).toHaveTextContent("$2,729,760");
    const total = rows.find((r) => /^Total/.test(r.textContent ?? ""));
    expect(total).toHaveTextContent("$31,210,017");
    for (const row of rows.slice(1)) expect(within(row).getAllByRole("cell")[0]?.textContent).toMatch(WHOLE_DOLLARS);
    expect(s.queryByRole("navigation", { name: "Primary" })).not.toBeInTheDocument();
    await waitFor(() => expect(document.title).toContain("Portfolio statement"));
  });
});
