import { Link } from "react-router-dom";
import { fetchClient, fetchTrade } from "../../api";
import { useAsync } from "../../hooks/useAsync";
import type { Trade } from "../../types";
import { formatCurrency, formatDateTime } from "../../utils/format";
import { formatPrice, formatQuantity, percentOf } from "../../utils/numbers";
import { assetClassLabels } from "../../utils/portfolio";
import { AsyncContent } from "../AsyncContent";
import { Drawer } from "../Drawer";
import { StatList } from "../StatList";
import { TradeSideBadge, TradeStatusBadge } from "./TradeBadges";
import { tradeNotional } from "./tradeColumns";

interface TradeDetailProps {
  tradeId: string;
  onClose: () => void;
}

function ClientLine({ clientId }: { clientId: string }) {
  const state = useAsync(() => fetchClient(clientId), [clientId]);
  if (state.error) return <span>{clientId}</span>;
  if (!state.data) return <span className="text-muted">Loading...</span>;
  return (
    <span>
      {state.data.name} <span className="text-muted">({state.data.contact})</span>
    </span>
  );
}

function TradeBody({ trade }: { trade: Trade }) {
  const fillRatio = percentOf(trade.filledQuantity, trade.quantity);
  return (
    <div className="trade-detail">
      <div className="trade-detail__summary">
        <TradeSideBadge side={trade.side} />
        <span className="trade-detail__headline">
          {formatQuantity(trade.quantity)} {trade.symbol} at {formatPrice(trade.price, trade.currency)}
        </span>
        <TradeStatusBadge status={trade.status} />
      </div>
      <StatList
        stats={[
          { label: "Executed", value: `${formatDateTime(trade.executedAt)} UTC` },
          { label: "Asset class", value: assetClassLabels[trade.assetClass] },
          { label: "Filled", value: `${formatQuantity(trade.filledQuantity)} (${Math.round(fillRatio * 100)}%)` },
          { label: "Notional", value: formatPrice(tradeNotional(trade), trade.currency) },
          { label: "Fees", value: formatCurrency(trade.fees, trade.currency) },
          { label: "Venue", value: trade.venue },
          { label: "Trader", value: trade.trader },
          { label: "Client", value: <ClientLine clientId={trade.clientId} /> },
        ]}
      />
      <p className="trade-detail__links">
        <Link to={`/instruments/${trade.symbol}`}>View {trade.symbol}</Link>
      </p>
    </div>
  );
}

export function TradeDetail({ tradeId, onClose }: TradeDetailProps) {
  const state = useAsync(() => fetchTrade(tradeId), [tradeId]);
  return (
    <Drawer label="Trade details" title={`Trade ${tradeId}`} onClose={onClose} closeLabel="Close trade details">
      <AsyncContent state={state} loadingLabel="Loading trade">
        {(trade) => <TradeBody trade={trade} />}
      </AsyncContent>
    </Drawer>
  );
}
