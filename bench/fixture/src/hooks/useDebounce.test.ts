import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDebounce } from "./useDebounce";

describe("useDebounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("holds the old value until changes stop for the delay", () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 200), { initialProps: { value: 1 } });
    rerender({ value: 2 });
    act(() => {
      vi.advanceTimersByTime(150);
    });
    rerender({ value: 3 });
    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(result.current).toBe(1);
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(result.current).toBe(3);
  });
});
