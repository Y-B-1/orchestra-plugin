import { expect, test } from 'claude-code/testing';
import type { On } from 'claude-code';

import { encode, rig, toBase64 } from './testkit.js';
import type { Rig } from './testkit.js';

const start = { cwd: '/work/proj', surface: null, isInteractive: false } as const;

function bottom(on: On, r: Rig) {
  const calls: { tool: string; command?: string; file_path?: string }[] = [];
  on('tool.call', async (_$, e) => {
    calls.push(e as never);
    return { result: { stdout: r.toolStdout, stderr: '' } } as never;
  });
  const offers: string[] = [];
  on('agent.offer', async (_$, e) => {
    offers.push((e as { agent: string }).agent);
    return { isOffered: true } as never;
  });
  const spawned: { prompt: string }[] = [];
  on('agent.spawn', async (_$, e) => {
    spawned.push(e as never);
    return { model: 'm', agentId: 'a1' } as never;
  });
  const registered: string[] = [];
  on('command.register', async (_$, e) => {
    registered.push((e as { name: string }).name);
    return { value: undefined } as never;
  });
  const opened: string[] = [];
  on('ui.open', async (_$, e) => {
    opened.push((e as { id: string }).id);
    return { value: { isPlaced: true } } as never;
  });
  on('ui.invalidate', async () => ({ value: undefined }) as never);
  return { calls, offers, spawned, registered, opened };
}

const deny = (reason: string) => `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":${JSON.stringify(reason)}}}`;

test('tool.call: git stash is denied in TypeScript with no Python run; git stash list runs', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  const denied = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git stash' });
  expect('deny' in denied).toBe(true);
  expect(b.calls.length).toBe(0);
  expect(r.runs.length).toBe(0);
  const ok = await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'git stash list' });
  expect('deny' in ok).toBe(false);
  expect(b.calls.length).toBe(1);
  expect(r.runs.length).toBe(0);
});

test('tool.call: a missing or non-string command denies', async ($, on) => {
  const r = rig(on);
  bottom(on, r);
  await $.session.start(start);
  const d = await $.tool.call({ tool: 'Bash', tool_use_id: 't1' } as never);
  expect('deny' in d).toBe(true);
});

test('tool.call: with the guard not ready (invalid rules) nothing is denied by the module', async ($, on) => {
  const r = rig(on, { files: { 'config/guard-rules.json': '{bad' } });
  const b = bottom(on, r);
  await $.session.start(start);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git stash' });
  expect('deny' in res).toBe(false);
  expect(b.calls.length).toBe(1);
});

test('tool.call: release and boundary commands delegate to Python and honor its deny', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  r.runAnswer = () => ({ exitCode: 0, stdout: deny('needs authorization') });
  await $.session.start(start);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git push origin main' });
  expect(res).toEqual({ deny: 'needs authorization' } as never);
  expect(b.calls.length).toBe(0);
  const run = r.runs.at(-1)!;
  expect(run.argv.slice(0, 1)).toEqual(['/bin/sh']);
  expect(run.argv.join(' ')).toContain('run-hook.sh PreToolUse --harness claude --from-mod');
  const stdin = JSON.parse(run.init!.stdin!);
  expect(stdin.tool_name).toBe('Bash');
  expect(stdin.tool_input.command).toBe('git push origin main');
  expect(stdin.cwd).toBe('/work/proj');
});

test('tool.call: a delegated allow reaches the tool', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  r.runAnswer = () => ({ exitCode: 0, stdout: '{}' });
  await $.session.start(start);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git push origin main' });
  expect('deny' in res).toBe(false);
  expect(b.calls.length).toBe(1);
});

test('tool.call: delegation fails closed on a bad exit, bad JSON or a thrown run', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  for (const answer of [
    () => ({ exitCode: 1, stdout: '' }),
    () => ({ exitCode: 0, stdout: 'not json' }),
    () => {
      throw new Error('spawn failed');
    },
  ]) {
    r.runAnswer = answer;
    const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git push origin main' });
    expect('deny' in res).toBe(true);
  }
  expect(b.calls.length).toBe(0);
});

test('tool.call: protected edits deny; settings.json and ordinary files pass', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  const denied = await $.tool.call({ tool: 'Edit', tool_use_id: 't1', file_path: '/work/proj/.claude/hooks.json' } as never);
  expect('deny' in denied).toBe(true);
  const marker = await $.tool.call({ tool: 'Write', tool_use_id: 't2', file_path: '/state/orchestra/mods/x.json' } as never);
  expect('deny' in marker).toBe(true);
  const ok = await $.tool.call({ tool: 'Edit', tool_use_id: 't3', file_path: '/work/proj/.claude/settings.json' } as never);
  expect('deny' in ok).toBe(false);
  const plain = await $.tool.call({ tool: 'Write', tool_use_id: 't4', file_path: '/work/proj/src/a.ts' } as never);
  expect('deny' in plain).toBe(false);
  expect(b.calls.length).toBe(2);
});

test('agent.offer: the orchestrator is not offered; others are', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  const o = await $.agent.offer({ agent: 'orchestra:orchestrator', description: 'd', source: 'plugin', provider: 'claude' } as never);
  expect(o).toEqual({ isOffered: false } as never);
  const p = await $.agent.offer({ agent: 'orchestra:builder', description: 'd', source: 'plugin', provider: 'claude' } as never);
  expect(p).toEqual({ isOffered: true } as never);
  expect(b.offers).toEqual(['orchestra:builder']);
});

function whereAnswer(r: Rig, standing: boolean) {
  r.runAnswer = (argv) => {
    if (argv.join(' ').includes('--cli where')) return { exitCode: 0, stdout: JSON.stringify({ repo: '/work/proj', state: '/s/state', standing_orders: standing }) };
    return { exitCode: 0, stdout: '{}' };
  };
}

test('agent.spawn: standing orders are appended verbatim with a sha256 line, once', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  whereAnswer(r, true);
  r.files['/s/state/standing-orders.md'] = 'Standing é\n';
  await $.session.start(start);
  await $.agent.spawn({ prompt: 'Do the work.', subagentType: 'orchestra:builder' } as never);
  const sha = '1b3529f2a81a1bae5918792efe0cdd5e81f09c20822665c26ecc449858d436b0';
  expect(b.spawned[0]!.prompt).toBe(`Do the work.\n\n## Standing orders (verbatim)\n\nStanding é\n\n\nsha256: ${sha}\n`);
  const again = b.spawned[0]!.prompt;
  await $.agent.spawn({ prompt: again, subagentType: 'orchestra:builder' } as never);
  expect(b.spawned[1]!.prompt).toBe(again);
  await $.agent.spawn({ prompt: 'x', subagentType: 'general-purpose' } as never);
  expect(b.spawned[2]!.prompt).toBe('x');
});

test('agent.spawn: no standing orders leaves the prompt alone and spawns are never refused', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  whereAnswer(r, false);
  await $.session.start(start);
  const res = await $.agent.spawn({ prompt: 'p', subagentType: 'orchestra:builder' } as never);
  expect('deny' in res).toBe(false);
  expect(b.spawned[0]!.prompt).toBe('p');
});

test('/orchestra-board is registered once and command.run opens the pane', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  r.runAnswer = () => ({ exitCode: 0, stdout: JSON.stringify({ version: 2, tasks: {}, session: null }) });
  await $.session.start(start);
  await $.session.start(start);
  expect(b.registered).toEqual(['orchestra-board']);
  await $.command.run({ command: 'orchestra-board', args: '' } as never);
  expect(b.opened).toEqual(['orchestra-board']);
});

test('verdict toasts: review, gate and accept receipts toast; other commands do not', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  r.toolStdout = JSON.stringify({ verdict: 'CLEAN' });
  await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'python3 scripts/orchestra.py review --task B5' });
  expect(r.toasts).toEqual(['Orchestra review: CLEAN']);
  r.toolStdout = JSON.stringify({ exit_code: 1 });
  await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'python3 x/orchestra.py --root r gate --id g' });
  expect(r.toasts.at(-1)).toBe('Orchestra gate: exit 1');
  r.toolStdout = 'not json';
  await $.tool.call({ tool: 'Bash', tool_use_id: 't3', command: 'python3 x/orchestra.py accept --task T' });
  r.toolStdout = JSON.stringify({ verdict: 'CLEAN' });
  await $.tool.call({ tool: 'Bash', tool_use_id: 't4', command: 'python3 x/orchestra.py status' });
  await $.tool.call({ tool: 'Bash', tool_use_id: 't5', command: 'echo hi' });
  expect(r.toasts.length).toBe(2);
  expect(b.calls.length).toBe(5);
  expect(toBase64(encode('é'))).toBe('w6k=');
});
