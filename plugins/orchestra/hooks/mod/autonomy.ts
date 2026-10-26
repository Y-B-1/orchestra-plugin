// SPEC 12.7: `/orchestra-autonomy on|off|status`, the stop toast and the status band. UI only: every
// decision stays in the engine, reached through `run-hook.sh --cli autonomy arm|disarm|status`.
// This file holds no `$`: the engine's module validator follows `$` only into a function declared in the
// same file, never across an import (B11 finding). orchestra.ts owns every `$` call and passes plain data
// here, so everything below is pure and takes the state the caller owns.

export const AUTONOMY_COMMAND = 'orchestra-autonomy';
/** SPEC 12.7: status is read at most this often while autonomy is active. */
export const POLL_MS = 30000;
export const USAGE = 'Orchestra autonomy: use /orchestra-autonomy on|off|status';

type Json = Record<string, unknown>;
export type Sub = 'arm' | 'disarm' | 'status';

export type AutonomyState = {
  registered: boolean;
  /** Last known: set by `on`, cleared by `off` or a seen stop. */
  active: boolean;
  /** `$.clock.now()` of the last status read; null means none yet. */
  lastRead: number | null;
  busy: boolean;
  band: boolean;
  /** Bumped by `startSession`, so a read in flight from an earlier session is dropped. */
  epoch: number;
  /** True when the state is not known: after `session.start`, or after a CLI arm seen in Bash. The next tick reads status. */
  unknown: boolean;
  /** Bumped when a command or a CLI arm changes the state, so a read that started before it is dropped. */
  changes: number;
  /** The band shown after a stop this process saw, kept until the next arm, disarm or session start. */
  stopText: string | undefined;
};

export type Cli = { ok: boolean; body: Json | null; error: string };
/** `band`: undefined leaves it, `{ text }` sets it, `{ text: undefined }` clears it. */
/** `armed`: autonomy went from not active to active with this answer. */
export type Outcome = { text: string; band?: { text: string | undefined }; armed?: boolean };

export function newAutonomy(): AutonomyState {
  return { registered: false, active: false, lastRead: null, busy: false, band: false, epoch: 0, unknown: true, changes: 0, stopText: undefined };
}

function parse(text: string): Json | null {
  try {
    const v: unknown = JSON.parse(text);
    return v !== null && !Array.isArray(v) && Object(v) === v ? (v as Json) : null;
  } catch {
    return null;
  }
}

function num(v: unknown): string {
  return v !== undefined && v !== null && Object(v).constructor === Number ? String(v) : '?';
}

/** The CLI prints errors as `{"error": ...}` on stderr with exit 2. */
export function cliResult(exitCode: number, stdout: string, stderr: string): Cli {
  if (exitCode !== 0) {
    const body = parse(stderr);
    if (body !== null && body['error'] !== undefined) return { ok: false, body: null, error: String(body['error']) };
    const text = stderr.trim() !== '' ? stderr.trim() : stdout.trim();
    return { ok: false, body: null, error: text !== '' ? text : `exit ${String(exitCode)}` };
  }
  const body = parse(stdout);
  if (body === null) return { ok: false, body: null, error: 'unreadable autonomy output' };
  return { ok: true, body, error: '' };
}

export function cliThrown(error: unknown): Cli {
  return { ok: false, body: null, error: String(error instanceof Error ? error.message : error) };
}

export function subOf(args: string): Sub | null {
  const word = args.trim().split(/\s+/)[0] ?? '';
  return word === 'on' ? 'arm' : word === 'off' ? 'disarm' : word === 'status' ? 'status' : null;
}

/** `silent` entries of a status read as `B2 62m`; anything malformed is skipped. */
function silentLabels(status: Json): string[] {
  const list = status['silent'];
  if (!Array.isArray(list)) return [];
  const labels: string[] = [];
  for (const item of list) {
    const row = parse(JSON.stringify(item ?? null));
    if (row !== null && typeof row['id'] === 'string') labels.push(`${row['id']} ${num(row['minutes'])}m`);
  }
  return labels;
}

/**
 * The active band: pass and deadline, then only what needs a glance: background workers running, stalls, and a worker
 * silent past the engine's limit. The Stop hook that stops a stalled run fires only at the end of a turn, so a session
 * left idle on a lost worker shows it here and nowhere else.
 */
function bandText(status: Json): string {
  const when = String(status['deadline'] ?? '');
  const hhmm = /T(\d{2}:\d{2})/.exec(when);
  let text = `Orchestra autonomy: pass ${num(status['passes'])}, deadline ${hhmm !== null ? hhmm[1]! : when !== '' ? when : '?'}`;
  const running = status['running'];
  if (typeof running === 'number' && running > 0) text += `, ${String(running)} worker${running === 1 ? '' : 's'} running`;
  const stalls = status['stalls'];
  if (typeof stalls === 'number' && stalls > 0) text += `, stalls ${String(stalls)}`;
  const silent = silentLabels(status);
  if (silent.length > 0) text += `, silent: ${silent.join(', ')}`;
  return text;
}

/** The band that stays after a stop, so a stop seen while the user looked away is still on screen. */
export function stopBand(status: Json): string {
  return `Orchestra autonomy stopped: ${String(status['last_stop_reason'] ?? 'unknown')}; /orchestra-autonomy on to re-arm`;
}

export function stopLine(status: Json): string {
  return `Orchestra autonomy stopped: ${String(status['last_stop_reason'] ?? 'unknown')} (pass ${num(status['passes'])}, stalls ${num(status['stalls'])})`;
}

/** Applies one status read. `stopped` is true when it was active until now and is not in this read. */
function apply(auto: AutonomyState, status: Json): { band: string | undefined; stopped: boolean } {
  auto.unknown = false;
  if (status['active'] === true) {
    auto.active = true;
    auto.stopText = undefined;
    return { band: bandText(status), stopped: false };
  }
  const stopped = auto.active;
  auto.active = false;
  // A disarm through the CLI is the owner's own act, like /orchestra-autonomy off: it clears the band.
  if (stopped) auto.stopText = status['last_stop_reason'] === 'disarmed' ? undefined : stopBand(status);
  return { band: auto.stopText, stopped };
}

/** What a finished CLI call for `sub` shows, and the band change that goes with it. */
export function commandOutcome(auto: AutonomyState, sub: Sub, res: Cli): Outcome {
  if (!res.ok || res.body === null) return { text: `Orchestra autonomy: ${res.error}` };
  const body = res.body;
  if (sub === 'arm') {
    const was = auto.active;
    auto.active = body['active'] === true;
    auto.unknown = false;
    auto.lastRead = null;
    auto.stopText = undefined;
    const pre = parse(JSON.stringify(body['preconditions'] ?? null)) ?? {};
    const lines = [`Orchestra autonomy: armed. Ledger: ${String(body['ledger'] ?? '?')}`];
    for (const key of Object.keys(pre)) lines.push(`${key}: ${String(pre[key])}`);
    return { text: lines.join('\n'), band: { text: undefined }, armed: !was && auto.active };
  }
  if (sub === 'disarm') {
    auto.active = false;
    auto.unknown = false;
    auto.stopText = undefined;
    const text = String(body['text'] ?? '');
    const line = body['was_active'] === true ? `Orchestra autonomy: disarmed${text !== '' ? `\n${text}` : ''}` : 'Orchestra autonomy: disarmed (it was not active)';
    return { text: line, band: { text: undefined } };
  }
  const was = auto.active;
  const seen = apply(auto, body);
  const armed = !was && auto.active;
  const parked = Array.isArray(body['parked']) ? body['parked'].length : 0;
  const band = { text: seen.band };
  if (body['active'] === true) return { text: `${bandText(body)}\nstalls ${num(body['stalls'])}, parked ${String(parked)}`, band, armed };
  const last = body['last_stop_reason'];
  return { text: `Orchestra autonomy: inactive${last !== undefined && last !== null ? ` (last stop: ${String(last)})` : ''}`, band };
}

/**
 * Whether the tick may read status at `now`; takes the slot when it may. `watch` (guard `minimal`) reads at every
 * tick while not active, so an arm from another session or a terminal ends the mod's fast path.
 */
export function pollDue(auto: AutonomyState, now: number, watch = false): boolean {
  if (!auto.active && !auto.unknown && !watch) return false;
  if (!(watch && !auto.active) && auto.lastRead !== null && now - auto.lastRead < POLL_MS) return false;
  auto.lastRead = now;
  return true;
}

/** What a tick's status read shows: a band change, and a toast text when a stop was just seen. */
export function pollOutcome(auto: AutonomyState, res: Cli): { band: string | undefined; toast: string | null; changed: boolean; armed: boolean } {
  if (!res.ok || res.body === null) return { band: undefined, toast: null, changed: false, armed: false };
  const was = auto.active;
  const seen = apply(auto, res.body);
  return { band: seen.band, toast: seen.stopped ? stopLine(res.body) : null, changed: true, armed: !was && auto.active };
}

/** `session.start`: forget the last session's flags. */
export function startSession(auto: AutonomyState): void {
  auto.epoch += 1;
  auto.active = false;
  auto.stopText = undefined;
  auto.unknown = true;
  auto.lastRead = null;
  auto.busy = false;
}

/** A change this process caused or saw (a command, a CLI arm): drops reads in flight; `unknown` also has the next tick read status. */
export function noteChange(auto: AutonomyState, unknown: boolean): void {
  auto.changes += 1;
  if (unknown) {
    auto.unknown = true;
    auto.lastRead = null;
  }
}
