import { expect, test } from 'claude-code/testing';
import type { TestBody } from 'claude-code/testing';
import type { On } from 'claude-code';

import { RULES_JSON } from './fixtures/guard-fixtures.js';
import { classifyCommand, klassOf, loadRules } from './guard.js';
import { failClosed, isWindowsPath, thrownReason } from './orchestra.js';
import { deferred, encode, EXPECTED_DIGEST, flush, rig, toBase64 } from './testkit.js';
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

test('tool.call: a hard deny is decided in TypeScript with no Python run; git status runs', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  // session.start reads `where` for the guard mode; the guard itself runs no Python.
  const runs = r.runs.length;
  const denied = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git reset --hard' });
  expect('deny' in denied).toBe(true);
  expect(b.calls.length).toBe(0);
  expect(r.runs.length).toBe(runs);
  const forced = await $.tool.call({ tool: 'Bash', tool_use_id: 't3', command: 'git push --force origin x' });
  expect('deny' in forced).toBe(true);
  expect(b.calls.length).toBe(0);
  expect(r.runs.length).toBe(runs);
  const ok = await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'git status' });
  expect('deny' in ok).toBe(false);
  expect(b.calls.length).toBe(1);
  expect(r.runs.length).toBe(runs);
});

test('tool.call: a softened deny is delegated to Python, which honors its deny or allow', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  r.runAnswer = () => ({ exitCode: 0, stdout: deny('protect mode: git stash') });
  await $.session.start(start);
  for (const command of ['git stash', 'git stash list', 'git add -A', 'git commit --amend', 'git push --tags origin']) {
    const before = r.runs.length;
    const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command });
    expect(res).toEqual({ deny: 'Orchestra guard: protect mode: git stash' } as never);
    expect(r.runs.length).toBe(before + 1);
    expect(r.runs.at(-1)!.argv.join(' ')).toContain('run-hook.sh PreToolUse --harness claude --from-mod');
    expect(JSON.parse(r.runs.at(-1)!.init!.stdin!).tool_input.command).toBe(command);
  }
  expect(b.calls.length).toBe(0);
  r.runAnswer = () => ({ exitCode: 0, stdout: '{}' });
  const ok = await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'git stash' });
  expect('deny' in ok).toBe(false);
  expect(b.calls.length).toBe(1);
});

test('tool.call: a softened deny with a failed delegation denies', async ($, on) => {
  const r = rig(on);
  bottom(on, r);
  r.runAnswer = () => ({ exitCode: 1, stdout: '' });
  await $.session.start(start);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git stash' });
  expect('deny' in res).toBe(true);
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
  expect(res).toEqual({ deny: 'Orchestra guard: needs authorization' } as never);
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

test('merged-delete is delegated', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  r.runAnswer = () => ({ exitCode: 0, stdout: deny('Branch x is not merged into origin/main (no ancestor, tree or covering-branch evidence)') });
  await $.session.start(start);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git branch -D x' });
  expect(res).toEqual({ deny: 'Orchestra guard: Branch x is not merged into origin/main (no ancestor, tree or covering-branch evidence)' } as never);
  expect(b.calls.length).toBe(0);
  const stdin = JSON.parse(r.runs.at(-1)!.init!.stdin!);
  expect(stdin.tool_input.command).toBe('git branch -D x');
  r.runAnswer = () => ({ exitCode: 0, stdout: '{}' });
  const ok = await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'git push origin --delete x' });
  expect('deny' in ok).toBe(false);
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
    if (argv.includes('--cli') && argv.at(-1) === 'where') return { exitCode: 0, stdout: JSON.stringify({ repo: '/work/proj', state: '/s/state', standing_orders: standing }) };
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
  // B11 registers /orchestra-autonomy beside the board; autonomy.test.ts asserts that one.
  expect(b.registered.filter((n) => n === 'orchestra-board')).toEqual(['orchestra-board']);
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

/** Mirrors hooks.py _mod_is_live: Python skips only for a marker under 15 s old whose digest matches its own. */
function pythonSkips(r: Rig, sid: string): boolean {
  const last = r.of(sid).at(-1);
  if (last === undefined) return false;
  const age = r.clock.now() - last.json.heartbeat_ms;
  return last.json.heartbeat_ms > 0 && age >= 0 && age < 15000 && last.json.rules_sha256 === EXPECTED_DIGEST;
}

test('R5 F1: a re-fired session.start that throws hands git stash to the Python fallback', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  await r.clock.advance(5000);
  expect(pythonSkips(r, 'sid-1')).toBe(true);
  r.files['.claude-plugin/plugin.json'] = null;
  await $.session.start(start);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git stash' });
  // The module did not decide: the call went on to the classic hook, and that hook guards in full.
  expect('deny' in res).toBe(false);
  expect(b.calls.length).toBe(1);
  expect(pythonSkips(r, 'sid-1')).toBe(false);
  await r.clock.advance(5000);
  expect(pythonSkips(r, 'sid-1')).toBe(false);
});

// O24 (R5b): whenever the TypeScript guard is not ready, a guarded call is decided by Python through
// `--from-mod`, which guards in full whatever the marker says; a failed delegation denies.
const PY_DENY = 'python full guard: git stash';

function pythonDenies(r: Rig): void {
  r.runAnswer = (argv) => (argv.includes('--from-mod') ? { exitCode: 0, stdout: deny(PY_DENY) } : { exitCode: 0, stdout: '{}' });
}

function expectDelegated(r: Rig, b: { calls: unknown[] }, res: unknown, tool: string, key: string, value: string): void {
  expect(res).toEqual({ deny: 'Orchestra guard: ' + PY_DENY } as never);
  expect(b.calls.length).toBe(0);
  const run = r.runs.filter((x) => x.argv.includes('--from-mod')).at(-1);
  expect(run === undefined).toBe(false);
  expect(run!.argv.join(' ')).toContain('run-hook.sh PreToolUse --harness claude --from-mod');
  const stdin = JSON.parse(run!.init!.stdin!);
  expect(stdin.tool_name).toBe(tool);
  expect(stdin.tool_input[key]).toBe(value);
  expect(stdin.cwd).toBe('/work/proj');
}

const yieldTick = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

test('O24 PROBE A: a rejected zero write and a failed re-start: git stash is decided by Python', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  await r.clock.advance(5000);
  r.beforeWrite = async (w) => {
    if (w.json.heartbeat_ms === 0) throw new Error('EIO');
  };
  r.files['.claude-plugin/plugin.json'] = null;
  await $.session.start(start);
  pythonDenies(r);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git stash' });
  expectDelegated(r, b, res, 'Bash', 'command', 'git stash');
});

test('O24 PROBE B: a zero write hung past the 2 s wait and a failed re-start: git stash is decided by Python', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  await r.clock.advance(5000);
  const hold = deferred();
  r.beforeWrite = async (w) => {
    if (w.json.heartbeat_ms === 0) await hold.promise;
  };
  r.files['.claude-plugin/plugin.json'] = null;
  const s = $.session.start(start);
  for (let i = 0; i < 10; i++) {
    await yieldTick();
    await r.clock.advance(1000);
  }
  await s;
  pythonDenies(r);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git stash' });
  hold.resolve();
  expectDelegated(r, b, res, 'Bash', 'command', 'git stash');
});

test('O24 PROBE C: a fresh closure whose first start fails delegates git stash, never passes it on', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  r.files['.claude-plugin/plugin.json'] = null;
  await $.session.start(start);
  pythonDenies(r);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git stash' });
  expectDelegated(r, b, res, 'Bash', 'command', 'git stash');
});

test('O24: a closure that has seen no session.start delegates guarded calls and edits', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  pythonDenies(r);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git stash' });
  expectDelegated(r, b, res, 'Bash', 'command', 'git stash');
  const edit = await $.tool.call({ tool: 'Edit', tool_use_id: 't2', file_path: '/work/proj/.claude/hooks.json' } as never);
  expectDelegated(r, b, edit, 'Edit', 'file_path', '/work/proj/.claude/hooks.json');
});

test('O24: a guarded call during a start in progress waits, then is delegated when that start fails', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  const runs = r.runs.length;
  // The re-start is held at its first step: the zero write of the last marker does not land.
  const hold = deferred();
  r.beforeWrite = async (w) => {
    if (w.json.heartbeat_ms === 0) await hold.promise;
  };
  r.files['.claude-plugin/plugin.json'] = null;
  pythonDenies(r);
  const s = $.session.start(start);
  await yieldTick();
  let settled = false;
  const call = $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git stash' }).then((v) => {
    settled = true;
    return v;
  });
  for (let i = 0; i < 5; i++) await yieldTick();
  expect(settled).toBe(false);
  expect(b.calls.length).toBe(0);
  expect(r.runs.length).toBe(runs);
  for (let i = 0; i < 10; i++) {
    await yieldTick();
    await r.clock.advance(1000);
  }
  await s;
  const res = await call;
  hold.resolve();
  expectDelegated(r, b, res, 'Bash', 'command', 'git stash');
});

test('GF9: a NotebookEdit is a guarded call, delegated while the guard is not ready', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  pythonDenies(r);
  const res = await $.tool.call({ tool: 'NotebookEdit', tool_use_id: 't1', notebook_path: '/work/proj/n.ipynb' } as never);
  expectDelegated(r, b, res, 'NotebookEdit', 'notebook_path', '/work/proj/n.ipynb');
});

test('GF9: with the guard ready a NotebookEdit of the state denies and an ordinary notebook passes', async ($, on) => {
  const r = rig(on, { env: { XDG_STATE_HOME: '/state', HOME: '/home/x', ORCHESTRA_STATE_DIR: '/run/state' } });
  const b = bottom(on, r);
  await $.session.start(start);
  for (const path of ['/run/state/n.ipynb', '/run/state/state.json', '/state/orchestra/mods/n.ipynb']) {
    const denied = await $.tool.call({ tool: 'NotebookEdit', tool_use_id: 't1', notebook_path: path } as never);
    expect('deny' in denied).toBe(true);
  }
  const ok = await $.tool.call({ tool: 'NotebookEdit', tool_use_id: 't2', notebook_path: '/work/proj/n.ipynb' } as never);
  expect('deny' in ok).toBe(false);
  expect(b.calls.length).toBe(1);
});

test('O24: a failed or unparseable delegation denies; an unguarded tool is not delegated', async ($, on) => {
  const r = rig(on, { files: { 'config/guard-rules.json': '{bad' } });
  const b = bottom(on, r);
  await $.session.start(start);
  for (const answer of [
    () => ({ exitCode: 1, stdout: '' }),
    () => ({ exitCode: 0, stdout: 'not json' }),
    () => ({ exitCode: 0, stdout: '{"hookSpecificOutput": 3}' }),
    () => {
      throw new Error('spawn failed');
    },
  ]) {
    r.runAnswer = answer;
    const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git stash' });
    expect('deny' in res).toBe(true);
    const edit = await $.tool.call({ tool: 'Write', tool_use_id: 't2', file_path: '/work/proj/src/a.ts' } as never);
    expect('deny' in edit).toBe(true);
  }
  expect(b.calls.length).toBe(0);
  const before = r.runs.length;
  const read = await $.tool.call({ tool: 'Read', tool_use_id: 't3', file_path: '/work/proj/a' } as never);
  expect('deny' in read).toBe(false);
  expect(r.runs.length).toBe(before);
  expect(b.calls.length).toBe(1);
});

test('O24: with the guard ready, allowed calls reach the tool with no Python process', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  pythonDenies(r);
  await $.session.start(start);
  const runs = r.runs.length;
  const ok = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'echo hi' });
  const edit = await $.tool.call({ tool: 'Edit', tool_use_id: 't2', file_path: '/work/proj/src/a.ts' } as never);
  expect('deny' in ok).toBe(false);
  expect('deny' in edit).toBe(false);
  expect(b.calls.length).toBe(2);
  expect(r.runs.length).toBe(runs);
});

const PANE = { title: 'Orchestra board', isFocused: true, bodyColumns: 80, placement: 'inline', scroll: { offset: 0, bodyRows: 20 }, view: {} } as const;

function texts(node: unknown, out: string[] = []): string[] {
  if (typeof node === 'string') out.push(node);
  else if (Array.isArray(node)) for (const n of node) texts(n, out);
  else if (node !== null && typeof node === 'object') {
    const n = node as { props?: { children?: unknown }; children?: unknown };
    texts(n.props?.children, out);
    texts(n.children, out);
  }
  return out;
}

async function board($: Parameters<TestBody>[0], r: Rig, status: unknown): Promise<string[]> {
  r.runAnswer = () => ({ exitCode: 0, stdout: JSON.stringify(status) });
  await $.command.run({ command: 'orchestra-board', args: '' } as never);
  const ui = await $.ui.mount({ plugin: 'orchestra', surface: 'terminal', component: 'Pane', props: PANE as never, requestId: 'orchestra-board' });
  const drawn = texts(await ui.drawn());
  await ui.unmount();
  return drawn;
}

const TASKS = {
  A: { role: 'builder', mode: 'implementation', state: 'running', worker: 'w1' },
  B: { role: 'reviewer', mode: 'review', state: 'queued', worker: null },
  C: { role: 'builder', mode: 'repair', state: 'running', worker: 'w2' },
};

test('R5 F3 and O21: the board renders the session and autonomy flags and the running-card count', async ($, on) => {
  const r = rig(on);
  bottom(on, r);
  await $.session.start(start);
  // M1: the board reads the engine's `board --view`; its counts are the engine's.
  const cards = Object.entries(TASKS).map(([id, t], i) => ({ id, ...t, seq: i + 1 }));
  const off = await board($, r, boardView(cards, { session: { active: false, size: null }, autonomy: { active: false } }));
  expect(off).toContain('Session: inactive; autonomy: off; run 012345');
  expect(off).toContain('Counts: queued 1, running 2, reported 0, repairing 0, held 0, parked 0, accepted 0');
  const on2 = await board($, r, boardView(cards, { session: { active: true, size: 'large' }, autonomy: { active: true } }));
  expect(on2).toContain('Session: active (large); autonomy: on; run 012345');
  const none = await board($, r, boardView([], { session: null, autonomy: null }));
  expect(none).toContain('Session: inactive; autonomy: off; run 012345');
  expect(none).toContain('Counts: queued 0, running 0, reported 0, repairing 0, held 0, parked 0, accepted 0');
});

function whereRuns(r: Rig): number {
  return r.runs.filter((run) => run.argv.includes('--cli') && run.argv.at(-1) === 'where').length;
}

test('O21: a where result without standing orders is not cached; one with them is, until session.start', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  r.files['/s/state/standing-orders.md'] = 'Orders\n';
  whereAnswer(r, false);
  await $.session.start(start);
  await $.agent.spawn({ prompt: 'one', subagentType: 'orchestra:builder' } as never);
  expect(b.spawned[0]!.prompt).toBe('one');
  whereAnswer(r, true);
  await $.agent.spawn({ prompt: 'two', subagentType: 'orchestra:builder' } as never);
  expect(b.spawned[1]!.prompt).toContain('## Standing orders (verbatim)');
  // M1: session.start reads `where` once more, for the guard mode.
  expect(whereRuns(r)).toBe(3);
  await $.agent.spawn({ prompt: 'three', subagentType: 'orchestra:builder' } as never);
  expect(whereRuns(r)).toBe(3);
  whereAnswer(r, false);
  await $.session.start(start);
  await $.agent.spawn({ prompt: 'four', subagentType: 'orchestra:builder' } as never);
  expect(whereRuns(r)).toBe(5);
  expect(b.spawned[3]!.prompt).toBe('four');
});

// O20 (SPEC A5): the TypeScript classifier mirrors the five shapes the Python guard closes.
const O20_DENY = [
  'function f { git reset --hard; }; f',
  'function f() { git reset --hard; }',
  'function f () { git reset --hard; }',
  'coproc git reset --hard',
  'coproc NAME { git reset --hard; }',
  "coproc bash -c 'git reset --hard'",
  'echo `git reset --hard`',
  '`echo git reset --hard`',
  'x="`git reset --hard`"',
  'case `git reset --hard` in x) ;; esac',
  'if `git reset --hard`; then :; fi',
  "echo 'git reset --hard' | (cat) 2>/dev/null | bash",
  "echo 'git reset --hard' | (cd x; cat) 2>/dev/null | bash",
  "echo 'git reset --hard' | (cd x; cat) 2>&1 | bash",
  "echo 'git reset --hard' | (cd x; cat) >&1 | bash",
  "echo 'git reset --hard' | (cd x; cat) </dev/stdin | bash",
  'eval $(time case x in x) echo git reset --hard;; esac)',
  'eval "$(time case x in x) echo git reset --hard;; esac)"',
  'bash -c "$(time case x in x) echo git reset --hard;; esac)"',
  'eval "$(cat >/dev/null <<EOF\n)\nEOF\necho git reset --hard)"',
  "eval \"$(cat >/dev/null <<'EOF'\n)\nEOF\necho git reset --hard)\"",
  "bash -c \"$(cat >/dev/null <<'EOF'\n)\nEOF\necho git reset --hard)\"",
];

const O20_ALLOW = [
  'function f { echo hi; }; f',
  'coproc cat',
  'echo `date`',
  'cd `git rev-parse --show-toplevel`',
  'echo "`date`"',
  'echo hi | (cat) 2>/dev/null | bash',
  'eval "$(time case x in x) echo ok;; esac)"',
  "eval \"$(cat >/dev/null <<'EOF'\n)\nEOF\necho ok)\"",
  '{ eval "$(ssh-agent -s)"; }',
  'if git diff --quiet; then echo clean; fi',
  'ls | (cd x; wc -l)',
  'echo $((1+2))',
];

// O23 (SPEC A5): a command-position $(...) is scanned like a command-position backtick.
const O23_DENY = [
  '$(echo git reset --hard)',
  'x=1 $(echo git reset --hard)',
  '$(printf %s "git reset --hard")',
  '{ $(echo git reset --hard); }',
  'if true; then $(echo git reset --hard); fi',
];
const O23_ALLOW = ['$(which python3) -V', '"$(git rev-parse --show-toplevel)"/scripts/x.sh', 'echo $(date)', '$(echo ls)'];

test('O23: a command-position $(...) producing a destructive command denies', () => {
  loadRules(RULES_JSON);
  const wrong = O23_DENY.filter((c) => klassOf(classifyCommand(c)) !== 'deny');
  expect(wrong).toEqual([]);
});

test('O23: the benign command-position and argument substitutions allow', () => {
  loadRules(RULES_JSON);
  const wrong = O23_ALLOW.filter((c) => klassOf(classifyCommand(c)) !== 'allow');
  expect(wrong).toEqual([]);
});

test('O20: function/coproc, top-level backticks, redirected groups, time case and heredocs in $(...) deny', () => {
  loadRules(RULES_JSON);
  const wrong = O20_DENY.filter((c) => klassOf(classifyCommand(c)) !== 'deny');
  expect(wrong).toEqual([]);
});

test('O20: the benign shapes and controls still allow', () => {
  loadRules(RULES_JSON);
  const wrong = O20_ALLOW.filter((c) => klassOf(classifyCommand(c)) !== 'allow');
  expect(wrong).toEqual([]);
});

// SPEC 5.16 items 1, 2, 4 and 8 (M1). The fake `$` models Node: a spawn whose cwd is gone throws ENOENT.
const enoent = () => Object.assign(new Error('spawn /bin/sh ENOENT'), { code: 'ENOENT' });
const GONE = '/work/gone';
const MISSING_CWD = 'Session directory no longer exists: cd to an existing directory, then retry';
const rootOf = (argv: readonly string[]) => argv[1]!.replace(/\/scripts\/run-hook\.sh$/, '');

/** Answers like a machine where `gone` no longer exists: a spawn there throws, `test -d` fails. */
function goneAnswer(r: Rig, gone: string) {
  r.runAnswer = (argv, init) => {
    if (init?.cwd === gone) throw enoent();
    if (argv[1] === '-c') return { exitCode: argv.at(-1) === gone ? 1 : 0, stdout: '' };
    return { exitCode: 0, stdout: '{}' };
  };
}

test('delegate spawns the hook from the plugin root when the session cwd is gone', async ($, on) => {
  const r = rig(on, { cwd: GONE });
  const b = bottom(on, r);
  goneAnswer(r, GONE);
  await $.session.start(start);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git push origin main' });
  expect('deny' in res).toBe(false);
  expect(b.calls.length).toBe(1);
  const run = r.runs.find((x) => x.argv.includes('--from-mod'))!;
  expect(run.init!.cwd).toBe(rootOf(run.argv));
  expect(JSON.parse(run.init!.stdin!).cwd).toBe(GONE);
});

test('cli reads pass --repo and keep their spawn cwd', async ($, on) => {
  const r = rig(on);
  bottom(on, r);
  whereAnswer(r, false);
  await $.session.start(start);
  await $.agent.spawn({ prompt: 'p', subagentType: 'orchestra:builder' } as never);
  await $.command.run({ command: 'orchestra-autonomy', args: 'status' } as never);
  await $.command.run({ command: 'orchestra-board', args: '' } as never);
  const cli = r.runs.filter((x) => x.argv.includes('--cli'));
  const tails = cli.map((x) => x.argv.slice(x.argv.indexOf('--cli')).join(' '));
  expect(tails).toContain('--cli --repo /work/proj where');
  expect(tails).toContain('--cli --repo /work/proj autonomy status');
  expect(tails).toContain('--cli --repo /work/proj board --view --session sid-1');
  for (const x of cli) expect(x.init!.cwd).toBe('/work/proj');
});

test('cli reads name a missing session directory instead of spawning it', async ($, on) => {
  const r = rig(on, { cwd: GONE });
  bottom(on, r);
  goneAnswer(r, GONE);
  await $.session.start(start);
  const res = (await $.command.run({ command: 'orchestra-autonomy', args: 'status' } as never)) as { text: string };
  expect(res.text).toContain(MISSING_CWD);
  const spawn = await $.agent.spawn({ prompt: 'p', subagentType: 'orchestra:builder' } as never);
  expect('deny' in spawn).toBe(false);
});

test('delegate failure reason names the failure class', async ($, on) => {
  const r = rig(on);
  bottom(on, r);
  await $.session.start(start);
  const reasonFor = async (answer: () => { exitCode: number; stdout: string }) => {
    r.runAnswer = answer;
    const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git push origin main' });
    return (res as { deny: string }).deny;
  };
  expect(await reasonFor(() => ({ exitCode: 3, stdout: '' }))).toBe('Orchestra guard error (exit 3); failing closed');
  // The fake `$` turns a thrown run into a HooksError without a code, so the class is the spawn class.
  expect(await reasonFor(() => { throw enoent(); })).toMatch(/^Orchestra guard error \(spawn: [A-Z]+\); failing closed$/);
  expect(await reasonFor(() => ({ exitCode: 0, stdout: 'not json' }))).toBe('Orchestra guard error (bad output); failing closed');
  // The fake cannot carry a thrown error's code or message; these two read them directly.
  expect(thrownReason(enoent())).toBe('Orchestra guard error (spawn: ENOENT); failing closed');
  expect(thrownReason(new Error('process timed out after 8000ms'))).toBe('Orchestra guard error (timeout); failing closed');
  expect(failClosed('timeout', '')).toBe('Orchestra guard error (timeout); failing closed');
});

test('delegate surfaces the reason of an exit-2 deny', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  r.runAnswer = () => ({ exitCode: 2, stdout: deny('Missing shell command') });
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git push origin main' });
  expect(res).toEqual({ deny: 'Orchestra guard: Missing shell command' } as never);
  r.runAnswer = () => ({ exitCode: 2, stdout: '' });
  const bare = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git push origin main' });
  expect(bare).toEqual({ deny: 'Orchestra guard error (exit 2); failing closed' } as never);
  expect(b.calls.length).toBe(0);
});

test('delegate passes an ask on to the native hook instead of deciding it', async ($, on) => {
  const r = rig(on);
  const b = bottom(on, r);
  await $.session.start(start);
  const ask = JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'ask', permissionDecisionReason: 'approve?' } });
  r.runAnswer = () => ({ exitCode: 0, stdout: ask });
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git push origin main' });
  expect((res as { deny?: string }).deny).toBeUndefined();
  expect(b.calls.length).toBe(1);
});

test('isWindowsPath: drive letters and backslashes read as Windows, POSIX paths do not', async () => {
  expect(isWindowsPath('C:\\Users\\a\\plugin')).toBe(true);
  expect(isWindowsPath('c:/Users/a/plugin')).toBe(true);
  expect(isWindowsPath('/home/a/plugin')).toBe(false);
  expect(isWindowsPath('/Users/a/My Plugin')).toBe(false);
});

// M1: the live board, worker links, the native task mirror and the guard `minimal` fast path.
const RUN_ID = '0123456789abcdef';
const COUNTS = { queued: 0, running: 0, reported: 0, repairing: 0, held: 0, parked: 0, accepted: 0 };
type CardIn = { id: string; state: string; seq: number; worker?: string | null; dependencies?: string[]; started_at?: number | null };

function boardView(cards: CardIn[], extra: Record<string, unknown> = {}) {
  const counts: Record<string, number> = { ...COUNTS };
  for (const c of cards) counts[c.state] = (counts[c.state] ?? 0) + 1;
  return {
    run_id: RUN_ID,
    session: { active: true, size: 'medium' },
    bound: true,
    autonomy: { active: false },
    counts,
    columns: {},
    cards: cards.map((c) => ({ role: 'builder', mode: 'implementation', worker: null, inline: false, dependencies: [], deps_open: [], review_of: [], files: [], started_at: null, ...c })),
    startable_now: [],
    next_wave: [],
    latest_review: null,
    latest_gate: null,
    pull_requests: [],
    guard_mode: 'minimal',
    ...extra,
  };
}

type Engine = { view: unknown; viewFails: boolean; where: Record<string, unknown>; status: Record<string, unknown>; fromMod: string };

/** Answers the CLI like the engine: `board --view`, `where`, `autonomy status` and the PreToolUse hook. */
function engine(r: Rig, init: Partial<Engine> = {}): Engine {
  const e: Engine = { view: boardView([]), viewFails: false, where: { repo: '/work/proj', state: '/s/state', standing_orders: false }, status: { active: false, last_stop_reason: null, parked: [] }, fromMod: '{}', ...init };
  r.runAnswer = (argv) => {
    if (argv.includes('--from-mod')) return { exitCode: 0, stdout: e.fromMod };
    if (argv.includes('board')) return e.viewFails ? { exitCode: 1, stdout: '' } : { exitCode: 0, stdout: JSON.stringify(e.view) };
    if (argv.at(-1) === 'where') return { exitCode: 0, stdout: JSON.stringify(e.where) };
    if (argv.includes('autonomy')) return { exitCode: 0, stdout: JSON.stringify(e.status) };
    return { exitCode: 0, stdout: '{}' };
  };
  return e;
}

const boardRuns = (r: Rig) => r.runs.filter((x) => x.argv.includes('board'));
const fromModRuns = (r: Rig) => r.runs.filter((x) => x.argv.includes('--from-mod'));

type Native = { id: string; subject: string; status: string; owner?: string; blockedBy: string[] };

/** The session around the module: the tool, Claude Code's task tools, agents and the UI ops. */
function stage(on: On, r: Rig, opts: { tools?: string[]; decision?: string } = {}) {
  const tasks: Native[] = [];
  const taskCalls: Record<string, unknown>[] = [];
  const calls: Record<string, unknown>[] = [];
  const failUpdates = new Set<string>();
  const agents: { id: string; status: string }[] = [];
  const checks: unknown[] = [];
  let nextId = 1;
  on('tool.call', async (_$, ev) => {
    const e = ev as unknown as Record<string, unknown>;
    const tool = String(e['tool']);
    if (tool === 'TaskList') {
      taskCalls.push(e);
      return { result: { tasks: tasks.map((t) => ({ ...t, blockedBy: [...t.blockedBy] })) }, text: '' } as never;
    }
    if (tool === 'TaskCreate') {
      taskCalls.push(e);
      const t = { id: String(nextId++), subject: String(e['subject']), status: 'pending', blockedBy: [] };
      tasks.push(t);
      return { result: { task: { id: t.id, subject: t.subject } }, text: '' } as never;
    }
    if (tool === 'TaskUpdate') {
      taskCalls.push(e);
      const t = tasks.find((x) => x.id === e['taskId']);
      if (t === undefined || failUpdates.has(t.id)) return { result: { success: false, taskId: String(e['taskId']), updatedFields: [], error: 'Task not found' }, text: '' } as never;
      if (typeof e['status'] === 'string') t.status = e['status'];
      if (typeof e['owner'] === 'string') t.owner = e['owner'];
      if (Array.isArray(e['addBlockedBy'])) t.blockedBy.push(...(e['addBlockedBy'] as string[]));
      return { result: { success: true, taskId: t.id, updatedFields: [] }, text: '' } as never;
    }
    calls.push(e);
    return { result: { stdout: r.toolStdout, stderr: '' } } as never;
  });
  on('tool.list', async () => ({ value: (opts.tools ?? ['Bash', 'TaskCreate', 'TaskUpdate', 'TaskList']).map((name) => ({ name, description: '', mcp: false })) }) as never);
  on('tool.check', async (_$, e) => {
    checks.push(e);
    return { decision: opts.decision ?? 'allow' } as never;
  });
  on('agent.list', async () => ({ value: agents.map((a) => ({ ...a, description: '', type: 'orchestra:builder' })) }) as never);
  const spawned: { prompt: string }[] = [];
  let agentId = 'a1';
  on('agent.spawn', async (_$, e) => {
    spawned.push(e as never);
    return { model: 'm', agentId } as never;
  });
  on('turn.complete', async () => ({ text: '' }) as never);
  const registered: string[] = [];
  on('command.register', async (_$, e) => {
    registered.push((e as { name: string }).name);
    return { value: undefined } as never;
  });
  on('ui.open', async () => ({ value: { isPlaced: true } }) as never);
  on('ui.close', async () => ({ value: undefined }) as never);
  on('ui.invalidate', async () => ({ value: undefined }) as never);
  return {
    tasks, taskCalls, calls, failUpdates, agents, checks, spawned, registered,
    setAgentId: (id: string) => {
      agentId = id;
    },
  };
}

async function openBoard($: Parameters<TestBody>[0]): Promise<void> {
  await $.command.run({ command: 'orchestra-board', args: '' } as never);
}

async function drawBoard($: Parameters<TestBody>[0], surface: 'terminal' | 'desktop' | 'mobile', bodyColumns: number) {
  return $.ui.mount({ plugin: 'orchestra', surface, component: 'Pane', props: { ...PANE, bodyColumns } as never, requestId: 'orchestra-board' });
}

test('board: registered and readable when the guard is not ready', async ($, on) => {
  const r = rig(on, { files: { 'config/guard-rules.json': '{bad' } });
  const s = stage(on, r);
  engine(r, { view: boardView([{ id: 'A', state: 'queued', seq: 1 }]) });
  await $.session.start(start);
  expect(s.registered).toContain('orchestra-board');
  await openBoard($);
  const ui = await drawBoard($, 'terminal', 120);
  expect(texts(await ui.drawn()).some((t) => t.startsWith('A builder/implementation'))).toBe(true);
  await ui.unmount();
});

test('board: reads board --view for this session; wide panes lay columns side by side, narrow and mobile stack', async ($, on) => {
  const r = rig(on);
  stage(on, r);
  engine(r, { view: boardView([{ id: 'B10', state: 'queued', seq: 10 }, { id: 'B2', state: 'queued', seq: 2 }]) });
  await $.session.start(start);
  await openBoard($);
  const run = boardRuns(r).at(-1)!;
  expect(run.argv.slice(run.argv.indexOf('--cli'))).toEqual(['--cli', '--repo', '/work/proj', 'board', '--view', '--session', 'sid-1']);
  const wide = await drawBoard($, 'terminal', 120);
  expect((await wide.find({ key: 'columns' })) !== undefined).toBe(true);
  const lines = texts(await wide.drawn()).filter((t) => /^B\d+ /.test(t));
  expect(lines.map((l) => l.split(' ')[0])).toEqual(['B2', 'B10']);
  await wide.unmount();
  const narrow = await drawBoard($, 'terminal', 80);
  expect((await narrow.find({ key: 'columns' })) === undefined).toBe(true);
  expect((await narrow.find({ key: 'stacked' })) !== undefined).toBe(true);
  await narrow.unmount();
  const phone = await drawBoard($, 'mobile', 200);
  expect((await phone.find({ key: 'stacked' })) !== undefined).toBe(true);
  await phone.unmount();
});

test('board: a failed refresh keeps the last good data and shows stale since', async ($, on) => {
  const r = rig(on);
  stage(on, r);
  const e = engine(r, { view: boardView([{ id: 'A', state: 'running', seq: 1 }]) });
  await $.session.start(start);
  await openBoard($);
  const ui = await drawBoard($, 'terminal', 80);
  expect(texts(await ui.drawn()).some((t) => t.startsWith('updated '))).toBe(true);
  e.viewFails = true;
  await ui.press({ key: 'refresh' });
  await flush();
  expect(boardRuns(r).length).toBe(2);
  await ui.unmount();
  // A fresh draw reads what the failed refresh left (the kit's redraw of the press's unawaited work is not awaited).
  const again = await drawBoard($, 'terminal', 80);
  const drawn = texts(await again.drawn());
  expect(drawn.some((t) => t.startsWith('A builder/implementation'))).toBe(true);
  expect(drawn.some((t) => /^stale since \d\d:\d\d:\d\d/.test(t))).toBe(true);
  await again.unmount();
});

test('board: refreshes after an orchestra.py Bash call, an orchestra spawn and a subagent turn; never on a 5 s poll', async ($, on) => {
  const r = rig(on);
  stage(on, r);
  engine(r);
  await $.session.start(start);
  await openBoard($);
  const opened = boardRuns(r).length;
  await r.clock.advance(5000);
  expect(boardRuns(r).length).toBe(opened);
  await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'echo hi' });
  await flush();
  expect(boardRuns(r).length).toBe(opened);
  await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'python3 x/orchestra.py status' });
  await flush();
  expect(boardRuns(r).length).toBe(opened + 1);
  await $.agent.spawn({ prompt: 'Worker orchestra-B2, token t.', subagentType: 'orchestra:builder' } as never);
  await flush();
  expect(boardRuns(r).length).toBe(opened + 2);
  await $.turn.complete({ answer: '', durationMs: 1, isAborted: false, turnId: 'u1', agentId: 'a1', reason: 'answer' } as never);
  await flush();
  expect(boardRuns(r).length).toBe(opened + 3);
  await $.turn.complete({ answer: '', durationMs: 1, isAborted: false, turnId: 'u2', reason: 'answer' } as never);
  await flush();
  expect(boardRuns(r).length).toBe(opened + 3);
});

test('board: an orchestra.py call with the guard not ready also refreshes', async ($, on) => {
  const r = rig(on, { files: { 'config/guard-rules.json': '{bad' } });
  stage(on, r);
  engine(r);
  await $.session.start(start);
  const before = boardRuns(r).length;
  await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'python3 x/orchestra.py status' });
  await flush();
  expect(boardRuns(r).length).toBe(before + 1);
});

test('board: a 30 s fallback refreshes while the pane is open; session.end stops it', async ($, on) => {
  const r = rig(on);
  stage(on, r);
  engine(r);
  await $.session.start(start);
  await openBoard($);
  const opened = boardRuns(r).length;
  await r.clock.advance(30000);
  await flush();
  expect(boardRuns(r).length).toBe(opened + 1);
  await $.session.end({ reason: 'other', sessionId: 'sid-1' } as never);
  await r.clock.advance(60000);
  await flush();
  expect(boardRuns(r).length).toBe(opened + 1);
});

test('worker links: a spawned worker links its card; agent status, a failed mark and a workflow run show on the card', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r);
  engine(r, { view: boardView([{ id: 'B2', state: 'running', seq: 2 }, { id: 'B3', state: 'running', seq: 3 }]) });
  await $.session.start(start);
  await $.agent.spawn({ prompt: 'Mode: implementation\nWorker orchestra-B2, assignment token t.', subagentType: 'orchestra:builder' } as never);
  s.setAgentId('a2');
  await $.agent.spawn({ prompt: '# B3: the pane\nMode: implementation', subagentType: 'orchestra:builder', workflow: { runId: 'wf_7', agentIndex: 1 } } as never);
  s.agents.push({ id: 'a1', status: 'failed' });
  await openBoard($);
  const ui = await drawBoard($, 'terminal', 80);
  const drawn = texts(await ui.drawn());
  expect(drawn).toContain('B2 builder/implementation - agent failed !');
  expect(drawn).toContain('B3 builder/implementation - workflow wf_7');
  await ui.unmount();
});

const subj = (id: string) => `[012345] ${id} builder/implementation`;

test('native tasks: cards are mirrored once, then only changed fields are sent, with blockedBy once both exist', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r);
  const e = engine(r, { view: boardView([{ id: 'A', state: 'queued', seq: 1 }, { id: 'B', state: 'queued', seq: 2, dependencies: ['A'] }]) });
  await $.session.start(start);
  await openBoard($);
  await flush();
  expect(s.tasks.map((t) => [t.subject, t.status, t.blockedBy])).toEqual([[subj('A'), 'pending', []], [subj('B'), 'pending', ['1']]]);
  e.view = boardView([{ id: 'A', state: 'running', seq: 1, worker: 'w1' }, { id: 'B', state: 'queued', seq: 2, dependencies: ['A'] }]);
  s.taskCalls.length = 0;
  await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'python3 x/orchestra.py start --task A' });
  await flush();
  expect(s.taskCalls.filter((c) => c['tool'] === 'TaskUpdate').map((c) => [c['taskId'], c['status'], c['owner']])).toEqual([['1', 'in_progress', 'w1']]);
  s.taskCalls.length = 0;
  await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'python3 x/orchestra.py status' });
  await flush();
  expect(s.taskCalls.map((c) => c['tool'])).toEqual(['TaskList']);
  expect(s.tasks.length).toBe(2);
});

test('native tasks: off when the task tools are missing, and when the session is not bound', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r, { tools: ['Bash'] });
  const e = engine(r, { view: boardView([{ id: 'A', state: 'queued', seq: 1 }]) });
  await $.session.start(start);
  await openBoard($);
  await flush();
  expect(s.taskCalls.length).toBe(0);
  const ui = await drawBoard($, 'terminal', 80);
  expect(texts(await ui.drawn()).some((t) => t.startsWith('Native tasks: off'))).toBe(true);
  await ui.unmount();
  e.view = boardView([{ id: 'A', state: 'queued', seq: 1 }], { bound: false });
  await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'python3 x/orchestra.py status' });
  await flush();
  expect(s.taskCalls.length).toBe(0);
});

test('native tasks: not bound to this session keeps sync off even with the tools allowed', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r);
  engine(r, { view: boardView([{ id: 'A', state: 'queued', seq: 1 }], { bound: false }) });
  await $.session.start(start);
  await openBoard($);
  await flush();
  expect(s.taskCalls.length).toBe(0);
  const ui = await drawBoard($, 'terminal', 80);
  expect(texts(await ui.drawn())).toContain('Native tasks: off (this session does not own the run)');
  await ui.unmount();
});

test('native tasks: a permission check that is not allow keeps sync off and raises no dialog', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r, { decision: 'ask' });
  engine(r, { view: boardView([{ id: 'A', state: 'queued', seq: 1 }]) });
  await $.session.start(start);
  await openBoard($);
  await flush();
  expect(s.checks.length > 0).toBe(true);
  expect(s.taskCalls.length).toBe(0);
});

test('native tasks: a deleted task is never re-created and a failed update drops its card', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r);
  const e = engine(r, { view: boardView([{ id: 'A', state: 'queued', seq: 1 }, { id: 'B', state: 'queued', seq: 2 }]) });
  await $.session.start(start);
  await openBoard($);
  await flush();
  expect(s.tasks.length).toBe(2);
  s.tasks.splice(0, 1);
  s.failUpdates.add('2');
  e.view = boardView([{ id: 'A', state: 'running', seq: 1 }, { id: 'B', state: 'running', seq: 2 }]);
  s.taskCalls.length = 0;
  await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'python3 x/orchestra.py status' });
  await flush();
  expect(s.taskCalls.filter((c) => c['tool'] === 'TaskCreate')).toEqual([]);
  expect(s.taskCalls.filter((c) => c['tool'] === 'TaskUpdate').map((c) => c['taskId'])).toEqual(['2']);
  e.view = boardView([{ id: 'A', state: 'accepted', seq: 1 }, { id: 'B', state: 'accepted', seq: 2 }]);
  s.taskCalls.length = 0;
  await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'python3 x/orchestra.py status' });
  await flush();
  expect(s.taskCalls.map((c) => c['tool'])).toEqual(['TaskList']);
});

test('native tasks: after a reload the existing tasks are matched by subject, not duplicated', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r);
  s.tasks.push({ id: '9', subject: subj('A'), status: 'in_progress', owner: 'w1', blockedBy: [] });
  engine(r, { view: boardView([{ id: 'A', state: 'running', seq: 1, worker: 'w1' }, { id: 'B', state: 'queued', seq: 2 }]) });
  await $.session.start(start);
  await openBoard($);
  await flush();
  expect(s.taskCalls.filter((c) => c['tool'] === 'TaskCreate').map((c) => c['subject'])).toEqual([subj('B')]);
  expect(s.taskCalls.filter((c) => c['tool'] === 'TaskUpdate')).toEqual([]);
});

async function minimalSession($: Parameters<TestBody>[0], r: Rig, autonomyActive: boolean): Promise<Engine> {
  const e = engine(r, { where: { repo: '/work/proj', state: '/s/state', standing_orders: false, guard_mode: 'minimal' }, status: { active: autonomyActive, last_stop_reason: null, parked: [] }, fromMod: deny(PY_DENY) });
  await $.session.start(start);
  await $.command.run({ command: 'orchestra-autonomy', args: 'status' } as never);
  return e;
}

test('guard minimal: a destructive git command passes to Claude Code without classification or Python', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r);
  await minimalSession($, r, false);
  const res = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git reset --hard' });
  expect('deny' in res).toBe(false);
  expect(s.calls.length).toBe(1);
  expect(fromModRuns(r).length).toBe(0);
});

test('guard minimal: an engine state write by shell is decided by Python; a state-file edit still denies', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r);
  await minimalSession($, r, false);
  const plain = await $.tool.call({ tool: 'Bash', tool_use_id: 't0', command: 'rm -rf build' });
  expect('deny' in plain).toBe(false);
  expect(fromModRuns(r).length).toBe(0);
  const shell = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'rm -rf ~/.local/state/orchestra' });
  expect(shell).toEqual({ deny: 'Orchestra guard: ' + PY_DENY } as never);
  expect(fromModRuns(r).length).toBe(1);
  const ledger = await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'echo x > "$ORCHESTRA_STATE_DIR/ledger.md"' });
  expect(ledger).toEqual({ deny: 'Orchestra guard: ' + PY_DENY } as never);
  const edit = await $.tool.call({ tool: 'Write', tool_use_id: 't3', file_path: '/state/orchestra/mods/x.json' } as never);
  expect('deny' in edit).toBe(true);
  expect(s.calls.length).toBe(1);
});

test('guard minimal: after a stopped run the mod never denies on its own; Python decides with the lock state', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r);
  const e = await minimalSession($, r, false);
  e.fromMod = '{}';
  e.status = { active: false, last_stop_reason: 'deadline', parked: [] };
  await $.command.run({ command: 'orchestra-autonomy', args: 'status' } as never);
  const reset = await $.tool.call({ tool: 'Bash', tool_use_id: 'm1', command: 'git reset --hard' });
  expect('deny' in reset).toBe(false);
  expect(s.calls.length).toBe(1);
});

test('guard minimal: with autonomy active, after a stopped run, or before the first status read, commands are classified as before', async ($, on) => {
  const r = rig(on);
  const s = stage(on, r);
  const e = await minimalSession($, r, false);
  const off = await $.tool.call({ tool: 'Bash', tool_use_id: 't0', command: 'git reset --hard' });
  expect('deny' in off).toBe(false);
  e.status = { active: true, last_stop_reason: null, parked: [] };
  await $.command.run({ command: 'orchestra-autonomy', args: 'status' } as never);
  const active = await $.tool.call({ tool: 'Bash', tool_use_id: 't1', command: 'git reset --hard' });
  expect('deny' in active).toBe(true);
  const stash = await $.tool.call({ tool: 'Bash', tool_use_id: 't2', command: 'git stash' });
  expect(stash).toEqual({ deny: 'Orchestra guard: ' + PY_DENY } as never);
  e.status = { active: false, last_stop_reason: 'deadline', parked: [] };
  await $.command.run({ command: 'orchestra-autonomy', args: 'status' } as never);
  const stopped = await $.tool.call({ tool: 'Bash', tool_use_id: 't3', command: 'git reset --hard' });
  expect('deny' in stopped).toBe(true);
  await $.session.start(start);
  const unknown = await $.tool.call({ tool: 'Bash', tool_use_id: 't4', command: 'git reset --hard' });
  expect('deny' in unknown).toBe(true);
  expect(s.calls.length).toBe(1);
});
