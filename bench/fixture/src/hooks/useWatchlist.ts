import { useCallback } from "react";
import { useLocalStorage } from "./useLocalStorage";

export const WATCHLIST_KEY = "pulse.watchlist";

export const defaultWatchlist = ["AAPL", "EURUSD", "XAU"];

export interface Watchlist {
  symbols: string[];
  isWatched: (symbol: string) => boolean;
  toggle: (symbol: string) => void;
}

/** Symbols the user follows, kept in this browser. */
export function useWatchlist(): Watchlist {
  const [symbols, setSymbols] = useLocalStorage<string[]>(WATCHLIST_KEY, defaultWatchlist);

  const isWatched = useCallback((symbol: string) => symbols.includes(symbol), [symbols]);

  const toggle = useCallback(
    (symbol: string) => {
      setSymbols((prev) => (prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol]));
    },
    [setSymbols],
  );

  return { symbols, isWatched, toggle };
}
