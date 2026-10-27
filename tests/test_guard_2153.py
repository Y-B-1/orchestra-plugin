"""2.15.3 card G1: `gh repo set-default` under a run or the unattended lock, one shared deadline for the approval
prompt hook, a closed lower pull request in the receipt order check, and a merge with no method flag."""
import json
import pathlib
import subprocess
import sys
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(HERE))

import test_guard_plane as tg
import test_merge_guard as tm
import test_prompt_approval as tpa
from orchestra_core import approval, prompt_approval

SET_DEFAULT_REASON = 'gh repo set-default changes which repository gh merges into; pass -R OWNER/REPO instead'
METHOD_REASON = 'add --squash, --merge or --rebase'


class SetDefaultTest(tg.PlaneFixture):
    COMMANDS = ('gh repo set-default', 'gh repo set-default owner/name', 'gh repo set-default --unset',
                'gh -R o/r repo set-default o/r')

    def test_denied_while_a_run_is_active_in_every_mode(self):
        self.arm()
        for mode in ('minimal', 'normal', 'protect'):
            for command in self.COMMANDS:
                with self.subTest(mode=mode, command=command):
                    result = self.decide(command, mode=mode, engine=self.engine)
                    self.assertEqual(tg.verdict(result), 'deny')
                    self.assertIn(SET_DEFAULT_REASON, tg.reason(result))

    def test_denied_under_the_unattended_lock_in_every_mode(self):
        self.stop()
        for mode in ('minimal', 'normal', 'protect'):
            for command in self.COMMANDS:
                with self.subTest(mode=mode, command=command):
                    result = self.decide(command, mode=mode, engine=self.engine)
                    self.assertEqual(tg.verdict(result), 'deny')
                    self.assertIn(SET_DEFAULT_REASON, tg.reason(result))

    def test_other_gh_repo_commands_are_not_denied_by_this_rule(self):
        self.arm()
        for command in ('gh repo view', 'gh repo clone o/r'):
            with self.subTest(command=command):
                self.assertNotEqual(tg.verdict(self.decide(command, mode='minimal', engine=self.engine)), 'deny')


class MergeMethodTest(tm.MergeFixture):
    def test_a_stacked_merge_with_no_method_flag_is_denied(self):
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        self.assertEqual(self.decide('gh pr merge 4'), ('deny', METHOD_REASON))
        self.assertEqual(self.decide('gh pr merge 4 --delete-branch'), ('deny', METHOD_REASON))
        self.assertEqual(self.decide('gh pr merge 4 --merge'), ('allow', ''))

    def test_a_receipt_merge_with_no_method_flag_is_denied(self):
        self.arm()
        self.open_pr(3)
        self.approve([3])
        sha = ' --match-head-commit ' + self.sha[3]
        self.assertEqual(self.decide('gh pr merge 3 --delete-branch' + sha), ('deny', METHOD_REASON))
        self.assertEqual(self.decide('gh pr merge 3 --merge --delete-branch' + sha), ('allow', ''))


class ClosedLowerTest(tm.MergeFixture):
    def setUp(self):
        super().setUp()
        self.arm()
        self.open_pr(3)
        self.open_pr(4)
        self.approve([3, 4])

    def test_a_closed_lower_pull_request_says_so(self):
        self.pr(3)['state'] = 'CLOSED'
        self.set_fake()
        result = self.decide(self.merge(4))
        self.assertEqual(result[0], 'deny')
        self.assertIn('pull request 3 was closed without merging; type approved again so the receipt drops it', result[1])
        self.assertNotIn('merge pull request 3 first', result[1])

    def test_an_open_lower_pull_request_still_says_merge_first(self):
        self.assertIn('merge pull request 3 first', self.decide(self.merge(4))[1])


class DeadlineTest(tpa.PromptFixture):
    def test_no_time_left_answers_with_the_text_and_calls_no_gh(self):
        self.stopped_run(3)
        self.log.unlink(missing_ok=True)
        with mock.patch.object(prompt_approval, 'DEADLINE', 0.0):
            reply = self.prompt('approved')
        self.assertIn('gh did not answer in time; type approved again', tpa.context(reply))
        self.assertEqual([c for c in self.calls() if c[:2] == ['pr', 'list']], [])
        self.assertIsNone(self.receipt())

    def test_each_gh_call_gets_at_most_the_time_left(self):
        self.stopped_run(3)
        seen = []

        def slow(*args, **kw):
            seen.append(kw.get('timeout'))
            raise subprocess.TimeoutExpired(args[0], kw.get('timeout'))

        fake = types.SimpleNamespace(run=slow, SubprocessError=subprocess.SubprocessError, DEVNULL=subprocess.DEVNULL)
        with mock.patch.object(prompt_approval, 'DEADLINE', 2.0), mock.patch.object(approval, 'subprocess', fake):
            reply = self.prompt('approved')
        self.assertEqual(len(seen), 1)
        self.assertLessEqual(seen[0], 2.0)
        self.assertIn('gh did not answer in time; type approved again', tpa.context(reply))
        self.assertIsNone(self.receipt())

    def test_the_default_deadline_is_eight_seconds_inside_the_hook_timeout(self):
        self.assertEqual(prompt_approval.DEADLINE, 8)
        hooks = json.loads((HERE.parent / 'plugins/orchestra/hooks/claude.json').read_text())
        self.assertIn('"timeout": 10', json.dumps(hooks))


if __name__ == '__main__':
    unittest.main()
