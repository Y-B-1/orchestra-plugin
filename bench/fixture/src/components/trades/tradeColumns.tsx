import { Link } from "react-router-dom";
import { clientName } from "../../api";
import type { Trade } from "../../types";
import { formatDateTime } from "../../utils/format";
import { formatPrice, formatQuantity } from "../../utils/numbers";
import type { Column } from "../Table";
import { TradeSideBadge, TradeStatusBadge } from "./TradeBadges";

export function tradeNotional(trade: Trade): number {
  return trade.filledQuantity * trade.price;
}

const executed: Column<Trade> = {
  key: "executedAt",
  header: "Time",
  render: (trade) => <time dateTime={trade.executedAt}>{formatDateTime(trade.executedAt)}</time>,
  sortValue: (trade) => formatDateTime(trade.executedAt),
};

const id: Column<Trade> = {
  key: "id",
  header: "Trade",
  rowHeader: true,
  render: (trade) => <span className="table__mono">{trade.id}</span>,
  sortValue: (trade) => trade.id,
};

const symbol: Column<Trade> = {
  key: "symbol",
  header: "Instrument",
  render: (trade) => (
    <Link to={`/instruments/${trade.symbol}`} className="table__link" onClick={(event) => event.stopPropagation()}>
      {trade.symbol}
    </Link>
  ),
  sortValue: (trade) => trade.symbol,
};

const side: Column<Trade> = {
  key: "side",
  header: "Side",
  render: (trade) => <TradeSideBadge side={trade.side} />,
  sortValue: (trade) => trade.side,
};

const quantity: Column<Trade> = {
  key: "quantity",
  header: "Quantity",
  align: "right",
  render: (trade) => formatQuantity(trade.quantity),
  sortValue: (trade) => trade.quantity,
};

const price: Column<Trade> = {
  key: "price",
  header: "Price",
  align: "right",
  render: (trade) => formatPrice(trade.price, trade.currency),
  sortValue: (trade) => trade.price,
};

const notional: Column<Trade> = {
  key: "notional",
  header: "Notional",
  align: "right",
  render: (trade) => formatPrice(tradeNotional(trade), trade.currency),
  sortValue: (trade) => tradeNotional(trade),
};

const client: Column<Trade> = {
  key: "client",
  header: "Client",
  render: (trade) => clientName(trade.clientId),
  sortValue: (trade) => clientName(trade.clientId),
};

const status: Column<Trade> = {
  key: "status",
  header: "Status",
  render: (trade) => <TradeStatusBadge status={trade.status} />,
  sortValue: (trade) => trade.status,
};

/** Columns of the full trade blotter. */
export const blotterColumns: Column<Trade>[] = [id, executed, symbol, side, quantity, price, notional, client, status];

/** Columns for a trade list already scoped to one instrument. */
export const instrumentTradeColumns: Column<Trade>[] = [id, executed, side, quantity, price, client, status];
