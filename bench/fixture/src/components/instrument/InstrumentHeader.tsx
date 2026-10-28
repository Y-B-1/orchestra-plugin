import type { Instrument } from "../../types";
import { formatVolume } from "../../utils/format";
import { formatPrice } from "../../utils/numbers";
import { assetClassLabels } from "../../utils/portfolio";
import { PriceChange } from "../PriceChange";
import { WatchButton } from "./WatchButton";

export function InstrumentHeader({ instrument }: { instrument: Instrument }) {
  const previous = instrument.price / (1 + instrument.changePct);
  const change = instrument.price - previous;
  return (
    <header className="instrument-header">
      <div>
        <p className="instrument-header__symbol">
          {instrument.symbol}
          <span className="chip">{assetClassLabels[instrument.assetClass]}</span>
        </p>
        <h2 className="instrument-header__name">{instrument.name}</h2>
        <WatchButton symbol={instrument.symbol} />
      </div>
      <div className="instrument-header__quote">
        <p className="instrument-header__price" aria-label="Last price">
          {formatPrice(instrument.price, instrument.currency)}
        </p>
        <PriceChange amount={change} pct={instrument.changePct} currency={instrument.currency} />
        <p className="instrument-header__volume">Volume {formatVolume(instrument.volume)}</p>
      </div>
    </header>
  );
}
