import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useLocalStorage } from "./useLocalStorage";

describe("useLocalStorage", () => {
  it("starts from the stored value", () => {
    localStorage.setItem("pulse.test", JSON.stringify(["a", "b"]));
    const { result } = renderHook(() => useLocalStorage<string[]>("pulse.test", []));
    expect(result.current[0]).toEqual(["a", "b"]);
  });

  it("writes updates back to storage and survives bad JSON", () => {
    const { result } = renderHook(() => useLocalStorage("pulse.count", 0));
    act(() => result.current[1]((prev) => prev + 2));
    expect(result.current[0]).toBe(2);
    expect(localStorage.getItem("pulse.count")).toBe("2");
    localStorage.setItem("pulse.broken", "{not json");
    const broken = renderHook(() => useLocalStorage("pulse.broken", "fallback"));
    expect(broken.result.current[0]).toBe("fallback");
  });

  it("reads the new key when the key changes", () => {
    localStorage.setItem("pulse.notes.a", JSON.stringify(["note for a"]));
    localStorage.setItem("pulse.notes.b", JSON.stringify(["note for b"]));
    const { result, rerender } = renderHook(({ id }) => useLocalStorage<string[]>(`pulse.notes.${id}`, []), {
      initialProps: { id: "a" },
    });
    rerender({ id: "b" });
    expect(result.current[0]).toEqual(["note for b"]);
    expect(JSON.parse(localStorage.getItem("pulse.notes.a") ?? "[]")).toEqual(["note for a"]);
  });
});
