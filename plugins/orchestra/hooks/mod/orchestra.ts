import type { Hook, On, Register } from 'claude-code';

import { AUTONOMY_COMMAND, cliResult, cliThrown, commandOutcome, newAutonomy, noteChange, pollDue, pollOutcome, startSession, subOf, USAGE } from './autonomy.js';
import type { AutonomyState, Cli, Sub } from './autonomy.js';
import { classifyCommand, editDenied, editTools, klassOf, loadRules, shellTools } from './guard.js';
import { fromBase64, GUARD_DIGEST_FILES, guardDigest, HEARTBEAT_MS, markerJson, markerPath, sha256Hex, utf8 } from './marker.js';

// SPEC 10.3 to 10.5. One closure per process: the marker tick, the TypeScript guard, offers, standing
// orders, the board and verdict toasts. The Python hook stays the authority for release, release-multi
// and boundary commands; this module delegates them and fails closed.
//
// Autonomy (SPEC 12.7): `autonomy.ts` holds the pure logic. The engine's module validator follows `$` only
// into a function declared in the same file, so the `$` calls for it are the autonomy* functions below.

const DELEGATED = ['release', 'release-multi', 'boundary'];
// SPEC 10.3: the tools the mod guards; known without loaded rules, so a not-ready guard still delegates them (O24).
const GUARDED = ['Bash', 'Edit', 'Write', 'MultiEdit'];
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

/** The first two words after `orchestra.py`, skipping `--opt [value]` tokens. */
function subWords(command: string): string[] {
  const words = command.split(/\s+/).filter((w) => w !== '');
  const at = words.findIndex((w) => w.endsWith('orchestra.py'));
  const found: string[] = [];
  if (at < 0) return found;
  for (let i = at + 1; i < words.length && found.length < 2; i++) {
    const w = words[i]!;
    if (w.startsWith('--')) {
      if (!w.includes('=') && i + 1 < words.length && !words[i + 1]!.startsWith('-')) i++;
      continue;
    }
    found.push(w);
  }
  return found;
}

/** The first of review, gate or accept after `orchestra.py`. */
function verdictSub(command: string): string | null {
  const first = subWords(command)[0];
  return first !== undefined && VERDICT_SUBS.includes(first) ? first : null;
}

/** True for `orchestra.py ... autonomy arm`: the documented way to arm a run (SPEC 12.1). */
function armsAutonomy(command: string): boolean {
  const words = subWords(command);
  return words[0] === 'autonomy' && words[1] === 'arm';
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

async function delegate($: Dollar, tool: string, toolInput: Json, sessionId: string): Promise<string | null> {
  const cwd = await $.session.cwd();
  const payload = JSON.stringify({ tool_name: tool, tool_input: toolInput, cwd, session_id: sessionId });
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

async function autonomyCli($: Dollar, sub: Sub): Promise<Cli> {
  try {
    const cwd = await $.session.cwd();
    const run = await runHook($, ['--cli', 'autonomy', sub], undefined, cwd);
    return cliResult(run.exitCode, run.stdout, run.stderr);
  } catch (error) {
    return cliThrown(error);
  }
}

function autonomyBand($: Dollar, auto: AutonomyState, text: string | undefined): void {
  if (text === undefined && !auto.band) return;
  try {
    $.ui.status(text);
    auto.band = text !== undefined;
  } catch {
    // The band is a convenience (SPEC 10.2): a missing or failing API skips it.
  }
}

async function autonomyRegister($: Dollar, auto: AutonomyState): Promise<void> {
  if (auto.registered) return;
  auto.registered = true;
  try {
    await $.command.register({ name: AUTONOMY_COMMAND, description: 'Arm, disarm or show the Orchestra autonomous loop', argumentHint: 'on|off|status' });
  } catch {
    auto.registered = false;
  }
}

async function autonomyCommand($: Dollar, auto: AutonomyState, args: string): Promise<{ text: string }> {
  try {
    const sub = subOf(args);
    if (sub === null) return { text: USAGE };
    // Status reads that started before this command ended are stale: noteChange drops them.
    noteChange(auto, false);
    const res = await autonomyCli($, sub);
    noteChange(auto, false);
    const out = commandOutcome(auto, sub, res);
    if (out.band !== undefined) autonomyBand($, auto, out.band.text);
    return { text: out.text };
  } catch (error) {
    return { text: `Orchestra autonomy: ${String(error instanceof Error ? error.message : error)}` };
  }
}

/** One step of the existing tick: reads status at most every 30 s while active; never throws. */
async function autonomyPoll($: Dollar, auto: AutonomyState): Promise<void> {
  if ((!auto.active && !auto.unknown) || auto.busy) return;
  const epoch = auto.epoch;
  const changes = auto.changes;
  auto.busy = true;
  try {
    const now = await $.clock.now();
    if (epoch !== auto.epoch || !pollDue(auto, now)) return;
    const res = await autonomyCli($, 'status');
    if (epoch !== auto.epoch || changes !== auto.changes) return;
    const out = pollOutcome(auto, res);
    if (!out.changed) return;
    autonomyBand($, auto, out.band);
    if (out.toast !== null) $.ui.toast(out.toast);
  } catch {
    // A failed read is retried at the next interval; a tick never throws.
  } finally {
    if (epoch === auto.epoch) auto.busy = false;
  }
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
  let rawXdg: string | undefined;
  let xdg: string | undefined;
  let home: string | undefined;
  let starting: Promise<void> | null = null;
  let where: Where | null = null;
  let boardRegistered = false;
  let boardTimer: { cancel: () => void } | null = null;
  let boardStatus: Json | null = null;
  const auto = newAutonomy();
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
    // R5 finding 2: the generation is taken before any await, so of overlapping starts only the last runs on.
    cancelTick();
    const mine = gen;
    guardReady = false;
    where = null;
    const prevSeen = lastSeen;
    const prevWriters = writers;
    let done: () => void = () => undefined;
    const settled = new Promise<void>((resolve) => (done = resolve));
    starting = settled;
    // R5 finding 1: the guard is not ready from here on, so no fresh marker of the last session may stay.
    const zeroPrev = async (): Promise<void> => {
      if (prevWriters === null || prevSeen === null) return;
      await Promise.race([enqueue(prevWriters.zero(prevSeen)), $.clock.sleep(2000)]);
    };
    let ready = false;
    try {
      ready = await (async (): Promise<boolean> => {
        await zeroPrev();
        const x = await $.env.get('XDG_STATE_HOME');
        const h = await $.env.get('HOME');
        const envXdg = x ? x : undefined;
        const envHome = h ? h : undefined;
        if (mine !== gen) return false;
        rawXdg = envXdg;
        xdg = envXdg && envXdg.startsWith('/') ? envXdg : undefined;
        home = envHome && envHome.startsWith('/') ? envHome : undefined;
        if (xdg === undefined && home === undefined) return false;
        const root = $.plugin.root;
        const rules = await $.fs.read(`${root}/config/guard-rules.json`);
        const pluginJson = await $.fs.read(`${root}/.claude-plugin/plugin.json`);
        const contents: (Uint8Array | null)[] = [];
        for (const rel of GUARD_DIGEST_FILES) {
          try {
            const bytes = await $.fs.read(`${root}/${rel}`, { as: 'bytes' });
            contents.push(fromBase64(bytes.base64));
          } catch {
            contents.push(null);
          }
        }
        if (mine !== gen) return false;
        loadRules(rules);
        const ver = String(asJson(pluginJson)?.['version'] ?? '');
        const dig = guardDigest(contents);
        version = ver;
        digest = dig;
        const sx = xdg;
        const sh = home;
        const id = await $.session.id();
        if (mine !== gen) return false;
        guardReady = true;
        retired.delete(id);
        lastSeen = id;
        const write = async (sid: string, heartbeat: number): Promise<void> => {
          const path = markerPath(sx, sh, sid);
          if (path !== null) await $.fs.write(path, markerJson(sid, ver, dig, heartbeat));
        };
        const fresh = (sid: string) => async (): Promise<void> => {
          const now = await $.clock.now();
          if (retired.has(sid)) return;
          await write(sid, now);
        };
        const zero = (sid: string) => async (): Promise<void> => {
          await write(sid, 0);
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
            // SPEC 12.7: the autonomy read rides this tick (no second timer) and never blocks the marker.
            void autonomyPoll($, auto);
          });
        }
        return true;
      })();
    } catch {
      // No guard and no fresh marker: Python covers the session.
      if (mine === gen) {
        cancelTick();
        guardReady = false;
        const w = writers;
        const sid = lastSeen;
        if (w !== null && sid !== null) await Promise.race([enqueue(w.zero(sid)), $.clock.sleep(2000)]).catch(() => undefined);
      }
    } finally {
      done();
      if (starting === settled) starting = null;
    }
    try {
      if (ready && !boardRegistered) {
        boardRegistered = true;
        await $.command.register({ name: BOARD, description: 'Show the Orchestra board: cards, session and autonomy' });
      }
    } catch {
      // The board is a convenience; it never takes the guard down.
    }
    try {
      startSession(auto);
      autonomyBand($, auto, undefined);
      await autonomyRegister($, auto);
    } catch {
      // Autonomy UI is a convenience; it never takes the guard down.
    }
    return next(e);
  });

  on('session.end', async ($, e, next) => {
    const reason: string = e.reason;
    if (reason !== 'clear' && reason !== 'resume') cancelTick();
    try {
      if (reason !== 'clear' && reason !== 'resume') {
        auto.active = false;
        autonomyBand($, auto, undefined);
      }
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
    // A start in flight first zeroes the last marker or makes the guard ready (R5 finding 1).
    while (starting !== null) await starting;
    const input = e as unknown as Json;
    const tool = String(input['tool']);
    if (!guardReady) {
      // O24: no loaded guard, so Python decides with `--from-mod` (full guard, no marker skip).
      if (!GUARDED.includes(tool) && !shellTools().includes(tool) && !editTools().includes(tool)) return next(e);
      const toolInput: Json = { ...input };
      delete toolInput['tool'];
      delete toolInput['tool_use_id'];
      delete toolInput['consent'];
      const reason = await delegate($, tool, toolInput, lastSeen ?? '');
      if (reason !== null) return { deny: reason };
      return next(e);
    }
    if (shellTools().includes(tool)) {
      const raw = input['command'] !== undefined ? input['command'] : input['cmd'];
      if (raw === undefined || Object(raw).constructor !== String) return { deny: 'Missing shell command' };
      const command = String(raw);
      const d = classifyCommand(command);
      const klass = klassOf(d);
      if (klass === 'deny') return { deny: d.reason !== '' ? d.reason : FAIL_CLOSED };
      if (DELEGATED.includes(klass)) {
        const sid = lastSeen ?? '';
        const reason = await delegate($, tool, { command }, sid);
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
      try {
        // SPEC 12.1: a run armed through Bash is not seen by the command path; the next tick reads status.
        if (armsAutonomy(command)) noteChange(auto, true);
      } catch {
        // Autonomy UI never changes the tool's answer.
      }
      return result;
    }
    if (editTools().includes(tool)) {
      const target = input['file_path'] !== undefined ? input['file_path'] : input['path'];
      const cwd = await $.session.cwd();
      const stateDir = await $.env.get('ORCHESTRA_STATE_DIR');
      const path = target === undefined ? undefined : String(target);
      const sd = stateDir ? stateDir : null;
      // Both the base Python reads (XDG_STATE_HOME as given) and the marker base are protected.
      const denied = editDenied(path, cwd, { stateDir: sd, xdg: rawXdg, home }) || (rawXdg !== xdg && editDenied(path, cwd, { stateDir: sd, xdg, home }));
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
      // O21: only a result with standing orders is cached; session.start clears it.
      if (where === null || !where.standingOrders) where = await readWhere($);
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

  on('command.run', { command: AUTONOMY_COMMAND }, async ($, e) => autonomyCommand($, auto, e.args));

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
    let running = 0;
    const tasks = asJson(JSON.stringify(status['tasks'] ?? {})) ?? {};
    for (const id of Object.keys(tasks)) {
      const t = asJson(JSON.stringify(tasks[id])) ?? {};
      if (t['state'] === 'running') running += 1;
      rows.push(`${id}  ${String(t['role'] ?? '-')}  ${String(t['mode'] ?? '-')}  ${String(t['state'] ?? '-')}  ${String(t['worker'] ?? '-')}`);
    }
    // The engine's own flags: session.active and autonomy.active (null or absent reads as off).
    const session = asJson(JSON.stringify(status['session'] ?? null));
    const autonomy = asJson(JSON.stringify(status['autonomy'] ?? null));
    const lines = [
      `Session: ${session !== null && session['active'] === true ? 'active' : 'inactive'}`,
      `Autonomy: ${autonomy !== null && autonomy['active'] === true ? 'on' : 'off'}`,
      `Running cards: ${running}`,
      `Cards: ${rows.length}`,
      ...rows,
    ];
    return Box({ flexDirection: 'column', children: lines.map((line) => Text({ children: line })) });
  });
};
