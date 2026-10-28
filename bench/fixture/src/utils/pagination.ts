export const DEFAULT_PAGE_SIZE = 25;

export interface PageInfo {
  page: number;
  pageCount: number;
  firstIndex: number;
  lastIndex: number;
  total: number;
}

export function pageCount(total: number, pageSize = DEFAULT_PAGE_SIZE): number {
  if (pageSize <= 0) throw new Error("Page size must be positive");
  return Math.floor(total / pageSize) + 1;
}

/** Returns the rows for a 1-based page. Pages past the end are empty. */
export function paginate<T>(rows: readonly T[], page: number, pageSize = DEFAULT_PAGE_SIZE): T[] {
  const start = (page - 1) * pageSize;
  return rows.slice(start, start + pageSize);
}

/** Describes a page for "Showing 26 to 50 of 150" labels; indexes are 1-based. */
export function pageInfo(total: number, page: number, pageSize = DEFAULT_PAGE_SIZE): PageInfo {
  const count = pageCount(total, pageSize);
  const firstIndex = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastIndex = Math.min(total, page * pageSize);
  return { page, pageCount: count, firstIndex, lastIndex, total };
}

/** Page numbers to show in a pager, with null marking a gap: [1, null, 4, 5, 6, null, 9]. */
export function pageWindow(current: number, count: number, radius = 1): (number | null)[] {
  const pages: (number | null)[] = [];
  for (let page = 1; page <= count; page++) {
    const nearCurrent = Math.abs(page - current) <= radius;
    if (page === 1 || page === count || nearCurrent) {
      pages.push(page);
    } else if (pages[pages.length - 1] !== null) {
      pages.push(null);
    }
  }
  return pages;
}
