// The Kanban board and the native task mirror: pure logic over `orchestra.py board --view`. No `$` here: the
// engine's module validator follows `$` only into functions declared in the same file, so orchestra.ts owns every
// `$` call and passes plain data in.

export const COLUMNS = ['queued', 'running', 'reported', 'repairing', 'held', 'parked', 'accepted'] as const;

type Json = Record<string, unknown>;

export type Card = {
  id: string;
  role: string;
  mode: string;
  state: string;
  worker: string | null;
  dependencies: string[];
  depsOpen: string[];
  /** Engine clock, epoch seconds. */
  startedAt: number | null;
  seq: number;
  outcome: string | null;
};

export type View = {
  runId: string;
  sessionActive: boolean;
  sessionSize: string | null;
  bound: boolean;
  autonomyActive: boolean;
  counts: Record<string, number>;
  cards: Card[];
  startableNow: string[];
  nextWave: string[];
  latestReview: string | null;
  latestGate: string | null;
};

/** What the mod knows of the agent working a card: its id when local, its Workflow run when there is one. */
export type Link = { agentId?: string; workflowRunId?: string; spawnedAt: number };

export type NativeTask = { id: string; subject: string; status: string; owner?: string; blockedBy: string[] };
export type Create = { cardId: string; subject: string; description: string };
export type Update = { cardId: string; taskId: string; fields: { status?: string; owner?: string; addBlockedBy?: string[] } };

function obj(v: unknown): Json | null {
  return v !== null && typeof v === 'object' && !Array.isArray(v) ? (v as Json) : null;
}

function strings(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
}

function parseCard(v: unknown): Card | null {
  const c = obj(v);
  if (c === null || typeof c['id'] !== 'string' || c['id'] === '') return null;
  const text = (k: string): string => (typeof c[k] === 'string' ? (c[k] as string) : '-');
  return {
    id: c['id'],
    role: text('role'),
    mode: text('mode'),
    state: text('state'),
    worker: typeof c['worker'] === 'string' && c['worker'] !== '' ? c['worker'] : null,
    dependencies: strings(c['dependencies']),
    depsOpen: strings(c['deps_open']),
    startedAt: typeof c['started_at'] === 'number' ? c['started_at'] : null,
    seq: typeof c['seq'] === 'number' ? c['seq'] : Number.MAX_SAFE_INTEGER,
    outcome: typeof c['outcome'] === 'string' && c['outcome'] !== '' ? c['outcome'] : null,
  };
}

/** `board --view` output, or null when it is not a view. */
export function parseView(text: string): View | null {
  let body: Json | null;
  try {
    body = obj(JSON.parse(text));
  } catch {
    return null;
  }
  if (body === null || !Array.isArray(body['cards'])) return null;
  const session = obj(body['session']) ?? {};
  const counts: Record<string, number> = {};
  const rawCounts = obj(body['counts']) ?? {};
  for (const s of COLUMNS) counts[s] = typeof rawCounts[s] === 'number' ? (rawCounts[s] as number) : 0;
  const review = obj(body['latest_review']);
  const gate = obj(body['latest_gate']);
  return {
    runId: typeof body['run_id'] === 'string' ? body['run_id'] : '',
    sessionActive: session['active'] === true,
    sessionSize: typeof session['size'] === 'string' ? session['size'] : null,
    bound: body['bound'] === true,
    autonomyActive: obj(body['autonomy'])?.['active'] === true,
    counts,
    cards: body['cards'].map(parseCard).filter((c): c is Card => c !== null),
    startableNow: strings(body['startable_now']),
    nextWave: strings(body['next_wave']),
    latestReview: review === null ? null : `Review ${String(review['id'] ?? '?')}: ${String(review['verdict'] ?? '?')} @${String(review['head'] ?? '')}`,
    latestGate: gate === null ? null : `gate ${String(gate['name'] ?? '?')}: ${gate['passed'] === true ? 'passed' : 'failed'} @${String(gate['head'] ?? '')}`,
  };
}

/** Side-by-side columns need a wide pane on a surface that lays out rows; anything else stacks. */
export function layoutOf(bodyColumns: number, surface: string): 'columns' | 'stacked' {
  return bodyColumns >= 100 && (surface === 'terminal' || surface === 'desktop') ? 'columns' : 'stacked';
}

const two = (n: number): string => String(n).padStart(2, '0');

/** Local wall-clock HH:MM:SS. */
export function clockText(ms: number): string {
  const d = new Date(ms);
  return `${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())}`;
}

function ageText(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h${two(Math.floor((s % 3600) / 60))}m`;
}

function cardLine(card: Card, nowMs: number, link: Link | undefined, agents: ReadonlyMap<string, string>): string {
  const parts = [card.id, `${card.role}/${card.mode}`, card.worker ?? '-'];
  if (card.startedAt !== null) parts.push(ageText(nowMs / 1000 - card.startedAt));
  if (card.depsOpen.length > 0) parts.push(`deps ${card.depsOpen.join(',')}`);
  const status = link?.agentId !== undefined ? agents.get(link.agentId) : undefined;
  if (link?.workflowRunId !== undefined) parts.push(`workflow ${link.workflowRunId}`);
  else if (status !== undefined) parts.push(`agent ${status}`);
  if (card.state === 'running' && status === 'failed') parts.push('!');
  return parts.join(' ');
}

export type PaneInput = {
  view: View | null;
  nowMs: number;
  okAt: number | null;
  staleSince: number | null;
  links: ReadonlyMap<string, Link>;
  agents: ReadonlyMap<string, string>;
  syncLine: string;
  bodyColumns: number;
  surface: string;
};

export type PaneModel = { layout: 'columns' | 'stacked'; header: string[]; sections: { title: string; lines: string[] }[] };

export function paneModel(input: PaneInput): PaneModel {
  const { view } = input;
  const layout = layoutOf(input.bodyColumns, input.surface);
  const freshness: string[] = [];
  if (input.staleSince !== null) {
    freshness.push(`stale since ${clockText(input.staleSince)}${input.okAt !== null ? `, data from ${ageText((input.nowMs - input.okAt) / 1000)} ago` : ''}`);
  } else if (input.okAt !== null) {
    freshness.push(`updated ${ageText((input.nowMs - input.okAt) / 1000)} ago`);
  }
  if (view === null) return { layout, header: ['Orchestra: no board yet', ...freshness, input.syncLine], sections: [] };
  const header = [
    `Session: ${view.sessionActive ? 'active' : 'inactive'}${view.sessionSize !== null ? ` (${view.sessionSize})` : ''}; autonomy: ${view.autonomyActive ? 'on' : 'off'}; run ${view.runId.slice(0, 6) || '-'}`,
    `Counts: ${COLUMNS.map((s) => `${s} ${view.counts[s] ?? 0}`).join(', ')}`,
    `Startable now: ${view.startableNow.join(', ') || '-'}; next wave: ${view.nextWave.join(', ') || '-'}`,
    `${view.latestReview ?? 'Review: -'}; ${view.latestGate ?? 'gate: -'}`,
    ...freshness,
    input.syncLine,
  ];
  const sections = COLUMNS.map((s) => ({
    title: `${s[0]!.toUpperCase()}${s.slice(1)} (${view.counts[s] ?? 0})`,
    lines: view.cards
      .filter((c) => c.state === s)
      .sort((a, b) => a.seq - b.seq)
      .map((c) => cardLine(c, input.nowMs, input.links.get(c.id), input.agents)),
  }));
  return { layout, header, sections };
}

/** The card a spawned worker serves: `Worker orchestra-<ID>` anywhere, else a first line `# <ID>:`. */
export function cardIdOf(prompt: string): string | null {
  const worker = /\bWorker orchestra-([A-Za-z0-9][A-Za-z0-9_-]*)/.exec(prompt);
  if (worker !== null) return worker[1]!;
  const heading = /^#\s+([A-Za-z0-9][A-Za-z0-9_-]*):/.exec(prompt.split('\n', 1)[0] ?? '');
  return heading !== null ? heading[1]! : null;
}

export function runShort(runId: string): string {
  return runId.slice(0, 6);
}

export function subjectOf(short: string, card: Card): string {
  return `[${short}] ${card.id} ${card.role}/${card.mode}${card.outcome !== null ? `: ${card.outcome}` : ''}`;
}

/** The native status a card state maps to; null leaves the task alone. */
export function nativeStatus(state: string): 'pending' | 'in_progress' | 'completed' | null {
  if (state === 'queued' || state === 'held' || state === 'parked') return 'pending';
  if (state === 'running' || state === 'reported' || state === 'repairing') return 'in_progress';
  if (state === 'accepted') return 'completed';
  return null;
}

/** TaskList keeps no metadata: a task belongs to card ID of this run when its subject starts `[<short>] <ID> `. */
export function matchTasks(short: string, tasks: readonly NativeTask[]): Map<string, NativeTask> {
  const prefix = `[${short}] `;
  const out = new Map<string, NativeTask>();
  for (const t of tasks) {
    if (!t.subject.startsWith(prefix)) continue;
    const id = t.subject.slice(prefix.length).split(' ', 1)[0] ?? '';
    if (id !== '' && t.subject.length > prefix.length + id.length && !out.has(id)) out.set(id, t);
  }
  return out;
}

/** `TaskList`'s `{ tasks }`, or null when the answer is not one. */
export function parseTaskList(result: unknown): NativeTask[] | null {
  const tasks = obj(result)?.['tasks'];
  if (!Array.isArray(tasks)) return null;
  const out: NativeTask[] = [];
  for (const raw of tasks) {
    const t = obj(raw);
    if (t === null || typeof t['id'] !== 'string' || typeof t['subject'] !== 'string') continue;
    out.push({ id: t['id'], subject: t['subject'], status: String(t['status'] ?? ''), ...(typeof t['owner'] === 'string' ? { owner: t['owner'] } : {}), blockedBy: strings(t['blockedBy']) });
  }
  return out;
}

export function planCreates(view: View, matched: ReadonlyMap<string, NativeTask>, dropped: ReadonlySet<string>): Create[] {
  const short = runShort(view.runId);
  return view.cards
    .filter((c) => nativeStatus(c.state) !== null && !matched.has(c.id) && !dropped.has(c.id))
    .map((c) => ({ cardId: c.id, subject: subjectOf(short, c), description: `Orchestra card ${c.id} (${c.role}/${c.mode}) of run ${view.runId}, mirrored from the Orchestra board.` }));
}

export function planUpdates(view: View, matched: ReadonlyMap<string, NativeTask>, dropped: ReadonlySet<string>): Update[] {
  const out: Update[] = [];
  for (const c of view.cards) {
    const status = nativeStatus(c.state);
    const t = matched.get(c.id);
    if (status === null || t === undefined || dropped.has(c.id)) continue;
    const fields: Update['fields'] = {};
    if (t.status !== status) fields.status = status;
    if (c.worker !== null && t.owner !== c.worker) fields.owner = c.worker;
    const blockers = c.dependencies
      .map((d) => (dropped.has(d) ? undefined : matched.get(d)?.id))
      .filter((id): id is string => id !== undefined && !t.blockedBy.includes(id));
    if (blockers.length > 0) fields.addBlockedBy = blockers;
    if (Object.keys(fields).length > 0) out.push({ cardId: c.id, taskId: t.id, fields });
  }
  return out;
}
