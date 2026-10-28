import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { closeApp, openApp, SLOW } from "./helpers";

afterEach(closeApp);

function endpoints(chart: Element): { first: number; last: number } {
  const points = (chart.querySelector("polyline")?.getAttribute("points") ?? "").trim().split(/\s+/);
  const y = (pair: string | undefined) => Number((pair ?? "").split(",")[1]);
  return { first: y(points[0]), last: y(points[points.length - 1]) };
}

describe("bugs and refactor", () => {
  it("C7 marking everything read clears the bell count straight away", async () => {
    const s = await openApp("/settings");
    fireEvent.click(await s.findByRole("button", { name: "Notifications, 3 unread" }, SLOW));
    const panel = s.getByRole("region", { name: "Notification list" });
    fireEvent.click(within(panel).getByRole("button", { name: /^Mark all( as)? read$/ }));
    await waitFor(() => expect(s.getByRole("button", { name: "Notifications" })).toBeInTheDocument());
    expect(within(panel).queryByRole("button", { name: /^Mark .* as read$/ })).not.toBeInTheDocument();
  });

  it("C8 a rising price history is drawn rising", async () => {
    const s = await openApp("/instruments/AAPL");
    const chart = await s.findByRole("img", { name: /AAPL daily closes over 3 months/ }, SLOW);
    const { first, last } = endpoints(chart);
    expect(last).toBeLessThan(first);
  });

  it("C8 a falling price history is drawn falling", async () => {
    const s = await openApp("/instruments/TSLA");
    const chart = await s.findByRole("img", { name: /TSLA daily closes over 3 months/ }, SLOW);
    const { first, last } = endpoints(chart);
    expect(last).toBeGreaterThan(first);
  });

  it("C9 the dashboard table shows prices with the same digits as everywhere else", async () => {
    const s = await openApp("/");
    const region = s.getByRole("region", { name: "Instruments" });
    const eurusd = (await within(region).findByRole("link", { name: "EURUSD" }, SLOW)).closest("tr");
    expect(eurusd?.textContent).toContain("$1.0842");
    const gbpusd = within(region).getByRole("link", { name: "GBPUSD" }).closest("tr");
    expect(gbpusd?.textContent).toContain("$1.2967");
    const xau = within(region).getByRole("link", { name: "XAU" }).closest("tr");
    expect(xau?.textContent).toContain("$2,641.50");
  });
});
