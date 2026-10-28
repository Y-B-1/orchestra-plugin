import { useMemo, useState, type KeyboardEvent, type ReactNode } from "react";
import type { SortState } from "../types";
import { ariaSort, nextSort, sortBy, type SortValue } from "../utils/sort";
import { EmptyState } from "./Feedback";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** Present on sortable columns: the value rows are ordered by. */
  sortValue?: (row: T) => SortValue;
  align?: "left" | "right";
  /** Renders the cell as a row header (`<th scope="row">`). */
  rowHeader?: boolean;
  cellClassName?: (row: T) => string | undefined;
}

interface TableProps<T> {
  columns: readonly Column<T>[];
  rows: readonly T[];
  rowKey: (row: T) => string;
  caption?: string;
  emptyMessage?: string;
  /** Initial sort for a table that sorts its own rows. */
  initialSort?: SortState | null;
  /**
   * Controlled sort: pass `sort` and `onSortChange` when the caller sorts the
   * rows itself, for example before paginating. The table then renders rows as given.
   */
  sort?: SortState | null;
  onSortChange?: (next: SortState) => void;
  onRowClick?: (row: T) => void;
  rowLabel?: (row: T) => string;
  selectedKey?: string | null;
  footer?: ReactNode;
  className?: string;
}

/** Sorts rows by the column named in `sort`; unknown or unsortable columns keep the input order. */
export function sortRows<T>(rows: readonly T[], columns: readonly Column<T>[], sort: SortState | null): T[] {
  if (!sort) return [...rows];
  const column = columns.find((c) => c.key === sort.key);
  if (!column?.sortValue) return [...rows];
  return sortBy(rows, column.sortValue, sort.direction);
}

export function Table<T>({
  columns,
  rows,
  rowKey,
  caption,
  emptyMessage = "Nothing to show.",
  initialSort = null,
  sort,
  onSortChange,
  onRowClick,
  rowLabel,
  selectedKey = null,
  footer,
  className,
}: TableProps<T>) {
  const controlled = sort !== undefined;
  const [ownSort, setOwnSort] = useState<SortState | null>(initialSort);
  const activeSort = controlled ? sort : ownSort;

  const visibleRows = useMemo(
    () => (controlled ? [...rows] : sortRows(rows, columns, ownSort)),
    [controlled, rows, columns, ownSort],
  );

  function changeSort(key: string) {
    const next = nextSort(activeSort, key);
    if (controlled) {
      onSortChange?.(next);
    } else {
      setOwnSort(next);
    }
  }

  function onRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, row: T) {
    if (!onRowClick) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onRowClick(row);
    }
  }

  const alignClass = (column: Column<T>) => (column.align === "right" ? "table__num" : undefined);

  return (
    <div className="table-wrap">
      <table className={`table${onRowClick ? " table--interactive" : ""}${className ? ` ${className}` : ""}`}>
        {caption ? <caption className="visually-hidden">{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={alignClass(column)}
                aria-sort={column.sortValue ? ariaSort(activeSort, column.key) : undefined}
              >
                {column.sortValue ? (
                  <button type="button" className="table__sort" onClick={() => changeSort(column.key)}>
                    {column.header}
                    <span className="table__sort-icon" aria-hidden="true">
                      {activeSort?.key === column.key ? (activeSort.direction === "asc" ? "▲" : "▼") : ""}
                    </span>
                  </button>
                ) : (
                  column.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row) => {
            const key = rowKey(row);
            return (
              <tr
                key={key}
                className={key === selectedKey ? "table__row--selected" : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={onRowClick ? (event) => onRowKeyDown(event, row) : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                aria-label={rowLabel ? rowLabel(row) : undefined}
              >
                {columns.map((column) => {
                  const classes = [alignClass(column), column.cellClassName?.(row)].filter(Boolean).join(" ") || undefined;
                  return column.rowHeader ? (
                    <th key={column.key} scope="row" className={classes}>
                      {column.render(row)}
                    </th>
                  ) : (
                    <td key={column.key} className={classes}>
                      {column.render(row)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
        {footer ? <tfoot>{footer}</tfoot> : null}
      </table>
      {visibleRows.length === 0 ? <EmptyState message={emptyMessage} /> : null}
    </div>
  );
}
