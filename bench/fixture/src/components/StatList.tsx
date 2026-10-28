import type { ReactNode } from "react";

export interface Stat {
  label: string;
  value: ReactNode;
  hint?: string;
}

/** A compact grid of label and value pairs, used for key figures in panels and drawers. */
export function StatList({ stats, columns = 2 }: { stats: readonly Stat[]; columns?: 1 | 2 | 3 | 4 }) {
  return (
    <dl className={`stat-list stat-list--cols-${columns}`}>
      {stats.map((stat) => (
        <div key={stat.label} className="stat-list__item">
          <dt className="stat-list__label" title={stat.hint}>
            {stat.label}
          </dt>
          <dd className="stat-list__value">{stat.value}</dd>
        </div>
      ))}
    </dl>
  );
}
