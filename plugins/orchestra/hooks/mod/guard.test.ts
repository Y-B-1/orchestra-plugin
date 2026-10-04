import { expect, test } from 'claude-code/testing';

import { CORPUS, RULES_JSON } from './fixtures/guard-fixtures.js';
import { O17_CASES } from './fixtures/o17-cases.js';
import { classifyCommand, editDenied, klassOf, loadRules } from './guard.js';
import { GUARD_DIGEST_FILES, guardDigest } from './marker.js';

loadRules(RULES_JSON);

type Case = { id: string; input: unknown; class: string; category?: string };

function run(cases: Case[]): string[] {
  const wrong: string[] = [];
  for (const c of cases) {
    const input = c.input as { command?: string; tool?: string; path?: string; cwd?: string };
    if (typeof input.command === 'string') {
      const d = classifyCommand(input.command);
      const klass = klassOf(d);
      if (klass !== c.class || (d.boundary ?? undefined) !== c.category) {
        wrong.push(`${c.id}: want ${c.class}/${c.category ?? ''} got ${klass}/${d.boundary ?? ''} for ${JSON.stringify(input.command)}`);
      }
    } else {
      const denied = editDenied(input.path, input.cwd ?? '/', { stateDir: null, xdg: '/tmp/b5-state', home: '/home/u' });
      if ((denied ? 'deny' : 'allow') !== c.class) wrong.push(`${c.id}: want ${c.class} got ${denied ? 'deny' : 'allow'} for ${JSON.stringify(input)}`);
    }
  }
  return wrong;
}

test('corpus parity: every guard-corpus.json case gets the Python verdict', () => {
  expect(CORPUS.length).toBeGreaterThan(300);
  expect(run(CORPUS as Case[])).toEqual([]);
});

test('corpus parity: O17 cases (reserved words, groups, arithmetic, case patterns)', () => {
  expect(O17_CASES.length).toBeGreaterThan(50);
  expect(run(O17_CASES as Case[])).toEqual([]);
});

test('corpus carries the B2-r2, B2-r3 and O16 cases the brief names', () => {
  const ids = CORPUS.map((c) => c.id).join(' ');
  expect(ids).toContain('inline-r2b');
  expect(ids).toContain('inline-r3');
  expect(CORPUS.some((c) => (c.input as { command?: string }).command?.includes('xargs bash -c') === true)).toBe(true);
});

test('classifier: malformed input denies, size and depth caps', () => {
  expect(klassOf(classifyCommand(''))).toBe('deny');
  expect(klassOf(classifyCommand('   '))).toBe('deny');
  expect(classifyCommand('echo "unterminated').category).toBe('malformed');
  expect(classifyCommand('cat <<EOF\nno end').reason).toBe('Malformed heredoc');
  expect(klassOf(classifyCommand('echo ' + 'a'.repeat(131100)))).toBe('deny');
  expect(klassOf(classifyCommand('git stash'))).toBe('deny');
  expect(klassOf(classifyCommand('git stash list'))).toBe('deny');
  expect(klassOf(classifyCommand('git stash show -p stash@{1}'))).toBe('deny');
  expect(klassOf(classifyCommand('git add --no-ignore-removal'))).toBe('deny');
  expect(klassOf(classifyCommand("git add '*'"))).toBe('deny');
  expect(klassOf(classifyCommand('git add ../'))).toBe('deny');
  expect(klassOf(classifyCommand('git add -vA'))).toBe('deny');
  expect(klassOf(classifyCommand('git add ./src/x.ts'))).toBe('allow');
  expect(klassOf(classifyCommand('git commit -m "never run git add -A or git stash"'))).toBe('allow');
});

test('FX6: crafted nested shells deny well inside the hook timeout (reading budget)', () => {
  const quote = (text: string): string => "'" + text.replace(/'/g, `'"'"'`) + "'";
  const nested = (levels: number, width: number): string => {
    let body = 'git status';
    for (let i = 0; i < levels; i++) body = 'sudo -u $(a) x ' + Array(width).fill('$(b) bash -c ' + quote(body)).join(' ');
    return body + '; git ' + 'reset --hard';
  };
  for (const [levels, width] of [[5, 2], [4, 4], [6, 2], [5, 3]] as const) {
    const start = performance.now();
    const decision = classifyCommand(nested(levels, width));
    expect(performance.now() - start).toBeLessThan(5000);
    expect(klassOf(decision)).toBe('deny');
  }
});

test('FX6: a wrapper option substitution before a dash word is dropped as a reading, not denied', () => {
  expect(klassOf(classifyCommand('xargs -P $(nproc) make -s'))).toBe('allow');
  expect(klassOf(classifyCommand('sudo -u $(whoami) df -h'))).toBe('allow');
  expect(klassOf(classifyCommand('sudo -u $(whoami) git ' + 'reset --hard'))).toBe('deny');
});

test('A8: settings.json is not protected; hooks.json, config.toml and .orchestra are', () => {
  const env = { stateDir: null, xdg: '/state', home: '/home/u' };
  for (const p of ['.claude/settings.json', '.claude/settings.local.json']) {
    expect(editDenied(p, '/work', env)).toBe(false);
  }
  for (const p of ['.claude/hooks.json', '.claude/config.toml', '.orchestra/x']) {
    expect(editDenied(p, '/work', env)).toBe(true);
  }
  expect(editDenied('.claude/agents/orchestra-builder.md', '/work', env)).toBe(true);
  expect(editDenied('.claude/agents/orchestra_builder.md', '/work', env)).toBe(true);
  expect(editDenied('.claude/agents/other.md', '/work', env)).toBe(false);
  expect(editDenied(undefined, '/work', env)).toBe(true);
  expect(editDenied('', '/work', env)).toBe(true);
});

test('A8: nested harness directory, B-F4', () => {
  const env = { stateDir: null, xdg: '/state', home: '/home/u' };
  const cwd = '/work/.claude/plugins/x';
  expect(editDenied('.claude/hooks.json', cwd, env)).toBe(true);
  expect(editDenied('.claude/config.toml', cwd, env)).toBe(true);
  expect(editDenied('notes.md', cwd, env)).toBe(false);
  expect(editDenied('.claude/plugins/x/readme.md', cwd, env)).toBe(false);
});

test('A8: the state directory is protected except the coordinator files at its root', () => {
  const env = { stateDir: '/s/state', xdg: '/xdg', home: '/home/u' };
  for (const n of ['progress.md', 'standing-orders.md', 'autonomy.md']) expect(editDenied(`/s/state/${n}`, '/w', env)).toBe(false);
  for (const n of ['state.json', 'policy.json', 'sub/progress.md']) expect(editDenied(`/s/state/${n}`, '/w', env)).toBe(true);
  expect(editDenied('../state/state.json', '/s/other', env)).toBe(true);
  // Without ORCHESTRA_STATE_DIR the repo state directories under the base are protected the same way.
  const bare = { stateDir: null, xdg: '/xdg', home: '/home/u' };
  const id = 'a'.repeat(24);
  expect(editDenied(`/xdg/orchestra/${id}/state.json`, '/w', bare)).toBe(true);
  expect(editDenied(`/xdg/orchestra/${id}/progress.md`, '/w', bare)).toBe(false);
  expect(editDenied('/xdg/orchestra/notes.md', '/w', bare)).toBe(false);
});

test('A12: the marker directory is protected under XDG_STATE_HOME and under HOME', () => {
  const xdg = { stateDir: null, xdg: '/xdg', home: '/home/u' };
  expect(editDenied('/xdg/orchestra/mods/s1.json', '/xdg', xdg)).toBe(true);
  expect(editDenied('mods/../mods/s2.json', '/xdg/orchestra/mods', xdg)).toBe(true);
  expect(editDenied('/xdg/orchestra/notes.md', '/xdg', xdg)).toBe(false);
  const home = { stateDir: null, xdg: undefined, home: '/home/u' };
  expect(editDenied('/home/u/.local/state/orchestra/mods/s1.json', '/home/u', home)).toBe(true);
  const empty = { stateDir: null, xdg: '', home: '/home/u' };
  expect(editDenied('/home/u/.local/state/orchestra/mods/s1.json', '/home/u', empty)).toBe(true);
});

test('digest parity: guardDigest matches hashlib for fixed synthetic file contents', () => {
  // Expected value computed with python3 hashlib over the same relpath NUL length NUL bytes records, in
  // GUARD_DIGEST_FILES order: rules `{"a":1}\n`, guards `print("g")\n`, hooks.py missing, guard.ts bytes below.
  // The test harness cannot run Python; the real-file equality is observed in the headless run.
  expect(GUARD_DIGEST_FILES).toEqual([
    'config/guard-rules.json',
    'scripts/orchestra_core/guards.py',
    'scripts/orchestra_core/hooks.py',
    'hooks/mod/guard.ts',
  ]);
  const enc = (s: string): Uint8Array => Uint8Array.from(Array.from(s).map((c) => c.charCodeAt(0)));
  const digest = guardDigest([enc('{"a":1}\n'), enc('print("g")\n'), null, Uint8Array.from([0xc3, 0xa9, 0xc3, 0xbf, 0x00, 0x78])]);
  expect(digest).toBe('976961f81917e588edc5430271e54fe0bb6c80491ee9800dcfcf35a5b779678c');
});
