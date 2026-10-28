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

    def run_check(self, *args):
        p = subprocess.run([sys.executable, str(LEAN), 'check', *args], cwd=self.repo, capture_output=True, text=True)
        return p

    def findings(self, *args):
        p = self.run_check('--json', *args)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)['findings']

    def kinds(self, *args):
        return {(f['kind'], f['path']) for f in self.findings(*args)}

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


if __name__ == '__main__':
    unittest.main()
