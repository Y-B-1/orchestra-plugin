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
METHOD_REASON = approval.METHOD_REASON


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
        self.assertEqual(self.decide('gh pr merge 4 -R o/r --merge'), ('allow', ''))

    def test_the_method_deny_names_only_a_flag_the_guard_then_allows(self):
        """F119 (2.15.3): the guard lets only --merge through on a run pull request, so its method deny names only it."""
        self.assertIn('--merge', METHOD_REASON)
        for flag in ('--squash', '--rebase'):
            self.assertNotIn(flag, METHOD_REASON)
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        self.assertEqual(self.decide('gh pr merge 4 --squash')[0], 'deny')
        self.assertIn('not allowed', self.decide('gh pr merge 4 --squash')[1])

    def test_a_receipt_merge_with_no_method_flag_is_denied(self):
        self.arm()
        self.open_pr(3)
        self.approve([3])
        sha = ' --match-head-commit ' + self.sha[3]
        self.assertEqual(self.decide('gh pr merge 3 --delete-branch' + sha), ('deny', METHOD_REASON))
        self.assertEqual(self.decide('gh pr merge 3 -R o/r --merge --delete-branch' + sha), ('allow', ''))


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

    def test_engine_lock_waits_get_at_most_the_time_left(self):
        """RC note (N2): the engine writes wait for the lock no longer than the deadline leaves."""
        from orchestra_core.engine import Engine
        self.stopped_run(3)
        engine = Engine(self.state, self.repo, lock_wait=5.0)
        seen = []
        for name in ('stop_stale_autonomy', 'record_owner_approval'):
            real = getattr(engine, name)

            def wrapped(*args, _real=real, _name=name, **kw):
                seen.append((_name, engine.lock_wait))
                return _real(*args, **kw)
            setattr(engine, name, wrapped)
        with mock.patch.object(prompt_approval, 'DEADLINE', 1.0):
            self.prompt('approved', engine=engine)
        self.assertEqual([n for n, _ in seen], ['stop_stale_autonomy', 'record_owner_approval'])
        self.assertTrue(all(wait <= 1.0 for _, wait in seen), seen)

    def test_the_default_deadline_is_eight_seconds_inside_the_hook_timeout(self):
        self.assertEqual(prompt_approval.DEADLINE, 8)
        hooks = json.loads((HERE.parent / 'plugins/orchestra/hooks/claude.json').read_text())
        self.assertIn('"timeout": 10', json.dumps(hooks))



class MergeNamesItsRepositoryTest(tm.MergeFixture):
    """RS note (N1): a gated merge names the recorded repository with -R, so the checkout's remotes (a remote add, a
    gh-resolved config, set-default) cannot point it at another one. The printed merge carries -R."""

    def test_a_gated_merge_without_its_repository_is_denied(self):
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        decision, reason = self.decide('gh pr merge 4 --merge')
        self.assertEqual(decision, 'deny')
        self.assertIn('gh pr merge 4 -R o/r', reason)

    def test_the_recorded_repository_or_its_url_is_allowed(self):
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        for command in ('gh pr merge 4 -R o/r --merge', 'gh pr merge 4 --repo o/r --merge', 'gh pr merge 4 --repo=o/r --merge',
                        'gh pr merge https://github.example/o/r/pull/4 --merge'):
            with self.subTest(command=command):
                self.assertEqual(self.decide(command), ('allow', ''))

    def test_another_repository_is_denied(self):
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        decision, reason = self.decide('gh pr merge 4 -R x/y --merge')
        self.assertEqual(decision, 'deny')
        self.assertIn('o/r', reason)

    def test_the_receipt_prints_the_repository(self):
        self.arm()
        self.open_pr(3)
        self.approve([3])
        decision, reason = self.decide('gh pr merge 3 --merge --delete-branch --match-head-commit ' + self.sha[3])
        self.assertEqual(decision, 'deny')
        self.assertIn('gh pr merge 3 -R o/r --merge --delete-branch --match-head-commit ' + self.sha[3], reason)
        self.assertEqual(self.decide('gh pr merge 3 -R o/r --merge --delete-branch --match-head-commit ' + self.sha[3]),
                         ('allow', ''))

    def test_set_default_reason_matches_what_the_merge_accepts(self):
        self.arm()
        self.assertEqual(self.decide('gh repo set-default x/y')[0], 'deny')
        self.assertIn('-R OWNER/REPO', approval.SET_DEFAULT_REASON)


class GraphqlMergeTest(tm.MergeFixture):
    """RS out-of-scope note: a gh api graphql merge mutation, or a query read from a file, is gated like gh api .../merge."""

    def test_graphql_merge_is_denied_under_a_lock(self):
        self.arm()
        self.open_pr(3)
        for command in ("gh api graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"X\"}) { clientMutationId } }'",
                        "gh api graphql -f query='mutation { enablePullRequestAutoMerge(input: {}) { clientMutationId } }'",
                        'gh api graphql -F query=@q.graphql', 'gh api graphql --input m.json',
                        'gh api graphql --input=m.json', 'gh api graphql --input -'):
            with self.subTest(command=command):
                self.assertEqual(self.decide(command)[0], 'deny')

    def test_a_body_from_a_file_or_stdin_stays_gated_after_the_receipt(self):
        """RZ: `--input` hides the body, so even with a receipt the guard cannot see which pull request it merges."""
        self.arm()
        self.open_pr(3)
        self.approve([3])
        for command in ('gh api graphql --input m.json', 'gh api graphql --input -', 'gh api graphql -F query=@q.graphql'):
            with self.subTest(command=command):
                self.assertEqual(self.decide(command)[0], 'deny')

    def test_the_minimal_hook_denies_a_graphql_body_from_a_file_after_the_receipt(self):
        """RZ scenario: default guard mode, owner typed approved, a merge mutation read from m.json."""
        from orchestra_core.hooks import handle_event
        self.arm()
        self.open_pr(3)
        self.approve([3])
        payload = {'tool_name': 'Bash', 'tool_input': {'command': 'gh api graphql --input m.json'}, 'cwd': str(self.repo)}
        output = handle_event('PreToolUse', payload, mode='minimal', state_dir=str(self.state)).output
        self.assertEqual(output.get('hookSpecificOutput', {}).get('permissionDecision'), 'deny')

    def test_flags_before_the_graphql_endpoint_are_gated_too(self):
        """FX5 note: gh takes flags on either side of the endpoint."""
        self.arm()
        self.open_pr(3)
        self.approve([3])
        for command in ('gh api --input m.json graphql', 'gh api -F query=@q.graphql graphql',
                        "gh api -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }' graphql"):
            with self.subTest(command=command):
                self.assertEqual(self.decide(command)[0], 'deny')
        self.assertIsNone(self.decide("gh api -f query='{ viewer { login } }' graphql"))

    def test_a_graphql_read_is_not_gated(self):
        self.arm()
        self.open_pr(3)
        self.assertIsNone(self.decide("gh api graphql -f query='{ viewer { login } }'"))


if __name__ == '__main__':
    unittest.main()
