import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { Instrument } from "../types";
import { formatCurrency, formatSignedPercent, formatVolume } from "../utils/format";

type SortKey = "symbol" | "price" | "changePct" | "volume";

export function InstrumentTable({ instruments }: { instruments: Instrument[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("symbol");
  const [descending, setDescending] = useState(false);

  const rows = useMemo(() => {
    const sorted = [...instruments].sort((a, b) => {
      const left = a[sortKey];
      const right = b[sortKey];
      if (typeof left === "number" && typeof right === "number") return left - right;
      return String(left).localeCompare(String(right));
    });
    return descending ? sorted.reverse() : sorted;
  }, [instruments, sortKey, descending]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setDescending((prev) => !prev);
    } else {
      setSortKey(key);
      setDescending(false);
    }
  }

  function header(key: SortKey, label: string) {
    const active = key === sortKey;
    return (
      <th scope="col" aria-sort={active ? (descending ? "descending" : "ascending") : "none"}>
        <button type="button" className="table__sort" onClick={() => toggleSort(key)}>
          {label}
        </button>
      </th>
    );
  }

  return (
    <table className="table">
      <thead>
        <tr>
          {header("symbol", "Instrument")}
          {header("price", "Price")}
          {header("changePct", "Change")}
          {header("volume", "Volume")}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.symbol}>
            <th scope="row">
              <Link to={`/instruments/${row.symbol}`} className="table__symbol table__link">
                {row.symbol}
              </Link>
              <span className="table__name">{row.name}</span>
            </th>
            <td className="table__num">{formatCurrency(row.price, row.currency)}</td>
            <td className={`table__num ${row.changePct >= 0 ? "text-up" : "text-down"}`}>
              {formatSignedPercent(row.changePct)}
            </td>
            <td className="table__num">{formatVolume(row.volume)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
