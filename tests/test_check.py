"""Tests for `lean.py check`: the pre-PR diff scan."""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path

LEAN = Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts/lean.py'


def git(cwd, *args):
    subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)


class Check(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, 'init', '-q', '-b', 'main')
        git(self.repo, 'config', 'user.email', 't@example.com')
        git(self.repo, 'config', 'user.name', 'T')
        self.write('README.txt', 'hello\n')
        self.commit('init')
        git(self.repo, 'switch', '-q', '-c', 'feature')

    def write(self, path, text):
        p = self.repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg='change'):
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', msg)

    def run_check(self, *args, cwd=None):
        p = subprocess.run([sys.executable, str(LEAN), 'check', *args], cwd=cwd or self.repo, capture_output=True, text=True)
        return p

    def findings(self, *args, cwd=None):
        p = self.run_check('--json', *args, cwd=cwd)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)['findings']

    def kinds(self, *args, cwd=None):
        return {(f['kind'], f['path']) for f in self.findings(*args, cwd=cwd)}

    def test_clean_branch_has_no_findings(self):
        p = self.run_check()
        self.assertEqual(p.returncode, 0)
        self.assertIn('no findings', p.stdout)

    def test_size_flags_new_big_file_and_names_counts(self):
        self.write('big.py', 'x = 1\n' * 600)
        f = [f for f in self.findings() if f['kind'] == 'size']
        self.assertEqual([x['path'] for x in f], ['big.py'])
        self.assertIn('0', f[0]['message'])
        self.assertIn('600', f[0]['message'])

    def test_size_max_lines_option(self):
        self.write('mid.py', 'x = 1\n' * 50)
        self.assertNotIn(('size', 'mid.py'), self.kinds())
        self.assertIn(('size', 'mid.py'), self.kinds('--max-lines', '40'))

    def test_size_only_when_file_grew(self):
        self.write('old.py', 'x = 1\n' * 600)
        self.commit()
        git(self.repo, 'branch', '-f', 'main', 'HEAD')
        self.write('old.py', 'x = 1\n' * 590)
        self.assertNotIn(('size', 'old.py'), self.kinds())
        self.write('old.py', 'x = 1\n' * 610)
        self.assertIn(('size', 'old.py'), self.kinds())

    def test_size_skips_generated_lock_and_binary(self):
        self.write('a.lock', 'x\n' * 600)
        self.write('package-lock.json', '{}\n' * 600)
        self.write('app.min.js', 'x\n' * 600)
        self.write('dist/out.js', 'x\n' * 600)
        self.write('gen.py', '# This file is generated\n' + 'x = 1\n' * 600)
        (self.repo / 'blob.bin').write_bytes(b'\0\1\2\n' * 600)
        self.write('fix.patch', '+x\n' * 600)
        self.write('rows.csv', 'a,b\n' * 600)
        self.assertFalse([k for k in self.kinds() if k[0] == 'size'])

    def test_size_waiver(self):
        self.write('big.py', 'x = 1\n' * 600)
        self.write('.orchestra/budget-waivers', 'big.* legacy table, split later\n')
        self.assertNotIn(('size', 'big.py'), self.kinds())

    def test_untracked_files_are_scanned(self):
        self.write('new.py', 'import pdb\npdb.set_trace()\n')
        self.assertIn(('debug', 'new.py'), self.kinds())

    def test_staged_and_unstaged_changes_are_scanned(self):
        self.write('a.js', 'debugger;\n')
        git(self.repo, 'add', 'a.js')
        self.write('b.js', 'x\n')
        self.commit()
        self.write('b.js', 'x\nconsole.log(1)\n')
        k = self.kinds()
        self.assertIn(('debug', 'a.js'), k)
        self.assertIn(('debug', 'b.js'), k)

    def test_test_weakened_added_lines(self):
        self.write('t.test.js', "it.skip('a', () => {})\n")
        self.write('t.py', '@pytest.mark.skip\nx = 1  # noqa\n')
        self.write('u.ts', '// @ts-ignore\n')
        f = [f for f in self.findings() if f['kind'] == 'test-weakened']
        self.assertEqual({x['path'] for x in f}, {'t.test.js', 't.py', 'u.ts'})
        self.assertIn('needs a reason in the report', f[0]['message'])

    def test_test_weakened_raised_timeout(self):
        self.write('vitest.config.js', 'export default { testTimeout: 5000 }\n')
        self.commit()
        git(self.repo, 'branch', '-f', 'main', 'HEAD')
        self.write('vitest.config.js', 'export default { testTimeout: 60000 }\n')
        self.assertIn(('test-weakened', 'vitest.config.js'), self.kinds())

    def test_test_weakened_snapshot_ci_and_config(self):
        self.write('__snapshots__/a.snap', 'x\n')
        self.write('.github/workflows/ci.yml', 'on: push\n')
        self.write('tsconfig.json', '{}\n')
        self.write('pyproject.toml', '[tool.ruff]\nline-length = 100\n')
        k = self.kinds()
        for p in ('__snapshots__/a.snap', '.github/workflows/ci.yml', 'tsconfig.json', 'pyproject.toml'):
            self.assertIn(('test-weakened', p), k)

    def test_pyproject_outside_lint_sections_is_not_flagged(self):
        self.write('pyproject.toml', '[project]\nname = "x"\n')
        self.assertNotIn(('test-weakened', 'pyproject.toml'), self.kinds())

    def test_self_mock(self):
        self.write('pkg/__init__.py', '')
        self.write('a.test.js', "vi.mock('./thing')\njest.mock('react')\n")
        self.write('t.py', "from unittest import mock\nmock.patch('pkg.mod.fn')\nmock.patch('os.path.exists')\n")
        f = [f for f in self.findings() if f['kind'] == 'self-mock']
        self.assertEqual(sorted((x['path'], x['line']) for x in f), [('a.test.js', 1), ('t.py', 2)])

    def test_debug_print_only_with_debug_in_python(self):
        self.write('app.py', "print('hello')\nprint('DEBUG x')\nbreakpoint()\n")
        f = [f for f in self.findings() if f['kind'] == 'debug']
        self.assertEqual([x['line'] for x in f], [2, 3])

    def test_docs_that_quote_patterns_are_not_code(self):
        self.write('notes.md', "Use `[DEBUG-a1]` tags and never `.skip(` a test.\n")
        self.assertFalse([f for f in self.findings() if f['kind'] in ('debug', 'test-weakened')])

    def test_rules_files(self):
        self.write('AGENTS.md', 'rules\n')
        self.write('.claude/settings.json', '{}\n')
        k = self.kinds()
        self.assertIn(('rules', 'AGENTS.md'), k)
        self.assertIn(('rules', '.claude/settings.json'), k)

    def test_sensitive_paths(self):
        for p in ('src/auth/x.py', 'login.ts', 'db/migrations/001.sql', 'lib/Payment_service.py', '.env.local', 'webhook.js'):
            self.write(p, 'x\n')
        self.write('src/plain.py', 'x\n')
        k = {p for kind, p in self.kinds() if kind == 'sensitive'}
        self.assertEqual(k, {'src/auth/x.py', 'login.ts', 'db/migrations/001.sql', 'lib/Payment_service.py', '.env.local', 'webhook.js'})

    def test_secret_reported_without_value(self):
        key = 'AKIA' + 'ABCDEFGHIJKLMNOP'
        self.write('conf.txt', f'a\nkey = {key}\n')
        self.write('pk.txt', '-----BEGIN RSA PRIVATE KEY-----\n')
        self.write('gh.txt', 'ghp_' + 'a' * 36 + '\n')
        p = self.run_check()
        self.assertEqual(p.returncode, 0)
        self.assertIn('secret conf.txt:2', p.stdout)
        self.assertIn('secret pk.txt:1', p.stdout)
        self.assertIn('secret gh.txt:1', p.stdout)
        self.assertNotIn(key, p.stdout + p.stderr)
        self.assertNotIn('ghp_aaaa', p.stdout)

    def test_text_output_grouped_with_summary(self):
        self.write('app.py', "print('DEBUG')\n")
        out = self.run_check().stdout.strip().splitlines()
        self.assertTrue(out[0].startswith('debug app.py:1 '))
        self.assertIn('finding', out[-1])

    def test_json_shape_and_base(self):
        self.write('app.js', 'debugger;\n')
        d = json.loads(self.run_check('--json').stdout)
        sha = subprocess.run(['git', 'rev-parse', 'main'], cwd=self.repo, capture_output=True, text=True).stdout.strip()
        self.assertEqual(d['base'], sha)
        self.assertEqual(set(d['findings'][0]), {'kind', 'path', 'line', 'message'})
        self.assertEqual(d['counts']['debug'], 1)

    def test_base_option(self):
        self.write('a.js', 'debugger;\n')
        self.commit()
        self.assertIn(('debug', 'a.js'), self.kinds())
        self.assertNotIn(('debug', 'a.js'), self.kinds('--base', 'HEAD'))

    def test_invalid_arguments_exit_2(self):
        for args in (['--bogus'], ['--max-lines', 'x'], ['--max-lines'], ['--base']):
            self.assertEqual(self.run_check(*args).returncode, 2, args)
        self.assertEqual(self.run_check('--base', 'nope-ref').returncode, 2)

    def test_non_utf8_content_does_not_crash(self):
        (self.repo / 'latin.js').write_bytes(b'x\n')
        self.commit()
        (self.repo / 'latin.js').write_bytes(b'caf\xe9 = 1\ndebugger;\n')
        (self.repo / 'new.js').write_bytes(b'caf\xe9\ndebugger;\n')
        k = self.kinds()
        self.assertIn(('debug', 'latin.js'), k)
        self.assertIn(('debug', 'new.js'), k)

    def test_path_with_double_quote_staged_and_untracked(self):
        self.write('a"b.js', 'debugger;\n')
        git(self.repo, 'add', '-A')
        self.write('c"d.js', 'debugger;\n')
        k = self.kinds()
        self.assertIn(('debug', 'a"b.js'), k)
        self.assertIn(('debug', 'c"d.js'), k)

    def test_path_with_space(self):
        self.write('my dir/my file.js', 'debugger;\n')
        self.commit()
        self.write('my dir/my file.js', 'debugger;\nconsole.log(1)\n')
        self.assertIn(('debug', 'my dir/my file.js'), self.kinds())

    def test_run_from_subdirectory_reads_relative_to_root(self):
        self.write('sub/huge.py', 'x = 1\n' * 700)
        self.write('sub/small.py', 'x = 1\n' * 600)
        self.write('.orchestra/budget-waivers', 'sub/small.py legacy\n')
        k = self.kinds(cwd=self.repo / 'sub')
        self.assertIn(('size', 'sub/huge.py'), k)
        self.assertNotIn(('size', 'sub/small.py'), k)

    def test_pure_rename_is_not_growth(self):
        self.write('old.py', "x = 1\n" * 599 + "print('DEBUG')\n" + 'y = 1  # noqa\n')
        self.commit()
        git(self.repo, 'branch', '-f', 'main', 'HEAD')
        git(self.repo, 'mv', 'old.py', 'moved.py')
        k = self.kinds()
        self.assertFalse([x for x in k if x[1] == 'moved.py' and x[0] in ('size', 'debug', 'test-weakened')], k)

    def test_renamed_and_grown_file_compares_with_old_path(self):
        self.write('old.py', 'x = 1\n' * 600)
        self.commit()
        git(self.repo, 'branch', '-f', 'main', 'HEAD')
        git(self.repo, 'mv', 'old.py', 'moved.py')
        self.write('moved.py', 'x = 1\n' * 600 + 'debugger;\n')
        f = [f for f in self.findings() if f['path'] == 'moved.py']
        self.assertEqual([x['kind'] for x in f if x['kind'] != 'size'], ['debug'])
        self.assertIn('600 lines at base, 601 now', [x['message'] for x in f if x['kind'] == 'size'][0])

    def test_sensitive_plurals_and_camel_case(self):
        paths = ('src/payments/charge.ts', 'src/permissions/policy.ts', 'authMiddleware.ts', 'src/oauth.ts', 'a/userSessions.py')
        for p in paths:
            self.write(p, 'x\n')
        self.write('src/author.py', 'x\n')
        k = {p for kind, p in self.kinds() if kind == 'sensitive'}
        self.assertEqual(k, set(paths))

    def test_binary_file_is_skipped(self):
        (self.repo / 'blob.bin').write_bytes(b'\0debugger;\n' * 600)
        self.commit()
        (self.repo / 'blob.bin').write_bytes(b'\0debugger;\n' * 700)
        (self.repo / 'new.bin').write_bytes(b'\0console.log(1)\n' * 600)
        self.assertFalse([k for k in self.kinds() if k[0] in ('size', 'debug')])

    def test_deleted_file_is_not_scanned(self):
        self.write('gone.py', 'x = 1\n' * 600)
        self.commit()
        git(self.repo, 'branch', '-f', 'main', 'HEAD')
        (self.repo / 'gone.py').unlink()
        self.assertFalse([k for k in self.kinds() if k[0] == 'size'])

    def test_no_merge_base_exits_2(self):
        git(self.repo, 'switch', '-q', '--orphan', 'unrelated')
        self.write('z.txt', 'z\n')
        self.commit('orphan')
        p = self.run_check()
        self.assertEqual(p.returncode, 2)
        self.assertIn('no base', p.stderr)

    def test_generated_marker_must_be_a_comment_saying_so(self):
        self.write('a.py', '# Generated reports are written elsewhere\n' + 'x = 1\n' * 600)
        self.write('b.py', '# Code generated by protoc. DO NOT EDIT.\n' + 'x = 1\n' * 600)
        self.write('c.py', 'x = 1\n' * 10 + '# this file is generated\n' + 'x = 1\n' * 600)
        k = self.kinds()
        self.assertIn(('size', 'a.py'), k)
        self.assertNotIn(('size', 'b.py'), k)
        self.assertIn(('size', 'c.py'), k)

    def test_timeout_compared_only_with_same_test(self):
        self.write('t.test.js', "it('a', fn, {timeout: 5000})\nit('b', fn, {timeout: 9000})\n")
        self.commit()
        git(self.repo, 'branch', '-f', 'main', 'HEAD')
        self.write('t.test.js', "it('a', fn, {timeout: 4000})\nit('b', fn, {timeout: 9000})\nit('c', fn, {timeout: 7000})\n")
        self.assertNotIn(('test-weakened', 't.test.js'), self.kinds())
        self.write('t.test.js', "it('a', fn, {timeout: 6000})\nit('b', fn, {timeout: 9000})\n")
        self.assertIn(('test-weakened', 't.test.js'), self.kinds())


if __name__ == '__main__':
    unittest.main()
