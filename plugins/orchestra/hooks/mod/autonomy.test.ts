import { expect, test } from 'claude-code/testing';
import type { On } from 'claude-code';

import { rig } from './testkit.js';
import type { Rig } from './testkit.js';

const start = { cwd: '/work/proj', surface: null, isInteractive: false } as const;

function stage(on: On) {
  const registered: string[] = [];
  on('command.register', async (_$, e) => {
    registered.push((e as { name: string }).name);
    return { value: undefined } as never;
  });
  const bands: (string | undefined)[] = [];
  on('ui.status', async (_$, e) => {
    bands.push((e as { text: string | undefined }).text);
    return { value: undefined } as never;
  });
  on('tool.call', async () => ({ result: { stdout: '', stderr: '' } }) as never);
  return { registered, bands };
}

const ARGV_TAIL = (action: string) => ['--cli', '--repo', '/work/proj', 'autonomy', action];
const isAutonomy = (argv: readonly string[]) => argv.includes('autonomy');
const autonomyRuns = (r: Rig) => r.runs.filter((run) => isAutonomy(run.argv));
const action = (argv: readonly string[]) => argv[argv.length - 1];

const ACTIVE = { active: true, parked: [], last_stop_reason: null, passes: 2, max_passes: 5, stalls: 0, max_stalls: 2, deadline: '2026-10-05T07:30:00+00:00' };
const STOPPED = { ...ACTIVE, active: false, passes: 5, last_stop_reason: 'cap-passes' };

function answers(r: Rig, table: Record<string, { exitCode: number; stdout: string; stderr?: string }>) {
  r.runAnswer = (argv) => {
    if (!isAutonomy(argv)) return { exitCode: 0, stdout: '{}' };
    return table[action(argv)!] ?? { exitCode: 0, stdout: '{}' };
  };
}

const run = ($: { command: { run: (i: never) => Promise<{ text?: string }> } }, args: string) => $.command.run({ command: 'orchestra-autonomy', args } as never);

test('autonomy: /orchestra-autonomy is registered once across repeated starts', async ($, on) => {
  const r = rig(on);
  const s = stage(on);
  answers(r, {});
  await $.session.start(start);
  await $.session.start(start);
  expect(s.registered.filter((n) => n === 'orchestra-autonomy')).toEqual(['orchestra-autonomy']);
});

test('autonomy: on, off and status call the CLI with the right argv and render its output', async ($, on) => {
  const r = rig(on);
  stage(on);
  answers(r, {
    arm: { exitCode: 0, stdout: JSON.stringify({ active: true, ledger: '/state/autonomy.md', preconditions: { permission_mode: 'bypassPermissions (user settings)', keep_awake: 'User step: enable keep-awake' } }) },
    disarm: { exitCode: 0, stdout: JSON.stringify({ was_active: true, reason: 'disarmed', text: '## Autonomy report' }) },
    status: { exitCode: 0, stdout: JSON.stringify(ACTIVE) },
  });
  await $.session.start(start);
  const on1 = await run($ as never, 'on');
  expect(action(autonomyRuns(r).at(-1)!.argv)).toBe('arm');
  expect(autonomyRuns(r).at(-1)!.argv.slice(-5)).toEqual(ARGV_TAIL('arm'));
  expect(autonomyRuns(r).at(-1)!.argv[1]).toContain('scripts/run-hook.sh');
  expect(autonomyRuns(r).at(-1)!.init!.cwd).toBe('/work/proj');
  expect(on1.text).toContain('armed');
  expect(on1.text).toContain('/state/autonomy.md');
  expect(on1.text).toContain('bypassPermissions');
  expect(on1.text).toContain('keep-awake');
  const st = await run($ as never, 'status');
  expect(action(autonomyRuns(r).at(-1)!.argv)).toBe('status');
  expect(st.text).toContain('pass 2/5');
  const off = await run($ as never, 'off');
  expect(action(autonomyRuns(r).at(-1)!.argv)).toBe('disarm');
  expect(off.text).toContain('disarmed');
});

test('autonomy: on with no ledger shows the template path the CLI names', async ($, on) => {
  const r = rig(on);
  stage(on);
  const message = 'Ledger template written to /state/proj/autonomy.md: fill the ledger, then arm again';
  answers(r, { arm: { exitCode: 2, stdout: '', stderr: JSON.stringify({ error: message }) } });
  await $.session.start(start);
  const res = await run($ as never, 'on');
  expect(res.text).toContain('/state/proj/autonomy.md');
  expect(res.text).toContain('fill the ledger');
});

test('autonomy: an unknown argument shows usage and runs no CLI', async ($, on) => {
  const r = rig(on);
  stage(on);
  await $.session.start(start);
  const res = await run($ as never, 'sideways');
  expect(res.text).toContain('on|off|status');
  expect(autonomyRuns(r).length).toBe(0);
});

test('autonomy: a CLI failure or unparseable output renders an error and does not throw', async ($, on) => {
  const r = rig(on);
  stage(on);
  answers(r, { status: { exitCode: 3, stdout: '', stderr: 'boom' } });
  await $.session.start(start);
  const failed = await run($ as never, 'status');
  expect(failed.text).toContain('boom');
  answers(r, { status: { exitCode: 0, stdout: 'not json' } });
  const garbled = await run($ as never, 'status');
  expect(garbled.text).toContain('Orchestra autonomy');
  r.runAnswer = () => {
    throw new Error('spawn failed');
  };
  const thrown = await run($ as never, 'off');
  expect(thrown.text).toContain('Orchestra autonomy');
});

test('autonomy: the tick reads status at most every 30 s, only while active, and toasts a stop once', async ($, on) => {
  const r = rig(on);
  const s = stage(on);
  const table: Record<string, { exitCode: number; stdout: string }> = {
    arm: { exitCode: 0, stdout: JSON.stringify({ active: true, ledger: '/state/autonomy.md', preconditions: {} }) },
    status: { exitCode: 0, stdout: JSON.stringify({ ...STOPPED, last_stop_reason: null }) },
  };
  answers(r, table);
  await $.session.start(start);
  // Not active: the one startup read (unknown state), then ticks never read status.
  await r.clock.advance(60000);
  expect(autonomyRuns(r).length).toBe(1);
  await run($ as never, 'on');
  table['status'] = { exitCode: 0, stdout: JSON.stringify(ACTIVE) };
  expect(autonomyRuns(r).length).toBe(2);
  // First tick after arming reads once; the next five ticks (25 s) read nothing more.
  await r.clock.advance(5000);
  const afterFirst = autonomyRuns(r).filter((x) => action(x.argv) === 'status').length;
  expect(afterFirst).toBe(2);
  await r.clock.advance(25000);
  expect(autonomyRuns(r).filter((x) => action(x.argv) === 'status').length).toBe(2);
  await r.clock.advance(5000);
  expect(autonomyRuns(r).filter((x) => action(x.argv) === 'status').length).toBe(3);
  expect(r.toasts.length).toBe(0);
  // The run stops by cap: one toast with reason and counts; afterwards no more reads.
  table['status'] = { exitCode: 0, stdout: JSON.stringify(STOPPED) };
  await r.clock.advance(30000);
  expect(r.toasts.length).toBe(1);
  expect(r.toasts[0]).toContain('cap-passes');
  expect(r.toasts[0]).toContain('5/5');
  const reads = autonomyRuns(r).filter((x) => action(x.argv) === 'status').length;
  await r.clock.advance(120000);
  expect(autonomyRuns(r).filter((x) => action(x.argv) === 'status').length).toBe(reads);
  expect(r.toasts.length).toBe(1);
});

test('autonomy: a tick CLI failure while active never throws and keeps polling', async ($, on) => {
  const r = rig(on);
  stage(on);
  const table: Record<string, { exitCode: number; stdout: string }> = {
    arm: { exitCode: 0, stdout: JSON.stringify({ active: true, ledger: '/l', preconditions: {} }) },
    status: { exitCode: 1, stdout: '' },
  };
  answers(r, table);
  await $.session.start(start);
  await run($ as never, 'on');
  await r.clock.advance(35000);
  expect(r.toasts.length).toBe(0);
  table['status'] = { exitCode: 0, stdout: JSON.stringify(STOPPED) };
  await r.clock.advance(35000);
  expect(r.toasts.length).toBe(1);
});

test('autonomy: the status band shows pass N/M and deadline while active and clears after a stop or off', async ($, on) => {
  const r = rig(on);
  const s = stage(on);
  const table: Record<string, { exitCode: number; stdout: string }> = {
    arm: { exitCode: 0, stdout: JSON.stringify({ active: true, ledger: '/l', preconditions: {} }) },
    status: { exitCode: 0, stdout: JSON.stringify(ACTIVE) },
    disarm: { exitCode: 0, stdout: JSON.stringify({ was_active: true, reason: 'disarmed', text: '' }) },
  };
  answers(r, table);
  await $.session.start(start);
  await run($ as never, 'on');
  await run($ as never, 'status');
  expect(s.bands.at(-1)).toBe('Orchestra autonomy: pass 2/5, deadline 07:30');
  table['status'] = { exitCode: 0, stdout: JSON.stringify(STOPPED) };
  await r.clock.advance(35000);
  expect(s.bands.at(-1)).toBeUndefined();
  // Re-arm, then off clears the band.
  table['status'] = { exitCode: 0, stdout: JSON.stringify(ACTIVE) };
  await run($ as never, 'on');
  await run($ as never, 'status');
  expect(s.bands.at(-1)).toContain('pass 2/5');
  await run($ as never, 'off');
  expect(s.bands.at(-1)).toBeUndefined();
});

test('autonomy: session.end clears a shown band and stops reading', async ($, on) => {
  const r = rig(on);
  const s = stage(on);
  answers(r, {
    arm: { exitCode: 0, stdout: JSON.stringify({ active: true, ledger: '/l', preconditions: {} }) },
    status: { exitCode: 0, stdout: JSON.stringify(ACTIVE) },
  });
  await $.session.start(start);
  await run($ as never, 'on');
  await run($ as never, 'status');
  expect(s.bands.at(-1)).toContain('pass 2/5');
  await $.session.end({ reason: 'other', sessionId: 'sid-1' } as never);
  expect(s.bands.at(-1)).toBeUndefined();
  const reads = autonomyRuns(r).length;
  await r.clock.advance(60000);
  expect(autonomyRuns(r).length).toBe(reads);
});

const statusReads = (r: Rig) => autonomyRuns(r).filter((x) => action(x.argv) === 'status').length;

test('autonomy: a run armed through the CLI before session.start gets the band and exactly one stop toast', async ($, on) => {
  const r = rig(on);
  const s = stage(on);
  const table: Record<string, { exitCode: number; stdout: string }> = { status: { exitCode: 0, stdout: JSON.stringify(ACTIVE) } };
  answers(r, table);
  await $.session.start(start);
  await r.clock.advance(5000);
  expect(statusReads(r)).toBe(1);
  expect(s.bands.at(-1)).toBe('Orchestra autonomy: pass 2/5, deadline 07:30');
  expect(r.toasts.length).toBe(0);
  table['status'] = { exitCode: 0, stdout: JSON.stringify(STOPPED) };
  await r.clock.advance(30000);
  expect(r.toasts.length).toBe(1);
  expect(r.toasts[0]).toContain('cap-passes');
  expect(s.bands.at(-1)).toBeUndefined();
  const reads = statusReads(r);
  await r.clock.advance(120000);
  expect(statusReads(r)).toBe(reads);
  expect(r.toasts.length).toBe(1);
});

test('autonomy: an inactive session reads status once at startup and not again', async ($, on) => {
  const r = rig(on);
  const s = stage(on);
  answers(r, { status: { exitCode: 0, stdout: JSON.stringify({ ...STOPPED, last_stop_reason: null }) } });
  await $.session.start(start);
  await r.clock.advance(120000);
  expect(statusReads(r)).toBe(1);
  expect(r.toasts.length).toBe(0);
  expect(s.bands.at(-1)).toBeUndefined();
});

test('autonomy: a failed startup read is retried at the next interval until one answers', async ($, on) => {
  const r = rig(on);
  stage(on);
  const table: Record<string, { exitCode: number; stdout: string }> = { status: { exitCode: 1, stdout: '' } };
  answers(r, table);
  await $.session.start(start);
  await r.clock.advance(5000);
  expect(statusReads(r)).toBe(1);
  table['status'] = { exitCode: 0, stdout: JSON.stringify({ ...STOPPED, last_stop_reason: null }) };
  await r.clock.advance(30000);
  expect(statusReads(r)).toBe(2);
  await r.clock.advance(120000);
  expect(statusReads(r)).toBe(2);
});

test('autonomy: a Bash orchestra.py autonomy arm makes the next tick read status', async ($, on) => {
  const r = rig(on);
  const s = stage(on);
  const table: Record<string, { exitCode: number; stdout: string }> = { status: { exitCode: 0, stdout: JSON.stringify({ ...STOPPED, last_stop_reason: null }) } };
  answers(r, table);
  await $.session.start(start);
  await r.clock.advance(120000);
  expect(statusReads(r)).toBe(1);
  expect(s.bands.at(-1)).toBeUndefined();
  table['status'] = { exitCode: 0, stdout: JSON.stringify(ACTIVE) };
  await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'python3 ~/plugin/scripts/orchestra.py autonomy arm' });
  await r.clock.advance(5000);
  expect(statusReads(r)).toBe(2);
  expect(s.bands.at(-1)).toBe('Orchestra autonomy: pass 2/5, deadline 07:30');
  table['status'] = { exitCode: 0, stdout: JSON.stringify(STOPPED) };
  await r.clock.advance(30000);
  expect(r.toasts.length).toBe(1);
  // Other orchestra.py calls do not trigger a read.
  const reads = statusReads(r);
  await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'python3 ~/plugin/scripts/orchestra.py status' });
  await r.clock.advance(60000);
  expect(statusReads(r)).toBe(reads);
});

test('autonomy: clear and resume session.end keep polling alive', async ($, on) => {
  const r = rig(on);
  const s = stage(on);
  const table: Record<string, { exitCode: number; stdout: string }> = { status: { exitCode: 0, stdout: JSON.stringify(ACTIVE) } };
  answers(r, table);
  await $.session.start(start);
  await r.clock.advance(5000);
  expect(s.bands.at(-1)).toContain('pass 2/5');
  for (const reason of ['clear', 'resume']) {
    await $.session.end({ reason, sessionId: 'sid-1' } as never);
    expect(s.bands.at(-1)).toContain('pass 2/5');
    const before = statusReads(r);
    await r.clock.advance(35000);
    expect(statusReads(r)).toBeGreaterThan(before);
  }
  table['status'] = { exitCode: 0, stdout: JSON.stringify(STOPPED) };
  await r.clock.advance(35000);
  expect(r.toasts.length).toBe(1);
});

test('autonomy: a status read in flight when off runs is dropped: band stays cleared and no stop toast', async ($, on) => {
  const r = rig(on);
  const s = stage(on);
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => (release = resolve));
  let hold = true;
  r.runAnswer = async (argv) => {
    if (!isAutonomy(argv)) return { exitCode: 0, stdout: '{}' };
    if (action(argv) === 'status') {
      const snapshot = JSON.stringify(ACTIVE);
      if (hold) await held;
      return { exitCode: 0, stdout: snapshot };
    }
    if (action(argv) === 'arm') return { exitCode: 0, stdout: JSON.stringify({ active: true, ledger: '/l', preconditions: {} }) };
    return { exitCode: 0, stdout: JSON.stringify({ was_active: true, reason: 'disarmed', text: '' }) };
  };
  await $.session.start(start);
  await run($ as never, 'on');
  await r.clock.advance(5000);
  expect(statusReads(r)).toBe(1);
  await run($ as never, 'off');
  hold = false;
  release();
  await r.clock.advance(1000);
  expect(s.bands.at(-1)).toBeUndefined();
  await r.clock.advance(120000);
  expect(r.toasts.length).toBe(0);
  expect(s.bands.at(-1)).toBeUndefined();
});
