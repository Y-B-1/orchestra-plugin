import data from "../data/reports.json";
import type { Report, ReportStatus } from "../types";
import { delay } from "./client";

const reports = data as Report[];

export async function fetchReports(status?: ReportStatus): Promise<Report[]> {
  const rows = status ? reports.filter((r) => r.status === status) : reports;
  const sorted = [...rows].sort((a, b) => b.date.localeCompare(a.date));
  return delay(sorted.map((row) => ({ ...row })));
}
