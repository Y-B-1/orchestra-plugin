import { Link } from "react-router-dom";
import type { Instrument } from "../../types";
import { topMovers } from "../../utils/markets";
import { PriceChange } from "../PriceChange";

function MoverList({ title, rows }: { title: string; rows: Instrument[] }) {
  return (
    <div className="movers__group">
      <h3 className="movers__title">{title}</h3>
      {rows.length === 0 ? (
        <p className="movers__none">None today</p>
      ) : (
        <ol className="movers__list">
          {rows.map((instrument) => (
            <li key={instrument.symbol} className="movers__item">
              <Link to={`/instruments/${instrument.symbol}`}>{instrument.symbol}</Link>
              <span className="movers__name">{instrument.name}</span>
              <PriceChange pct={instrument.changePct} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function TopMovers({ instruments }: { instruments: readonly Instrument[] }) {
  const { gainers, losers } = topMovers(instruments);
  return (
    <div className="movers">
      <MoverList title="Gainers" rows={gainers} />
      <MoverList title="Losers" rows={losers} />
    </div>
  );
}
