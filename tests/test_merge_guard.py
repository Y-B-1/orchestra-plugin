import json
import os
import pathlib
import subprocess
import sys
import time
import unittest
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core import approval
from orchestra_core.engine import Engine

FAKE_DIR = pathlib.Path(__file__).resolve().parent / 'fixtures/fake-gh'
PR_URL = 'https://github.example/o/r/pull/%d'
EVIDENCE = dict(event='UserPromptSubmit', session_id='S', prompt_id=None, prompt_sha256='a' * 64)


class MergeFixture(te.AutonomyFixture):
    """A real repository and engine, with the fake gh first on PATH. `self.live` is what the fake reports."""

    def setUp(self):
        super().setUp()
        self.fake, self.log = self.root / 'fake.json', self.root / 'gh.log'
        self.live, self.sha = [], {}
        self.set_fake()
        patch = mock.patch.dict(os.environ, PATH=str(FAKE_DIR) + os.pathsep + os.environ['PATH'],
                                FAKE_GH_DATA=str(self.fake), FAKE_GH_LOG=str(self.log))
        patch.start()
        self.addCleanup(patch.stop)

    def set_fake(self, **extra):
        self.fake.write_text(json.dumps(dict(prs=self.live, **extra)))

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def open_pr(self, number, base=None, head=None):
        """A local branch with one commit, a live open pull request for it, and the run's record of it."""
        head = head or 'feat/%d' % number
        self.git('switch', '-q', 'work')
        self.git('switch', '-qc', head)
        (self.repo / ('f%d' % number)).write_text('x')
        self.git('add', 'f%d' % number)
        self.git('commit', '-qm', 'pr %d' % number)
        self.sha[number] = self.git('rev-parse', 'HEAD')
        self.git('switch', '-q', 'work')
        self.live.append(dict(number=number, state='OPEN', baseRefName=base or self.default_branch, headRefName=head,
                              headRefOid=self.sha[number]))
        self.set_fake()
        self.engine.record_pr('main', self.lease, PR_URL % number)

    def pr(self, number):
        return next(p for p in self.live if p['number'] == number)

    def approve(self, numbers):
        """Stop the run, then record the owner's receipt for the pull requests in this merge order."""
        self.engine.disarm_autonomy()
        entries = {e['number']: e for e in json.loads(self.engine.state_path.read_text())['pull_requests']}
        prs = [dict(order=i, number=n, repo=entries[n]['repo'], url=entries[n]['url'], head_ref=entries[n]['head_ref'],
                    head_sha=entries[n]['head_sha'], base_ref=entries[n]['base_ref']) for i, n in enumerate(numbers, 1)]
        self.engine.record_owner_approval(prs, [], EVIDENCE)

    def merge(self, number, flags='--merge --delete-branch', sha=True):
        return 'gh pr merge %d %s%s' % (number, flags, ' --match-head-commit ' + self.sha[number] if sha else '')

    def decide(self, command, **kw):
        return approval.merge_decision(command, self.repo, self.state, self.repo, **kw)

    def approved_pair(self):
        """PR 3 on the default branch, PR 4 stacked on it; both approved in that order."""
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        self.approve([3, 4])


class MergeShapeTest(MergeFixture):
    def setUp(self):
        super().setUp()
        self.approved_pair()

    def test_repo_flag_env_prefix_branch_and_foreign_url_denied(self):
        ok = '--merge --delete-branch --match-head-commit ' + self.sha[3]
        for command in ('gh pr merge 3 -R o/r ' + ok, 'gh pr merge 3 --repo o/r ' + ok, 'gh -R o/r pr merge 3 ' + ok,
                        'GH_REPO=o/r gh pr merge 3 ' + ok, 'gh pr merge feat/3 ' + ok, 'gh pr merge ' + ok,
                        'gh pr merge https://github.example/x/y/pull/3 ' + ok):
            with self.subTest(command=command):
                self.assertEqual(self.decide(command)[0], 'deny')

    def test_plain_number_and_recorded_url_allowed(self):
        ok = '--merge --delete-branch --match-head-commit ' + self.sha[3]
        for target in ('3', PR_URL % 3):
            with self.subTest(target=target):
                self.assertEqual(self.decide('gh pr merge %s %s' % (target, ok)), ('allow', ''))

    def test_gh_api_merge_call_denied_with_hint(self):
        decision = self.decide('gh api -X PUT repos/o/r/pulls/3/merge -f sha=' + self.sha[3])
        self.assertEqual(decision[0], 'deny')
        self.assertIn('gh pr merge 3', decision[1])

    def test_compound_and_env_wrapper_merge_denied_when_gated(self):
        for command in ('cd /repo && gh pr merge 3 --merge --delete-branch --match-head-commit abc',
                        'export GH_REPO=o/r; gh pr merge 3 --merge', 'env GH_REPO=o/r gh pr merge 3'):
            with self.subTest(command=command):
                decision = self.decide(command)
                self.assertEqual(decision[0], 'deny')
                self.assertIn('run the merge alone', decision[1])

    def test_commands_without_a_merge_are_not_gated(self):
        for command in ('gh pr list', 'git status', 'gh pr view 3', 'echo done'):
            with self.subTest(command=command):
                self.assertIsNone(self.decide(command))


class GateTest(MergeFixture):
    def test_unreadable_state_denied(self):
        self.engine.state_path.write_text('{not json')
        self.assertEqual(self.decide('gh pr merge 3 --merge')[0], 'deny')
        self.engine.state_path.write_text('[]')
        self.assertEqual(self.decide('gh pr merge 3 --merge')[0], 'deny')

    def test_no_state_returns_none(self):
        self.engine.state_path.unlink()
        self.assertIsNone(self.decide('gh pr merge 3 --merge'))

    def test_no_autonomous_entry_inactive_and_not_unattended_returns_none_with_no_gh_call(self):
        self.assertIsNone(self.decide('gh pr merge 3 --merge --delete-branch'))
        self.assertEqual(self.calls(), [])

    def test_autonomy_active_denied(self):
        self.arm()
        self.open_pr(3)
        decision = self.decide(self.merge(3))
        self.assertEqual(decision[0], 'deny')
        self.assertIn('autonomy is active', decision[1])

    def test_stopped_run_without_a_receipt_denied(self):
        self.arm()
        self.open_pr(3)
        self.engine.disarm_autonomy()
        decision = self.decide(self.merge(3))
        self.assertEqual(decision[0], 'deny')
        self.assertIn('approved', decision[1])

    def test_raw_unattended(self):
        stopped = dict(active=False, report={})
        cases = [({}, False), ({'autonomy': None}, False), ({'autonomy': dict(active=True, report={})}, False),
                 ({'autonomy': dict(active=False)}, False), ({'autonomy': stopped}, True),
                 ({'autonomy': stopped, 'run_id': 'r', 'approval': {'run': 'r'}}, False),
                 ({'autonomy': stopped, 'run_id': 'r', 'approval': {'run': 'old'}}, True), ([], False)]
        for state, expected in cases:
            with self.subTest(state=state):
                self.assertIs(approval.raw_unattended(state), expected)


class ReceiptTest(MergeFixture):
    def setUp(self):
        super().setUp()
        self.arm()
        self.open_pr(3)
        self.open_pr(5)  # recorded, never approved
        self.open_pr(6)
        self.approve([3, 6])

    def test_allowed_with_merge_delete_branch_and_the_head_commit(self):
        self.assertEqual(self.decide(self.merge(3)), ('allow', ''))

    def test_receipt_survives_start_resume_and_a_morning_session(self):
        self.engine.interrupt('main', self.lease)
        self.lease = self.engine.open_session('main')  # start resumes the run
        self.assertEqual(self.decide(self.merge(3)), ('allow', ''))
        self.engine.interrupt('main', self.lease)
        Engine(self.state, self.repo, clock=lambda: self.now[0] + 86400).open_session('main', harness_session='morning')
        self.assertEqual(self.decide(self.merge(3)), ('allow', ''))

    def test_pull_request_not_in_the_receipt_denied(self):
        decision = self.decide(self.merge(5))
        self.assertEqual(decision[0], 'deny')
        self.assertIn('receipt', decision[1])

    def test_head_moved_denied(self):
        self.pr(3)['headRefOid'] = 'f' * 40
        self.set_fake()
        self.assertEqual(self.decide(self.merge(3))[0], 'deny')

    def test_match_head_commit_absent_or_wrong_denied(self):
        self.assertEqual(self.decide(self.merge(3, sha=False))[0], 'deny')
        self.assertEqual(self.decide('gh pr merge 3 --merge --delete-branch --match-head-commit ' + 'e' * 40)[0], 'deny')

    def test_lower_order_not_yet_merged_denied_then_allowed_once_merged(self):
        decision = self.decide(self.merge(6))
        self.assertEqual(decision[0], 'deny')
        self.assertIn('3', decision[1])
        self.pr(3)['state'] = 'MERGED'
        self.set_fake()
        self.assertEqual(self.decide(self.merge(6)), ('allow', ''))

    def test_squash_admin_and_auto_denied(self):
        for flags in ('--squash', '--rebase', '--admin', '--auto', '--merge --admin', '--merge --delete-branch --auto'):
            with self.subTest(flags=flags):
                self.assertEqual(self.decide(self.merge(3, flags))[0], 'deny')

    def test_receipt_for_another_run_denied(self):
        raw = json.loads(self.engine.state_path.read_text())
        raw['approval']['run'] = '0' * 16
        self.engine.state_path.write_text(json.dumps(raw))
        self.assertEqual(self.decide(self.merge(3))[0], 'deny')

    def test_closed_pull_request_denied(self):
        self.pr(3)['state'] = 'CLOSED'
        self.set_fake()
        self.assertEqual(self.decide(self.merge(3))[0], 'deny')


class StackOrderTest(MergeFixture):
    def test_child_based_on_merged_parent_branch_denied_names_pr_edit_base(self):
        self.approved_pair()
        self.pr(3)['state'] = 'MERGED'
        self.set_fake()
        decision = self.decide(self.merge(4))
        self.assertEqual(decision[0], 'deny')
        self.assertIn('gh pr edit 4 --base ' + self.default_branch, decision[1])

    def test_child_based_on_an_open_run_branch_allowed(self):
        self.approved_pair()
        self.assertEqual(self.decide(self.merge(4)), ('allow', ''))

    def test_child_on_an_open_run_branch_allowed_while_autonomy_is_active(self):
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        self.assertEqual(self.decide(self.merge(4)), ('allow', ''))
        self.assertEqual(self.decide(self.merge(3))[0], 'deny')

    def test_pull_request_outside_the_run_based_on_the_default_branch_denied_while_active(self):
        self.arm()
        self.open_pr(3)
        self.live.append(dict(number=9, state='OPEN', baseRefName=self.default_branch, headRefName='other', headRefOid='d' * 40))
        self.set_fake()
        self.assertEqual(self.decide('gh pr merge 9 --merge')[0], 'deny')


class GhRunnerTest(MergeFixture):
    def test_timeout_is_six_seconds_or_less_and_slow_gh_denies(self):
        self.approved_pair()
        self.assertLessEqual(approval.GH_TIMEOUT, 6)
        timeouts = []
        real = subprocess.run

        def spy(*args, **kw):
            timeouts.append(kw.get('timeout'))
            return real(*args, **kw)

        with mock.patch.object(approval.subprocess, 'run', side_effect=spy):
            self.assertEqual(self.decide(self.merge(3)), ('allow', ''))
        self.assertTrue(timeouts and all(t is not None and t <= 6 for t in timeouts), timeouts)
        self.set_fake(list_sleep=5)
        started = time.monotonic()
        with mock.patch.object(approval, 'GH_TIMEOUT', 0.5):
            decision = self.decide(self.merge(3))
        self.assertEqual(decision[0], 'deny')
        self.assertLess(time.monotonic() - started, 4)

    def test_pr_list_uses_limit_1000_and_missing_recorded_pr_is_denied(self):
        self.approved_pair()
        self.log.unlink()
        self.assertEqual(self.decide(self.merge(3)), ('allow', ''))
        listed = [c for c in self.calls() if c[:2] == ['pr', 'list']]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0][listed[0].index('--limit') + 1], '1000')
        self.assertEqual(listed[0][listed[0].index('-R') + 1], 'o/r')
        self.assertEqual(listed[0][listed[0].index('--state') + 1], 'all')
        self.live[:] = [p for p in self.live if p['number'] != 3]
        self.set_fake()
        decision = self.decide(self.merge(3))
        self.assertEqual(decision[0], 'deny')
        self.assertIn('unreachable', decision[1])

    def test_pr_list_failure_denied(self):
        self.approved_pair()
        self.set_fake(list_exit=1)
        self.assertEqual(self.decide(self.merge(3))[0], 'deny')

    def test_missing_gh_denied(self):
        self.approved_pair()
        with mock.patch.dict(os.environ, PATH=str(self.root)):
            self.assertEqual(self.decide(self.merge(3))[0], 'deny')

    def test_injected_runner_answers_and_its_failure_denies(self):
        self.approved_pair()
        answer = lambda args, cwd: json.dumps(self.live)
        self.assertEqual(self.decide(self.merge(3), gh=answer), ('allow', ''))

        def broken(args, cwd):
            raise approval.GhError('boom')

        self.assertEqual(self.decide(self.merge(3), gh=broken)[0], 'deny')

    def test_the_approval_prompt_matches_only_the_whole_word(self):
        for text in ('approved', ' Approved. ', 'APPROVED!'):
            self.assertTrue(approval.APPROVAL_PROMPT.fullmatch(text), text)
        for text in ('approved please', 'not approved', 'I approved', ''):
            self.assertFalse(approval.APPROVAL_PROMPT.fullmatch(text), text)


if __name__ == '__main__':
    unittest.main()
