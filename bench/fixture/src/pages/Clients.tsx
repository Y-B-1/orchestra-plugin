import { useCallback, useEffect, useState } from "react";
import { fetchClients } from "../api";
import { AsyncContent } from "../components/AsyncContent";
import { ClientDrawer } from "../components/ClientDrawer";
import { ClientList } from "../components/ClientList";
import { toError, type AsyncState } from "../hooks/useAsync";
import { useDebounce } from "../hooks/useDebounce";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { Client } from "../types";

export const SEARCH_DEBOUNCE_MS = 150;

export function Clients() {
  useDocumentTitle("Clients");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [results, setResults] = useState<AsyncState<Client[]>>({ data: null, loading: true, error: null });
  const debouncedQuery = useDebounce(query, SEARCH_DEBOUNCE_MS);
  const close = useCallback(() => setSelectedId(null), []);

  // The previous results stay on screen while the next search is in flight.
  useEffect(() => {
    setResults((prev) => ({ ...prev, loading: true, error: null }));
    fetchClients(debouncedQuery).then(
      (data) => setResults({ data, loading: false, error: null }),
      (error: unknown) => setResults({ data: null, loading: false, error: toError(error) }),
    );
  }, [debouncedQuery]);

  return (
    <div className="page">
      <section className="panel" aria-label="Clients">
        <div className="panel__header">
          <h2 className="panel__title">Clients</h2>
          <input
            type="search"
            className="input"
            placeholder="Search clients"
            aria-label="Search clients"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <AsyncContent
          state={results}
          loadingLabel="Loading clients"
          isEmpty={(rows) => rows.length === 0}
          emptyMessage="No clients match your search."
        >
          {(rows) => <ClientList clients={rows} selectedId={selectedId} onSelect={setSelectedId} />}
        </AsyncContent>
      </section>
      {selectedId ? <ClientDrawer clientId={selectedId} onClose={close} /> : null}
    </div>
  );
}
