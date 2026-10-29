// Shared helpers for the hidden benchmark tests. Copied to src/__bench__/ after a run.
// The app is mounted through the real entry point (src/main.tsx), so providers live wherever
// the solution put them. Only what a user sees is asserted.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

// The first import of main.tsx transforms the whole app, which can take seconds under load.
vi.setConfig({ testTimeout: 20000 });

// Track every React root so closeApp can unmount the previous app and its window listeners.
const roots = vi.hoisted(() => [] as { unmount(): void }[]);
vi.mock("react-dom/client", async (importOriginal) => {
  const mod = await importOriginal<typeof import("react-dom/client")>();
  return {
    ...mod,
    createRoot: (...args: Parameters<typeof mod.createRoot>) => {
      const root = mod.createRoot(...args);
      roots.push(root);
      return root;
    },
  };
});

let mounts = 0;

export async function openApp(route = "/") {
  // The app is mounted outside testing-library's render, so React's act environment is off.
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = false;
  document.body.innerHTML = '<div id="root"></div>';
  delete document.documentElement.dataset.theme;
  window.history.pushState({}, "", route);
  const spec = `../main.tsx?bench=${++mounts}`;
  // Fresh copies of every app module, so module-level state does not survive a "reload".
  vi.resetModules();
  await import(/* @vite-ignore */ spec);
  await screen.findByRole("main", {}, { timeout: 15000 });
  return screen;
}

export function closeApp() {
  for (const root of roots.splice(0)) root.unmount();
  document.body.innerHTML = "";
}

export const SLOW = { timeout: 4000 };

export function pick(select: HTMLElement, text: RegExp) {
  const el = select as HTMLSelectElement;
  const option = Array.from(el.options).find((o) => text.test(o.textContent ?? ""));
  if (!option) throw new Error(`no option matching ${String(text)}`);
  fireEvent.change(el, { target: { value: option.value } });
}

// Wait for the option: a page may fill its dropdown after data loads, as a user would see it fill in.
export async function pickReady(select: HTMLElement, text: RegExp) {
  await waitFor(() => pick(select, text), SLOW);
}

export const SRC = join(process.cwd(), "src");

export function sourceFiles(dir = SRC): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    if (name === "__bench__") continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) out.push(...sourceFiles(full));
    else out.push(full);
  }
  return out;
}

export const isTest = (f: string) => /\.test\.tsx?$/.test(f);
export const read = (f: string) => readFileSync(f, "utf8");

export function themeBlocks(): { light: string; dark: string } {
  const css = read(join(SRC, "styles", "theme.css"));
  const light = /:root\s*\{([^}]*)\}/.exec(css)?.[1] ?? "";
  const dark = /:root\[data-theme=["']?dark["']?\]\s*\{([^}]*)\}/.exec(css)?.[1] ?? "";
  return { light, dark };
}

export function token(block: string, name: string): string | undefined {
  return new RegExp(`${name}\\s*:\\s*([^;]+);`).exec(block)?.[1]?.trim().toLowerCase();
}

export function testBugs(): { skipped: string[]; snapshots: string[]; duplicates: string[]; suppressions: string[] } {
  const skipped: string[] = [];
  const snapshots: string[] = [];
  const duplicates: string[] = [];
  const suppressions: string[] = [];
  for (const file of sourceFiles()) {
    const text = read(file);
    if (file.includes("__snapshots__") || file.endsWith(".snap")) snapshots.push(file);
    if (/eslint-disable/.test(text)) suppressions.push(file);
    if (!isTest(file)) continue;
    if (/\b(?:it|test|describe)\.(?:skip|todo)\b|\bxit\(|\bxdescribe\(/.test(text)) skipped.push(file);
    if (/toMatch(?:Inline)?Snapshot/.test(text)) snapshots.push(file);
    const seen = new Set<string>();
    const re = /\b(?:it|test)\(\s*(["'`])(.+?)\1\s*,\s*(?:async\s*)?\(\)\s*=>\s*\{([\s\S]*?)\n\s{2}\}\);/g;
    for (const m of text.matchAll(re)) {
      const body = (m[3] ?? "").replace(/\s+/g, " ").trim();
      if (body === "") continue;
      if (seen.has(body)) duplicates.push(`${file}: ${m[2]}`);
      seen.add(body);
    }
  }
  return { skipped, snapshots, duplicates, suppressions };
}

export const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Body rows of a table (rows inside tbody). */
export function bodyRows(table: HTMLElement): HTMLTableRowElement[] {
  return Array.from(table.querySelectorAll<HTMLTableRowElement>("tbody tr"));
}

/** The table row whose first cell's text is exactly `label`. */
export function rowByLabel(label: string, root: ParentNode = document): HTMLTableRowElement {
  const rows = Array.from(root.querySelectorAll<HTMLTableRowElement>("tr"));
  const row = rows.find((r) => (r.cells[0]?.textContent ?? "").trim() === label);
  if (!row) throw new Error(`no row labelled ${label}`);
  return row;
}

export const usd0 = (value: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);

/** Replaces the holdings data for the next openApp, as if the portfolio held exactly these rows. */
export function mockHoldings(rows: { id: string; symbol: string; quantity: number; avgCost: number; openedAt: string; book: string }[]) {
  vi.doMock("../data/holdings.json", () => ({ default: rows }));
}

export function unmockHoldings() {
  vi.doUnmock("../data/holdings.json");
}

export const holding = (id: string, symbol: string, quantity: number, avgCost: number) => ({
  id,
  symbol,
  quantity,
  avgCost,
  openedAt: "2026-01-01",
  book: "Test",
});

function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

/** Captures the file a "download" click would save, without navigating. */
export function captureDownload() {
  let blob: Blob | null = null;
  const urlApi = URL as unknown as Record<string, unknown>;
  urlApi.createObjectURL = (b: Blob) => {
    blob = b;
    return "blob:bench";
  };
  urlApi.revokeObjectURL = () => undefined;
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  return {
    async text() {
      if (!blob) throw new Error("nothing was downloaded");
      return readBlob(blob);
    },
    restore() {
      click.mockRestore();
      delete urlApi.createObjectURL;
      delete urlApi.revokeObjectURL;
    },
  };
}

/** Parses CSV text with quoted cells into rows of cells. */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]!;
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\r" || ch === "\n") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else cell += ch;
  }
  if (cell !== "" || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}

export const WHOLE_DOLLARS = /^-?\$\d{1,3}(,\d{3})*$/;
