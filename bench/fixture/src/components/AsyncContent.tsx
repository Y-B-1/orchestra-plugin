import type { ReactNode } from "react";
import type { AsyncState } from "../hooks/useAsync";
import { EmptyState, ErrorState, Loading } from "./Feedback";

interface AsyncContentProps<T> {
  state: AsyncState<T> & { reload?: () => void };
  loadingLabel: string;
  /** When given, data for which this returns true shows `emptyMessage` instead of the content. */
  isEmpty?: (data: T) => boolean;
  emptyMessage?: string;
  children: (data: T) => ReactNode;
}

/**
 * The loading, error and empty states every data-backed view shares. The
 * previous data stays visible while a reload is in flight.
 */
export function AsyncContent<T>({ state, loadingLabel, isEmpty, emptyMessage = "Nothing to show.", children }: AsyncContentProps<T>) {
  const { data, loading, error, reload } = state;
  return (
    <>
      {loading ? <Loading label={loadingLabel} /> : null}
      {error ? <ErrorState error={error} onRetry={reload} /> : null}
      {data !== null && isEmpty?.(data) ? <EmptyState message={emptyMessage} /> : null}
      {data !== null && !isEmpty?.(data) ? children(data) : null}
    </>
  );
}
