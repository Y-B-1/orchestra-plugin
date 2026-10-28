import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeAll, describe, expect, it } from "vitest";
import { latency } from "../api";
import { NotificationsProvider, READ_NOTIFICATIONS_KEY, useNotifications } from "./useNotifications";

beforeAll(() => {
  latency.ms = 0;
});

const wrapper = ({ children }: { children: ReactNode }) => <NotificationsProvider>{children}</NotificationsProvider>;

describe("useNotifications", () => {
  it("loads notifications and counts the unread ones, honouring stored read state", async () => {
    const fresh = renderHook(() => useNotifications(), { wrapper });
    await waitFor(() => expect(fresh.result.current.loading).toBe(false));
    expect(fresh.result.current.items).toHaveLength(8);
    expect(fresh.result.current.unreadCount).toBe(3);
    fresh.unmount();

    localStorage.setItem(READ_NOTIFICATIONS_KEY, JSON.stringify(["n-108", "n-106"]));
    const restored = renderHook(() => useNotifications(), { wrapper });
    await waitFor(() => expect(restored.result.current.loading).toBe(false));
    expect(restored.result.current.unreadCount).toBe(1);
  });

  it("marks one notification as read and remembers it", async () => {
    const { result } = renderHook(() => useNotifications(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.markRead("n-107"));
    expect(result.current.unreadCount).toBe(2);
    expect(JSON.parse(localStorage.getItem(READ_NOTIFICATIONS_KEY) ?? "[]")).toContain("n-107");
  });
});
