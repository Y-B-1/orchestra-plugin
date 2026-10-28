import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchRecentTrades } from "../../api";
import { useAsync } from "../../hooks/useAsync";
import { AsyncContent } from "../AsyncContent";
import { Table } from "../Table";
import { TradeDetail } from "../trades/TradeDetail";
import { instrumentTradeColumns } from "../trades/tradeColumns";

export function RecentTrades({ symbol }: { symbol: string }) {
  const state = useAsync(() => fetchRecentTrades(symbol, 10), [symbol]);
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <>
      <AsyncContent state={state} loadingLabel="Loading trades">
        {(trades) => (
          <Table
            caption={`Recent ${symbol} trades`}
            columns={instrumentTradeColumns}
            rows={trades}
            rowKey={(trade) => trade.id}
            emptyMessage={`No recent trades in ${symbol}.`}
            onRowClick={(trade) => setOpenId(trade.id)}
            rowLabel={(trade) => `Trade ${trade.id}`}
            selectedKey={openId}
          />
        )}
      </AsyncContent>
      <p className="panel__footer-link">
        <Link to={`/trades?symbol=${encodeURIComponent(symbol)}`}>All {symbol} trades</Link>
      </p>
      {openId ? <TradeDetail tradeId={openId} onClose={() => setOpenId(null)} /> : null}
    </>
  );
}
