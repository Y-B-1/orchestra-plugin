import type { Client } from "../types";
import { formatCompactCurrency } from "../utils/format";

interface ClientListProps {
  clients: Client[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function ClientList({ clients, selectedId, onSelect }: ClientListProps) {
  return (
    <ul className="client-list">
      {clients.map((client) => (
        <li key={client.id}>
          <button
            type="button"
            className={`client-list__item${client.id === selectedId ? " client-list__item--active" : ""}`}
            onClick={() => onSelect(client.id)}
          >
            <span className="client-list__name">{client.name}</span>
            <span className="client-list__meta">
              {client.region} / {client.tier}
            </span>
            <span className="client-list__aum">{formatCompactCurrency(client.aum)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
