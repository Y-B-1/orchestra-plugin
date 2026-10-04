// Shared rig for the module tests. Not a test file and not loaded by the plugin.
//
// The test's own hooks sit beneath the real module, so every `$` operation the module makes needs an
// answer here: file reads of the plugin root, file writes, the session id, process runs, toasts.
import { mock } from 'claude-code/testing';
import type { On } from 'claude-code';

import { RULES_JSON } from './fixtures/guard-fixtures.js';
import { guardDigest } from './marker.js';

export const encode = (s: string): Uint8Array => Uint8Array.from(Array.from(unescape(encodeURIComponent(s))).map((c) => c.charCodeAt(0)));

const BASE64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
export function toBase64(bytes: Uint8Array): string {
  let out = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const n = (bytes[i]! << 16) | ((bytes[i + 1] ?? 0) << 8) | (bytes[i + 2] ?? 0);
    out += BASE64[(n >> 18) & 63]! + BASE64[(n >> 12) & 63]!;
    out += i + 1 < bytes.length ? BASE64[(n >> 6) & 63]! : '=';
    out += i + 2 < bytes.length ? BASE64[n & 63]! : '=';
  }
  return out;
}

/** The plugin-root files the module reads, as the rig serves them (by path suffix). */
export const ROOT_FILES: Record<string, string | null> = {
  '.claude-plugin/plugin.json': JSON.stringify({ name: 'orchestra', version: '2.0.0' }),
  'config/guard-rules.json': RULES_JSON,
  'scripts/orchestra_core/guards.py': 'guards = 1\n',
  'scripts/orchestra_core/hooks.py': 'hooks = 1\n',
  'hooks/mod/guard.ts': 'export {}\n',
};

export const EXPECTED_DIGEST = guardDigest(
  ['config/guard-rules.json', 'scripts/orchestra_core/guards.py', 'scripts/orchestra_core/hooks.py', 'hooks/mod/guard.ts'].map((rel) => {
    const text = ROOT_FILES[rel];
    return text === null || text === undefined ? null : encode(text);
  }),
);

export type Written = { path: string; json: { session_id: string; heartbeat_ms: number; plugin_version: string; rules_sha256: string | null } };
export type Ran = { argv: readonly string[]; init?: { stdin?: string; cwd?: string } };
export type RunAnswer = { exitCode: number; stdout: string; stderr?: string };

export type RigOptions = {
  now?: number;
  env?: Record<string, string>;
  id?: string;
  files?: Record<string, string | null>;
  cwd?: string;
  /**
   * Answer `clock.now` and the waits from a small clock of this file's own instead of `mock.clock`, so
   * `nowGate` can hold the time late. `mock.clock` owns `clock.now` and always answers it at once.
   */
  lateClock?: boolean;
};

type TestClock = Pick<ReturnType<typeof mock.clock>, 'now' | 'advance' | 'settle'>;

const settled = async (): Promise<void> => {
  for (let k = 0; k < 25; k++) await new Promise<void>((resolve) => setTimeout(resolve, 0));
};

function miniClock(on: On, start: number, gate: () => Promise<void> | null): TestClock {
  let now = start;
  const timers: { due: number; resolve: () => void }[] = [];
  const wait = async (_$: unknown, e: { ms: number }) => {
    await new Promise<void>((resolve) => timers.push({ due: now + Math.max(e.ms, 0), resolve }));
    return { value: undefined } as never;
  };
  on('clock.now', async () => {
    const held = gate();
    if (held) await held;
    return { value: now };
  });
  on('clock.sleep', wait as never);
  on('clock.after', wait as never);
  on('clock.every', wait as never);
  const advance = async (ms: number): Promise<void> => {
    const target = now + ms;
    for (;;) {
      timers.sort((a, b) => a.due - b.due);
      const next = timers[0];
      if (!next || next.due > target) break;
      timers.shift();
      now = Math.max(now, next.due);
      next.resolve();
      await settled();
    }
    now = target;
    await settled();
  };
  return { now: () => now, advance, settle: () => advance(0) };
}

export type Rig = {
  clock: TestClock;
  id: string;
  /** Writes that completed, in order. */
  writes: Written[];
  /** Every write the module started, in order, completed or not. */
  started: Written[];
  /** A hook run before each write completes; reject to fail the write, wait to hold it. */
  beforeWrite: ((w: Written) => Promise<void>) | null;
  /** Awaited by `session.id()` before it answers: holds the id late. */
  idGate: Promise<void> | null;
  /** Awaited by `clock.now()` before it answers: holds the time late. */
  nowGate: Promise<void> | null;
  runs: Ran[];
  /** Answers a process run; default is an allow. */
  runAnswer: (argv: readonly string[], init?: Ran['init']) => RunAnswer | Promise<RunAnswer>;
  toasts: string[];
  /** Stdout of the tool result the bottom tool.call hook returns. */
  toolStdout: string;
  files: Record<string, string | null>;
  /** The marker writes for one id, oldest first. */
  of: (id: string) => Written[];
};

export function rig(on: On, options: RigOptions = {}): Rig {
  const env = options.env ?? { XDG_STATE_HOME: '/state', HOME: '/home/x' };
  mock.env(on, env);
  const state: Rig = {
    clock: undefined as never,
    id: options.id ?? 'sid-1',
    writes: [],
    started: [],
    beforeWrite: null,
    idGate: null,
    nowGate: null,
    runs: [],
    runAnswer: () => ({ exitCode: 0, stdout: '{}' }),
    toasts: [],
    toolStdout: '',
    files: { ...ROOT_FILES, ...(options.files ?? {}) },
    of: (id) => state.writes.filter((w) => w.json.session_id === id),
  };
  const clock = options.lateClock ? miniClock(on, options.now ?? 1000, () => state.nowGate) : mock.clock(on, { now: options.now ?? 1000 });
  state.clock = clock;
  on('session.start', async (_$, e) => ({ cwd: e.cwd }));
  on('session.end', async (_$, e) => ({ sessionId: e.sessionId }));
  on('session.id', async () => {
    if (state.idGate) await state.idGate;
    return { value: state.id };
  });
  on('session.cwd', async () => ({ value: options.cwd ?? '/work/proj' }));
  on('fs.read', async (_$, e) => {
    const rel = Object.keys(state.files).find((key) => (e.path === key || e.path.endsWith('/' + key)));
    if (rel === undefined) return { deny: 'ENOENT ' + e.path };
    const text = state.files[rel];
    if (text === null || text === undefined) return { deny: 'ENOENT ' + e.path };
    return { value: e.as === 'bytes' ? { base64: toBase64(encode(text)) } : text };
  });
  on('fs.write', async (_$, e) => {
    const written: Written = { path: e.path, json: JSON.parse(e.text) };
    state.started.push(written);
    if (state.beforeWrite) await state.beforeWrite(written);
    state.writes.push(written);
    return { value: undefined };
  });
  on('process.run', async (_$, e) => {
    state.runs.push({ argv: e.argv, init: e.init as Ran['init'] });
    const answer = await state.runAnswer(e.argv, e.init as Ran['init']);
    return { value: { exitCode: answer.exitCode, stdout: answer.stdout, stderr: answer.stderr ?? '', isStdoutTruncated: false, isStderrTruncated: false } };
  });
  on('ui.toast', async (_$, e) => {
    state.toasts.push(e.text);
    return { value: undefined };
  });
  return state;
}

export function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve: () => void = () => undefined;
  const promise = new Promise<void>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
