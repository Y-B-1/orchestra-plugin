import { useState } from "react";
import { fetchReports } from "../api";
import { AsyncContent } from "../components/AsyncContent";
import { StatusBadge } from "../components/StatusBadge";
import { Tabs } from "../components/Tabs";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { Report, ReportStatus } from "../types";
import { formatDate } from "../utils/format";

type ReportFilter = ReportStatus | "all";

const filters: { id: ReportFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "published", label: "Published" },
  { id: "scheduled", label: "Scheduled" },
  { id: "draft", label: "Drafts" },
  { id: "failed", label: "Failed" },
];

function ReportList({ reports }: { reports: Report[] }) {
  return (
    <ul className="report-list">
      {reports.map((report) => (
        <li key={report.id} className="report-list__item">
          <div>
            <p className="report-list__title">{report.title}</p>
            <p className="report-list__meta">
              {formatDate(report.date)} by {report.author}
              {report.pages > 0 ? `, ${report.pages} pages` : ""}
            </p>
          </div>
          <StatusBadge status={report.status} />
        </li>
      ))}
    </ul>
  );
}

function FilteredReports({ filter }: { filter: ReportFilter }) {
  const state = useAsync(() => fetchReports(filter === "all" ? undefined : filter), [filter]);
  return (
    <AsyncContent
      state={state}
      loadingLabel="Loading reports"
      isEmpty={(rows) => rows.length === 0}
      emptyMessage="No reports with this status."
    >
      {(rows) => <ReportList reports={rows} />}
    </AsyncContent>
  );
}

export function Reports() {
  useDocumentTitle("Reports");
  const [filter, setFilter] = useState<ReportFilter>("all");

  return (
    <div className="page">
      <section className="panel" aria-label="Daily reports">
        <div className="panel__header">
          <h2 className="panel__title">Daily reports</h2>
        </div>
        <Tabs
          label="Report status"
          value={filter}
          onChange={(id) => setFilter(id as ReportFilter)}
          tabs={filters.map((item) => ({
            id: item.id,
            label: item.label,
            render: () => <FilteredReports filter={item.id} />,
          }))}
        />
      </section>
    </div>
  );
}
