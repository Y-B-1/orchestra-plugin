import type { On, Register } from 'claude-code';

import { HEARTBEAT_MS, markerJson, markerPath } from './marker.js';

// Thin slice: liveness marker only. No guard; a null rules_sha256 never
// matches the Python table, so the classic hook keeps guarding.
// SPEC 10.2 fallback: the validator rejects a typeof presence check, so API
// presence rests on load-time validation (a drifted API fails the module at
// load and leaves no marker).
export const register: Register = (on: On) => {
  let current: string | null = null;
  let cancel: (() => void) | null = null;
  let version = '';

  on('session.start', async ($, e, next) => {
    try {
      version = JSON.parse(await $.fs.read(`${$.plugin.root}/.claude-plugin/plugin.json`)).version;
      current = await $.session.id();
      const xdg = await $.env.get('XDG_STATE_HOME');
      const home = await $.env.get('HOME');
      await $.fs.write(markerPath(xdg, home, current), markerJson(current, version, null, Date.now()));
      cancel = $.clock.every(HEARTBEAT_MS, async () => {
        const id = await $.session.id();
        if (current !== null && id !== current) {
          await $.fs.write(markerPath(xdg, home, current), markerJson(current, version, null, 0));
          current = id;
        }
        await $.fs.write(markerPath(xdg, home, id), markerJson(id, version, null, Date.now()));
      });
    } catch {
      // Marker unavailable: Python covers the session.
    }
    return next(e);
  });

  on('session.end', async ($, e, next) => {
    if (cancel) cancel();
    cancel = null;
    if (current !== null) {
      try {
        const xdg = await $.env.get('XDG_STATE_HOME');
        const home = await $.env.get('HOME');
        await $.fs.write(markerPath(xdg, home, current), markerJson(current, version, null, 0));
      } catch {
        // A stale marker is treated as dead by Python.
      }
    }
    return next(e);
  });
};
