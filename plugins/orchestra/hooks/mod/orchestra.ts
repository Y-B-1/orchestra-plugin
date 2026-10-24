import type { Hook, On, Register } from 'claude-code';

import { AUTONOMY_COMMAND, cliResult, cliThrown, commandOutcome, newAutonomy, noteChange, pollDue, pollOutcome, startSession, subOf, USAGE } from './autonomy.js';
import type { AutonomyState, Cli, Sub } from './autonomy.js';
import { cardIdOf, matchTasks, paneModel, parseTaskList, parseView, planCreates, planUpdates, runShort } from './board.js';
import type { Link, View } from './board.js';
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
const GUARDED = ['Bash', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit'];
// Fallback for an unexpected error whose class is not known; `delegate` names its class with `failClosed`.
const FAIL_CLOSED = 'Orchestra guard error; failing closed';
const MISSING_CWD = 'Session directory no longer exists: cd to an existing directory, then retry';
const STATE_DENY = 'Use the structured coordinator API for state; protect installed runtime configuration';
const VERDICT_SUBS = ['review', 'gate', 'accept'];
const BOARD = 'orchestra-board';
/** The board refreshes on events; this is the fallback while the pane is open. */
const BOARD_FALLBACK_MS = 30000;
const TASK_TOOLS = ['TaskCreate', 'TaskUpdate', 'TaskList'];
/**
 * Guard `minimal`: a shell command that may write Orchestra's engine state, ledger, policy or installed runtime
 * files, or carry the owner's approval word, still goes to the Python hook; every other one is Claude Code's call.
 */
const ENGINE_TOUCH = /orchestra|ORCHESTRA_|\.claude|ledger|state\.json|policy\.json|standing-orders|approv/i;

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

/** True for a shell command that runs `orchestra.py`: the board may have changed. */
function runsEngine(command: unknown): boolean {
  return typeof command === 'string' && /orchestra\.py\b/.test(command);
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
type Where = { repo: string; state: string; standingOrders: boolean; guardMode: string | null };

type Run = Awaited<ReturnType<Dollar['process']['run']>>;

/** A deny that names its source, so the model reads a policy decision, not a tool failure. */
export function blocked(reason: string): { deny: string } {
  return { deny: reason.startsWith('Orchestra') ? reason : `Orchestra guard: ${reason}` };
}

/** SPEC 5.16 item 4: the reason names the one failure class. `detail` is the spawn code or the exit status. */
const MODE_LINE = /^[ \t]*Mode:[ \t]+\S/m;
const BRIEF_PATH = /brief at (\/[^\s`'"]+)/;

/** F23: the brief path an Orchestra spawn names, when neither the prompt nor that readable file has a Mode line. */
export async function briefWithoutMode($: { fs: { read(path: string): Promise<string> } }, prompt: string): Promise<string | null> {
  if (MODE_LINE.test(prompt)) return null;
  const m = BRIEF_PATH.exec(prompt);
  if (m === null) return null;
  const path = m[1]!.replace(/[.,;:)]+$/, '');
  let text: string;
  try {
    text = await $.fs.read(path);
  } catch {
    return null;
  }
  return MODE_LINE.test(text) ? null : path;
}

export function failClosed(kind: 'spawn' | 'exit' | 'timeout' | 'bad output', detail: string): string {
  const named = kind === 'spawn' ? `spawn: ${detail}` : kind === 'exit' ? `exit ${detail}` : kind;
  return `Orchestra guard error (${named}); failing closed`;
}

/** Names the class of an error `process.run` threw: a timeout, or a spawn failure with its code. */
export function thrownReason(error: unknown): string {
  const e = Object(error) as { code?: unknown; message?: unknown };
  const message = typeof e.message === 'string' ? e.message : String(error);
  if (/time(d)?[ -]?out|ETIMEDOUT/i.test(message) || e.code === 'ETIMEDOUT') return failClosed('timeout', '');
  const code = typeof e.code === 'string' && e.code !== '' ? e.code : (/\bE[A-Z0-9]{3,}\b/.exec(message)?.[0] ?? 'UNKNOWN');
  return failClosed('spawn', code);
}

/** A drive-letter or backslash path: the mod's POSIX path rules do not hold there, so it stays inert (Python guards in full). */
export function isWindowsPath(path: string): boolean {
  return /^[A-Za-z]:[\\/]/.test(path) || path.includes('\\');
}

/** SPEC 5.16 item 2: the cwd is explicit; `delegate` passes the plugin root, the CLI reads the session cwd. */
async function runHook($: Dollar, args: string[], stdin: string | undefined, opts: { cwd: string }): Promise<Run> {
  // Git Bash on Windows has no /bin/sh on the native PATH: `sh` is found there, and the script path takes forward slashes.
  const windows = isWindowsPath($.plugin.root);
  const root = windows ? $.plugin.root.replace(/\\/g, '/') : $.plugin.root;
  return $.process.run([windows ? 'sh' : '/bin/sh', `${root}/scripts/run-hook.sh`, ...args], { stdin, cwd: opts.cwd, timeoutMs: 8000 });
}

async function delegate($: Dollar, tool: string, toolInput: Json, sessionId: string): Promise<string | null> {
  let run: Run;
  try {
    // The hook starts from the plugin root, which always exists; the session cwd travels in the payload.
    const cwd = await $.session.cwd();
    const payload = JSON.stringify({ tool_name: tool, tool_input: toolInput, cwd, session_id: sessionId });
    run = await runHook($, ['PreToolUse', '--harness', 'claude', '--from-mod'], payload, { cwd: $.plugin.root });
  } catch (error) {
    return thrownReason(error);
  }
  const out = asJson(run.stdout);
  // Exit 2 is the hook's own deny (a malformed command): surface its reason when one is present (H4).
  if (run.exitCode !== 0 && !(run.exitCode === 2 && out !== null)) return failClosed('exit', String(run.exitCode));
  if (out === null) return failClosed('bad output', '');
  const hso = out['hookSpecificOutput'];
  if (hso === undefined) return run.exitCode === 0 ? null : failClosed('exit', String(run.exitCode));
  const spec = asJson(JSON.stringify(hso));
  if (spec === null) return failClosed('bad output', '');
  if (spec['permissionDecision'] === 'deny') return String(spec['permissionDecisionReason'] ?? failClosed('bad output', ''));
  // `ask` passes on: a tool.call hook cannot prompt, so the native PreToolUse hook, which never skips a release, decides.
  return run.exitCode === 0 ? null : failClosed('exit', String(run.exitCode));
}

/** A CLI read from the session cwd with `--repo <cwd>`; `gone` when that directory no longer exists. */
async function cliRun($: Dollar, args: string[]): Promise<{ run: Run } | { gone: true }> {
  const cwd = await $.session.cwd();
  try {
    return { run: await runHook($, ['--cli', '--repo', cwd, ...args], undefined, { cwd }) };
  } catch (error) {
    let exists = true;
    try {
      const probe = await $.process.run(['/bin/sh', '-c', 'test -d "$1"', 'sh', cwd], { cwd: $.plugin.root, timeoutMs: 8000 });
      exists = probe.exitCode === 0;
    } catch {
      // The probe could not run: report the original failure.
    }
    if (!exists) return { gone: true };
    throw error;
  }
}

async function readWhere($: Dollar): Promise<Where | null> {
  const res = await cliRun($, ['where']);
  if ('gone' in res) return null;
  const body = res.run.exitCode === 0 ? asJson(res.run.stdout) : null;
  if (body === null) return null;
  const mode = body['guard_mode'];
  return { repo: String(body['repo'] ?? ''), state: String(body['state'] ?? ''), standingOrders: body['standing_orders'] === true, guardMode: typeof mode === 'string' ? mode : null };
}

async function autonomyCli($: Dollar, sub: Sub): Promise<Cli> {
  try {
    const res = await cliRun($, ['autonomy', sub]);
    if ('gone' in res) return { ok: false, body: null, error: MISSING_CWD };
    return cliResult(res.run.exitCode, res.run.stdout, res.run.stderr);
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

/** Told of every autonomy CLI answer, so the caller can follow `last_stop_reason`. */
type Seen = (sub: Sub, res: Cli) => void;

async function autonomyCommand($: Dollar, auto: AutonomyState, args: string, seen: Seen): Promise<{ text: string }> {
  try {
    const sub = subOf(args);
    if (sub === null) return { text: USAGE };
    // Status reads that started before this command ended are stale: noteChange drops them.
    noteChange(auto, false);
    const res = await autonomyCli($, sub);
    noteChange(auto, false);
    seen(sub, res);
    const out = commandOutcome(auto, sub, res);
    if (out.band !== undefined) autonomyBand($, auto, out.band.text);
    return { text: out.text };
  } catch (error) {
    return { text: `Orchestra autonomy: ${String(error instanceof Error ? error.message : error)}` };
  }
}

/** One step of the existing tick: reads status at most every 30 s while active, every tick while `watch`; never throws. */
async function autonomyPoll($: Dollar, auto: AutonomyState, seen: Seen, watch: boolean): Promise<void> {
  if ((!auto.active && !auto.unknown && !watch) || auto.busy) return;
  const epoch = auto.epoch;
  const changes = auto.changes;
  auto.busy = true;
  try {
    const now = await $.clock.now();
    if (epoch !== auto.epoch || !pollDue(auto, now, watch)) return;
    const res = await autonomyCli($, 'status');
    if (epoch !== auto.epoch || changes !== auto.changes) return;
    seen('status', res);
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

type Sync = { wanted: boolean; line: string; runId: string; known: Set<string>; dropped: Set<string> };

/** The board's state, owned by the register closure and passed to the `$` functions below. */
type Board = {
  /** The last good `board --view`, when it was read, and since when reads fail (null while they succeed). */
  view: View | null;
  okAt: number | null;
  staleSince: number | null;
  /** The refresh in flight, if any, and whether one more pass is wanted after it. */
  running: Promise<void> | null;
  queued: boolean;
  links: Map<string, Link>;
  agents: Map<string, string>;
  /** Native task mirror: per run, the cards seen with a task and the cards dropped from sync for the rest of the run. */
  sync: Sync;
};

function newBoard(): Board {
  return {
    view: null, okAt: null, staleSince: null, running: null, queued: false, links: new Map(), agents: new Map(),
    sync: { wanted: true, line: 'Native tasks: off (no board read yet)', runId: '', known: new Set(), dropped: new Set() },
  };
}

/** One task sync against the view just read. Never throws; never asks: a verdict other than allow keeps it off. */
async function syncTasks($: Dollar, sync: Sync, view: View): Promise<void> {
  const off = (why: string): void => {
    sync.line = `Native tasks: off (${why})`;
  };
  try {
    if (!sync.wanted) return off('turned off');
    if (!view.sessionActive || view.runId === '') return off('no active run');
    if (!view.bound) return off('this session does not own the run');
    const names = (await $.tool.list()).map((t) => t.name);
    if (!TASK_TOOLS.every((n) => names.includes(n))) return off('task tools unavailable');
    // Every task tool must pass without a dialog: `$.tool.call` runs the permission check, which can ask.
    const probes: [string, Json][] = [
      ['TaskCreate', { subject: `[${runShort(view.runId)}] probe`, description: 'Orchestra board probe' }],
      ['TaskUpdate', { taskId: 'probe' }],
      ['TaskList', {}],
    ];
    for (const [tool, input] of probes) {
      const probe = await $.tool.check({ tool, input });
      if (probe.decision !== 'allow') return off(`${tool} is not allowed without asking (${probe.decision})`);
    }
    if (sync.runId !== view.runId) {
      sync.runId = view.runId;
      sync.known = new Set();
      sync.dropped = new Set();
    }
    const listed = parseTaskList((await $.tool.call({ tool: 'TaskList' })).result);
    if (listed === null) return off('TaskList answer unreadable');
    const matched = matchTasks(runShort(view.runId), listed);
    // A task this process saw that is gone was deleted by the person: never re-create it.
    for (const id of sync.known) if (!matched.has(id)) sync.dropped.add(id);
    for (const c of planCreates(view, matched, sync.dropped)) {
      try {
        const made = (await $.tool.call({ tool: 'TaskCreate', subject: c.subject, description: c.description })).result as { task?: { id?: unknown } } | undefined;
        const id = made?.task?.id;
        if (typeof id === 'string' && id !== '') matched.set(c.cardId, { id, subject: c.subject, status: 'pending', blockedBy: [] });
      } catch {
        // Tried again at the next sync.
      }
    }
    for (const id of matched.keys()) sync.known.add(id);
    for (const u of planUpdates(view, matched, sync.dropped)) {
      let ok = false;
      try {
        const res = (await $.tool.call({ tool: 'TaskUpdate', taskId: u.taskId, ...u.fields })).result as { success?: unknown } | undefined;
        ok = res?.success === true;
      } catch {
        ok = false;
      }
      if (!ok) sync.dropped.add(u.cardId);
    }
    sync.line = 'Native tasks: on';
  } catch {
    off('sync failed');
  }
}

async function refreshOnce($: Dollar, board: Board): Promise<void> {
  let sid = '';
  try {
    sid = await $.session.id();
  } catch {
    // Read without a session id: `bound` is then false and sync stays off.
  }
  let view: View | null = null;
  try {
    const res = await cliRun($, ['board', '--view', ...(sid !== '' ? ['--session', sid] : [])]);
    if (!('gone' in res) && res.run.exitCode === 0) view = parseView(res.run.stdout);
  } catch {
    view = null;
  }
  const now = await $.clock.now();
  if (view === null) {
    if (board.staleSince === null) board.staleSince = now;
  } else {
    board.view = view;
    board.okAt = now;
    board.staleSince = null;
  }
  try {
    board.agents = new Map((await $.agent.list()).map((a) => [a.id, a.status]));
  } catch {
    // Agent status is a convenience: the last list stays.
  }
  if (view !== null) await syncTasks($, board.sync, view);
  try {
    $.ui.invalidate('ui.render');
  } catch {
    // No pane drawn: nothing to redraw.
  }
}

/**
 * At most one refresh runs and one waits: a call during a run queues one more pass and settles with that run.
 * Never throws, so a caller may leave it unawaited.
 */
async function refreshBoard($: Dollar, board: Board): Promise<void> {
  if (isWindowsPath($.plugin.root)) return;
  if (board.running !== null) {
    board.queued = true;
    return board.running;
  }
  const run = (async (): Promise<void> => {
    try {
      do {
        board.queued = false;
        await refreshOnce($, board);
      } while (board.queued);
    } catch {
      // A failed read is shown as stale; the next event or the fallback timer tries again.
    } finally {
      board.running = null;
    }
  })();
  board.running = run;
  return run;
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
  const board = newBoard();
  // Guard `minimal` fast path inputs: the policy's mode from `where`, and whether the last status read showed a
  // stopped run (its kept report may hold the unattended lock, which this module cannot see); null is unknown.
  let guardMode: string | null = null;
  let runStopped: boolean | null = null;
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

  const seen = (sub: Sub, res: Cli): void => {
    if (sub !== 'status' || !res.ok || res.body === null) runStopped = null;
    else runStopped = res.body['last_stop_reason'] !== null && res.body['last_stop_reason'] !== undefined;
  };

  const applyWhere = (w: Where | null): void => {
    guardMode = w === null ? null : w.guardMode;
    if (w !== null && w.standingOrders) where = w;
  };

  const cancelBoardTimer = (): void => {
    if (boardTimer) boardTimer.cancel();
    boardTimer = null;
  };

  on('session.start', async ($, e, next) => {
    // R5 finding 2: the generation is taken before any await, so of overlapping starts only the last runs on.
    cancelTick();
    const mine = gen;
    guardReady = false;
    where = null;
    guardMode = null;
    runStopped = null;
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
        const o = await $.env.get('ORCHESTRA_STATE_DIR');
        const envXdg = x ? x : undefined;
        const envHome = h ? h : undefined;
        if (mine !== gen) return false;
        rawXdg = envXdg;
        xdg = envXdg && envXdg.startsWith('/') ? envXdg : undefined;
        home = envHome && envHome.startsWith('/') ? envHome : undefined;
        if (xdg === undefined && home === undefined) return false;
        const root = $.plugin.root;
        if (isWindowsPath(root)) return false;  // Not supported on Windows: no marker, so the Python hooks guard every call
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
        const so = o ? o : undefined;
        const id = await $.session.id();
        if (mine !== gen) return false;
        guardReady = true;
        retired.delete(id);
        lastSeen = id;
        const write = async (sid: string, heartbeat: number): Promise<void> => {
          const path = markerPath(sx, sh, sid, so);
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
            // Under guard `minimal` the fast path rests on this read, so it runs at every tick while not active.
            void autonomyPoll($, auto, seen, guardMode === 'minimal');
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
      if (!isWindowsPath($.plugin.root) && !boardRegistered) {
        boardRegistered = true;
        await $.command.register({ name: BOARD, description: 'Show the Orchestra board: cards, session and autonomy' });
      }
    } catch {
      // The board is a convenience; it never takes the guard down.
    }
    // Tool calls do not wait for this read: until it lands the guard mode is unknown, which classifies as before.
    if (ready && mine === gen) {
      const w = await readWhere($).catch(() => null);
      if (mine === gen) applyWhere(w);
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
    cancelBoardTimer();
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
      if (reason !== null) return blocked(reason);
      const passed = await next(e);
      try {
        if (runsEngine(input['command'] ?? input['cmd'])) void refreshBoard($, board);
      } catch {
        // The board never changes the tool's answer.
      }
      return passed;
    }
    if (shellTools().includes(tool)) {
      const raw = input['command'] !== undefined ? input['command'] : input['cmd'];
      if (raw === undefined || Object(raw).constructor !== String) return blocked('Missing shell command');
      const command = String(raw);
      // Guard `minimal` with autonomy known to be off and no stopped run: Claude Code's permission mode owns generic
      // command classification; only a command that may touch Orchestra's own files still goes to Python.
      const minimal = guardMode === 'minimal' && !auto.active && !auto.unknown && runStopped === false;
      if (minimal) {
        if (ENGINE_TOUCH.test(command)) {
          const reason = await delegate($, tool, { command }, lastSeen ?? '');
          if (reason !== null) return blocked(reason);
        }
      } else {
        const d = classifyCommand(command);
        const klass = klassOf(d);
        // A softened deny is mode-dependent (normal relaxes it) and the mod reads no policy: Python decides, like a release.
        // Under `minimal` the mod cannot see the unattended lock, so every deny goes to Python, which knows it.
        if (klass === 'deny' && !d.soften && guardMode !== 'minimal') return blocked(d.reason !== '' ? d.reason : FAIL_CLOSED);
        if (klass === 'deny' || DELEGATED.includes(klass)) {
          const sid = lastSeen ?? '';
          const reason = await delegate($, tool, { command }, sid);
          if (reason !== null) return blocked(reason);
        }
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
      try {
        if (runsEngine(command)) void refreshBoard($, board);
      } catch {
        // The board never changes the tool's answer.
      }
      return result;
    }
    if (editTools().includes(tool)) {
      const target = tool === 'NotebookEdit' ? input['notebook_path'] : input['file_path'] !== undefined ? input['file_path'] : input['path'];
      const cwd = await $.session.cwd();
      const stateDir = await $.env.get('ORCHESTRA_STATE_DIR');
      const path = target === undefined ? undefined : String(target);
      const sd = stateDir ? stateDir : null;
      // Both the base Python reads (XDG_STATE_HOME as given) and the marker base are protected.
      const denied = editDenied(path, cwd, { stateDir: sd, xdg: rawXdg, home }) || (rawXdg !== xdg && editDenied(path, cwd, { stateDir: sd, xdg, home }));
      if (denied) return blocked(STATE_DENY);
    }
    return next(e);
  }).catch(async (_$, e, next) => {
    if (next.called) return next(e);
    return blocked(FAIL_CLOSED);
  });

  on('agent.offer', async (_$, e, next) => {
    if (e.agent === 'orchestra:orchestrator') return { isOffered: false };
    return next(e);
  });

  on('agent.spawn', async ($, e, next) => {
    if (!e.subagentType.startsWith('orchestra:')) return next(e);
    const modeLess = await briefWithoutMode($, e.prompt);
    if (modeLess !== null) return { deny: `Orchestra brief ${modeLess} has no "Mode: <mode>" line; add it to the brief or the prompt before spawning` };
    let spawn = e;
    try {
      // O21: only a result with standing orders is cached; session.start clears it.
      if (where === null || !where.standingOrders) where = await readWhere($);
      const w = where;
      if (w !== null && w.standingOrders && w.state !== '') {
        const text = await $.fs.read(`${w.state}/standing-orders.md`);
        const sha = sha256Hex(utf8(text));
        if (!e.prompt.includes(`sha256: ${sha}`)) {
          spawn = { ...e, prompt: `${e.prompt}\n\n## Standing orders (verbatim)\n\n${text}\n\nsha256: ${sha}\n` };
        }
      }
    } catch {
      // Standing orders unavailable: the spawn still goes ahead.
    }
    const result = await next(spawn);
    try {
      const card = cardIdOf(e.prompt);
      if (card !== null && result.deny === undefined) {
        const runId = e.workflow?.runId;
        board.links.set(card, { ...(result.agentId !== undefined ? { agentId: result.agentId } : {}), ...(runId ? { workflowRunId: runId } : {}), spawnedAt: await $.clock.now() });
      }
      void refreshBoard($, board);
    } catch {
      // A link is a convenience; the spawn's answer stands.
    }
    return result;
  });

  on('turn.complete', async ($, e, next) => {
    const result = await next(e);
    try {
      if (e.agentId !== undefined) void refreshBoard($, board);
    } catch {
      // The board never changes a turn's answer.
    }
    return result;
  });

  on('command.run', { command: BOARD }, async ($) => {
    try {
      await $.ui.open({ id: BOARD, title: 'Orchestra board', focus: true });
      await refreshBoard($, board);
      cancelBoardTimer();
      boardTimer = $.clock.every(BOARD_FALLBACK_MS, () => refreshBoard($, board));
    } catch {
      // The board is a convenience; a failure leaves the pane as it was.
    }
    return {};
  });

  on('command.run', { command: AUTONOMY_COMMAND }, async ($, e) => {
    const out = await autonomyCommand($, auto, e.args, seen);
    applyWhere(await readWhere($).catch(() => null));
    return out;
  });

  on('ui.close', { id: BOARD }, async (_$, e, next) => {
    const result = await next(e);
    cancelBoardTimer();
    return result;
  });

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== BOARD) return next(e);
    const { Box, Text, Button } = $.ui.resolve(e);
    let now = board.okAt ?? 0;
    try {
      now = await $.clock.now();
    } catch {
      // Ages read from the last refresh.
    }
    const sync = board.sync;
    const m = paneModel({ view: board.view, nowMs: now, okAt: board.okAt, staleSince: board.staleSince, links: board.links, agents: board.agents, syncLine: sync.line, bodyColumns: e.props.bodyColumns, surface: e.surface });
    const buttons = Box({
      flexDirection: 'row',
      gap: 1,
      children: [
        Button({ key: 'refresh', label: 'Refresh', onPress: () => void refreshBoard($, board) }),
        Button({
          key: 'native-tasks',
          label: sync.wanted ? 'Native tasks: turn off' : 'Native tasks: turn on',
          onPress: () => {
            sync.wanted = !sync.wanted;
            void refreshBoard($, board);
          },
        }),
      ],
    });
    const section = (s: { title: string; lines: string[] }, grow: boolean) =>
      Box({ key: `column-${s.title.split(' ')[0]!.toLowerCase()}`, flexDirection: 'column', ...(grow ? { flexGrow: 1 } : {}), children: [Text({ bold: true, children: s.title }), ...s.lines.map((line) => Text({ wrap: 'truncate', children: line }))] });
    const body = m.layout === 'columns'
      ? Box({ key: 'columns', flexDirection: 'row', gap: 1, children: m.sections.map((s) => section(s, true)) })
      : Box({ key: 'stacked', flexDirection: 'column', children: m.sections.filter((s) => s.lines.length > 0).map((s) => section(s, false)) });
    return Box({ flexDirection: 'column', children: [...m.header.map((line) => Text({ children: line })), buttons, ...(m.sections.length > 0 ? [body] : [])] });
  });
};
