import { Link } from "react-router-dom";
import { fetchTrades } from "../../api";
import { useAsync } from "../../hooks/useAsync";
import type { Trade } from "../../types";
import { AsyncContent } from "../AsyncContent";
import { Table, type Column } from "../Table";
import { blotterColumns } from "../trades/tradeColumns";

const shownColumns = new Set(["executedAt", "symbol", "side", "notional", "client"]);
const columns: Column<Trade>[] = blotterColumns.filter((column) => shownColumns.has(column.key));

/** The latest trades across all clients, for a quick glance on the dashboard. */
export function RecentActivity({ limit = 6 }: { limit?: number }) {
  const state = useAsync(() => fetchTrades(), []);
  return (
    <>
      <AsyncContent state={state} loadingLabel="Loading activity">
        {(trades) => (
          <Table
            caption="Latest trades"
            columns={columns}
            rows={trades.slice(0, limit)}
            rowKey={(trade) => trade.id}
            emptyMessage="No trades yet today."
          />
        )}
      </AsyncContent>
      <p className="panel__footer-link">
        <Link to="/trades">Open the trade blotter</Link>
      </p>
    </>
  );
}
