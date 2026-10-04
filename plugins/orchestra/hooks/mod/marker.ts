// Pure helpers only: the engine's validator never follows `$` across an import.

export const HEARTBEAT_MS = 5000;

export type Marker = {
  session_id: string;
  heartbeat_ms: number;
  plugin_version: string;
  rules_sha256: string | null;
};

/** ${XDG_STATE_HOME:-$HOME/.local/state}/orchestra/mods/<session_id>.json */
export function markerPath(xdg: string | undefined, home: string | undefined, sessionId: string): string {
  const base = xdg ? xdg : `${home}/.local/state`;
  return `${base}/orchestra/mods/${sessionId}.json`;
}

export function markerJson(sessionId: string, version: string, rules: string | null, heartbeat: number): string {
  const marker: Marker = {
    session_id: sessionId,
    heartbeat_ms: heartbeat,
    plugin_version: version,
    rules_sha256: rules,
  };
  return JSON.stringify(marker);
}
