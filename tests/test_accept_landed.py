"""`accept` compares the commit a builder report names (ACC): work built in a linked worktree and fast-forward merged
into the run checkout is accepted, and every refusal names what differs."""
import json
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import EngineError


class AcceptLandedFixture(te.EngineFixture):
    def setUp(self):
        super().setUp()
        self.side = self.root / 'side'
        self.git('worktree', 'add', '-q', '-b', 'side', str(self.side))

    def side_git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.side), *args], text=True).strip()

    def build(self, content='built in the worktree'):
        """A builder card for file `a`, its commit made in the linked worktree, reported with that commit on ARTIFACT."""
        self.task('a')
        token = self.engine.dispatch('main', self.lease, 'a', 'w-a')
        (self.side / 'a').write_text(content)
        self.side_git('commit', '-qam', 'built a')
        self.sha = self.side_git('rev-parse', 'HEAD')
        self.engine.report('w-a', token, te.done('Built a.').replace('ARTIFACT: fixture', 'ARTIFACT: %s clean' % self.sha))
        self.assertEqual(self.sha, self.engine.status()['tasks']['a']['report_sha'])

    def merge(self):
        self.git('merge', '-q', '--ff-only', 'side')

    def tamper(self, key, value):
        state = json.loads(self.engine.state_path.read_text())
        state['tasks']['a']['report_artifact'][key] = value
        self.engine.state_path.write_text(json.dumps(state))

    def refused(self, pattern):
        with self.assertRaisesRegex(EngineError, pattern):
            self.engine.accept('main', self.lease, 'a')
        self.assertEqual('reported', self.engine.status()['tasks']['a']['state'])


class AcceptLandedTests(AcceptLandedFixture):
    def test_merge_before_accept_passes(self):
        self.build()
        self.merge()
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def test_accept_before_merge_passes(self):
        self.build()
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def test_edit_to_a_scoped_file_after_the_merge_is_refused(self):
        self.build()
        self.merge()
        (self.repo / 'a').write_text('edited after the merge')
        self.refused('Reported artifact is stale')

    def test_staged_scoped_file_after_the_merge_is_refused(self):
        self.build()
        self.merge()
        (self.repo / 'a').write_text('staged after the merge')
        self.git('add', 'a')
        self.refused('Reported artifact is stale')

    def test_commit_to_a_scoped_file_after_the_merge_is_refused(self):
        self.build()
        self.merge()
        (self.repo / 'a').write_text('committed after the merge')
        self.git('commit', '-qam', 'edit a')
        self.refused('Reported artifact is stale')

    def test_reported_commit_that_never_landed_is_refused(self):
        self.build()
        (self.repo / 'a').write_text('different work on the run branch')
        self.git('commit', '-qam', 'other a')
        self.refused('Reported artifact is stale')

    def test_changed_repo_identity_or_policy_is_refused(self):
        for key in ('repo', 'identity', 'policy'):
            with self.subTest(key):
                self.tearDown()
                self.setUp()
                self.build()
                self.merge()
                self.tamper(key, 'elsewhere')
                self.refused(r'Reported artifact is stale: (?:[a-z]+, )*%s(?:,| differ)' % key)

    def test_stale_refusal_names_the_differing_keys(self):
        self.task('a')
        token = self.engine.dispatch('main', self.lease, 'a', 'w-a')
        self.engine.report('w-a', token, te.done('Built a.'))
        (self.repo / 'a').write_text('edited after the report')
        with self.assertRaises(EngineError) as ctx:
            self.engine.accept('main', self.lease, 'a')
        self.assertEqual('Reported artifact is stale: fingerprint, status differ since the report (changed: a '
                         '(uncommitted)); re-report or send a repair card', str(ctx.exception))


class SelfReviewRefusalTests(te.EngineFixture):
    def refusal(self, **kw):
        self.task('a')
        token = self.engine.dispatch('main', self.lease, 'a', 'w-a')
        self.engine.report('w-a', token, te.done('Built a.', **kw))
        with self.assertRaises(EngineError) as ctx:
            self.engine.accept('main', self.lease, 'a')
        return str(ctx.exception)

    def test_failing_check_is_named_with_its_exit_code(self):
        self.assertEqual('Self-review has a failing check or unmet criterion: check "pytest -q" exited 3',
                         self.refusal(checks=[{'command': 'ruff', 'exit_code': 0}, {'command': 'pytest -q', 'exit_code': 3}]))

    def test_red_first_check_without_a_later_pass_is_named(self):
        self.assertEqual('Self-review has a failing check or unmet criterion: check "pytest t" '
                         '(expect: fail) has no later passing run',
                         self.refusal(checks=[{'command': 'pytest t', 'exit_code': 1, 'expect': 'fail'}]))

    def test_unmet_criterion_is_named_by_its_text(self):
        self.assertEqual('Self-review has a failing check or unmet criterion: criterion not met: renders the board',
                         self.refusal(criteria=[{'criterion': 'check behavior', 'met': True, 'evidence': 'ok'},
                                               {'criterion': 'renders the board', 'met': False, 'evidence': 'no'}]))


if __name__ == '__main__':
    unittest.main()
