import type { ReportStatus } from "../types";

const labels: Record<ReportStatus, string> = {
  draft: "Draft",
  published: "Published",
  failed: "Failed",
  scheduled: "Scheduled",
};

export function StatusBadge({ status }: { status: ReportStatus }) {
  return <span className={`badge badge--${status}`}>{labels[status]}</span>;
}
