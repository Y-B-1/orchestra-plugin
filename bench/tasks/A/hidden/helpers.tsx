// Shared helpers for the hidden benchmark tests. Copied to src/__bench__/ after a run.
// The app is mounted through the real entry point (src/main.tsx), so providers live wherever
// the solution put them. Only what a user sees is asserted.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, screen } from "@testing-library/react";
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
