import { describe, expect, it } from "vitest";
import { readJson, writeJson } from "./storage";

describe("storage", () => {
  it("returns the fallback when nothing is stored", () => {
    expect(readJson("missing", { a: 1 })).toEqual({ a: 1 });
  });

  it("round-trips a stored value", () => {
    writeJson("k", { a: 2, b: true });
    expect(readJson("k", { a: 1, b: false })).toEqual({ a: 2, b: true });
  });


});
