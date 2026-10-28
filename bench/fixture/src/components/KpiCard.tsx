import type { Kpi } from "../types";
import { formatCompactCurrency, formatNumber, formatPercent, formatSignedPercent } from "../utils/format";

function formatValue(kpi: Kpi): string {
  switch (kpi.format) {
    case "currency":
      return formatCompactCurrency(kpi.value);
    case "percent":
      return formatPercent(kpi.value);
    default:
      return formatNumber(kpi.value);
  }
}

export function KpiCard({ kpi }: { kpi: Kpi }) {
  const tone = kpi.deltaPct >= 0 ? "up" : "down";
  return (
    <article className="kpi-card" aria-label={kpi.label}>
      <h3 className="kpi-card__label">{kpi.label}</h3>
      <p className="kpi-card__value">{formatValue(kpi)}</p>
      <p className={`kpi-card__delta kpi-card__delta--${tone}`}>{formatSignedPercent(kpi.deltaPct)}</p>
    </article>
  );
}
