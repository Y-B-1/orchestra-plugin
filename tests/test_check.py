"""Tests for `lean.py check`: the pre-PR diff scan. Pure rules are called directly; a real repo is made only where the
behavior depends on git (diff, rename, base, quoting)."""
import contextlib, io, json, re, subprocess, sys, tempfile, unittest
from pathlib import Path

from tests.support import LEAN, git, make_repo
import check  # noqa: E402  (tests.support put the scripts folder on sys.path)

KEY = 'AKIA' + 'ABCDEFGHIJKLMNOP'  # built in parts: a fake credential the scan must find
GH = 'ghp_' + 'a' * 36
SECRETS = ['sk_live_' + 'a' * 24, 'gho_' + 'a' * 36, 'ghs_' + 'a' * 36, 'ghr_' + 'a' * 36, 'ASIA' + 'A' * 16, 'whsec_' + 'a' * 24,
           'xapp-1-' + 'a' * 12, 'xoxa-2-' + 'a' * 12, 'npm_' + 'a' * 36, 'AIza' + 'a' * 35, '-----BEGIN PGP PRIVATE KEY BLOCK-----', KEY, GH,
           '-----BEGIN RSA PRIVATE KEY-----']


def rule(kind, line):
    return any(k == kind and re.search(rx, line) for k, rx, _ in check.LINE_RULES)


class PureRulesTest(unittest.TestCase):
    def test_line_rules(self):
        weak = ['@pytest.mark.skip', 'x = 1  # noqa', 'x = 1  #noqa', '// @ts-ignore', '// @ts-nocheck', "xtest('a', f)",
                "fit('b', f)", '@pytest.mark.xfail', "self.skipTest('x')", '# ruff: noqa', '# pylint: disable=all', '# pragma: no cover',
                't.Skip("flaky")', '//nolint:errcheck', '#[ignore]', '@Disabled', '/* istanbul ignore next */', '// biome-ignore lint: x']
        debug = ['console.log(1)', 'console.debug(x)', 'debugger;', '  debugger', 'x; debugger', '[DEBUG-a1] x', 'breakpoint()', 'import pdb; pdb.set_trace()']
        mock = ["vi.mock('./thing')", "vi.mock('@/lib/db')", "vi.mock(import('./db'))", "vi.doMock('~/x')", "jest.mock('src/y')"]
        plain = ['x = 1', "print('hello')", "vi.mock('react')", "jest.mock('react')", 'my_debugger = 1', 'mock.patch("os.path.exists")']
        for line in ("it.skip('a', f)", "it.only('a', f)", "it.skipIf(ci)('c', f)", "test.fixme('d', f)", "it.todo('e')", 'describe.skip("x", f)'):
            with self.subTest('test-only', line=line):
                self.assertTrue(re.search(check.TEST_ONLY, line))
        for kind, hits in (('test-weakened', weak), ('debug', debug), ('self-mock', mock), ('secret', SECRETS)):
            for line in hits:
                with self.subTest(kind, line=line):
                    self.assertTrue(rule(kind, line))
        for line in plain:
            for kind in ('test-weakened', 'debug', 'self-mock', 'secret'):
                with self.subTest('plain', kind=kind, line=line):
                    self.assertFalse(rule(kind, line))

    def test_path_patterns(self):
        weak = ['__snapshots__/a.snap', '.github/workflows/ci.yml', 'tsconfig.json', 'ruff.toml', 'mypy.ini', 'pytest.ini', 'biome.json',
                'vitest.config.ts', '.pre-commit-config.yaml', '.gitlab-ci.yml', 'scripts/check.sh', 'web/.eslintrc.json']
        rules = ['AGENTS.md', 'packages/web/CLAUDE.md', '.claude/settings.json', 'packages/web/.claude/rules/testing.md',
                 '.agents/skills/e2e/SKILL.md', '.cursor/rules/a.mdc', '.orchestra/budget-waivers', 'docs/AGENT-MEMORY.md',
                 'CONTRIBUTING.md', 'docs/contributing.md', 'CODING_STANDARDS.md', 'docs/Coding_Standards.md']
        for rx, yes, no in ((check.WEAK_FILES, weak, ['src/app.py', 'docs/ci.md']), (check.RULES_FILES, rules, ['src/agents.py', 'README.md', 'packages/web/CONTRIBUTING.md', 'docs/guides/CONTRIBUTING.md'])):
            for p in yes:
                with self.subTest(p):
                    self.assertTrue(re.search(rx, p))
            for p in no:
                with self.subTest(p):
                    self.assertFalse(re.search(rx, p))

    def test_words(self):
        for path, want in (('src/authMiddleware.tsx', {'src', 'auth', 'middleware', 'tsx'}), ('JWTAuth.java', {'jwt', 'auth', 'java'}),
                           ('lib/Payment_service.py', {'lib', 'payment', 'service', 'py'}), ('src/APIToken.py', {'src', 'api', 'token', 'py'}),
                           ('a/userSessions.py', {'a', 'user', 'session', 'py'}), ('src/address.py', {'src', 'address', 'py'})):
            with self.subTest(path):
                self.assertEqual(check.words(path), want)

    def test_is_sensitive(self):
        yes = ['src/auth/x.py', 'login.ts', 'db/migrations/001.sql', 'lib/Payment_service.py', '.env.local', 'webhook.js',
               'src/authentication/index.ts', 'src/authorization.ts', 'app/oauth2.py', 'lib/jwt.ts', 'server/credentials.ts', 'src/APIToken.ts',
               'JWTAuth.java', 'src/signin/page.tsx', 'lib/rbac.ts', 'db/schema.prisma', 'supabase/policies.sql', 'lib/encryption.ts',
               'src/payments/charge.ts', 'src/permissions/policy.ts', 'authMiddleware.ts', 'src/oauth.ts', 'a/userSessions.py']
        no = ['src/plain.py', 'src/author.py', 'src/authority.ts', 'README.md', 'src/address.ts']
        for p in yes:
            with self.subTest(p):
                self.assertTrue(check.is_sensitive(p))
        for p in no:
            with self.subTest(p):
                self.assertFalse(check.is_sensitive(p))

    def test_raised_timeouts(self):
        for rem, add, want in (
                (['testTimeout: 5000'], ['testTimeout: 60000'], [1]),
                (['testTimeout: 5000'], ['testTimeout: 60_000'], [1]),
                (['@pytest.mark.timeout(5)'], ['@pytest.mark.timeout(60)'], [1]),
                (['testTimeout: 5000'], ['testTimeout: 4000'], []),
                (["it('a', fn, {timeout: 5000})", "it('b', fn, {timeout: 9000})"],  # compared with the same test only
                 ["it('a', fn, {timeout: 4000})", "it('b', fn, {timeout: 9000})", "it('c', fn, {timeout: 7000})"], []),
                (["it('a', fn, {timeout: 5000})", "it('b', fn, {timeout: 9000})"], ["it('a', fn, {timeout: 6000})", "it('b', fn, {timeout: 9000})"], [1]),
                ([], ['testTimeout: 60000'], [])):
            with self.subTest(rem=rem, add=add):
                info = {'rem': rem, 'add': list(enumerate(add, 1))}
                self.assertEqual(list(check.raised_timeouts(info)), want)

    def test_tool_section_lines(self):
        toml = '[project]\nname = "x"\n[tool.coverage.report]\nfail_under = 90\n[tool.other]\nx = 1\n'
        for lines, want in (([2], False), ([4], True), ([3], True), ([6], False), ([2, 4], True), ([], False)):
            with self.subTest(lines):
                self.assertEqual(check.tool_section_lines(toml, lines), want)

    def test_count_tests(self):
        cases = [  # (path, added lines, removed lines, tests added, tests removed)
            ('tests/test_a.py', ['def test_x(self):', '    async def test_y():', 'def helper():', '# def test_no'], ['def test_old():'], 2, 1),
            ('web/a.test.ts', ["it('a', () => {", "  test.each([1])('b', n => {", '  it.each`t`(', 'item(1)', 'latest(2)'], ["it('z', () => {"], 3, 1),
            ('pkg/a_test.go', ['func TestOne(t *testing.T) {', 'func Testify() {', 'func helper() {'], [], 1, 0),
            ('tests/a_test.rs', ['#[test]', '#[tokio::test]', 'fn x() {'], ['#[test]'], 1, 1),
            ('src/app.py', ['def test_in_app():'], [], 0, 0),
            ('tests/notes.txt', ['def test_x():'], [], 0, 0),
        ]
        for path, add, rem, a, r in cases:
            with self.subTest(path):
                self.assertEqual(check.count_tests({path: (add, rem)})[:2], (a, r))
        grew = check.count_tests({'tests/test_a.py': (['def test_a():', 'def test_b():', 'def test_c():'], []),
                                  'tests/test_b.py': (['def test_d():'], ['def test_e():'])})
        self.assertEqual(grew, (4, 1, [('tests/test_a.py', 3)]))


class Check(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = make_repo(Path(self.tmp.name) / 'repo')
        git(self.repo, 'switch', '-q', '-c', 'feature')

    def write(self, path, text):
        p = self.repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg='change', base=False):
        """Commit everything; with base, also move main there so later edits are judged against this state."""
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', msg)
        if base:
            git(self.repo, 'branch', '-f', 'main', 'HEAD')

    def result(self, base=None, max_lines=500, cwd=None):
        return check.check(base, max_lines, cwd=cwd or self.repo)

    def found(self, **kw):
        """{(kind, path, line)} of the findings."""
        return {(f['kind'], f['path'], f['line']) for f in self.result(**kw)['findings']}

    def kinds(self, **kw):
        return {(k, p) for k, p, _ in self.found(**kw)}

    def run_text(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.chdir(self.repo), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = check.run_check(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_new_files_are_scanned_by_their_path_and_content(self):
        files = {
            'a.test.ts': "it.skip('a', f)\n", 'repo.ts': 'q.skip(offset).take(n)\n', 'app.rs': 'for l in lines.iter().skip(1) {}\n',
            'u.ts': '// @ts-ignore\n', 'cypress/e2e/login.cy.ts': "it.only('a', f)\n", 'e2e/login.ts': "it.only('a', f)\n",
            'spec/models/user_spec.rb': "it.only('a', f)\n", 'models/user_spec.rb': "it.only('a', f)\n",
            'notes.md': 'Use `[DEBUG-a1]` tags and never `.skip(` a test.\n', 'keys.md': f'see {KEY}\n',  # docs quote patterns; secrets still count
            '__snapshots__/a.snap': 'x\n', 'weak/pyproject.toml': '[tool.ruff]\nline-length = 100\n', 'plain/pyproject.toml': '[project]\nname = "x"\n',
            'm.test.ts': "vi.mock('@/lib/db')\nvi.mock('react')\n", 'pkg/__init__.py': '', 'backend/app/services/ledger_core.py': 'def charge(): pass\n',
            'app/time.py': 'def now(): pass\n', 'app/mine.py': 'def f(): pass\n', 'docs.md': "patch('app.services.f') in a doc\n",
            't.py': "patch('app.services.ledger_core.charge')\npatch.object(ledger_core, 'charge')\nmonkeypatch.setattr('app.x', 1)\n"
                    "patch('os.path.exists')\npatch('time.sleep')\npatch('mine.f')\n",
            'app.py': "print('hello')\nprint('DEBUG x')\nbreakpoint()\n", 'a.js': '  debugger\nconsole.debug(x)\n',
            'AGENTS.md': 'rules\n', 'src/auth/x.py': 'x\n', '.env.local': 'x\n', 'src/plain.py': 'x\n',
        }
        for p, text in files.items():
            self.write(p, text)
        self.write('.orchestra/sessions/abc/asks.md', 'x\n')  # Orchestra's own ledger is never part of the branch
        (self.repo / 'blob.bin').write_bytes(b'\0\ndebugger;\n' * 600)  # binary: no line is read
        want = {('test-weakened', 'a.test.ts', 1), ('test-weakened', 'u.ts', 1), ('test-weakened', 'cypress/e2e/login.cy.ts', 1),
                ('test-weakened', 'e2e/login.ts', 1), ('test-weakened', 'spec/models/user_spec.rb', 1), ('test-weakened', 'models/user_spec.rb', 1),
                ('secret', 'keys.md', 1), ('test-weakened', '__snapshots__/a.snap', None), ('test-weakened', 'weak/pyproject.toml', None),
                ('self-mock', 'm.test.ts', 1), ('self-mock', 't.py', 1), ('self-mock', 't.py', 2), ('self-mock', 't.py', 3), ('self-mock', 't.py', 6),
                ('debug', 'app.py', 2), ('debug', 'app.py', 3), ('debug', 'a.js', 1), ('debug', 'a.js', 2), ('rules', 'AGENTS.md', None),
                ('sensitive', 'src/auth/x.py', None), ('sensitive', 'cypress/e2e/login.cy.ts', None), ('sensitive', 'e2e/login.ts', None), ('sensitive', '.env.local', None)}
        self.assertEqual(self.found(), want)

    def test_size_flags_a_new_file_past_the_budget_except_lockfiles_data_binary_generated_and_waived(self):
        big = 'x = 1\n' * 600
        for p in ('big.py', 'a.lock', 'package-lock.json', 'app.min.js', 'dist/out.js', 'fix.patch', 'rows.csv', 'pnpm-lock.yaml', 'go.sum',
                  'CHANGELOG.md', 'messages/en.json', 'npm-shrinkwrap.json', 'packages.lock.json', 'w.py'):
            self.write(p, big)
        self.write('gen.py', '# This file is generated\n' + big)
        self.write('b.py', '# Code generated by protoc. DO NOT EDIT.\n' + big)
        self.write('a.py', '# Generated reports are written elsewhere\n' + big)  # not a generated marker
        self.write('c.py', 'x = 1\n' * 10 + '# this file is generated\n' + big)  # the marker must be near the top
        (self.repo / 'blob.bin').write_bytes(b'\0\1\2\n' * 600)
        self.write('.orchestra/budget-waivers', 'w.* legacy table, split later\n')
        found = self.result()['findings']
        self.assertEqual({f['path'] for f in found if f['kind'] == 'size'}, {'big.py', 'a.py', 'c.py'})
        self.assertIn('0 lines at base, 600 now', next(f['message'] for f in found if f['path'] == 'big.py'))
        self.assertIn(('rules', '.orchestra/budget-waivers', None), self.found())

    def test_size_counts_only_growth_and_honors_max_lines(self):
        for p in ('shrunk.py', 'grown.py', 'gone.py'):
            self.write(p, 'x = 1\n' * 600)
        self.commit(base=True)
        self.write('shrunk.py', 'x = 1\n' * 590)
        self.write('grown.py', 'x = 1\n' * 610)
        (self.repo / 'gone.py').unlink()
        self.write('mid.py', 'x = 1\n' * 50)
        self.assertEqual(self.kinds(), {('size', 'grown.py')})
        self.assertEqual(self.kinds(max_lines=40), {('size', 'grown.py'), ('size', 'mid.py')})

    def test_staged_unstaged_and_odd_paths_are_scanned(self):
        self.write('a.js', 'debugger;\n')
        git(self.repo, 'add', 'a.js')
        self.write('b.js', 'x\n')
        self.write('my dir/my file.js', 'debugger;\n')
        self.commit()
        self.write('b.js', 'x\nconsole.log(1)\n')
        self.write('my dir/my file.js', 'debugger;\nconsole.log(1)\n')
        self.write('a"b.js', 'debugger;\n')
        git(self.repo, 'add', 'a"b.js')
        self.write('c"d.js', 'debugger;\n')
        self.assertEqual(self.found(), {('debug', 'a.js', 1), ('debug', 'b.js', 2), ('debug', 'my dir/my file.js', 1), ('debug', 'my dir/my file.js', 2),
                                        ('debug', 'a"b.js', 1), ('debug', 'c"d.js', 1)})

    def test_non_utf8_content_does_not_crash(self):
        (self.repo / 'latin.js').write_bytes(b'x\n')
        self.commit()
        (self.repo / 'latin.js').write_bytes(b'caf\xe9 = 1\ndebugger;\n')
        (self.repo / 'new.js').write_bytes(b'caf\xe9\ndebugger;\n')
        self.assertEqual(self.kinds(), {('debug', 'latin.js'), ('debug', 'new.js')})

    def test_run_from_a_subdirectory_reads_relative_to_the_root(self):
        self.write('sub/huge.py', 'x = 1\n' * 700)
        self.write('sub/small.py', 'x = 1\n' * 600)
        self.write('.orchestra/budget-waivers', 'sub/small.py legacy\n')
        self.assertEqual({k for k in self.kinds(cwd=self.repo / 'sub') if k[0] == 'size'}, {('size', 'sub/huge.py')})

    def test_a_pure_rename_is_not_growth(self):
        self.write('old.py', 'x = 1\n' * 599 + "print('DEBUG')\n" + 'y = 1  # noqa\n')
        self.commit(base=True)
        git(self.repo, 'mv', 'old.py', 'moved.py')
        self.assertEqual(self.found(), set())

    def test_a_renamed_and_grown_file_compares_with_its_old_path(self):
        self.write('old.py', 'x = 1\n' * 600)
        self.commit(base=True)
        git(self.repo, 'mv', 'old.py', 'moved.py')
        self.write('moved.py', 'x = 1\n' * 600 + 'debugger;\n')
        f = self.result()['findings']
        self.assertEqual({(x['kind'], x['path']) for x in f}, {('size', 'moved.py'), ('debug', 'moved.py')})
        self.assertIn('600 lines at base, 601 now', next(x['message'] for x in f if x['kind'] == 'size'))

    def test_a_skip_already_in_a_touched_test_file_is_reported_once(self):
        self.write('test_a.py', '@pytest.mark.skip(reason="x")\ndef test_a():\n    pass\n\n@unittest.skip("y")\ndef test_b():\n    pass\n')
        self.write('test_b.py', '@pytest.mark.skip\ndef test_c():\n    pass\n')
        self.write('app.py', 'rows.skip(1)\n')
        # a skip inside a string, a regex or an iterator call is not a skipped test
        self.write('test_c.py', "X = '@pytest.mark.skip'\nRX = r'\\.skip\\('\nY = \"it.skip('a', f)\"\n")
        self.write('c.test.ts', 'const n = lines.iter().skip(1)\nq.skip(2)\nconst t = \"it.skip(1)\"\n')
        self.commit(base=True)
        self.write('test_a.py', (self.repo / 'test_a.py').read_text() + '\ndef test_d():\n    assert 1\n')
        self.write('test_c.py', (self.repo / 'test_c.py').read_text() + 'Z = 1\n')
        self.write('c.test.ts', (self.repo / 'c.test.ts').read_text() + 'const z = 1\n')
        self.write('app.py', 'rows.skip(2)\n')
        r = self.result()['findings']
        self.assertEqual([(f['kind'], f['path'], f['line']) for f in r], [('skipped-test', 'test_a.py', None)])
        self.assertIn('2 skipped tests', r[0]['message'])

    def test_a_file_renamed_away_from_a_watched_path_is_still_judged_by_the_old_name(self):
        self.write('.github/workflows/ci.yml', 'on: push\n')
        self.write('AGENTS.md', 'rules\n')
        self.commit(base=True)
        git(self.repo, 'mv', '.github/workflows/ci.yml', 'disabled-ci.yml')
        git(self.repo, 'mv', 'AGENTS.md', 'docs-old.md')
        self.assertEqual(self.found(), {('test-weakened', 'disabled-ci.yml', None), ('rules', 'docs-old.md', None)})

    def test_a_type_change_does_not_hide_line_rules(self):
        self.write('link', 'plain\n')
        self.write('app.js', 'ok();\n')
        self.commit(base=True)
        (self.repo / 'link').unlink()
        (self.repo / 'link').symlink_to('app.js')
        self.write('app.js', 'ok();\ndebugger;\n')
        self.assertIn(('debug', 'app.js', 2), self.found())

    def test_changes_against_the_base(self):
        base = {'vitest.config.js': 'export default { testTimeout: 5000 }\n', 't1.test.js': 'x({ testTimeout: 5000 })\n',
                'repo.ts': 'q.skip(offset).take(n)\nfetch(u, { timeout: 5000 })\n', 'ruff.toml': 'x\n',
                't2.test.js': "it('a', fn, {timeout: 5000})\nit('b', fn, {timeout: 9000})\n",
                't3.test.js': "it('a', fn, {timeout: 5000})\nit('b', fn, {timeout: 9000})\n",
                'test_a.py': '@pytest.mark.timeout(5)\ndef test_a(): pass\n', 'tests/test_b.py': 'assert f(1) == 1\n',
                'tests/test_a.py': 'assert f(1) == 1\nassert f(2) == 2\n',
                'p1/pyproject.toml': '[project]\nname = "x"\n[tool.coverage.report]\nfail_under = 90\n',
                'p2/pyproject.toml': '[project]\nname = "x"\n[tool.coverage.report]\nfail_under = 90\n',
                'test_m.py': '@pytest.mark.skip(reason="x")\ndef test_a():\n    pass\n'}
        for p, text in base.items():
            self.write(p, text)
        self.commit(base=True)
        git(self.repo, 'rm', '-q', 'tests/test_b.py')
        for p, text in {
                'vitest.config.js': 'export default { testTimeout: 60000 }\n', 't1.test.js': 'x({ testTimeout: 60_000 })\n',
                'repo.ts': 'q.skip(offset).take(n)\nfetch(u, { timeout: 8000 })\n', 'ruff.toml': 'y\n',
                't2.test.js': "it('a', fn, {timeout: 4000})\nit('b', fn, {timeout: 9000})\nit('c', fn, {timeout: 7000})\n",
                't3.test.js': "it('a', fn, {timeout: 6000})\nit('b', fn, {timeout: 9000})\n",
                'test_a.py': '@pytest.mark.timeout(60)\ndef test_a(): pass\n', 'tests/test_a.py': 'f(1)\n',
                'p1/pyproject.toml': '[project]\nname = "x"\n[tool.coverage.report]\n',
                'p2/pyproject.toml': '[project]\nname = "y"\n[tool.coverage.report]\nfail_under = 90\n',
                # a skip that only moved inside a test file is not new
                'test_m.py': 'def test_a():\n    pass\n\n@pytest.mark.skip(reason="x")\ndef test_b():\n    pass\n'}.items():
            self.write(p, text)
        self.assertEqual(self.found(), {
            ('test-weakened', 'vitest.config.js', None), ('test-weakened', 'vitest.config.js', 1), ('test-weakened', 't1.test.js', 1),
            ('test-weakened', 't3.test.js', 1), ('test-weakened', 'test_a.py', 1), ('test-weakened', 'ruff.toml', None),
            ('test-weakened', 'tests/test_b.py', None), ('test-weakened', 'tests/test_a.py', None), ('test-weakened', 'p1/pyproject.toml', None)})

    def test_a_suppression_that_only_moved_is_not_new_but_one_removal_hides_one_copy(self):
        self.write('a.py', 'x = 1  # type: ignore\n')
        self.write('c.py', 'x = 1  # noqa\n')
        self.commit(base=True)
        (self.repo / 'a.py').unlink()
        (self.repo / 'c.py').unlink()
        self.write('b.py', 'x = 1  # type: ignore\n')
        self.write('d.py', 'x = 1  # noqa\n')
        self.write('e.py', 'x = 1  # noqa\n')
        flagged = {p for k, p, _ in self.found() if k == 'test-weakened'}
        self.assertNotIn('b.py', flagged)
        self.assertEqual(len(flagged & {'d.py', 'e.py'}), 1)

    def test_a_test_count_is_reported_only_past_a_net_growth_of_five(self):
        self.write('tests/test_many.py', ''.join(f'def test_{i}():\n    assert {i}\n' for i in range(7)))
        f = self.result()['findings']
        self.assertEqual([(x['path'], x['line']) for x in f if x['kind'] == 'test-count'], [('tests/test_many.py', None)])
        self.assertIn('7 tests added, 0 removed (net +7): each added test must prove a behavior no existing test proves',
                      next(x['message'] for x in f if x['kind'] == 'test-count'))
        self.write('tests/test_many.py', ''.join(f'def test_{i}():\n    assert {i}\n' for i in range(5)))
        self.assertNotIn('test-count', {k for k, _ in self.kinds()})

    def test_user_diff_config_is_neutralized(self):
        self.write('a.js', 'one\n2\n3\n4\nfive\n')
        self.commit(base=True)
        ext = self.repo.parent / 'ext.sh'
        ext.write_text('#!/bin/sh\nexit 0\n')
        ext.chmod(0o755)
        git(self.repo, 'config', 'diff.external', str(ext))
        git(self.repo, 'config', 'diff.interHunkContext', '10')
        self.write('a.js', 'ONE\n2\n3\n4\ndebugger;\n')
        self.assertEqual(self.found(), {('debug', 'a.js', 5)})

    def test_the_base_is_the_merge_base_even_when_the_base_branch_moved(self):
        self.write('app.js', 'x\nconsole.log(1)\n')
        self.write('big.py', 'x = 1\n' * 620)
        self.commit('c')
        git(self.repo, 'switch', '-q', 'main')
        git(self.repo, 'merge', '-q', '--ff-only', 'feature')
        self.write('app.js', 'x\n')
        self.write('big.py', 'x = 1\n' * 600)
        self.commit('main trims')
        git(self.repo, 'switch', '-q', 'feature')
        self.write('feature.js', 'y\n')
        self.commit('f')
        self.assertEqual(self.found(base='main'), set())
        self.assertEqual(self.found(), set())

    def test_no_merge_base_gives_no_result(self):
        git(self.repo, 'switch', '-q', '--orphan', 'unrelated')
        self.write('z.txt', 'z\n')
        self.commit('orphan')
        self.assertIsNone(self.result())

    def test_text_output_names_the_base_groups_findings_and_never_prints_a_secret(self):
        code, out, _ = self.run_text()
        self.assertEqual((code, out.strip().splitlines()[-1]), (0, 'no findings'))
        self.write('app.py', "print('DEBUG')\n")
        self.write('big.py', 'x = 1\n' * 600)
        self.write('conf.txt', f'a\nkey = {KEY}\n')
        self.write('pk.txt', '-----BEGIN RSA PRIVATE KEY-----\n')
        self.write('gh.txt', GH + '\n')
        code, out, err = self.run_text()
        lines = out.strip().splitlines()
        sha = git(self.repo, 'rev-parse', 'main')
        self.assertEqual(lines[0], f'base {sha[:9]} (merge-base with main), 5 files, +605 -0 lines')
        self.assertTrue(lines[1].startswith('size big.py '))
        self.assertTrue(lines[2].startswith('debug app.py:1 '))
        self.assertEqual(lines[-1], '5 findings (size 1, debug 1, secret 3)')
        for want in ('secret conf.txt:2', 'secret pk.txt:1', 'secret gh.txt:1'):
            self.assertIn(want, out)
        self.assertNotIn(KEY, out + err)
        self.assertNotIn(GH[:8], out)

    def test_arguments(self):
        self.write('a.js', 'debugger;\n')
        self.commit()
        self.assertEqual(self.found(), {('debug', 'a.js', 1)})
        self.assertEqual(self.found(base='HEAD'), set())
        for args in (['--bogus'], ['--max-lines', 'x'], ['--max-lines'], ['--base'], ['--base', 'nope-ref']):
            with self.subTest(args):
                self.assertEqual(self.run_text(*args)[0], 2)
        self.assertIn('no base', self.run_text('--base', 'nope-ref')[2])

    def test_the_command_line_prints_json(self):
        self.write('app.js', 'debugger;\n')
        p = subprocess.run([sys.executable, str(LEAN), 'check', '--json'], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        d = json.loads(p.stdout)
        self.assertEqual(d['base'], git(self.repo, 'rev-parse', 'main'))
        self.assertEqual(set(d['findings'][0]), {'kind', 'path', 'line', 'message'})
        self.assertEqual(d['counts'], {'debug': 1})


if __name__ == '__main__':
    unittest.main()
