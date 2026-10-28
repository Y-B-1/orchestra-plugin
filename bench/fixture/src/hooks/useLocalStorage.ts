import { useCallback, useEffect, useState } from "react";

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

/**
 * State that is mirrored to localStorage under `key`. Unlike `readJson`, the
 * stored value replaces the fallback instead of being merged into it, so it
 * works for arrays and primitives too.
 */
export function useLocalStorage<T>(key: string, fallback: T): [T, (next: T | ((prev: T) => T)) => void] {
  const [entry, setEntry] = useState(() => ({ key, value: read(key, fallback) }));

  // A new key (for example another client's notes) starts from what is stored under it.
  let current = entry;
  if (entry.key !== key) {
    current = { key, value: read(key, fallback) };
    setEntry(current);
  }

  useEffect(() => {
    try {
      localStorage.setItem(current.key, JSON.stringify(current.value));
    } catch {
      // Storage can be full or blocked; the in-memory value still applies.
    }
  }, [current.key, current.value]);

  const update = useCallback(
    (next: T | ((prev: T) => T)) => {
      setEntry((prev) => {
        const value = typeof next === "function" ? (next as (prev: T) => T)(prev.value) : next;
        return { key: prev.key, value };
      });
    },
    [],
  );

  return [current.value, update];
}
