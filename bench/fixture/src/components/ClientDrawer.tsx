import type { Client } from "../types";
import { fetchClient } from "../api";
import { useAsync } from "../hooks/useAsync";
import { formatCurrency, formatDateTime } from "../utils/format";
import { AsyncContent } from "./AsyncContent";
import { ClientNotes } from "./clients/ClientNotes";
import { Drawer } from "./Drawer";
import { Tabs } from "./Tabs";

interface ClientDrawerProps {
  clientId: string;
  onClose: () => void;
}

function Details({ client }: { client: Client }) {
  return (
    <dl className="details">
      <dt>Tier</dt>
      <dd>{client.tier}</dd>
      <dt>Region</dt>
      <dd>{client.region}</dd>
      <dt>Contact</dt>
      <dd>
        {client.contact} (<a href={`mailto:${client.email}`}>{client.email}</a>)
      </dd>
      <dt>Assets under management</dt>
      <dd>{formatCurrency(client.aum)}</dd>
      <dt>Last activity</dt>
      <dd>{formatDateTime(client.lastActivity)} UTC</dd>
      <dt>Notes</dt>
      <dd>{client.notes}</dd>
    </dl>
  );
}

export function ClientDrawer({ clientId, onClose }: ClientDrawerProps) {
  const state = useAsync(() => fetchClient(clientId), [clientId]);
  const { data } = state;

  return (
    <Drawer label="Client details" title={data ? data.name : "Client"} onClose={onClose} closeLabel="Close details">
      <AsyncContent state={state} loadingLabel="Loading client">
        {(client) => (
          <Tabs
            label="Client sections"
            tabs={[
              { id: "details", label: "Details", render: () => <Details client={client} /> },
              { id: "notes", label: "Notes", render: () => <ClientNotes key={client.id} clientId={client.id} /> },
            ]}
          />
        )}
      </AsyncContent>
    </Drawer>
  );
}
