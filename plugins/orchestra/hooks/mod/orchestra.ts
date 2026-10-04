import type { Hook, On, Register } from 'claude-code';

import { classifyCommand, editDenied, editTools, klassOf, loadRules, shellTools } from './guard.js';
import { fromBase64, GUARD_DIGEST_FILES, guardDigest, HEARTBEAT_MS, markerJson, markerPath, sha256Hex, utf8 } from './marker.js';

// SPEC 10.3 to 10.5. One closure per process: the marker tick, the TypeScript guard, offers, standing
// orders, the board and verdict toasts. The Python hook stays the authority for release, release-multi
// and boundary commands; this module delegates them and fails closed.
//
// Autonomy (B11) is not here. Its seam: a later card adds `autonomy.ts` and calls it from the
// `session.start` and `session.end` handlers below, at the marked comments.

const DELEGATED = ['release', 'release-multi', 'boundary'];
const FAIL_CLOSED = 'Orchestra guard error; failing closed';
const STATE_DENY = 'Use the structured coordinator API for state; protect installed runtime configuration';
const VERDICT_SUBS = ['review', 'gate', 'accept'];
const BOARD = 'orchestra-board';

type Json = Record<string, unknown>;

function asJson(text: string): Json | null {
  try {
    const v: unknown = JSON.parse(text);
    return v !== null && !Array.isArray(v) && Object(v) === v ? (v as Json) : null;
  } catch {
    return null;
  }
}

/** The first of review, gate or accept after `orchestra.py`, skipping `--opt [value]` tokens. */
function verdictSub(command: string): string | null {
  const words = command.split(/\s+/).filter((w) => w !== '');
  const at = words.findIndex((w) => w.endsWith('orchestra.py'));
  if (at < 0) return null;
  for (let i = at + 1; i < words.length; i++) {
    const w = words[i]!;
    if (w.startsWith('--')) {
      if (!w.includes('=') && i + 1 < words.length && !words[i + 1]!.startsWith('-')) i++;
      continue;
    }
    return VERDICT_SUBS.includes(w) ? w : null;
  }
  return null;
}

function toastText(sub: string, out: string): string | null {
  const body = asJson(out);
  if (body === null) return null;
  if (body['verdict'] !== undefined && String(Object(body['verdict']).constructor === String) === 'true') return `Orchestra ${sub}: ${String(body['verdict'])}`;
  const code = body['exit_code'];
  if (code !== undefined && Object(code).constructor === Number) return `Orchestra ${sub}: exit ${String(code)}`;
  return null;
}

type Dollar = Parameters<Hook<'tool.call'>>[0];
type Where = { repo: string; state: string; standingOrders: boolean };

async function runHook($: Dollar, args: string[], stdin: string | undefined, cwd: string | undefined) {
  return $.process.run(['/bin/sh', `${$.plugin.root}/scripts/run-hook.sh`, ...args], { stdin, cwd, timeoutMs: 8000 });
}

async function delegate($: Dollar, tool: string, command: string, sessionId: string): Promise<string | null> {
  const cwd = await $.session.cwd();
  const payload = JSON.stringify({ tool_name: tool, tool_input: { command }, cwd, session_id: sessionId });
  const run = await runHook($, ['PreToolUse', '--harness', 'claude', '--from-mod'], payload, cwd);
  if (run.exitCode !== 0) return FAIL_CLOSED;
  const out = asJson(run.stdout);
  if (out === null) return FAIL_CLOSED;
  const hso = out['hookSpecificOutput'];
  if (hso === undefined) return null;
  const spec = asJson(JSON.stringify(hso));
  if (spec === null) return FAIL_CLOSED;
  if (spec['permissionDecision'] === 'deny') return String(spec['permissionDecisionReason'] ?? FAIL_CLOSED);
  return null;
}

async function readWhere($: Dollar): Promise<Where | null> {
  const cwd = await $.session.cwd();
  const run = await runHook($, ['--cli', 'where'], undefined, cwd);
  const body = run.exitCode === 0 ? asJson(run.stdout) : null;
  if (body === null) return null;
  return { repo: String(body['repo'] ?? ''), state: String(body['state'] ?? ''), standingOrders: body['standing_orders'] === true };
}

export const register: Register = (on: On) => {
  let tick: { cancel: () => void } | null = null;
  let gen = 0;
  let guardReady = false;
  let lastSeen: string | null = null;
  const retired = new Set<string>();
  let queue: Promise<void> = Promise.resolve();
  let digest: string | null = null;
  let version = '';
  let xdg: string | undefined;
  let home: string | undefined;
  let where: Where | null = null;
  let boardRegistered = false;
  let boardTimer: { cancel: () => void } | null = null;
  let boardStatus: Json | null = null;
  let writers: { fresh: (sid: string) => () => Promise<void>; zero: (sid: string) => () => Promise<void> } | null = null;

  const enqueue = (job: () => Promise<void>): Promise<void> => {
    queue = queue.then(job).catch(() => undefined);
    return queue;
  };

  const cancelTick = (): void => {
    gen += 1;
    if (tick) tick.cancel();
    tick = null;
  };

  on('session.start', async ($, e, next) => {
    cancelTick();
    guardReady = false;
    where = null;
    try {
      const x = await $.env.get('XDG_STATE_HOME');
      const h = await $.env.get('HOME');
      xdg = x ? x : undefined;
      home = h ? h : undefined;
      if (xdg === undefined && home === undefined) return next(e);
      const root = $.plugin.root;
      loadRules(await $.fs.read(`${root}/config/guard-rules.json`));
      version = String(asJson(await $.fs.read(`${root}/.claude-plugin/plugin.json`))?.['version'] ?? '');
      const contents: (Uint8Array | null)[] = [];
      for (const rel of GUARD_DIGEST_FILES) {
        try {
          const bytes = await $.fs.read(`${root}/${rel}`, { as: 'bytes' });
          contents.push(fromBase64(bytes.base64));
        } catch {
          contents.push(null);
        }
      }
      digest = guardDigest(contents);
      guardReady = true;

      const mine = gen;
      const id = await $.session.id();
      retired.delete(id);
      lastSeen = id;
      const fresh = (sid: string) => async (): Promise<void> => {
        const now = await $.clock.now();
        if (retired.has(sid)) return;
        await $.fs.write(markerPath(xdg, home, sid), markerJson(sid, version, digest, now));
      };
      const zero = (sid: string) => async (): Promise<void> => {
        await $.fs.write(markerPath(xdg, home, sid), markerJson(sid, version, digest, 0));
      };
      writers = { fresh, zero };
      await Promise.race([enqueue(fresh(id)), $.clock.sleep(2000)]);
      if (mine === gen) {
        tick = $.clock.every(HEARTBEAT_MS, async () => {
          let current: string;
          try {
            current = await $.session.id();
          } catch {
            return;
          }
          if (mine !== gen || lastSeen === null) return;
          if (current !== lastSeen) {
            const old = lastSeen;
            retired.add(old);
            enqueue(zero(old));
            retired.delete(current);
            lastSeen = current;
          }
          enqueue(fresh(current));
        });
      }
      if (!boardRegistered) {
        boardRegistered = true;
        await $.command.register({ name: BOARD, description: 'Show the Orchestra board: cards, session and autonomy' });
      }
      // B11 seam: autonomy startup goes here (autonomy.ts is owned by that card).
    } catch {
      // No guard and no marker: Python covers the session.
    }
    return next(e);
  });

  on('session.end', async ($, e, next) => {
    const reason: string = e.reason;
    if (reason !== 'clear' && reason !== 'resume') cancelTick();
    try {
      // B11 seam: autonomy shutdown goes here.
      const sid = e.sessionId ? e.sessionId : lastSeen;
      if (sid && writers) {
        retired.add(sid);
        const job = enqueue(writers.zero(sid));
        const budget = next.budget.remainingMs;
        const wait = Math.max(0, Math.min(2000, budget - 1000));
        await Promise.race([job, $.clock.sleep(wait)]);
      }
    } catch {
      // A stale marker is treated as dead by Python.
    }
    return next(e);
  });

  on('tool.call', async ($, e, next) => {
    if (!guardReady) return next(e);
    const input = e as unknown as Json;
    const tool = String(input['tool']);
    if (shellTools().includes(tool)) {
      const raw = input['command'] !== undefined ? input['command'] : input['cmd'];
      if (raw === undefined || Object(raw).constructor !== String) return { deny: 'Missing shell command' };
      const command = String(raw);
      const d = classifyCommand(command);
      const klass = klassOf(d);
      if (klass === 'deny') return { deny: d.reason !== '' ? d.reason : FAIL_CLOSED };
      if (DELEGATED.includes(klass)) {
        const sid = lastSeen ?? '';
        const reason = await delegate($, tool, command, sid);
        if (reason !== null) return { deny: reason };
      }
      const result = await next(e);
      try {
        const sub = verdictSub(command);
        const out = (result as { result?: { stdout?: string } }).result?.stdout;
        if (sub !== null && out !== undefined) {
          const text = toastText(sub, String(out));
          if (text !== null) $.ui.toast(text);
        }
      } catch {
        // A toast never changes the tool's answer.
      }
      return result;
    }
    if (editTools().includes(tool)) {
      const target = input['file_path'] !== undefined ? input['file_path'] : input['path'];
      const cwd = await $.session.cwd();
      const stateDir = await $.env.get('ORCHESTRA_STATE_DIR');
      const denied = editDenied(target === undefined ? undefined : String(target), cwd, { stateDir: stateDir ? stateDir : null, xdg, home });
      if (denied) return { deny: STATE_DENY };
    }
    return next(e);
  }).catch(async (_$, e, next) => {
    if (next.called) return next(e);
    return { deny: FAIL_CLOSED };
  });

  on('agent.offer', async (_$, e, next) => {
    if (e.agent === 'orchestra:orchestrator') return { isOffered: false };
    return next(e);
  });

  on('agent.spawn', async ($, e, next) => {
    if (!e.subagentType.startsWith('orchestra:')) return next(e);
    try {
      if (where === null) where = await readWhere($);
      const w = where;
      if (w !== null && w.standingOrders && w.state !== '') {
        const text = await $.fs.read(`${w.state}/standing-orders.md`);
        const sha = sha256Hex(utf8(text));
        if (!e.prompt.includes(`sha256: ${sha}`)) {
          return next({ ...e, prompt: `${e.prompt}\n\n## Standing orders (verbatim)\n\n${text}\n\nsha256: ${sha}\n` });
        }
      }
    } catch {
      // Standing orders unavailable: the spawn still goes ahead.
    }
    return next(e);
  });

  on('command.run', { command: BOARD }, async ($) => {
    try {
      await $.ui.open({ id: BOARD, title: 'Orchestra board', focus: true });
      const refresh = async (): Promise<void> => {
        const cwd = await $.session.cwd();
        const run = await runHook($, ['--cli', 'status'], undefined, cwd);
        boardStatus = run.exitCode === 0 ? asJson(run.stdout) : null;
        $.ui.invalidate('ui.render');
      };
      await refresh();
      if (boardTimer) boardTimer.cancel();
      boardTimer = $.clock.every(HEARTBEAT_MS, refresh);
    } catch {
      // The board is a convenience; a failure leaves the pane as it was.
    }
    return {};
  });

  on('ui.close', { id: BOARD }, async (_$, e, next) => {
    const result = await next(e);
    if (boardTimer) boardTimer.cancel();
    boardTimer = null;
    return result;
  });

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== BOARD) return next(e);
    const { Box, Text } = $.ui.resolve(e);
    const status = boardStatus;
    if (status === null) return Box({ children: [Text({ children: 'Orchestra: no status yet' })] });
    const rows: string[] = [];
    const tasks = asJson(JSON.stringify(status['tasks'] ?? {})) ?? {};
    for (const id of Object.keys(tasks)) {
      const t = asJson(JSON.stringify(tasks[id])) ?? {};
      rows.push(`${id}  ${String(t['role'] ?? '-')}  ${String(t['mode'] ?? '-')}  ${String(t['state'] ?? '-')}  ${String(t['worker'] ?? '-')}`);
    }
    const session = status['session'];
    const autonomy = asJson(JSON.stringify(status['autonomy'] ?? {}));
    const lines = [
      `Session: ${session === null || session === undefined ? 'inactive' : 'active'}`,
      `Autonomy: ${autonomy === null ? 'off' : String(autonomy['mode'] ?? autonomy['state'] ?? 'set')}`,
      `Cards: ${rows.length}`,
      ...rows,
    ];
    return Box({ flexDirection: 'column', children: lines.map((line) => Text({ children: line })) });
  });
};
