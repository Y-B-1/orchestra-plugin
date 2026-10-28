import { beforeAll, describe, expect, it } from "vitest";
import { fetchClients, fetchInstrument, fetchInstruments, fetchReports, latency, NotFoundError } from "./index";

beforeAll(() => {
  latency.ms = 0;
});

describe("instruments", () => {
  it("returns every instrument by default", async () => {
    expect(await fetchInstruments()).toHaveLength(12);
  });

  it("filters by asset class", async () => {
    const fx = await fetchInstruments("fx");
    expect(fx.map((i) => i.symbol)).toEqual(["EURUSD", "GBPUSD", "USDJPY"]);
  });

  it("rejects an unknown symbol", async () => {
    await expect(fetchInstrument("NOPE")).rejects.toBeInstanceOf(NotFoundError);
  });

});

describe("clients", () => {
  it("searches by name", async () => {
    const rows = await fetchClients("harbor");
    expect(rows.map((c) => c.id)).toEqual(["c-002"]);
  });



});

describe("reports and kpis", () => {
  it("lists reports newest first", async () => {
    const dates = (await fetchReports()).map((r) => r.date);
    expect(dates[0]).toBe("2026-10-31");
    expect(dates).toEqual([...dates].sort().reverse());
  });


});
