"""Unit tests for the test gate (scripts/gate.py): full-once, scoped e2e, skips, status and the Stop-hook condition."""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

from tests.support import LEAN, git, make_repo
import gate, lean  # noqa: E402  (tests.support put the scripts folder on sys.path)

OK, FAIL = [sys.executable, '-c', 'pass'], [sys.executable, '-c', 'raise SystemExit(1)']


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
        make_repo(Path(self.cwd) / 'repo')
        self.cwd = str(Path(self.cwd) / 'repo')
        git(self.cwd, 'checkout', '-q', '-b', 'work')

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
            gate.file(self.cwd).write_text(damaged)
            self.assertEqual(self.cli('status').returncode, 1)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)

    def test_stop_hook_condition_names_the_gate(self):
        self.assertIn('gate', ' '.join(gate.missing(self.cwd)))
        self.cli('skip', 'unit', 'x')
        self.cli('skip', 'e2e', 'x')
        self.assertEqual(gate.missing(self.cwd), [])

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

    def test_a_later_green_command_does_not_hide_a_red_one_at_head(self):
        self.cli('skip', 'e2e', 'none')
        self.cli('unit', '--full', '--', *OK)
        self.assertEqual(self.cli('unit', '--scoped', '--', *FAIL).returncode, 1)
        self.assertEqual(self.cli('unit', '--scoped', '--', sys.executable, '-c', 'x = 1').returncode, 0)
        self.assertEqual(self.cli('status').returncode, 1)

    def test_the_latest_run_of_the_same_command_decides(self):
        self.cli('skip', 'e2e', 'none')
        flag = Path(self.cwd) / 'flag'
        cmd = [sys.executable, '-c', 'import os, sys; sys.exit(0 if os.path.exists(sys.argv[1]) else 1)', str(flag)]
        self.cli('unit', '--full', '--', *OK)
        self.cli('unit', '--scoped', '--', *cmd)
        self.assertEqual(self.cli('status').returncode, 1)
        flag.write_text('x')
        self.cli('unit', '--scoped', '--', *cmd)
        self.assertEqual(self.cli('status').returncode, 0)
        runs = json.loads(gate.file(self.cwd).read_text())['work']['runs']['unit']
        self.assertEqual([r['exit'] for r in runs], [0, 0])  # the full run, and the flag command's latest run only

    def test_e2e_every_command_at_head_must_be_green(self):
        self.cli('skip', 'unit', 'none')
        self.cli('e2e', '--', *FAIL, '--grep', 'a')
        self.cli('e2e', '--', *OK, '--grep', 'b')
        self.assertEqual(self.cli('status').returncode, 1)

    def test_state_is_per_repository_not_per_session(self):
        a, b = {lean.SESSION_ENV: 'sess-a'}, {lean.SESSION_ENV: 'sess-b'}
        self.assertEqual(self.cli('unit', '--full', '--', *OK, env=a).returncode, 0)
        self.assertEqual(self.cli('unit', '--full', '--', *OK, env=b).returncode, 3)
        self.assertEqual(self.cli('skip', 'e2e', 'none', env=b).returncode, 0)
        self.assertEqual(self.cli('status', env=a).returncode, 0)

    def test_outside_a_repository_the_state_sits_in_the_folder(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(LEAN), 'gate', 'skip', 'unit', 'x'], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(d) / '.orchestra/gate.json').exists())

    def test_parallel_records_all_land(self):
        procs = [subprocess.Popen([sys.executable, str(LEAN), 'gate', 'unit', '--scoped', '--', sys.executable, '-c', f'x = {i}'],
                                  cwd=self.cwd, stderr=subprocess.PIPE, text=True) for i in range(20)]
        codes = [(p.wait(), p.stderr.read()) for p in procs]
        for p in procs:
            p.stderr.close()
        self.assertEqual([c for c, _ in codes], [0] * 20, codes)
        self.assertEqual(len(json.loads(gate.file(self.cwd).read_text())['work']['runs']['unit']), 20)

    def test_e2e_scope_reads_config_and_npm_scripts(self):
        scripts = {'e2e:changed': 'e2e run --changed-since main', 'test:e2e': 'e2e run', 'test': 'vitest run',
                   'chain': 'e2e run --changed-since main && e2e run', 'semi': 'e2e run --grep x; e2e run',
                   'fallback': 'e2e run --last-failed || e2e run', 'sub': 'e2e run --grep $(echo x)'}
        (Path(self.cwd) / 'package.json').write_text(json.dumps({'scripts': scripts}))
        table = [
            (['npx', 'vitest', 'run', '--config', 'vitest.config.e2e.ts'], False),
            (['npx', 'jest', '-c', 'jest.config.e2e.js'], False),
            (['npm', 'run', 'e2e:changed'], True), (['pnpm', 'e2e:changed'], True), (['yarn', 'run', 'e2e:changed'], True),
            (['npm', 'run', 'test:e2e'], False), (['npm', 'run', 'test:e2e', '--', '--grep', 'x'], True),
            (['npm', 'run', 'nope'], False), (['npm', 'test'], False),
            (['npm', 'run', 'test:e2e', '--changed-since=HEAD~1'], False), (['npm', 'run', 'test:e2e', '--grep', 'x'], False),
            (['pnpm', 'test:e2e', '--grep', 'x'], True),
            (['npm', 'run', 'chain'], False), (['npm', 'run', 'semi'], False), (['npm', 'run', 'fallback'], False),
            (['npm', 'run', 'sub'], False),
            (['cypress', 'run', '--spec', 'cypress/e2e/login.cy.ts'], True),
            (['playwright', 'test', '-g', 'login'], True), (['playwright', 'test', '--only-changed=origin/main'], True),
        ]
        for cmd, scoped in table:
            self.assertEqual(gate.e2e_scoped(cmd, self.cwd), scoped, cmd)

    def test_a_failing_lock_does_not_lose_the_run(self):
        with mock.patch.object(gate.fcntl, 'flock', side_effect=OSError(77, 'no locks')):
            gate.record(self.cwd, lambda entry: entry.setdefault('skips', {}).__setitem__('unit', 'x'))
        self.assertEqual(gate.entry_of(self.cwd)['skips'], {'unit': 'x'})

    def test_a_wrong_shaped_state_file_reads_as_empty_and_is_rewritten(self):
        f = gate.file(self.cwd)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({'work': {'runs': {'unit': [1, 'x']}, 'skips': 5, 'full': []}}))
        self.assertEqual(self.cli('unit', '--scoped', '--', *OK).returncode, 0)
        self.assertEqual([r['exit'] for r in gate.entry_of(self.cwd)['runs']['unit']], [0])

    def test_usage_errors(self):
        for args in (['unit', '--', *OK], ['unit', '--full'], ['unit', '--full', '--'], ['bogus'], []):
            self.assertEqual(self.cli(*args).returncode, 2, args)


if __name__ == '__main__':
    unittest.main()
