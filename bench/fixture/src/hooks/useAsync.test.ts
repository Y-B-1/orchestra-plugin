import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { toError, useAsync } from "./useAsync";

describe("useAsync", () => {
  it("starts loading, then exposes the data or the error", async () => {
    const ok = renderHook(() => useAsync(() => Promise.resolve(42), []));
    expect(ok.result.current.loading).toBe(true);
    await waitFor(() => expect(ok.result.current.data).toBe(42));
    expect(ok.result.current.loading).toBe(false);

    const failed = renderHook(() => useAsync(() => Promise.reject(new Error("boom")), []));
    await waitFor(() => expect(failed.result.current.error?.message).toBe("boom"));
    expect(failed.result.current.data).toBeNull();
    expect(toError("nope").message).toBe("nope");
  });

  it("runs the loader again on reload", async () => {
    const load = vi.fn().mockResolvedValue("ok");
    const { result } = renderHook(() => useAsync(load, []));
    await waitFor(() => expect(result.current.data).toBe("ok"));
    act(() => result.current.reload());
    await waitFor(() => expect(load).toHaveBeenCalledTimes(2));
  });

  it("ignores a response that arrives after the inputs changed", async () => {
    let resolveFirst: (value: string) => void = () => undefined;
    const first = new Promise<string>((resolve) => {
      resolveFirst = resolve;
    });
    const { result, rerender } = renderHook(({ q }) => useAsync(() => (q === "a" ? first : Promise.resolve("b")), [q]), {
      initialProps: { q: "a" },
    });
    rerender({ q: "b" });
    await waitFor(() => expect(result.current.data).toBe("b"));
    await act(async () => {
      resolveFirst("a");
      await first;
    });
    expect(result.current.data).toBe("b");
  });
});
