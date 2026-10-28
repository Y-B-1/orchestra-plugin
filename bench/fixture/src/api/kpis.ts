import data from "../data/kpis.json";
import type { Kpi } from "../types";
import { delay } from "./client";

export async function fetchKpis(): Promise<Kpi[]> {
  return delay((data as Kpi[]).map((kpi) => ({ ...kpi })));
}
