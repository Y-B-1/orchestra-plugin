import { expect, test } from 'claude-code/testing';

import { CORPUS, RULES_JSON } from './fixtures/guard-fixtures.js';
import { O17_CASES } from './fixtures/o17-cases.js';
import { classifyCommand, editDenied, klassOf, loadRules, longPrefix } from './guard.js';
import { GUARD_DIGEST_FILES, guardDigest } from './marker.js';

loadRules(RULES_JSON);

type Case = { id: string; input: unknown; class: string; category?: string; decision_category?: string };

function run(cases: Case[]): string[] {
  const wrong: string[] = [];
  for (const c of cases) {
    const input = c.input as { command?: string; tool?: string; path?: string; cwd?: string };
    if (typeof input.command === 'string') {
      const d = classifyCommand(input.command);
      const klass = klassOf(d);
      if (klass !== c.class || (d.boundary ?? undefined) !== c.category) {
        wrong.push(`${c.id}: want ${c.class}/${c.category ?? ''} got ${klass}/${d.boundary ?? ''} for ${JSON.stringify(input.command)}`);
      } else if (c.decision_category !== undefined && d.category !== c.decision_category) {
        wrong.push(`${c.id}: want decision category ${c.decision_category} got ${d.category} for ${JSON.stringify(input.command)}`);
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

test('test_corpus_decision_category_matches: every case with decision_category matches decision.category', () => {
  const named = (CORPUS as Case[]).filter((c) => c.decision_category !== undefined);
  expect(named.length).toBeGreaterThanOrEqual(8);
  for (const c of named) {
    const d = classifyCommand((c.input as { command: string }).command);
    expect(d.category).toBe(c.decision_category);
    expect(klassOf(d)).toBe(c.class);
    expect(c.class === 'boundary' ? 'merged-delete' : 'apiwrite').toBe(c.decision_category);
  }
});

const SOFTEN: Record<string, string | null> = {
  'soften-stash': 'warn', 'soften-add-all': 'allow', 'soften-commit-all': 'allow', 'soften-amend': 'warn',
  'soften-push-tags': 'warn', 'soften-push-refspec-colon': 'warn',
  'nosoften-push-prune': null, 'nosoften-push-mirror': null, 'nosoften-stash-then-reset': null,
  'nosoften-stash-then-force-push': null, 'nosoften-push-tags-extra-refspec': null, 'nosoften-push-tags-prune': null,
};

test('D4 2.7: soften rides the deny decision; a hard deny anywhere drops it; two softened denies keep the stricter level', () => {
  for (const [id, level] of Object.entries(SOFTEN)) {
    const c = (CORPUS as Case[]).find((x) => x.id === id)!;
    const d = classifyCommand((c.input as { command: string }).command);
    expect([id, klassOf(d), d.soften]).toEqual([id, 'deny', level]);
  }
  for (const command of ['git status', 'git reset --hard', 'git push origin main']) expect(classifyCommand(command).soften).toBeNull();
  expect(classifyCommand('git add -A && git stash').soften).toBe('warn');
  expect(classifyCommand('git stash && git add -A').soften).toBe('warn');
  expect(classifyCommand("bash -c 'git add -A' && git commit --amend").soften).toBe('warn');
  expect(classifyCommand('git add -A; git commit -am x').soften).toBe('allow');
  for (const command of ['git stash; git clean -f', "bash -c 'git stash; git checkout .'", 'echo $(git stash) $(git reset --hard)', 'git add -A && echo "$(git push --force origin x)"', 'git stash\ngit branch -D a b']) {
    const d = classifyCommand(command);
    expect([command, klassOf(d), d.soften]).toEqual([command, 'deny', null]);
  }
  expect(classifyCommand('git commit --amend').reason).toBe('Amend rewrites history; make a new commit instead');
  expect(classifyCommand('git push --tags origin').reason).toBe('Push needs one explicit remote and refspec');
  expect(classifyCommand('git push origin :x').reason).toBe('Push needs one non-deleting refspec');
});

test('D4 2.7: gh workflow run names, gh categories, config boundaries, builtins', () => {
  for (const [command, name] of [['gh workflow run release.yml', 'release.yml'], ['gh workflow run -f env=prod --ref main deploy.yml', 'deploy.yml']] as const) {
    const d = classifyCommand(command);
    expect([klassOf(d), d.workflow]).toEqual(['release', name]);
  }
  expect(classifyCommand('gh workflow run').workflow).toBeNull();
  expect(classifyCommand('gh api -X DELETE repos/o/r').workflow).toBeNull();
  expect(classifyCommand('git status').workflow).toBeNull();
  for (const [command, category] of [['gh prm 12', 'ghcustom'], ['gh pr edit 12 --base main', 'prbase'], ['gh pr edit 12 -Bmain', 'prbase'], ['gh pr edit 12 --base=main', 'prbase'], ['gh api -X DELETE repos/o/r', 'apiwrite'], ['gh api -X POST repos/o/r/git/refs -f ref=x', 'providerrelease']]) {
    const d = classifyCommand(command!);
    expect([command, klassOf(d), d.category]).toEqual([command, 'release', category]);
  }
  for (const command of ['gh alias set a b', 'gh alias import f', 'gh alias delete a', 'gh extension install o/r', 'gh ext list']) {
    const d = classifyCommand(command);
    expect([command, klassOf(d), d.boundary]).toEqual([command, 'boundary', 'config']);
  }
  for (const command of ['gh alias list', 'gh pr view 3', 'gh issue list', 'gh repo view', 'gh run view 1', 'gh auth status', 'gh', 'gh --help', 'gh -R o/r pr view']) {
    expect([command, klassOf(classifyCommand(command))]).toEqual([command, 'allow']);
  }
});

test('D4 2.7: gh api write forms are release, reads and the allow list are allow', () => {
  const release = ['gh api repos/o/r -f default_branch=x', 'gh api repos/o/r -F a=b', 'gh api repos/o/r --field a=b', 'gh api repos/o/r --raw-field a=b', 'gh api repos/o/r -fa=b', 'gh api repos/o/r --input=x.json',
    'gh api -X delete repos/o/r', 'gh api -iXDELETE repos/o/r', 'gh api -H "A: b" -X DELETE repos/o/r', 'gh api repos/o/r --method DELETE', 'gh api -X PATCH /repos/o/r', 'gh api -X PATCH https://api.github.com/repos/o/r',
    'gh api -X POST repos/o/r/pulls/3/reviews%2e%2e/x -f a=b', 'gh api -X PUT repos/o/r/pulls', 'gh api -X POST -f a=b'];
  for (const command of release) expect([command, klassOf(classifyCommand(command))]).toEqual([command, 'release']);
  const allow = ['gh api repos/o/r', 'gh api -X GET repos/o/r -f a=b', 'gh api --method=get repos/o/r -F a=b', 'gh api -H "A: b" repos/o/r', 'gh api repos/o/r/issues/3/comments -f body=x', 'gh api -X POST /repos/o/r/pulls -f title=t',
    'gh api -X POST https://api.github.com/repos/o/r/pulls?x=1 -f title=t', 'gh api graphql -f query=query', 'gh api -X POST repos/o/r/pulls/3/comments -f body=x'];
  for (const command of allow) expect([command, klassOf(classifyCommand(command))]).toEqual([command, 'allow']);
});

test('merged-delete: kind, remote, branch and argv ride the decision; stand-alone denials hold', () => {
  const local = classifyCommand('git branch --del --forc x');
  expect([klassOf(local), local.category, local.kind, local.remote, local.branch]).toEqual(['boundary', 'merged-delete', 'local', null, 'x']);
  expect(local.argv).toEqual(['git', 'branch', '--del', '--forc', 'x']);
  const remote = classifyCommand('git push --delete origin x');
  expect([klassOf(remote), remote.category, remote.kind, remote.remote, remote.branch]).toEqual(['boundary', 'merged-delete', 'remote', 'origin', 'x']);
  for (const command of ['git branch -d y && git branch -D x', 'git branch -D a; git branch -D b', 'cd /o && git branch -D x']) {
    expect(classifyCommand(command).reason).toBe('Run each branch deletion as its own command, not chained or batched with other calls');
  }
  for (const command of ['git -C /o branch -D x', 'GIT_DIR=/o git branch -D x', 'sudo git branch -D x', 'xargs git branch -D x', 'echo $(git branch -D x)', "bash -c 'git branch -D x'"]) {
    expect(classifyCommand(command).reason).toBe('Branch deletion must run plainly in the session repository');
  }
  for (const command of ['git branch -D x y', 'git branch -D -r origin/x', 'git push origin :x', 'git push origin --delete x y', 'git push https://h/r.git --delete x', 'git push origin --delete --force x']) {
    expect(klassOf(classifyCommand(command))).toBe('deny');
  }
  expect(klassOf(classifyCommand('git branch -d -r origin/x'))).toBe('boundary');
  expect(classifyCommand('git branch -d -r origin/x').category).toBe('boundary');
});

test('merged-delete: any git global option before the verb denies (R2 test_merged_delete_global_config_option_denied)', () => {
  for (const command of ['git -c core.pager=/tmp/x push origin --delete x2', 'git -c core.editor=/h push origin --delete x2',
    'git --config-env=core.askPass=E push origin --delete x2', 'git -c x=y branch -D b', 'git --config-env=x=E branch -D b',
    'git --namespace=n branch -D b', 'git --namespace n push origin -d x2', 'git --exec-path=/x branch -D b', 'git --bare branch -D b',
    'git -p push origin --delete x2', 'git --no-pager branch -D b']) {
    const d = classifyCommand(command);
    expect([klassOf(d), d.reason]).toEqual(['deny', 'Branch deletion must run plainly in the session repository']);
  }
});

test('heredoc data and apostrophe in a double-quoted substitution: the T5 corpus cases get the Python verdict', () => {
  const t5 = /^(allow-heredoc-(cat-file|cat-unquoted|gh-body-file|git-commit-F)|allow-quote-apostrophe-[123]|deny-heredoc-shell-.+|deny-quote-(force-push|unbalanced)|deny-heredoc-(2r|19|21|18))$/;
  const cases = (CORPUS as Case[]).filter((c) => t5.test(c.id));
  expect(cases.length).toBe(20);
  expect(run(cases)).toEqual([]);
  expect(cases.filter((c) => ['deny-heredoc-2r', 'deny-heredoc-19', 'deny-heredoc-21'].includes(c.id)).map((c) => c.class)).toEqual(['allow', 'allow', 'allow']);
  expect(klassOf(classifyCommand("cat <<'EOF' > >(bash)\ngit reset --hard\nEOF"))).toBe('deny');
  expect(klassOf(classifyCommand('cat <<EOF\n$(git reset --hard)\nEOF'))).toBe('deny');
  expect(klassOf(classifyCommand('echo "$(git push --force origin x)"'))).toBe('deny');
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

// F89: a fixed wall-clock budget failed under load. The crafted case is timed against a benign twin of the same
// shape in the same run, interleaved, so machine load scales both. Measured crafted/benign ratio over 3 runs and 4
// shapes: 0.82 to 1.11; the factor is more than 7 times the worst. The ceiling is the harness per-test limit named in
// scripts/check.sh and is never tighter. One test per shape keeps each inside that limit.
const RATIO_FACTOR = 8;
const HARNESS_LIMIT_MS = 5000;
const TEST_TIMEOUT_MS = 30000; // the runner's default 5 s per test is too tight when other suites load the machine; its option is timeoutMs
for (const [levels, width] of [[5, 2], [4, 4], [6, 2], [5, 3]] as const) {
  test(`FX6: crafted nested shell ${levels}x${width} denies in time comparable to its benign twin (F89)`, { timeoutMs: TEST_TIMEOUT_MS }, () => {
    const quote = (text: string): string => "'" + text.replace(/'/g, `'"'"'`) + "'";
    const nested = (tail: string): string => {
      let body = 'git status';
      for (let i = 0; i < levels; i++) body = 'sudo -u $(a) x ' + Array(width).fill('$(b) bash -c ' + quote(body)).join(' ');
      return body + tail;
    };
    const median = (xs: number[]): number => [...xs].sort((x, y) => x - y)[Math.floor(xs.length / 2)] as number;
    const time = (command: string): { ms: number; klass: string } => {
      const start = performance.now();
      const klass = klassOf(classifyCommand(command));
      return { ms: performance.now() - start, klass };
    };
    expect(klassOf(classifyCommand('git status'))).toBe('allow');
    const benign: number[] = [];
    const crafted: number[] = [];
    for (let round = 0; round < 3; round++) {
      const b = time(nested('; git status'));
      const c = time(nested('; git ' + 'reset --hard'));
      expect(b.klass).toBe('deny'); // the shape alone spends the reading budget, so the benign twin denies as malformed too
      expect(c.klass).toBe('deny');
      benign.push(b.ms);
      crafted.push(c.ms);
    }
    expect(median(crafted)).toBeLessThan(median(benign) * RATIO_FACTOR);
    expect(median(crafted)).toBeLessThan(HARNESS_LIMIT_MS);
  });
}

test('FX6: a wrapper option substitution before a dash word is dropped as a reading, not denied', () => {
  expect(klassOf(classifyCommand('xargs -P $(nproc) make -s'))).toBe('allow');
  expect(klassOf(classifyCommand('sudo -u $(whoami) df -h'))).toBe('allow');
  expect(klassOf(classifyCommand('sudo -u $(whoami) git ' + 'reset --hard'))).toBe('deny');
});

test('GF8: files under <state>/review-packages are writable; the directory entry and other state stay protected', () => {
  const run = '/state/orchestra/0123456789abcdef01234567';
  for (const env of [{ stateDir: '/s/state', xdg: '/state', home: '/home/u' }, { stateDir: null, xdg: '/state', home: '/home/u' }]) {
    const root = env.stateDir ?? run;
    expect(editDenied(root + '/review-packages/B1/diff.patch', '/work', env)).toBe(false);
    expect(editDenied(root + '/review-packages', '/work', env)).toBe(true);
    expect(editDenied(root + '/state.json', '/work', env)).toBe(true);
    expect(editDenied(root + '/review-packages/../state.json', '/work', env)).toBe(true);
  }
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

test('SPEC 5.15: a strict prefix of a guarded long option reads as that option, the first listed winning', () => {
  const guarded = ['--all', '--amend'];
  expect(longPrefix('commit', '--am', guarded)).toBe('--amend');
  expect(longPrefix('commit', '--am=x', guarded)).toBe('--amend');
  expect(longPrefix('commit', '--a', guarded)).toBe('--all');
  for (const token of ['--amend', '--', '-a', '-am', 'am', '--x', '--amendx', '']) expect(longPrefix('commit', token, guarded)).toBeNull();
  expect(longPrefix('worktree', '--am', guarded)).toBeNull();
  expect(longPrefix('log', '--am', guarded)).toBeNull();
});

test('SPEC 5.15: abbreviated long options classify as the full option, exemptions only in full', () => {
  const deny = [
    'git add --al', 'git add --a', 'git add --upd', 'git add --no-ignore-rem', 'git reset --har', 'git clean --forc', 'git clean --f',
    'git branch --del --forc x y', 'git checkout --forc', 'git switch --disc', 'git push --mir origin', 'git push --ta origin',
    'git push --pru origin', 'git push --al origin', 'git commit --am -m x', 'git commit --amend', 'git clean -f --dry',
    'git restore --staged --work .',
  ];
  for (const command of deny) expect([command, klassOf(classifyCommand(command))]).toEqual([command, 'deny']);
  // SPEC 5.14 (F13): `--del` is `--delete`, and a plain `push --delete` is now a merged-delete boundary, not a release.
  const del = classifyCommand('git push --del origin x');
  expect([klassOf(del), del.category]).toEqual(['boundary', 'merged-delete']);
  expect(klassOf(classifyCommand('git push --push-o=x origin main'))).toBe('release');
  expect(klassOf(classifyCommand('git push --push-o x origin main'))).toBe('release');
  for (const command of ['git commit -m x file', 'git commit --mess --amend', 'git commit --messa=--amend', 'git clean --dry-run -f', 'git restore --staged .', 'git worktree rem X', 'git worktree prun']) {
    expect([command, klassOf(classifyCommand(command))]).toEqual([command, 'allow']);
  }
  const tag = classifyCommand('git tag --del v1');
  expect([klassOf(tag), tag.boundary]).toEqual(['boundary', 'delete']);
});

test('SPEC 5.15: commit --amend is denied with its reason, in full and abbreviated', () => {
  for (const command of ['git commit --amend', 'git commit --am -m x', 'git commit --amen', 'git commit -m x --amend']) {
    const d = classifyCommand(command);
    expect([d.action, d.reason]).toEqual(['deny', 'Amend rewrites history; make a new commit instead']);
  }
  expect(classifyCommand('git commit -m --amend').action).toBe('allow');
});
