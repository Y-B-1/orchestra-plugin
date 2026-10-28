import { useState } from "react";
import { fetchPriceHistory, type HistoryRange } from "../../api";
import { useAsync } from "../../hooks/useAsync";
import type { PricePoint } from "../../types";
import { formatShortDate } from "../../utils/dates";
import { formatSignedPercent } from "../../utils/format";
import { formatPrice, toneOf } from "../../utils/numbers";
import { AsyncContent } from "../AsyncContent";
import { Sparkline } from "../Sparkline";
import { Tabs } from "../Tabs";

const ranges: { id: HistoryRange; label: string; description: string }[] = [
  { id: "1M", label: "1 month", description: "1 month" },
  { id: "3M", label: "3 months", description: "3 months" },
];

function HistoryChart({ symbol, points, currency, range }: { symbol: string; points: PricePoint[]; currency: string; range: string }) {
  const first = points[0];
  const last = points[points.length - 1];
  if (!first || !last) return <p className="feedback feedback--empty">No price history.</p>;
  const change = (last.close - first.close) / first.close;
  const closes = points.map((point) => point.close);
  return (
    <div className="price-history">
      <Sparkline
        values={closes}
        label={`${symbol} daily closes over ${range}, from ${formatPrice(first.close, currency)} to ${formatPrice(last.close, currency)}`}
        height={140}
        tone={toneOf(change)}
      />
      <div className="price-history__axis">
        <span>{formatShortDate(first.date)}</span>
        <span className={`text-${toneOf(change)}`}>{formatSignedPercent(change)} over the period</span>
        <span>{formatShortDate(last.date)}</span>
      </div>
      <p className="price-history__range">
        Low {formatPrice(Math.min(...closes), currency)} / High {formatPrice(Math.max(...closes), currency)}
      </p>
    </div>
  );
}

function RangePanel({ symbol, currency, range, description }: { symbol: string; currency: string; range: HistoryRange; description: string }) {
  const state = useAsync(() => fetchPriceHistory(symbol, range), [symbol, range]);
  return (
    <AsyncContent state={state} loadingLabel="Loading price history" isEmpty={(points) => points.length === 0} emptyMessage="No price history.">
      {(points) => <HistoryChart symbol={symbol} points={points} currency={currency} range={description} />}
    </AsyncContent>
  );
}

export function PriceHistory({ symbol, currency }: { symbol: string; currency: string }) {
  const [range, setRange] = useState<HistoryRange>("3M");
  return (
    <Tabs
      label="Price history range"
      value={range}
      onChange={(id) => setRange(id as HistoryRange)}
      tabs={ranges.map((item) => ({
        id: item.id,
        label: item.label,
        render: () => <RangePanel symbol={symbol} currency={currency} range={item.id} description={item.description} />,
      }))}
    />
  );
}
