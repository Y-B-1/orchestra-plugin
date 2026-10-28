import { formatNumber } from "../utils/format";
import { pageInfo, pageWindow } from "../utils/pagination";

interface PaginationProps {
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  /** Plural noun for the summary, e.g. "trades". */
  noun?: string;
}

export function Pagination({ total, page, pageSize, onPageChange, noun = "rows" }: PaginationProps) {
  const info = pageInfo(total, page, pageSize);
  const pages = pageWindow(page, info.pageCount);

  return (
    <nav className="pagination" aria-label="Pagination">
      <p className="pagination__summary" aria-live="polite">
        Showing {formatNumber(info.firstIndex)} to {formatNumber(info.lastIndex)} of {formatNumber(total)} {noun}
      </p>
      <div className="pagination__controls">
        <button
          type="button"
          className="button button--small"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </button>
        <ul className="pagination__pages">
          {pages.map((item, index) =>
            item === null ? (
              <li key={`gap-${index}`} className="pagination__gap" aria-hidden="true">
                ...
              </li>
            ) : (
              <li key={item}>
                <button
                  type="button"
                  className={`pagination__page${item === page ? " pagination__page--active" : ""}`}
                  aria-current={item === page ? "page" : undefined}
                  aria-label={`Page ${item}`}
                  onClick={() => onPageChange(item)}
                >
                  {item}
                </button>
              </li>
            ),
          )}
        </ul>
        <button
          type="button"
          className="button button--small"
          disabled={page >= info.pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </button>
      </div>
    </nav>
  );
}
