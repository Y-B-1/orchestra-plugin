import { Link, useParams } from "react-router-dom";
import { fetchInstrument, fetchInstrumentStats } from "../api";
import { AsyncContent } from "../components/AsyncContent";
import { InstrumentHeader } from "../components/instrument/InstrumentHeader";
import { KeyStats } from "../components/instrument/KeyStats";
import { PriceHistory } from "../components/instrument/PriceHistory";
import { RecentTrades } from "../components/instrument/RecentTrades";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { Instrument, InstrumentStats } from "../types";

interface InstrumentBundle {
  instrument: Instrument;
  stats: InstrumentStats;
}

async function loadInstrument(symbol: string): Promise<InstrumentBundle> {
  const [instrument, stats] = await Promise.all([fetchInstrument(symbol), fetchInstrumentStats(symbol)]);
  return { instrument, stats };
}

function InstrumentView({ instrument, stats }: InstrumentBundle) {
  return (
    <>
      <section className="panel" aria-label="Quote">
        <InstrumentHeader instrument={instrument} />
      </section>
      <div className="page__columns">
        <section className="panel" aria-label="Price history">
          <div className="panel__header">
            <h2 className="panel__title">Price history</h2>
          </div>
          <PriceHistory symbol={instrument.symbol} currency={instrument.currency} />
        </section>
        <section className="panel" aria-label="Key stats">
          <div className="panel__header">
            <h2 className="panel__title">Key stats</h2>
          </div>
          <KeyStats instrument={instrument} stats={stats} />
        </section>
      </div>
      <section className="panel" aria-label="Recent trades">
        <div className="panel__header">
          <h2 className="panel__title">Recent trades</h2>
        </div>
        <RecentTrades symbol={instrument.symbol} />
      </section>
    </>
  );
}

export function InstrumentDetail() {
  const { symbol = "" } = useParams();
  const upper = symbol.toUpperCase();
  useDocumentTitle(upper);
  const state = useAsync(() => loadInstrument(upper), [upper]);
  return (
    <div className="page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link to="/">Dashboard</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{upper}</span>
      </nav>
      <AsyncContent state={state} loadingLabel={`Loading ${upper}`}>
        {(bundle) => <InstrumentView instrument={bundle.instrument} stats={bundle.stats} />}
      </AsyncContent>
    </div>
  );
}
