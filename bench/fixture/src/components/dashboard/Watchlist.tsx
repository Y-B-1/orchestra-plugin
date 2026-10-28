import { Link } from "react-router-dom";
import { useWatchlist } from "../../hooks/useWatchlist";
import type { Instrument } from "../../types";
import { formatPrice } from "../../utils/numbers";
import { EmptyState } from "../Feedback";
import { PriceChange } from "../PriceChange";

/** The user's followed instruments, priced from the instrument list already loaded on the page. */
export function Watchlist({ instruments }: { instruments: readonly Instrument[] }) {
  const { symbols, toggle } = useWatchlist();
  const rows = symbols
    .map((symbol) => instruments.find((instrument) => instrument.symbol === symbol))
    .filter((instrument): instrument is Instrument => instrument !== undefined);

  if (rows.length === 0) {
    return <EmptyState message="Watch an instrument from its page to see it here." />;
  }

  return (
    <ul className="watchlist">
      {rows.map((instrument) => (
        <li key={instrument.symbol} className="watchlist__item">
          <Link to={`/instruments/${instrument.symbol}`} className="watchlist__symbol">
            {instrument.symbol}
          </Link>
          <span className="watchlist__price">{formatPrice(instrument.price, instrument.currency)}</span>
          <PriceChange pct={instrument.changePct} />
          <button
            type="button"
            className="watchlist__remove"
            onClick={() => toggle(instrument.symbol)}
            aria-label={`Stop watching ${instrument.symbol}`}
          >
            Remove
          </button>
        </li>
      ))}
    </ul>
  );
}
