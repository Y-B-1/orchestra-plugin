import { useId } from "react";
import type { AssetClass, TradeFilters as Filters, TradeSide } from "../../types";
import { isInvertedRange } from "../../utils/dates";
import { assetClassLabels } from "../../utils/portfolio";
import { SegmentedControl } from "../SegmentedControl";

interface TradeFiltersProps {
  value: Filters;
  onChange: (next: Filters) => void;
  onReset: () => void;
}

const sideOptions: { value: TradeSide | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "buy", label: "Buy" },
  { value: "sell", label: "Sell" },
];

const assetClasses = Object.keys(assetClassLabels) as AssetClass[];

export function isFiltered(filters: Filters): boolean {
  return (
    filters.side !== "all" || filters.assetClass !== "all" || filters.from !== "" || filters.to !== "" || filters.symbol.trim() !== ""
  );
}

export function TradeFilters({ value, onChange, onReset }: TradeFiltersProps) {
  const id = useId();
  const inverted = isInvertedRange(value.from, value.to);

  function set<K extends keyof Filters>(key: K, next: Filters[K]) {
    onChange({ ...value, [key]: next });
  }

  return (
    <form className="filters" role="search" aria-label="Trade filters" onSubmit={(event) => event.preventDefault()}>
      <div className="filters__field">
        <span className="filters__label" id={`${id}-side`}>
          Side
        </span>
        <SegmentedControl label="Side" options={sideOptions} value={value.side} onChange={(next) => set("side", next)} />
      </div>
      <div className="filters__field">
        <label className="filters__label" htmlFor={`${id}-class`}>
          Asset class
        </label>
        <select
          id={`${id}-class`}
          className="input input--compact"
          value={value.assetClass}
          onChange={(event) => set("assetClass", event.target.value as AssetClass | "all")}
        >
          <option value="all">All asset classes</option>
          {assetClasses.map((assetClass) => (
            <option key={assetClass} value={assetClass}>
              {assetClassLabels[assetClass]}
            </option>
          ))}
        </select>
      </div>
      <div className="filters__field">
        <label className="filters__label" htmlFor={`${id}-symbol`}>
          Instrument
        </label>
        <input
          id={`${id}-symbol`}
          type="search"
          className="input input--compact"
          placeholder="Symbol"
          value={value.symbol}
          onChange={(event) => set("symbol", event.target.value)}
        />
      </div>
      <div className="filters__field">
        <label className="filters__label" htmlFor={`${id}-from`}>
          From
        </label>
        <input
          id={`${id}-from`}
          type="date"
          className="input input--compact"
          value={value.from}
          max={value.to || undefined}
          onChange={(event) => set("from", event.target.value)}
        />
      </div>
      <div className="filters__field">
        <label className="filters__label" htmlFor={`${id}-to`}>
          To
        </label>
        <input
          id={`${id}-to`}
          type="date"
          className="input input--compact"
          value={value.to}
          min={value.from || undefined}
          aria-invalid={inverted || undefined}
          aria-describedby={inverted ? `${id}-range-error` : undefined}
          onChange={(event) => set("to", event.target.value)}
        />
      </div>
      <div className="filters__actions">
        <button type="button" className="button button--ghost" onClick={onReset} disabled={!isFiltered(value)}>
          Reset filters
        </button>
      </div>
      {inverted ? (
        <p className="filters__error" id={`${id}-range-error`} role="alert">
          The start date must be on or before the end date.
        </p>
      ) : null}
    </form>
  );
}
