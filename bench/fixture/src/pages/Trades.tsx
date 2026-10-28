import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { clientName, emptyTradeFilters, fetchTrades } from "../api";
import { AsyncContent } from "../components/AsyncContent";
import { Pagination } from "../components/Pagination";
import { sortRows, Table } from "../components/Table";
import { blotterColumns, tradeNotional } from "../components/trades/tradeColumns";
import { TradeDetail } from "../components/trades/TradeDetail";
import { TradeFilters } from "../components/trades/TradeFilters";
import { useAsync } from "../hooks/useAsync";
import { useDebounce } from "../hooks/useDebounce";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { SortState, Trade, TradeFilters as Filters } from "../types";
import { toCsv, downloadCsv, type CsvColumn } from "../utils/csv";
import { DEFAULT_PAGE_SIZE, paginate } from "../utils/pagination";

const csvColumns: CsvColumn<Trade>[] = [
  { header: "Trade", value: (t) => t.id },
  { header: "Executed (UTC)", value: (t) => t.executedAt },
  { header: "Instrument", value: (t) => t.symbol },
  { header: "Side", value: (t) => t.side },
  { header: "Quantity", value: (t) => t.quantity },
  { header: "Filled", value: (t) => t.filledQuantity },
  { header: "Price", value: (t) => t.price },
  { header: "Currency", value: (t) => t.currency },
  { header: "Notional", value: (t) => tradeNotional(t) },
  { header: "Client", value: (t) => clientName(t.clientId) },
  { header: "Trader", value: (t) => t.trader },
  { header: "Venue", value: (t) => t.venue },
  { header: "Status", value: (t) => t.status },
];

function initialFilters(params: URLSearchParams): Filters {
  return { ...emptyTradeFilters, symbol: params.get("symbol") ?? "" };
}

interface BlotterProps {
  trades: Trade[];
  sort: SortState | null;
  onSortChange: (next: SortState) => void;
  page: number;
  onPageChange: (page: number) => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function Blotter({ trades, sort, onSortChange, page, onPageChange, selectedId, onSelect }: BlotterProps) {
  const sorted = useMemo(() => sortRows(trades, blotterColumns, sort), [trades, sort]);
  const visible = paginate(sorted, page, DEFAULT_PAGE_SIZE);
  return (
    <>
      <Table
        caption="Trade blotter"
        columns={blotterColumns}
        rows={visible}
        rowKey={(trade) => trade.id}
        sort={sort}
        onSortChange={onSortChange}
        onRowClick={(trade) => onSelect(trade.id)}
        rowLabel={(trade) => `Trade ${trade.id}`}
        selectedKey={selectedId}
        emptyMessage="No trades match these filters."
      />
      <Pagination total={trades.length} page={page} pageSize={DEFAULT_PAGE_SIZE} onPageChange={onPageChange} noun="trades" />
    </>
  );
}

export function Trades() {
  useDocumentTitle("Trades");
  const [params] = useSearchParams();
  const [filters, setFilters] = useState<Filters>(() => initialFilters(params));
  const [sort, setSort] = useState<SortState | null>(null);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const symbol = useDebounce(filters.symbol, 250);

  const state = useAsync(
    () => fetchTrades({ ...filters, symbol }),
    [filters.side, filters.assetClass, filters.from, filters.to, symbol],
  );

  const changeFilters = useCallback((next: Filters) => {
    setFilters(next);
    setPage(1);
  }, []);

  const changeSort = useCallback((next: SortState) => {
    setSort(next);
    setPage(1);
  }, []);

  const close = useCallback(() => setSelectedId(null), []);

  function exportCsv() {
    if (!state.data) return;
    const rows = sortRows(state.data, blotterColumns, sort);
    downloadCsv(`pulse-trades-${new Date().toISOString().slice(0, 10)}.csv`, toCsv(rows, csvColumns));
  }

  return (
    <div className="page">
      <section className="panel" aria-label="Trades">
        <div className="panel__header">
          <h2 className="panel__title">Trade blotter</h2>
          <button type="button" className="button" onClick={exportCsv} disabled={!state.data || state.data.length === 0}>
            Export CSV
          </button>
        </div>
        <TradeFilters value={filters} onChange={changeFilters} onReset={() => changeFilters(emptyTradeFilters)} />
        <AsyncContent state={state} loadingLabel="Loading trades">
          {(trades) => (
            <Blotter
              trades={trades}
              sort={sort}
              onSortChange={changeSort}
              page={page}
              onPageChange={setPage}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </AsyncContent>
      </section>
      {selectedId ? <TradeDetail tradeId={selectedId} onClose={close} /> : null}
    </div>
  );
}
