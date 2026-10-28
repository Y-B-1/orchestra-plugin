import { fetchInstruments, fetchKpis } from "../api";
import { AsyncContent } from "../components/AsyncContent";
import { RecentActivity } from "../components/dashboard/RecentActivity";
import { TopMovers } from "../components/dashboard/TopMovers";
import { Watchlist } from "../components/dashboard/Watchlist";
import { InstrumentTable } from "../components/InstrumentTable";
import { KpiCard } from "../components/KpiCard";
import { SegmentedControl } from "../components/SegmentedControl";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { AssetClass } from "../types";
import { useState } from "react";

const filters: { value: AssetClass | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "equity", label: "Equities" },
  { value: "fx", label: "FX" },
  { value: "commodity", label: "Commodities" },
  { value: "bond", label: "Bonds" },
];

export function Dashboard() {
  useDocumentTitle("Dashboard");
  const [filter, setFilter] = useState<AssetClass | "all">("all");
  const kpis = useAsync(fetchKpis, []);
  const instruments = useAsync(() => fetchInstruments(filter === "all" ? undefined : filter), [filter]);
  const market = useAsync(() => fetchInstruments(), []);

  return (
    <div className="page">
      <section className="kpi-grid" aria-label="Key figures">
        <AsyncContent state={kpis} loadingLabel="Loading figures">
          {(rows) => rows.map((kpi) => <KpiCard key={kpi.id} kpi={kpi} />)}
        </AsyncContent>
      </section>
      <div className="page__columns">
        <section className="panel" aria-label="Instruments">
          <div className="panel__header">
            <h2 className="panel__title">Instruments</h2>
            <SegmentedControl label="Asset class" options={filters} value={filter} onChange={setFilter} />
          </div>
          <AsyncContent state={instruments} loadingLabel="Loading instruments">
            {(rows) => <InstrumentTable instruments={rows} />}
          </AsyncContent>
        </section>
        <div className="page__stack">
          <section className="panel" aria-label="Watchlist">
            <div className="panel__header">
              <h2 className="panel__title">Watchlist</h2>
            </div>
            <AsyncContent state={market} loadingLabel="Loading watchlist">
              {(rows) => <Watchlist instruments={rows} />}
            </AsyncContent>
          </section>
          <section className="panel" aria-label="Top movers">
            <div className="panel__header">
              <h2 className="panel__title">Top movers</h2>
            </div>
            <AsyncContent state={market} loadingLabel="Loading movers">
              {(rows) => <TopMovers instruments={rows} />}
            </AsyncContent>
          </section>
        </div>
      </div>
      <section className="panel" aria-label="Recent activity">
        <div className="panel__header">
          <h2 className="panel__title">Recent activity</h2>
        </div>
        <RecentActivity />
      </section>
    </div>
  );
}
