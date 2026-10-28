import type { TradeSide, TradeStatus } from "../../types";

const statusLabels: Record<TradeStatus, string> = {
  filled: "Filled",
  partial: "Partial",
  cancelled: "Cancelled",
};

export function TradeSideBadge({ side }: { side: TradeSide }) {
  return <span className={`side side--${side}`}>{side === "buy" ? "Buy" : "Sell"}</span>;
}

export function TradeStatusBadge({ status }: { status: TradeStatus }) {
  return <span className={`badge badge--trade-${status}`}>{statusLabels[status]}</span>;
}
