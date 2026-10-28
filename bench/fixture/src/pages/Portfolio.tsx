import { useMemo } from "react";
import { fetchPositions } from "../api";
import { AsyncContent } from "../components/AsyncContent";
import { AllocationChart } from "../components/portfolio/AllocationChart";
import { HoldingsTable } from "../components/portfolio/HoldingsTable";
import { PortfolioSummary } from "../components/portfolio/PortfolioSummary";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { Position } from "../types";
import { allocationByClass, portfolioTotals } from "../utils/portfolio";

function PortfolioView({ positions }: { positions: Position[] }) {
  const totals = useMemo(() => portfolioTotals(positions), [positions]);
  const allocation = useMemo(() => allocationByClass(positions), [positions]);
  return (
    <>
      <PortfolioSummary totals={totals} />
      <div className="page__columns">
        <section className="panel" aria-label="Holdings">
          <div className="panel__header">
            <h2 className="panel__title">Holdings</h2>
            <p className="panel__hint">Values in USD at today's FX rates</p>
          </div>
          <HoldingsTable positions={positions} totals={totals} />
        </section>
        <section className="panel" aria-label="Allocation">
          <div className="panel__header">
            <h2 className="panel__title">Allocation</h2>
          </div>
          <AllocationChart slices={allocation} />
        </section>
      </div>
    </>
  );
}

export function Portfolio() {
  useDocumentTitle("Portfolio");
  const state = useAsync(fetchPositions, []);
  return (
    <div className="page">
      <AsyncContent
        state={state}
        loadingLabel="Loading portfolio"
        isEmpty={(positions) => positions.length === 0}
        emptyMessage="This portfolio has no holdings."
      >
        {(positions) => <PortfolioView positions={positions} />}
      </AsyncContent>
    </div>
  );
}
