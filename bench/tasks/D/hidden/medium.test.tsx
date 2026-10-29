import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { closeApp, itemTexts, openApp, pickReady, resetApp, seed, SLOW } from "./helpers";

afterEach(resetApp);

const SETTINGS = "pulse.settings";

async function openNotes(s: Awaited<ReturnType<typeof openApp>>, client: string) {
  fireEvent.click(await s.findByText(client, {}, SLOW));
  const drawer = await s.findByRole("dialog", { name: "Client details" }, SLOW);
  fireEvent.click(await within(drawer).findByRole("tab", { name: /Notes/ }, SLOW));
  return drawer;
}

describe("D8 cancelled trade notionals", () => {
  it("D8 the blotter and the trade drawer show a cancelled trade's notional as $0.00", async () => {
    const s = await openApp("/trades");
    const table = await s.findByRole("table", { name: "Trade blotter" }, SLOW);
    const row = within(table).getByRole("row", { name: "Trade T-10146" });
    expect(row.textContent).toContain("$0.00");
    expect(table.textContent).not.toContain("0.0000");
    fireEvent.click(row);
    const drawer = await s.findByRole("dialog", { name: "Trade details" }, SLOW);
    await waitFor(() => expect(drawer.textContent).toContain("Notional"), SLOW);
    expect(drawer.textContent).toContain("$0.00");
    expect(drawer.textContent).not.toContain("0.0000");
  });

  it("D8 the dashboard's latest trades show no four-decimal notionals", async () => {
    const s = await openApp("/");
    const table = await s.findByRole("table", { name: "Latest trades" }, SLOW);
    await waitFor(() => expect(table.textContent).toContain("$0.00"), SLOW);
    expect(table.textContent).not.toContain("0.0000");
  });
});

describe("D9 book filter", () => {
  it("D9 narrows the holdings and their totals to one book", async () => {
    const s = await openApp("/portfolio");
    const table = await s.findByRole("table", { name: "Holdings" }, SLOW);
    const book = s.getByLabelText("Book") as HTMLSelectElement;
    expect(book).toHaveDisplayValue("All books");
    await pickReady(book, /^Growth$/);
    await waitFor(() => expect(within(table).getByText("Total (2 positions)")).toBeInTheDocument());
    const symbols = within(table).getAllByRole("link").map((a) => a.textContent);
    expect(symbols.sort()).toEqual(["NVDA", "TSLA"]);
    const total = within(table).getByText("Total (2 positions)").closest("tr");
    expect(total?.textContent).toContain("$5,398,600.00");
    expect(total?.textContent).toContain("+$1,168,100");
    expect(total?.textContent).toContain("17.3%");
    await pickReady(book, /^All books$/);
    await waitFor(() => expect(within(table).getByText("Total (11 positions)")).toBeInTheDocument());
  });
});

describe("D10 report digest setting", () => {
  it("D10 keeps a saved weekly digest switch that was off as Off", async () => {
    seed(SETTINGS, JSON.stringify({ theme: "dark", emailAlerts: false, pushAlerts: true, weeklyDigest: false }));
    const s = await openApp("/settings");
    expect(s.getByLabelText("Report digest")).toHaveDisplayValue("Off");
    expect(s.getByRole("switch", { name: "Dark theme" })).toBeChecked();
    expect(s.getByRole("switch", { name: "Email alerts" })).not.toBeChecked();
    expect(s.getByRole("switch", { name: "Push alerts" })).toBeChecked();
    expect(s.queryByRole("switch", { name: "Weekly digest" })).not.toBeInTheDocument();
  });

  it("D10 a saved switch that was on reads Weekly, and a new choice survives a reload", async () => {
    seed(SETTINGS, JSON.stringify({ theme: "light", emailAlerts: true, pushAlerts: false, weeklyDigest: true }));
    let s = await openApp("/settings");
    const digest = s.getByLabelText("Report digest");
    expect(digest).toHaveDisplayValue("Weekly");
    await pickReady(digest, /^Daily$/);
    await waitFor(() => expect(s.getByLabelText("Report digest")).toHaveDisplayValue("Daily"));
    closeApp();
    s = await openApp("/settings");
    expect(s.getByLabelText("Report digest")).toHaveDisplayValue("Daily");
  });

  it("D10 an unreadable saved value falls back to the defaults", async () => {
    for (const raw of ["{oops", "null", "[1,2]", '"dark"', '{"theme":5,"weeklyDigest":"yes"}']) {
      seed(SETTINGS, raw);
      const s = await openApp("/settings");
      expect(s.getByLabelText("Report digest")).toHaveDisplayValue("Weekly");
      expect(s.getByRole("switch", { name: "Dark theme" })).not.toBeChecked();
      expect(s.getByRole("switch", { name: "Email alerts" })).toBeChecked();
      resetApp();
    }
  });
});

describe("D11 report search", () => {
  it("D11 filters the current tab by title or author", async () => {
    const s = await openApp("/reports");
    await s.findByText("Daily market wrap", {}, SLOW);
    fireEvent.change(s.getByLabelText("Search reports"), { target: { value: "KIM" } });
    await waitFor(() => expect(s.queryByText("Daily market wrap")).not.toBeInTheDocument());
    expect(s.getByText("FX flows and positioning")).toBeInTheDocument();
    expect(s.getByText("Client exposure digest")).toBeInTheDocument();
    fireEvent.click(s.getByRole("tab", { name: /Scheduled/ }));
    expect(await s.findByText("No reports match your search.", {}, SLOW)).toBeInTheDocument();
    fireEvent.change(s.getByLabelText("Search reports"), { target: { value: "risk" } });
    expect(await s.findByText("Month-end risk review", {}, SLOW)).toBeInTheDocument();
    expect(s.queryByText("Weekly strategy note")).not.toBeInTheDocument();
  });
});

describe("D12 D13 client notes", () => {
  it("D12 notes show bold and web links but never markup or script links", async () => {
    const s = await openApp("/clients");
    const drawer = await openNotes(s, "Northwind Capital");
    const text =
      'Call **Ines** about [the pack](https://example.com/pack) <img src=x onerror="window.__benchPwned=1"> and [click me](javascript:window.__benchPwned=2)';
    fireEvent.change(within(drawer).getByLabelText("New note"), { target: { value: text } });
    fireEvent.click(within(drawer).getByRole("button", { name: "Add note" }));
    const bold = await within(drawer).findByText("Ines");
    expect(bold.closest("strong, b")).not.toBeNull();
    expect(within(drawer).getByRole("link", { name: "the pack" })).toHaveAttribute("href", "https://example.com/pack");
    expect(drawer.querySelector("img")).toBeNull();
    const hrefs = Array.from(drawer.querySelectorAll("[href]")).map((el) => (el.getAttribute("href") ?? "").trim().toLowerCase());
    expect(hrefs.some((href) => href.startsWith("javascript:"))).toBe(false);
    expect((window as { __benchPwned?: number }).__benchPwned).toBeUndefined();
  });

  it("D13 a note saved before pinning can be pinned to the top and stays pinned", async () => {
    seed(
      "pulse.client-notes.c-001",
      JSON.stringify([
        { id: "n2", text: "Newer note", author: "Dana Whitaker", createdAt: "2026-10-26T10:00:00Z" },
        { id: "n1", text: "Older note", author: "Dana Whitaker", createdAt: "2026-10-25T10:00:00Z" },
      ]),
    );
    let s = await openApp("/clients");
    let drawer = await openNotes(s, "Northwind Capital");
    const older = (await within(drawer).findByText("Older note")).closest("li")!;
    expect(itemTexts(drawer).findIndex((t) => t.includes("Newer note"))).toBe(0);
    fireEvent.click(within(older).getByRole("button", { name: "Pin" }));
    await waitFor(() => expect(itemTexts(drawer)[0]).toContain("Older note"));
    expect(itemTexts(drawer)[0]).toContain("Pinned");
    closeApp();
    s = await openApp("/clients");
    drawer = await openNotes(s, "Northwind Capital");
    await within(drawer).findByText("Older note");
    const first = drawer.querySelector("li")!;
    expect(first.textContent).toContain("Older note");
    expect(within(first).getByRole("button", { name: "Unpin" })).toBeInTheDocument();
  });

  it("D13 an unreadable saved notes value shows no notes and still takes new ones", async () => {
    seed("pulse.client-notes.c-001", '{"x":1}');
    const s = await openApp("/clients");
    const drawer = await openNotes(s, "Northwind Capital");
    expect(await within(drawer).findByText("No notes yet.")).toBeInTheDocument();
    fireEvent.change(within(drawer).getByLabelText("New note"), { target: { value: "Fresh start" } });
    fireEvent.click(within(drawer).getByRole("button", { name: "Add note" }));
    expect(await within(drawer).findByText("Fresh start")).toBeInTheDocument();
  });
});
