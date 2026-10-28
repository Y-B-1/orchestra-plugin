import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { closeApp, openApp, pick, pickReady, rowByLabel, SLOW } from "./helpers";

afterEach(closeApp);

async function compareTable() {
  await waitFor(() => rowByLabel("3 month change"), SLOW);
}

describe("A10 compare page", () => {
  it("A10 compare page is in the sidebar and compares AAPL and MSFT by default", async () => {
    const s = await openApp("/");
    const nav = s.getByRole("navigation", { name: "Primary" });
    fireEvent.click(within(nav).getByRole("link", { name: "Compare" }));
    expect(await s.findByRole("heading", { level: 1, name: "Compare" }, SLOW)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/compare");
    expect(await s.findByRole("heading", { name: "AAPL vs MSFT" }, SLOW)).toBeInTheDocument();
    expect(await s.findByLabelText("First instrument", {}, SLOW)).toHaveDisplayValue(/^AAPL/);
    expect(s.getByLabelText("Second instrument")).toHaveDisplayValue(/^MSFT/);
    await compareTable();
    expect(rowByLabel("Last price").textContent).toMatch(/\$227\.48[\s\S]*\$431\.20/);
    expect(rowByLabel("3 month change").textContent).toMatch(/\+?28\.06%[\s\S]*-2\.84%/);
    expect(rowByLabel("3 month high").textContent).toContain("$227.48");
    expect(rowByLabel("3 month low").textContent).toContain("$161.41");
    expect(rowByLabel("Exchange").textContent).toContain("NASDAQ");
    expect(rowByLabel("Sector").textContent).toContain("Technology");
  });

  it("A10 reads both symbols from the address and writes a new pick back", async () => {
    const s = await openApp("/compare?a=NVDA&b=TSLA");
    expect(await s.findByRole("heading", { name: "NVDA vs TSLA" }, SLOW)).toBeInTheDocument();
    await compareTable();
    expect(rowByLabel("3 month change").textContent).toMatch(/\+?46\.09%[\s\S]*-24\.43%/);
    await pickReady(await s.findByLabelText("Second instrument", {}, SLOW), /^XAU\b/);
    expect(await s.findByRole("heading", { name: "NVDA vs XAU" }, SLOW)).toBeInTheDocument();
    await waitFor(() => expect(new URLSearchParams(window.location.search).get("b")).toBe("XAU"));
    expect(new URLSearchParams(window.location.search).get("a")).toBe("NVDA");
    await waitFor(() => expect(rowByLabel("Last price").textContent).toContain("$2,641.50"));
  });

  it("A10 asks for two different instruments", async () => {
    const s = await openApp("/compare?a=XAU&b=XAU");
    expect(await s.findByText("Pick two different instruments.", {}, SLOW)).toBeInTheDocument();
    expect(s.queryByRole("table")).not.toBeInTheDocument();
  });

  it("A10 day change row uses the arrows", async () => {
    await openApp("/compare");
    await compareTable();
    const text = rowByLabel("Day change").textContent ?? "";
    expect(text).toMatch(/▲\s*\+1\.24%/);
    expect(text).toMatch(/▼\s*-0\.36%/);
  });

  it("A10 the instrument page links to the compare page", async () => {
    const s = await openApp("/instruments/AAPL");
    const link = await s.findByRole("link", { name: "Compare with another instrument" }, SLOW);
    expect(link).toHaveAttribute("href", "/compare?a=AAPL");
  });
});

describe("A11 search in the top bar", () => {
  function type(s: Awaited<ReturnType<typeof openApp>>, text: string) {
    const box = s.getByLabelText("Search Pulse");
    fireEvent.change(box, { target: { value: text } });
    return box as HTMLInputElement;
  }

  it("A11 finds a client and opens its drawer on the Clients page", async () => {
    const s = await openApp("/settings");
    const box = type(s, "nor");
    const results = await s.findByLabelText("Search results", {}, SLOW);
    fireEvent.click(await within(results).findByRole("link", { name: /Northwind Capital/ }, SLOW));
    const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
    expect(await within(drawer).findByRole("heading", { name: "Northwind Capital" }, SLOW)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/clients");
    expect(box.value).toBe("");
    expect(s.queryByLabelText("Search results")).not.toBeInTheDocument();
  });

  it("A11 finds an instrument by symbol and opens its page", async () => {
    const s = await openApp("/settings");
    type(s, "aapl");
    const results = await s.findByLabelText("Search results", {}, SLOW);
    fireEvent.click(await within(results).findByRole("link", { name: /AAPL/ }, SLOW));
    expect(await s.findByRole("heading", { name: "Apple Inc." }, SLOW)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/instruments/AAPL");
  });

  it("A11 groups results and lists matching pages", async () => {
    const s = await openApp("/settings");
    type(s, "port");
    const results = await s.findByLabelText("Search results", {}, SLOW);
    expect(await within(results).findByRole("link", { name: "Portfolio" }, SLOW)).toBeInTheDocument();
    expect(within(results).getByRole("link", { name: "Reports" })).toBeInTheDocument();
    expect(within(results).getByText("Pages")).toBeInTheDocument();
    type(s, "harbor");
    await waitFor(() => expect(within(s.getByLabelText("Search results")).getByText("Clients")).toBeInTheDocument());
    type(s, "euro");
    await waitFor(() => expect(within(s.getByLabelText("Search results")).getByText("Instruments")).toBeInTheDocument());
    expect(within(s.getByLabelText("Search results")).getByRole("link", { name: /EURUSD/ })).toBeInTheDocument();
  });

  it("A11 Enter opens the first result and Escape closes the list", async () => {
    const s = await openApp("/settings");
    let box = type(s, "zzzz");
    expect(await s.findByText("No matches", {}, SLOW)).toBeInTheDocument();
    fireEvent.keyDown(box, { key: "Escape" });
    await waitFor(() => expect(s.queryByLabelText("Search results")).not.toBeInTheDocument());
    box = type(s, "msft");
    await within(await s.findByLabelText("Search results", {}, SLOW)).findByRole("link", { name: /MSFT/ }, SLOW);
    fireEvent.keyDown(box, { key: "Enter", code: "Enter", keyCode: 13 });
    fireEvent.keyUp(box, { key: "Enter", code: "Enter", keyCode: 13 });
    // jsdom does not submit a form on a dispatched Enter key; a browser would.
    if (window.location.pathname !== "/instruments/MSFT" && (box as HTMLInputElement).form) fireEvent.submit((box as HTMLInputElement).form!);
    expect(await s.findByRole("heading", { name: "Microsoft Corp." }, SLOW)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/instruments/MSFT");
  });
});
