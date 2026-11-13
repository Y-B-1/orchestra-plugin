"""Unit tests for the test gate (scripts/gate.py): full-once, scoped e2e, skips, status and the Stop-hook condition."""
import json, os, shutil, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock

from tests.support import LEAN, git, make_repo
import gate, lean, procs  # noqa: E402  (tests.support put the scripts folder on sys.path)

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
        self.commit()  # the gate counts only commits the default branch lacks

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

    def claim(self, **fields):
        f = gate.file(self.cwd)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({'work': {'claim': fields}}))

    def test_concurrent_full_runs_let_exactly_one_run(self):
        slow = [sys.executable, '-c', 'import time; time.sleep(2)']
        procs = [subprocess.Popen([sys.executable, str(LEAN), 'gate', 'unit', '--full', '--', *slow], cwd=self.cwd,
                                  stderr=subprocess.PIPE, text=True) for _ in range(2)]
        out = [(p.wait(), p.stderr.read()) for p in procs]
        for p in procs:
            p.stderr.close()
        self.assertEqual(sorted(c for c, _ in out), [0, 3], out)
        refused = next(e for c, e in out if c == 3)
        self.assertIn('a full run is running for this branch (started ', refused)
        self.assertIn('); run scoped', refused)

    def test_a_claim_of_a_dead_process_does_not_block(self):
        dead = subprocess.Popen([sys.executable, '-c', 'pass'])
        dead.wait()
        self.claim(pid=dead.pid, start=int(time.time()), limit=600)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)

    def test_a_claim_past_its_limit_does_not_block(self):
        self.claim(pid=os.getpid(), start=int(time.time()) - 100, limit=10)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)

    def test_a_live_claim_within_its_limit_blocks(self):
        self.claim(pid=os.getpid(), start=int(time.time()), limit=600)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 3)

    def test_a_timed_out_full_run_leaves_no_claim(self):
        slow = [sys.executable, '-c', 'import time; time.sleep(3)']
        self.assertEqual(self.cli('unit', '--full', '--seconds', '1', '--', *slow).returncode, 124)
        self.assertNotIn('claim', json.loads(gate.file(self.cwd).read_text())['work'])
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)
        self.assertNotIn('claim', json.loads(gate.file(self.cwd).read_text())['work'])

    def test_scoped_is_always_allowed(self):
        for _ in range(2):
            self.assertEqual(self.cli('unit', '--scoped', '--', *OK).returncode, 0)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)
        self.assertEqual(self.cli('unit', '--scoped', '--', *FAIL).returncode, 1)

    def test_e2e_scope_detection(self):
        table = [
            (['e2e', 'run', '--changed-since', 'main'], True), (['e2e', 'run', '--grep', 'login'], True),
            (['e2e', 'run', '--tag=smoke'], True), (['e2e', 'run', '--last-failed'], False),
            (['e2e', 'run', '--shard', '1/4'], False), (['e2e', 'run', 'tests/a.e2e.ts'], True),
            (['npx', 'playwright', 'test', 'x.spec.ts'], True), (['vitest', 'run', 'a.test.tsx'], True),
            (['e2e', 'run'], False), (['e2e', 'run', '--headed'], False),
        ]
        for cmd, scoped in table:
            self.assertEqual(gate.e2e_scoped(cmd), scoped, cmd)

    def test_changed_since_needs_filters_in_the_e2e_config(self):
        run = ['e2e', 'run', '--changed-since', 'main']
        self.assertEqual(gate.filters_missing(run, self.cwd), '')  # no e2e config: nothing to check
        for name, text, missing in (('e2e.config.ts', 'export default { filters: {} }', ''), ('e2e.config.mjs', 'export default {}', 'e2e.config.mjs')):
            cfg = Path(self.cwd) / name
            cfg.write_text(text)
            self.assertEqual(gate.filters_missing(run, self.cwd), missing, name)
            self.assertEqual(gate.filters_missing(run + ['--grep', 'x'], self.cwd), '', 'another scope narrows the run')
            self.assertEqual(gate.filters_missing(['playwright', 'test', '--changed-since', 'main'], self.cwd), '', 'not the e2e runner')
            cfg.unlink()

    def test_filters_config_is_found_like_the_runner_finds_it(self):
        root, run = Path(self.cwd), ['e2e', 'run', '--changed-since', 'main']
        (root / 'pkg' / 'deep').mkdir(parents=True)
        (root / 'e2e.config.mts').write_text('export default {}')
        (root / 'pkg' / 'e2e.config.ts').write_text('export default { filters: {} }')
        self.assertEqual(gate.filters_missing(run, self.cwd), 'e2e.config.mts', '.mts is a config')
        self.assertEqual(gate.filters_missing(run + ['--config', 'pkg/e2e.config.ts'], self.cwd), '', '--config names the file')
        self.assertEqual(gate.filters_missing(run + ['--config=pkg/e2e.config.ts'], self.cwd), '')
        self.assertEqual(gate.filters_missing(run + ['-c', 'e2e.config.mts'], self.cwd), 'e2e.config.mts')
        self.assertEqual(gate.filters_missing(run, str(root / 'pkg' / 'deep')), '', 'the nearest config upward wins')
        (root / 'pkg' / 'e2e.config.ts').unlink()
        self.assertEqual(os.path.basename(gate.filters_missing(run, str(root / 'pkg' / 'deep'))), 'e2e.config.mts', 'found upward')

    def test_the_e2e_runner_is_found_after_runner_options_and_a_version(self):
        (Path(self.cwd) / 'e2e.config.ts').write_text('export default {}')
        for pre in (['npx', '--yes'], ['npx'], ['bunx'], ['pnpm', 'exec'], ['pnpm', 'dlx'], ['npx', '-y']):
            for name in ('e2e', 'e2e@latest', 'e2e@0.23.1'):
                run = pre + [name, 'run', '--changed-since', 'main']
                self.assertEqual(gate.filters_missing(run, self.cwd), 'e2e.config.ts', run)

    def test_owner_full_override_lifts_the_filters_refusal(self):
        (Path(self.cwd) / 'e2e.config.ts').write_text('export default {}')
        cmd = ('e2e', 'run', '--changed-since', 'main')
        self.assertEqual(self.cli('e2e', '--', *cmd).returncode, 3)
        if os.name == 'nt':  # the stub runner is a shell script that Windows cannot start without a shell: prove only that the refusal lifts
            self.assertNotEqual(self.cli('e2e', '--', *cmd, env={'ORCHESTRA_E2E_FULL': '1'}).returncode, 3)
            return
        bin_dir = Path(self.cwd).parent / 'bin'  # a stub runner that exits 0: the run is allowed and started
        bin_dir.mkdir()
        stub = bin_dir / 'e2e'
        stub.write_text('#!/bin/sh\nexit 0\n')
        stub.chmod(0o755)
        path = os.pathsep.join([str(bin_dir), os.environ.get('PATH', '')])
        self.assertEqual(self.cli('e2e', '--', *cmd, env={'ORCHESTRA_E2E_FULL': '1', 'PATH': path}).returncode, 0)

    def test_gate_e2e_refuses_changed_since_without_filters(self):
        (Path(self.cwd) / 'e2e.config.ts').write_text('export default {}')
        r = self.cli('e2e', '--', 'e2e', 'run', '--changed-since', 'main')
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn('no `filters`', r.stderr)
        self.assertIn('add `filters`', r.stderr)

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
        head = git(self.cwd, 'rev-parse', 'HEAD')
        lib, call = (procs.fcntl, 'flock') if procs.fcntl else (procs.msvcrt, 'locking')  # the OS lock call of this platform
        with mock.patch.object(lib, call, side_effect=OSError(77, 'no locks')):
            gate.record(self.cwd, lambda entry: entry.setdefault('skips', {}).__setitem__('unit', {'reason': 'x', 'head': head}))
        self.assertEqual(gate.entry_of(self.cwd)['skips'], {'unit': {'reason': 'x', 'head': head}})

    def test_a_pid_is_alive_only_when_it_is_a_running_process(self):
        self.assertTrue(procs.alive(os.getpid()))
        self.assertFalse(procs.alive(0))
        self.assertFalse(procs.alive(-5))

    def test_a_wrong_shaped_state_file_reads_as_empty_and_is_rewritten(self):
        f = gate.file(self.cwd)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({'work': {'runs': {'unit': [1, 'x']}, 'skips': 5, 'full': []}}))
        self.assertEqual(self.cli('unit', '--scoped', '--', *OK).returncode, 0)
        self.assertEqual([r['exit'] for r in gate.entry_of(self.cwd)['runs']['unit']], [0])

    def test_usage_errors(self):
        for args in (['unit', '--', *OK], ['unit', '--full'], ['unit', '--full', '--'], ['bogus'], []):
            self.assertEqual(self.cli(*args).returncode, 2, args)

    def test_a_skip_cannot_turn_a_red_gate_green(self):
        self.assertEqual(self.cli('unit', '--full', '--', *FAIL).returncode, 1)
        self.assertEqual(self.cli('skip', 'e2e', 'none').returncode, 0)
        self.assertEqual(self.cli('status').returncode, 1)
        refused = self.cli('skip', 'unit', 'flaky')
        self.assertEqual(refused.returncode, 3)
        self.assertIn('this repository has a unit runner: runs are recorded; a skip is for a repo with no runner', refused.stderr)
        self.assertEqual(self.cli('status').returncode, 1)

    def test_a_skip_of_a_kind_is_refused_after_a_run_of_that_kind(self):
        self.cli('e2e', '--', *OK, '--grep', 'x')
        self.assertEqual(self.cli('skip', 'e2e', 'none').returncode, 3)
        self.assertEqual(self.cli('skip', 'unit', 'none').returncode, 0)

    def test_an_earlier_skip_is_ignored_while_a_run_of_that_kind_is_red_at_head(self):
        self.cli('skip', 'unit', 'none')
        self.cli('skip', 'e2e', 'none')
        self.assertEqual(self.cli('status').returncode, 0)
        self.cli('unit', '--scoped', '--', *FAIL)
        self.assertEqual(self.cli('status').returncode, 1)

    def test_the_skip_hint_shows_only_when_no_run_of_that_kind_is_recorded(self):
        self.assertIn('gate skip unit REASON', self.cli('status').stdout)
        self.cli('unit', '--full', '--', *FAIL)
        self.assertNotIn('gate skip unit', self.cli('status').stdout)
        self.assertIn('gate skip e2e', self.cli('status').stdout)

    def recreate(self):
        self.cli('skip', 'e2e', 'old')
        self.cli('unit', '--full', '--', *OK)
        self.assertEqual(self.cli('status').returncode, 0)
        git(self.cwd, 'checkout', '-q', 'main')
        git(self.cwd, 'branch', '-q', '-D', 'work')
        git(self.cwd, 'checkout', '-q', '-b', 'work')
        git(self.cwd, 'commit', '-q', '--allow-empty', '-m', 'again')  # another message: the same commit within one second would be the old head

    def test_a_recreated_branch_starts_without_the_old_full_run_and_skips(self):
        self.recreate()
        self.assertEqual(self.cli('status').returncode, 1)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)

    def test_a_recreated_branch_is_not_held_by_a_scoped_run_alone(self):
        self.recreate()
        self.cli('e2e', '--', *OK, '--grep', 'x')
        self.cli('unit', '--scoped', '--', *OK)
        status = self.cli('status')
        self.assertEqual(status.returncode, 1)
        self.assertIn('gate unit --full', status.stdout)

    def test_a_full_run_that_reached_the_default_branch_no_longer_counts(self):
        self.cli('unit', '--full', '--', *OK)
        git(self.cwd, 'branch', '-f', 'main', 'work')
        self.commit()
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)

    def test_a_full_command_that_did_not_start_does_not_use_up_the_full_run(self):
        for code in (126, 127):
            self.assertEqual(self.cli('unit', '--full', '--', sys.executable, '-c', f'raise SystemExit({code})').returncode, code)
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)

    def test_status_names_a_red_full_run(self):
        self.cli('skip', 'e2e', 'none')
        self.cli('unit', '--full', '--', *FAIL)
        out = self.cli('status').stdout
        self.assertIn('exit 1', out)
        self.assertIn('raise SystemExit(1)', out)

    def test_a_skip_does_not_hide_a_red_run_after_one_more_commit(self):
        self.cli('skip', 'unit', 'r')
        self.assertEqual(self.cli('unit', '--full', '--', *FAIL).returncode, 1)
        self.cli('skip', 'e2e', 'r')
        self.assertEqual(self.cli('status').returncode, 1)
        self.commit()
        self.assertEqual(self.cli('status').returncode, 1)

    def test_an_amend_does_not_let_a_skip_through_after_a_run(self):
        self.cli('unit', '--full', '--', *FAIL)
        self.assertEqual(self.cli('skip', 'unit', 'r').returncode, 3)
        git(self.cwd, 'commit', '-q', '--amend', '--no-edit', '--allow-empty')
        refused = self.cli('skip', 'unit', 'r')
        self.assertEqual(refused.returncode, 3)
        self.assertIn('this repository has a unit runner: runs are recorded; a skip is for a repo with no runner', refused.stderr)
        self.cli('skip', 'e2e', 'r')
        self.assertEqual(self.cli('status').returncode, 1)

    def test_the_runner_flag_is_kept_at_the_top_level_and_old_files_still_read(self):
        self.cli('unit', '--scoped', '--', *OK)
        self.cli('e2e', '--', *OK, '--grep', 'x')
        self.assertEqual(json.loads(gate.file(self.cwd).read_text())['runner'], {'unit': True, 'e2e': True})
        gate.file(self.cwd).write_text('{"work": {"skips": {"unit": {"reason": "r", "head": "x"}}}}')
        self.assertEqual(self.cli('status').returncode, 1)
        gate.file(self.cwd).write_text('{"runner": 5}')
        self.assertEqual(self.cli('skip', 'unit', 'r').returncode, 0)

    def test_a_branch_with_no_commits_beyond_the_default_branch_has_nothing_to_gate(self):
        git(self.cwd, 'update-ref', 'refs/heads/main', 'HEAD')
        self.assertEqual(gate.missing(self.cwd), [])
        self.assertEqual(self.cli('status').returncode, 0)
        for args in (['skip', 'unit', 'r'], ['unit', '--full', '--', *OK]):
            done = self.cli(*args)
            self.assertEqual(done.returncode, 3, args)
            self.assertIn('no commits beyond main: nothing to gate yet; commit first', done.stderr)
        self.commit()
        self.assertEqual(self.cli('unit', '--full', '--', *OK).returncode, 0)

    def test_skip_e2e_is_refused_where_the_repo_holds_an_e2e_config(self):
        (Path(self.cwd) / 'e2e.config.ts').write_text('export default {}')
        r = self.cli('skip', 'e2e', 'no runner')
        self.assertEqual(r.returncode, 3)
        self.assertIn('gate: this repo has an e2e config (e2e.config.ts), so e2e runs scoped instead of skipped: '
                      'gate e2e -- e2e run --changed-since <base>. The owner allows a skip with ORCHESTRA_E2E_SKIP=1.', r.stderr)
        self.assertEqual(self.cli('skip', 'unit', 'no runner').returncode, 0)
        self.assertEqual(self.cli('skip', 'e2e', 'no runner', env={'ORCHESTRA_E2E_SKIP': '1'}).returncode, 0)
        self.assertEqual(self.cli('status').returncode, 0)

    def agentic(self, selected, report=True):
        """A repo with an e2e config holding filters, a report with one result per flag in selected, and a stub `e2e` that exits 0."""
        root = Path(self.cwd)
        (root / 'e2e.config.ts').write_text('export default { filters: [] }')
        if report:
            (root / '.e2e').mkdir()
            (root / '.e2e' / 'report.json').write_text(json.dumps({'run': {'results': [{'selected': s} for s in selected]}}))
        bin_dir = root.parent / 'bin'
        bin_dir.mkdir(exist_ok=True)
        stub = bin_dir / 'e2e'
        stub.write_text('#!/bin/sh\nexit 0\n')
        stub.chmod(0o755)
        return {'PATH': os.pathsep.join([str(bin_dir), os.environ.get('PATH', '')])}

    def last_run(self):
        return json.loads(gate.file(self.cwd).read_text())['work']['runs']['e2e'][-1]

    NOTE = 'gate: this --changed-since run left out no test (3 of 3 ran). The filter may have failed open'

    @unittest.skipIf(os.name == 'nt', 'the stub runner is a shell script')
    def test_a_changed_since_run_that_left_nothing_out_is_noted_and_recorded(self):
        env = self.agentic([True, True, True])
        r = self.cli('e2e', '--', 'e2e', 'run', '--changed-since', 'main', env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(self.NOTE, r.stderr)
        self.assertIn('lean.py e2e-doctor', r.stderr)
        self.assertEqual(self.last_run()['left_out'], 0)
        status = self.cli('status')
        self.assertIn(self.NOTE, status.stdout)

    @unittest.skipIf(os.name == 'nt', 'the stub runner is a shell script')
    def test_a_run_that_left_a_test_out_or_has_no_usable_report_stays_quiet(self):
        for selected, report, extra in (([True, False, True], True, []), ([True], True, []), ([], False, []), ([True, True], True, ['--grep', 'x'])):
            with self.subTest(selected=selected, report=report, extra=extra):
                shutil.rmtree(Path(self.cwd) / '.e2e', ignore_errors=True)
                env = self.agentic(selected, report)
                r = self.cli('e2e', '--', 'e2e', 'run', '--changed-since', 'main', *extra, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertNotIn('left out no test', r.stderr)
                self.assertNotIn('left_out', self.last_run())
                self.assertNotIn('left out no test', self.cli('status').stdout)

    def doctor(self, *args, env=None):
        r = subprocess.run([sys.executable, str(LEAN), 'e2e-doctor', *args], cwd=self.cwd, capture_output=True, text=True,
                           env={**os.environ, **(env or {})})
        return r.returncode, r.stdout

    def set_up_e2e(self, config='export default { filters: [decisionFilter({ model: m(process.env.TYPESAFE_AI_API_KEY) })] }'):
        root = Path(self.cwd)
        (root / 'e2e.config.ts').write_text(config)
        (root / 'package.json').write_text(json.dumps({'devDependencies': {'e2e': '^0.23.1', '@e2e-dev/decision': '^0.3.3'}}))
        (root / '.env.e2e.local').write_text('TYPESAFE_AI_API_KEY=sekret-value\n')
        (root / '.agents' / 'skills' / 'e2e').mkdir(parents=True)
        (root / '.agents' / 'skills' / 'e2e' / 'SKILL.md').write_text('skill')

    def test_e2e_doctor_passes_a_complete_setup_and_never_prints_a_key_value(self):
        self.set_up_e2e()
        code, out = self.doctor()
        self.assertEqual(code, 0, out)
        self.assertEqual([line.split()[0] for line in out.splitlines()], ['ok'] * 6, out)
        self.assertIn('TYPESAFE_AI_API_KEY', out)
        self.assertNotIn('sekret-value', out)

    def test_e2e_doctor_names_each_gap(self):
        self.set_up_e2e('export default { agent: process.env.OPENROUTER_API_KEY }')
        (Path(self.cwd) / 'package.json').write_text(json.dumps({'dependencies': {'e2e': '1'}}))
        (Path(self.cwd) / '.env.e2e.local').unlink()
        (Path(self.cwd) / '.agents' / 'skills' / 'e2e' / 'SKILL.md').unlink()
        code, out = self.doctor()
        self.assertEqual(code, 1, out)
        gaps = [line for line in out.splitlines() if line.startswith('gap')]
        self.assertEqual(len(gaps), 4, out)
        self.assertTrue(any('filters' in g for g in gaps) and any('@e2e-dev/decision' in g for g in gaps), out)
        self.assertTrue(any('OPENROUTER_API_KEY' in g for g in gaps) and any('SKILL.md' in g for g in gaps), out)
        code, out = self.doctor(env={'OPENROUTER_API_KEY': 'v4lue'})
        self.assertNotIn('OPENROUTER_API_KEY', ''.join(line for line in out.splitlines() if line.startswith('gap')))
        self.assertNotIn('v4lue', out)

    def test_e2e_doctor_without_a_config_gives_the_setup_command_and_rejects_bad_usage(self):
        code, out = self.doctor()
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count('gap'), 1, out)
        self.assertIn('npx e2e init --yes', out)
        self.assertIn('npm install --save-dev e2e @e2e-dev/web ai@^7', out)
        self.assertEqual(self.doctor('--bogus')[0], 2)
        self.assertEqual(self.doctor('--config')[0], 2)


if __name__ == '__main__':
    unittest.main()
