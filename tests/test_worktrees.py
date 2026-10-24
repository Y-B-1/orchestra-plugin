"""TREE2: the read-only `worktrees` listing, the wrong-base refusal and the resume hint. The engine never adds or removes a worktree."""
import json
import pathlib
import shlex
import subprocess
import sys
import unittest
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core import worktrees
from orchestra_core.engine import EngineError

CLI = SCRIPTS / 'orchestra.py'


class WorktreeFixture(te.EngineFixture):
    def add_worktree(self, name, commit=False, dirty=False):
        """What the harness does for a builder: a worktree under .claude/worktrees on its own branch."""
        path = self.repo / '.claude/worktrees' / name
        self.git('worktree', 'add', '-q', '-b', 'orchestra/' + name, str(path))
        run = lambda *a: subprocess.check_output(['git', '-C', str(path), *a], text=True).strip()
        if commit:
            (path / (name + '.txt')).write_text(name)
            run('add', name + '.txt')
            run('-c', 'user.name=T', '-c', 'user.email=t@example.invalid', 'commit', '-qm', name)
        if dirty:
            (path / 'dirty.txt').write_text('x')
        return path, run('rev-parse', 'HEAD')

    def built(self, name, sha):
        self.task(name)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        self.engine.report('w-' + name, token, te.done('Built').replace('ARTIFACT: fixture', 'ARTIFACT: ' + sha + ' clean'))

    def cli(self, *args, lease=False, expected=0):
        cmd = [sys.executable, str(CLI), '--repo', str(self.repo), '--state', str(self.engine.state_dir)]
        if lease:
            cmd += ['--lease', self.lease]
        result = subprocess.run(cmd + list(args), capture_output=True, text=True, timeout=60)
        self.assertEqual(expected, result.returncode, result.stderr + result.stdout)
        return json.loads(result.stdout if expected == 0 else result.stderr)


class ListingTests(WorktreeFixture):
    def test_each_leftover_worktree_names_branch_card_landed_and_clean(self):
        dirty, _ = self.add_worktree('C', dirty=True)  # cut at the initial commit, which serves no card
        landed, landed_sha = self.add_worktree('A', commit=True)
        self.git('merge', '-q', '--ff-only', 'orchestra/A')  # its commit is in HEAD
        self.built('A', landed_sha)
        unlanded, unlanded_sha = self.add_worktree('B', commit=True)
        self.built('B', unlanded_sha)
        found = {pathlib.Path(w['path']).name: w for w in self.engine.worktrees()['worktrees']}
        self.assertEqual({'A', 'B', 'C'}, set(found))
        self.assertEqual(('orchestra/A', 'A', True, True), tuple(found['A'][k] for k in ('branch', 'card', 'landed', 'clean')))
        self.assertEqual(('orchestra/B', 'B', False, True), tuple(found['B'][k] for k in ('branch', 'card', 'landed', 'clean')))
        self.assertEqual((None, True, False), (found['C']['card'], found['C']['landed'], found['C']['clean']))

    def test_remove_commands_only_for_landed_clean_worktrees(self):
        keep, _ = self.add_worktree('A')
        self.add_worktree('B', commit=True)
        self.add_worktree('C', dirty=True)
        result = self.engine.worktrees()
        self.assertEqual(['git worktree remove ' + shlex.quote(str(keep.resolve()))], result['remove'])
        self.assertEqual(3, result['leftover'])

    def test_no_listing_without_leftovers_and_the_main_checkout_is_never_listed(self):
        result = self.engine.worktrees()
        self.assertEqual(([], [], 0), (result['worktrees'], result['remove'], result['leftover']))

    def test_the_engine_never_runs_worktree_add_or_remove(self):
        self.add_worktree('A')
        calls = []
        real_run, real_out = subprocess.run, subprocess.check_output

        def spy(real):
            def inner(argv, *a, **k):
                calls.append(list(argv))
                return real(argv, *a, **k)
            return inner
        with mock.patch('subprocess.run', spy(real_run)), mock.patch('subprocess.check_output', spy(real_out)):
            self.engine.worktrees()
            with self.assertRaises(EngineError):
                self.engine.close_session('main', self.lease)
        self.assertTrue(calls)
        for argv in calls:
            self.assertFalse('worktree' in argv and ('add' in argv or 'remove' in argv or 'prune' in argv), argv)

    def test_cli_worktrees_needs_no_lease_and_board_and_finish_name_the_leftover_count(self):
        self.add_worktree('A')
        self.add_worktree('B', commit=True)
        listing = self.cli('worktrees')
        self.assertEqual(2, listing['leftover'])
        self.assertEqual(2, self.cli('board')['leftover_worktrees'])
        with self.assertRaisesRegex(EngineError, r'2 leftover worktrees under \.claude/worktrees; run `worktrees`'):
            self.engine.close_session('main', self.lease)

    def test_board_without_leftovers_is_unchanged(self):
        self.assertNotIn('leftover_worktrees', self.cli('board'))


class WrongBaseTests(WorktreeFixture):
    def reported(self, name, sha, base):
        self.task(name)
        if base is not None:
            self.engine.record_bases('main', self.lease, [name], base)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        return lambda: self.engine.report('w-' + name, token, te.done('Built').replace('ARTIFACT: fixture', 'ARTIFACT: ' + sha))

    def test_a_commit_that_does_not_descend_from_the_card_base_is_refused_naming_both(self):
        base = self.git('rev-parse', 'HEAD')
        (self.repo / 'later').write_text('x')
        self.git('add', 'later')
        self.git('commit', '-qm', 'later')
        tip = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-q', '--orphan', 'other')
        self.git('commit', '-qm', 'other root', '--allow-empty')
        wrong = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-q', 'master' if 'master' in self.git('branch', '--list', 'master') else 'main')
        report = self.reported('A', wrong, tip)
        with self.assertRaisesRegex(EngineError, r'Reported commit %s.*built on the wrong base.*card base is %s' % (wrong, tip)):
            report()
        self.assertEqual('running', self.engine.status()['tasks']['A']['state'])
        self.assertNotEqual(base, tip)

    def test_a_commit_built_on_the_base_is_accepted(self):
        base = self.git('rev-parse', 'HEAD')
        (self.repo / 'b').write_text('x')
        self.git('add', 'b')
        self.git('commit', '-qm', 'built')
        self.reported('A', self.git('rev-parse', 'HEAD'), base)()
        self.assertEqual('reported', self.engine.status()['tasks']['A']['state'])

    def test_a_card_without_a_recorded_base_is_unchecked(self):
        self.git('checkout', '-q', '--orphan', 'other')
        self.git('commit', '-qm', 'other root', '--allow-empty')
        self.reported('A', self.git('rev-parse', 'HEAD'), None)()
        self.assertEqual('reported', self.engine.status()['tasks']['A']['state'])


class ResumeTests(WorktreeFixture):
    def test_start_after_an_ended_run_names_each_requeued_card_and_its_saved_report(self):
        self.task('a')
        self.task('b', files=['b'])
        token_a = self.engine.wave('main', self.lease, ['a', 'b'])['assignments']['a']
        reports = self.engine.state_dir / 'reports'
        reports.mkdir()
        (reports / (token_a + '.md')).write_text('STATUS: PASS')
        self.engine.interrupt('main', self.lease)
        out = subprocess.run([sys.executable, str(CLI), '--repo', str(self.repo), '--state', str(self.engine.state_dir), 'start'],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(0, out.returncode, out.stderr)
        result = json.loads(out.stdout)
        self.assertEqual(['a', 'b'], result['requeued'])
        self.assertEqual([dict(task='a', worker='orchestra-a', report=str(reports / (token_a + '.md'))),
                          dict(task='b', worker='orchestra-b', report=None)], result['resume'])


if __name__ == '__main__':
    unittest.main()
