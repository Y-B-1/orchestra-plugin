import { useId } from "react";

interface SparklineProps {
  values: readonly number[];
  /** Accessible description, e.g. "AAPL closing prices over 3 months". */
  label: string;
  width?: number;
  height?: number;
  tone?: "up" | "down" | "flat";
  showArea?: boolean;
}

const PADDING = 2;

/** Maps values to SVG polyline points that fill a width by height box. */
export function sparklinePoints(values: readonly number[], width: number, height: number, padding = PADDING): [number, number][] {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = values.length > 1 ? (width - padding * 2) / (values.length - 1) : 0;
  const usable = height - padding * 2;
  return values.map((value, index) => {
    const x = padding + index * step;
    const y = padding + ((value - min) / span) * usable;
    return [Number(x.toFixed(2)), Number(y.toFixed(2))];
  });
}

export function Sparkline({ values, label, width = 320, height = 80, tone = "flat", showArea = true }: SparklineProps) {
  const titleId = useId();
  const points = sparklinePoints(values, width, height);
  if (points.length === 0) {
    return <p className="feedback feedback--empty">No price history.</p>;
  }
  const line = points.map(([x, y]) => `${x},${y}`).join(" ");
  const first = points[0];
  const last = points[points.length - 1];
  const area = first && last ? `M${first[0]},${height} L${line.replace(/ /g, " L")} L${last[0]},${height} Z` : "";

  return (
    <svg
      className={`sparkline sparkline--${tone}`}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      role="img"
      aria-labelledby={titleId}
      preserveAspectRatio="none"
      data-testid="price-sparkline"
    >
      <title id={titleId}>{label}</title>
      {showArea ? <path className="sparkline__area" d={area} /> : null}
      <polyline className="sparkline__line" points={line} fill="none" />
      {last ? <circle className="sparkline__dot" cx={last[0]} cy={last[1]} r={2.5} /> : null}
    </svg>
  );
}
