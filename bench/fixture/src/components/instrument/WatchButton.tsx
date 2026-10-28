import { useWatchlist } from "../../hooks/useWatchlist";

export function WatchButton({ symbol }: { symbol: string }) {
  const { isWatched, toggle } = useWatchlist();
  const watched = isWatched(symbol);
  return (
    <button
      type="button"
      className={`button button--small watch-button${watched ? " watch-button--active" : ""}`}
      aria-pressed={watched}
      onClick={() => toggle(symbol)}
    >
      <span aria-hidden="true">{watched ? "★" : "☆"}</span> {watched ? "Watching" : "Watch"}
    </button>
  );
}
