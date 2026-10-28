import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchNotifications } from "../api";
import type { AppNotification } from "../types";
import { toError } from "./useAsync";

export const READ_NOTIFICATIONS_KEY = "pulse.notifications.read";

interface NotificationsContextValue {
  items: AppNotification[];
  unreadCount: number;
  loading: boolean;
  error: Error | null;
  markRead: (id: string) => void;
  markAllRead: () => void;
}

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

function loadReadIds(): Set<string> {
  try {
    const raw = localStorage.getItem(READ_NOTIFICATIONS_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : []);
  } catch {
    return new Set();
  }
}

function saveReadIds(items: readonly AppNotification[]): void {
  try {
    const ids = items.filter((item) => item.read).map((item) => item.id);
    localStorage.setItem(READ_NOTIFICATIONS_KEY, JSON.stringify(ids));
  } catch {
    // Storage can be full or blocked; read state then lasts for this session only.
  }
}

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchNotifications().then(
      (rows) => {
        if (cancelled) return;
        const readIds = loadReadIds();
        setItems(rows.map((row) => (readIds.has(row.id) ? { ...row, read: true } : row)));
        setLoading(false);
      },
      (reason: unknown) => {
        if (cancelled) return;
        setError(toError(reason));
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const unreadCount = useMemo(() => items.filter((item) => !item.read).length, [items]);

  const markRead = useCallback((id: string) => {
    setItems((prev) => {
      const next = prev.map((item) => (item.id === id ? { ...item, read: true } : item));
      saveReadIds(next);
      return next;
    });
  }, []);

  const markAllRead = useCallback(() => {
    setItems((prev) => {
      for (const item of prev) item.read = true;
      saveReadIds(prev);
      return prev;
    });
  }, []);

  const value = useMemo<NotificationsContextValue>(
    () => ({ items, unreadCount, loading, error, markRead, markAllRead }),
    [items, unreadCount, loading, error, markRead, markAllRead],
  );

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}

export function useNotifications(): NotificationsContextValue {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error("useNotifications must be used inside NotificationsProvider");
  return ctx;
}
