import type { PortfolioTotals } from "../../types";
import { formatCompactCurrency, formatNumber } from "../../utils/format";
import { PriceChange } from "../PriceChange";

export function PortfolioSummary({ totals }: { totals: PortfolioTotals }) {
  const dayPct = totals.marketValueUsd - totals.dayChangeUsd === 0
    ? 0
    : totals.dayChangeUsd / (totals.marketValueUsd - totals.dayChangeUsd);
  return (
    <section className="kpi-grid" aria-label="Portfolio summary">
      <article className="kpi-card" aria-label="Market value">
        <h3 className="kpi-card__label">Market value</h3>
        <p className="kpi-card__value">{formatCompactCurrency(totals.marketValueUsd)}</p>
        <p className="kpi-card__note">{formatNumber(totals.positions)} positions</p>
      </article>
      <article className="kpi-card" aria-label="Unrealized P&L">
        <h3 className="kpi-card__label">Unrealized P&amp;L</h3>
        <p className="kpi-card__value">{formatCompactCurrency(totals.unrealizedPnlUsd)}</p>
        <PriceChange pct={totals.unrealizedPnlPct} className="kpi-card__note" />
      </article>
      <article className="kpi-card" aria-label="Day change">
        <h3 className="kpi-card__label">Day change</h3>
        <p className="kpi-card__value">{formatCompactCurrency(totals.dayChangeUsd)}</p>
        <PriceChange pct={dayPct} className="kpi-card__note" />
      </article>
      <article className="kpi-card" aria-label="Cost basis">
        <h3 className="kpi-card__label">Cost basis</h3>
        <p className="kpi-card__value">{formatCompactCurrency(totals.costBasisUsd)}</p>
        <p className="kpi-card__note">USD at today's rates</p>
      </article>
    </section>
  );
}
