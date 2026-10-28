import { describe, expect, it } from "vitest";
import { ariaSort, compareValues, nextSort, sortBy } from "./sort";

describe("sortBy", () => {
  it("compares numbers and strings, puts empty values last and leaves the input alone", () => {
    expect(compareValues(2, 10)).toBeLessThan(0);
    expect(compareValues("apple", "Banana")).toBeLessThan(0);
    expect(sortBy(["b", null, "a", ""], (v) => v)).toEqual(["a", "b", null, ""]);
    const input = [{ n: 2 }, { n: 3 }, { n: 1 }];
    expect(sortBy(input, (row) => row.n, "desc").map((row) => row.n)).toEqual([3, 2, 1]);
    expect(input.map((row) => row.n)).toEqual([2, 3, 1]);
  });
});

describe("nextSort", () => {
  it("flips the active column and starts a new one ascending", () => {
    expect(nextSort(null, "price")).toEqual({ key: "price", direction: "asc" });
    expect(nextSort({ key: "price", direction: "asc" }, "price")).toEqual({ key: "price", direction: "desc" });
    expect(nextSort({ key: "price", direction: "desc" }, "symbol")).toEqual({ key: "symbol", direction: "asc" });
    expect(ariaSort({ key: "price", direction: "desc" }, "price")).toBe("descending");
    expect(ariaSort({ key: "price", direction: "desc" }, "symbol")).toBe("none");
  });
});
