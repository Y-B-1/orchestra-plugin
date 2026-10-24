import { expect, test } from 'claude-code/testing';

import { cardIdOf, clockText, layoutOf, matchTasks, paneModel, parseView, planCreates, planUpdates, subjectOf } from './board.js';
import type { NativeTask, View } from './board.js';

const RUN = '0123456789abcdef';

function viewText(cards: unknown[], extra: Record<string, unknown> = {}): string {
  return JSON.stringify({
    run_id: RUN,
    session: { active: true, size: 'medium' },
    bound: true,
    autonomy: { active: false },
    counts: { queued: 1, running: 2, reported: 0, repairing: 0, held: 0, parked: 0, accepted: 1 },
    columns: {},
    cards,
    startable_now: ['B3'],
    next_wave: ['B3'],
    latest_review: { id: 'R1', verdict: 'CLEAN', categories: [], head: 'abc1234' },
    latest_gate: { name: 'unit', passed: false, head: 'abc1234' },
    pull_requests: [],
    guard_mode: 'minimal',
    ...extra,
  });
}

const card = (id: string, seq: number, state: string, more: Record<string, unknown> = {}) => ({
  id, role: 'builder', mode: 'implementation', state, worker: null, inline: false, dependencies: [], deps_open: [], review_of: [], files: [], started_at: null, seq, ...more,
});

function view(cards: unknown[], extra: Record<string, unknown> = {}): View {
  const v = parseView(viewText(cards, extra));
  if (v === null) throw new Error('fixture view did not parse');
  return v;
}

const base = { okAt: 100_000, staleSince: null, links: new Map(), agents: new Map(), syncLine: 'Native tasks: on', bodyColumns: 120, surface: 'terminal' };

test('parseView: rejects non-JSON, arrays and a view without cards', () => {
  expect(parseView('not json')).toBe(null);
  expect(parseView('[]')).toBe(null);
  expect(parseView(JSON.stringify({ run_id: RUN }))).toBe(null);
  expect(parseView(viewText([card('A', 1, 'queued')]))?.cards.map((c) => c.id)).toEqual(['A']);
});

test('layout: wide terminal and desktop panes are columns; narrow or mobile panes stack', () => {
  expect(layoutOf(120, 'terminal')).toBe('columns');
  expect(layoutOf(100, 'desktop')).toBe('columns');
  expect(layoutOf(99, 'terminal')).toBe('stacked');
  expect(layoutOf(200, 'mobile')).toBe('stacked');
  expect(layoutOf(200, 'vscode')).toBe('stacked');
});

test('pane: cards are ordered by seq, so B2 comes before B10', () => {
  const v = view([card('B10', 10, 'queued'), card('B2', 2, 'queued'), card('B1', 1, 'queued')]);
  const m = paneModel({ ...base, view: v, nowMs: 100_000 });
  const queued = m.sections.find((s) => s.title.startsWith('Queued'))!;
  expect(queued.lines.map((l) => l.split(' ')[0])).toEqual(['B1', 'B2', 'B10']);
});

test('pane: section counts and the header counts come from the engine view', () => {
  const v = view([card('A', 1, 'running'), card('B', 2, 'queued')]);
  const m = paneModel({ ...base, view: v, nowMs: 100_000 });
  expect(m.sections.map((s) => s.title)).toEqual(['Queued (1)', 'Running (2)', 'Reported (0)', 'Repairing (0)', 'Held (0)', 'Parked (0)', 'Accepted (1)']);
  expect(m.header).toContain('Counts: queued 1, running 2, reported 0, repairing 0, held 0, parked 0, accepted 1');
  expect(m.header).toContain('Startable now: B3; next wave: B3');
  expect(m.header).toContain('Review R1: CLEAN @abc1234; gate unit: failed @abc1234');
  expect(m.header).toContain('Session: active (medium); autonomy: off; run 012345');
});

test('pane: the header shows the age of the data, and a failed refresh shows stale since', () => {
  const v = view([card('A', 1, 'queued')]);
  const fresh = paneModel({ ...base, view: v, nowMs: 104_000 });
  expect(fresh.header).toContain('updated 4s ago');
  const failedAt = new Date(2026, 9, 24, 12, 34, 56).getTime();
  const stale = paneModel({ ...base, view: v, staleSince: failedAt, nowMs: failedAt + 1000 });
  expect(stale.header.some((h) => h.startsWith('stale since 12:34:56'))).toBe(true);
  expect(clockText(new Date(2026, 0, 2, 3, 4, 5).getTime())).toBe('03:04:05');
  const none = paneModel({ ...base, view: null, okAt: null, staleSince: failedAt, nowMs: failedAt });
  expect(none.header[0]).toBe('Orchestra: no board yet');
  expect(none.header.some((h) => h.startsWith('stale since 12:34:56'))).toBe(true);
});

test('pane: a card line names the worker, age, open deps and agent; a failed agent on a running card is marked', () => {
  const v = view([card('B2', 2, 'running', { worker: 'orchestra-B2', started_at: 40, deps_open: ['B1'], dependencies: ['B1'] }), card('B3', 3, 'running', { started_at: 90 })]);
  const links = new Map([['B2', { agentId: 'ag-1', spawnedAt: 0 }], ['B3', { workflowRunId: 'wf_9', spawnedAt: 0 }]]);
  const agents = new Map([['ag-1', 'failed']]);
  const m = paneModel({ ...base, view: v, links, agents, nowMs: 100_000 });
  const running = m.sections.find((s) => s.title.startsWith('Running'))!;
  expect(running.lines).toEqual(['B2 builder/implementation orchestra-B2 1m deps B1 agent failed !', 'B3 builder/implementation - 10s workflow wf_9']);
});

test('cardIdOf: the worker line first, else a first-line heading; nothing otherwise', () => {
  expect(cardIdOf('Mode: implementation\nWorker orchestra-M1, assignment token x.')).toBe('M1');
  expect(cardIdOf('# B10: the board\nWorker orchestra-B2 here')).toBe('B2');
  expect(cardIdOf('# B10: the board\nMode: review')).toBe('B10');
  expect(cardIdOf('Do the work.\n# B10: not the first line')).toBe(null);
});

const task = (id: string, subject: string, status = 'pending', blockedBy: string[] = [], owner?: string): NativeTask => ({ id, subject, status, blockedBy, ...(owner ? { owner } : {}) });

test('sync plan: one create per card with a mapped state; none for an existing or dropped card', () => {
  const v = view([card('A', 1, 'queued'), card('B', 2, 'running'), card('C', 3, 'accepted', { outcome: 'shipped' })]);
  expect(subjectOf('012345', v.cards[2]!)).toBe('[012345] C builder/implementation: shipped');
  const matched = matchTasks('012345', [task('1', '[012345] A builder/implementation'), task('2', '[999999] B builder/implementation'), task('3', '[012345] A1 x')]);
  expect([...matched.keys()]).toEqual(['A', 'A1']);
  const creates = planCreates(v, matched, new Set(['C']));
  expect(creates.map((c) => [c.cardId, c.subject])).toEqual([['B', '[012345] B builder/implementation']]);
});

test('sync plan: status, owner and blockedBy updates are sent only when they differ', () => {
  const v = view([card('A', 1, 'accepted', { worker: 'w1' }), card('B', 2, 'running', { worker: 'w2', dependencies: ['A'] }), card('C', 3, 'held')]);
  const matched = matchTasks('012345', [
    task('1', '[012345] A builder/implementation', 'completed', [], 'w1'),
    task('2', '[012345] B builder/implementation', 'pending'),
    task('3', '[012345] C builder/implementation', 'pending'),
  ]);
  expect(planUpdates(v, matched, new Set())).toEqual([{ cardId: 'B', taskId: '2', fields: { status: 'in_progress', owner: 'w2', addBlockedBy: ['1'] } }]);
  const done = matchTasks('012345', [
    task('1', '[012345] A builder/implementation', 'completed', [], 'w1'),
    task('2', '[012345] B builder/implementation', 'in_progress', ['1'], 'w2'),
    task('3', '[012345] C builder/implementation', 'pending'),
  ]);
  expect(planUpdates(v, done, new Set())).toEqual([]);
  expect(planUpdates(v, matched, new Set(['B']))).toEqual([]);
});
