import { describe, expect, it } from "vitest";
import { pageCount, pageInfo, pageWindow, paginate } from "./pagination";

const rows = Array.from({ length: 60 }, (_, index) => index + 1);

describe("pagination", () => {
  it("counts pages and slices a 1-based page", () => {
    expect(pageCount(60, 25)).toBe(3);
    expect(pageCount(10, 25)).toBe(1);
    expect(pageCount(0, 25)).toBe(1);
    expect(paginate(rows, 1, 25)).toHaveLength(25);
    expect(paginate(rows, 3, 25)).toEqual([51, 52, 53, 54, 55, 56, 57, 58, 59, 60]);
  });

  it("describes the visible range and collapses distant pages", () => {
    expect(pageInfo(60, 2, 25)).toEqual({ page: 2, pageCount: 3, firstIndex: 26, lastIndex: 50, total: 60 });
    expect(pageInfo(0, 1, 25)).toMatchObject({ firstIndex: 0, lastIndex: 0 });
    expect(pageWindow(5, 9)).toEqual([1, null, 4, 5, 6, null, 9]);
    expect(pageWindow(1, 3)).toEqual([1, 2, 3]);
  });
});
