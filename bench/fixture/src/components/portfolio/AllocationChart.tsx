import { useId } from "react";
import type { AllocationSlice } from "../../types";
import { formatCompactCurrency, formatPercent } from "../../utils/format";
import { assetClassLabels } from "../../utils/portfolio";

interface AllocationChartProps {
  slices: readonly AllocationSlice[];
  title?: string;
}

const BAR_HEIGHT = 22;
const GAP = 14;
const LABEL_WIDTH = 110;
const VALUE_WIDTH = 70;
const WIDTH = 480;

/** Horizontal bars, one per asset class, scaled so the largest slice fills the track. */
export function AllocationChart({ slices, title = "Allocation by asset class" }: AllocationChartProps) {
  const titleId = useId();
  const descId = useId();
  const largest = Math.max(0, ...slices.map((slice) => slice.weight));
  const track = WIDTH - LABEL_WIDTH - VALUE_WIDTH;
  const height = slices.length * (BAR_HEIGHT + GAP) - GAP;
  const description = slices
    .map((slice) => `${assetClassLabels[slice.assetClass]} ${formatPercent(slice.weight, 1)}`)
    .join(", ");

  if (slices.length === 0) {
    return <p className="feedback feedback--empty">No holdings to allocate.</p>;
  }

  return (
    <figure className="allocation">
      <svg
        className="allocation__chart"
        viewBox={`0 0 ${WIDTH} ${height}`}
        width="100%"
        role="img"
        aria-labelledby={`${titleId} ${descId}`}
      >
        <title id={titleId}>{title}</title>
        <desc id={descId}>{description}</desc>
        {slices.map((slice, index) => {
          const y = index * (BAR_HEIGHT + GAP);
          const barWidth = largest > 0 ? (slice.weight / largest) * track : 0;
          return (
            <g key={slice.assetClass} className={`allocation__row allocation__row--${slice.assetClass}`}>
              <text x={0} y={y + BAR_HEIGHT / 2} dominantBaseline="middle" className="allocation__label">
                {assetClassLabels[slice.assetClass]}
              </text>
              <rect x={LABEL_WIDTH} y={y} width={track} height={BAR_HEIGHT} rx={4} className="allocation__track" />
              <rect
                x={LABEL_WIDTH}
                y={y}
                width={Math.max(barWidth, 2)}
                height={BAR_HEIGHT}
                rx={4}
                className="allocation__bar"
                data-asset-class={slice.assetClass}
              />
              <text
                x={WIDTH}
                y={y + BAR_HEIGHT / 2}
                dominantBaseline="middle"
                textAnchor="end"
                className="allocation__value"
              >
                {formatPercent(slice.weight, 1)}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="allocation__legend">
        <ul>
          {slices.map((slice) => (
            <li key={slice.assetClass}>
              <span className={`allocation__swatch allocation__swatch--${slice.assetClass}`} aria-hidden="true" />
              {assetClassLabels[slice.assetClass]}: {formatCompactCurrency(slice.valueUsd)}
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}
