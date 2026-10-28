import data from "../data/clients.json";
import type { Client } from "../types";
import { matchesQuery } from "../utils/search";
import { delay, latency, NotFoundError } from "./client";

const clients = data as Client[];

export async function fetchClients(query = ""): Promise<Client[]> {
  const rows = clients.filter((c) => matchesQuery(query, c.name, c.contact, c.region));
  // Broad searches scan and return more rows, so they take longer to come back.
  return delay(
    rows.map((row) => ({ ...row })),
    latency.ms * (1 + rows.length / 2),
  );
}

export async function fetchClient(id: string): Promise<Client> {
  const found = clients.find((c) => c.id === id);
  if (!found) throw new NotFoundError("Client", id);
  return delay({ ...found });
}

export function clientName(id: string): string {
  return clients.find((c) => c.id === id)?.name ?? id;
}
