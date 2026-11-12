"""Unit tests for the test gate (scripts/gate.py): full-once, scoped e2e, skips, status and the Stop-hook condition."""
import os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orchestra'
LEAN = ROOT / 'scripts/lean.py'
sys.path.insert(0, str(ROOT / 'scripts'))
import gate, lean  # noqa: E402

OK, FAIL = [sys.executable, '-c', 'pass'], [sys.executable, '-c', 'raise SystemExit(1)']


def git(cwd, *args):
    subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)


class GateTest(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(lean.SESSION_ENV, None)
        os.environ.pop('ORCHESTRA_E2E_FULL', None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = self.tmp.name
        git(self.cwd, 'init', '-q', '-b', 'work')
        git(self.cwd, 'config', 'user.email', 't@example.com')
        git(self.cwd, 'config', 'user.name', 'T')
        self.commit()

    def commit(self):
        git(self.cwd, 'commit', '-q', '--allow-empty', '-m', 'c')

    def cli(self, *args, env=None):
        return subprocess.run([sys.executable, str(LEAN), 'gate', *args], cwd=self.cwd, capture_output=True, text=True,
                              env={**os.environ, **(env or {})})

    def test_first_full_run_allowed_second_refused(self):
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)
        again = self.cli('unit', '--full', '--', *OK)
        self.assertEqual(again.returncode, 3)
        self.assertIn('a full run is already recorded for this branch; run scoped', again.stderr)

    def test_a_failing_full_run_returns_its_exit_and_still_counts(self):
        self.assertEqual(self.cli('unit', '--full', '--', *FAIL).returncode, 1)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 3)

    def test_a_timed_out_full_run_does_not_count(self):
        slow = [sys.executable, '-c', 'import time; time.sleep(30)']
        self.assertEqual(self.cli('unit', '--full', '--seconds', '0.5', '--', *slow).returncode, 124)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)

    def test_scoped_is_always_allowed(self):
        for _ in range(2):
            self.assertEqual(self.cli('unit', '--scoped', '--', *OK).returncode, 0)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)
        self.assertEqual(self.cli('unit', '--scoped', '--', *FAIL).returncode, 1)

    def test_e2e_scope_detection(self):
        table = [
            (['e2e', 'run', '--changed-since', 'main'], True), (['e2e', 'run', '--grep', 'login'], True),
            (['e2e', 'run', '--tag=smoke'], True), (['e2e', 'run', '--last-failed'], True),
            (['e2e', 'run', '--shard', '1/4'], True), (['e2e', 'run', 'tests/a.e2e.ts'], True),
            (['npx', 'playwright', 'test', 'x.spec.ts'], True), (['vitest', 'run', 'a.test.tsx'], True),
            (['e2e', 'run'], False), (['e2e', 'run', '--headed'], False),
        ]
        for cmd, scoped in table:
            self.assertEqual(gate.e2e_scoped(cmd), scoped, cmd)

    def test_e2e_unscoped_refused_unless_owner_allows(self):
        cmd = [sys.executable, '-c', 'pass']  # no scope flag
        r = self.cli('e2e', '--', *cmd)
        self.assertEqual(r.returncode, 3)
        self.assertIn('ORCHESTRA_E2E_FULL=1', r.stderr)
        self.assertEqual(self.cli('e2e', '--', *cmd, env={'ORCHESTRA_E2E_FULL': '1'}).returncode, 0)
        self.assertEqual(self.cli('e2e', '--', *OK, '--grep', 'x').returncode, 0)

    def test_skip_requires_a_reason(self):
        self.assertEqual(self.cli('skip', 'unit').returncode, 2)
        self.assertEqual(self.cli('skip', 'lint', 'no runner').returncode, 2)
        self.assertEqual(self.cli('skip', 'unit', 'no', 'runner').returncode, 0)

    def test_status_holds_and_goes_stale_for_the_head_part_only(self):
        s = self.cli('status')
        self.assertEqual(s.returncode, 1)
        self.assertIn('gate unit --full', s.stdout)
        self.cli('unit', '--full', '--', *OK)
        self.cli('skip', 'e2e', 'no', 'e2e')
        self.assertEqual(self.cli('status').returncode, 0)
        self.commit()
        stale = self.cli('status')
        self.assertEqual(stale.returncode, 1)
        self.assertIn('gate unit --scoped', stale.stdout)
        self.assertNotIn('--full', stale.stdout)
        self.cli('unit', '--scoped', '--', *OK)
        self.assertEqual(self.cli('status').returncode, 0)

    def test_a_failed_unit_run_at_head_does_not_hold(self):
        self.cli('skip', 'e2e', 'no e2e')
        self.cli('unit', '--full', '--', *FAIL)
        self.assertEqual(self.cli('status').returncode, 1)

    def test_a_skip_covers_unit_without_a_full_run(self):
        self.cli('skip', 'unit', 'no', 'runner')
        self.cli('skip', 'e2e', 'no', 'runner')
        self.assertEqual(self.cli('status').returncode, 0)

    def test_e2e_run_at_head_holds_e2e(self):
        self.cli('skip', 'unit', 'none')
        self.assertEqual(self.cli('status').returncode, 1)
        self.cli('e2e', '--', *OK, '--grep', 'x')
        self.assertEqual(self.cli('status').returncode, 0)

    def test_damaged_gate_json_reads_as_empty(self):
        self.cli('skip', 'e2e', 'none')
        for damaged in ('{not json', '[1]', '{"work": 5}'):
            gate.file(self.cwd, None).write_text(damaged)
            self.assertEqual(self.cli('status').returncode, 1)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)

    def test_stop_hook_condition_names_the_gate(self):
        self.assertIn('gate', ' '.join(gate.missing(self.cwd, None)))
        self.cli('skip', 'unit', 'x')
        self.cli('skip', 'e2e', 'x')
        self.assertEqual(gate.missing(self.cwd, None), [])

    def test_goal_missing_asks_for_the_gate_only_with_commits_beyond_base(self):
        git(self.cwd, 'update-ref', 'refs/heads/main', 'HEAD')
        lean.state_dir(self.cwd, create=True)
        lean.ledger(self.cwd).write_text('- [x] A1: done\n- [x] review: clean\n')
        self.assertEqual(lean.goal_missing(self.cwd, None, []), [])
        self.commit()
        self.assertIn('gate unit --full', ' '.join(lean.goal_missing(self.cwd, None, [])))
        self.cli('skip', 'unit', 'x')
        self.cli('skip', 'e2e', 'x')
        self.assertEqual(lean.goal_missing(self.cwd, None, []), [])

    def test_usage_errors(self):
        for args in (['unit', '--', *OK], ['unit', '--full'], ['unit', '--full', '--'], ['bogus'], []):
            self.assertEqual(self.cli(*args).returncode, 2, args)


if __name__ == '__main__':
    unittest.main()
