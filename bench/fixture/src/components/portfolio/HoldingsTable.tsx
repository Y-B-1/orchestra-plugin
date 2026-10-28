import { Link } from "react-router-dom";
import type { PortfolioTotals, Position } from "../../types";
import { formatCurrency, formatPercent } from "../../utils/format";
import { formatPrice, formatQuantity, formatSignedCurrency, toneOf } from "../../utils/numbers";
import { assetClassLabels } from "../../utils/portfolio";
import { PriceChange } from "../PriceChange";
import { Table, type Column } from "../Table";

const columns: Column<Position>[] = [
  {
    key: "symbol",
    header: "Instrument",
    rowHeader: true,
    render: (p) => (
      <>
        <Link to={`/instruments/${p.symbol}`} className="table__symbol table__link">
          {p.symbol}
        </Link>
        <span className="table__name">{p.name}</span>
      </>
    ),
    sortValue: (p) => p.symbol,
  },
  {
    key: "assetClass",
    header: "Asset class",
    render: (p) => assetClassLabels[p.assetClass],
    sortValue: (p) => assetClassLabels[p.assetClass],
  },
  {
    key: "book",
    header: "Book",
    render: (p) => p.book,
    sortValue: (p) => p.book,
  },
  {
    key: "quantity",
    header: "Quantity",
    align: "right",
    render: (p) => formatQuantity(p.quantity),
    sortValue: (p) => p.quantity,
  },
  {
    key: "avgCost",
    header: "Avg cost",
    align: "right",
    render: (p) => formatPrice(p.avgCost, p.currency),
    sortValue: (p) => p.avgCost,
  },
  {
    key: "price",
    header: "Price",
    align: "right",
    render: (p) => (
      <>
        {formatPrice(p.price, p.currency)}
        <PriceChange pct={p.changePct} className="table__sub" />
      </>
    ),
    sortValue: (p) => p.price,
  },
  {
    key: "marketValueUsd",
    header: "Market value (USD)",
    align: "right",
    render: (p) => formatCurrency(p.marketValueUsd),
    sortValue: (p) => p.marketValueUsd,
  },
  {
    key: "unrealizedPnlUsd",
    header: "Unrealized P&L",
    align: "right",
    render: (p) => formatSignedCurrency(p.unrealizedPnlUsd),
    sortValue: (p) => p.unrealizedPnlUsd,
    cellClassName: (p) => `text-${toneOf(p.unrealizedPnlUsd)}`,
  },
  {
    key: "weight",
    header: "Weight",
    align: "right",
    render: (p) => formatPercent(p.weight, 1),
    sortValue: (p) => p.weight,
  },
];

function TotalsRow({ totals }: { totals: PortfolioTotals }) {
  return (
    <tr className="table__totals">
      <th scope="row" colSpan={6}>
        Total ({totals.positions} positions)
      </th>
      <td className="table__num" data-testid="total-market-value">
        {formatCurrency(totals.marketValueUsd)}
      </td>
      <td className={`table__num text-${toneOf(totals.unrealizedPnlUsd)}`}>{formatSignedCurrency(totals.unrealizedPnlUsd)}</td>
      <td className="table__num">{formatPercent(totals.positions > 0 ? 1 : 0, 1)}</td>
    </tr>
  );
}

export function HoldingsTable({ positions, totals }: { positions: Position[]; totals: PortfolioTotals }) {
  return (
    <Table
      caption="Holdings"
      columns={columns}
      rows={positions}
      rowKey={(p) => p.id}
      initialSort={{ key: "marketValueUsd", direction: "desc" }}
      emptyMessage="This portfolio has no holdings."
      footer={<TotalsRow totals={totals} />}
    />
  );
}
