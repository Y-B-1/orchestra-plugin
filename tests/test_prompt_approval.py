"""T2b2: the UserPromptSubmit approval hook, the scheduler guard and the merge glue of the PreToolUse hook.

The tests assert the hook's decisions through `handle_prompt` and `handle_event` against a real repository, a real
engine and the fake gh of T2b1; nothing asserts the fake."""
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(HERE))

import test_guard_plane as tp
import test_merge_guard as tm
from orchestra_core import approval, portable
from orchestra_core.engine import Engine
from orchestra_core.hooks import handle_event, main
from orchestra_core.prompt_approval import handle_prompt

NIGHT, MORNING = 'NIGHT', 'MORNING'


def context(reply):
    return reply.get('hookSpecificOutput', {}).get('additionalContext', '')


class PromptFixture(tp.PlaneFixture):
    """The run is bound to the harness session NIGHT; the owner's prompts come from MORNING."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.state)
        self.engine = Engine(self.state, self.repo, clock=lambda: self.now[0])
        self.lease = self.engine.open_session('main', harness_session=NIGHT)

    def prompt(self, text, session=MORNING, engine=None, **kw):
        payload = dict(prompt=text, session_id=session, prompt_id='p-1', cwd=str(self.repo), hook_event_name='UserPromptSubmit')
        return handle_prompt(payload, self.state, self.repo, engine=engine or self.engine, **kw)

    def reviewed(self, *numbers):
        data = self.raw()
        for entry in data.get('pull_requests', []):
            if entry['number'] in numbers:
                entry['reviewed'] = True
        self.engine.state_path.write_text(json.dumps(data))

    def stopped_run(self, *numbers, bases=None):
        """Arm, open and review a pull request for each number, then stop the run: the report is kept."""
        self.arm()
        for number in numbers:
            self.open_pr(number, base=(bases or {}).get(number))
        self.reviewed(*numbers)
        self.engine.disarm_autonomy()

    def receipt(self):
        return self.raw().get('approval')


class PromptHookTest(PromptFixture):
    def test_approved_variants_record_with_the_prompt_hash(self):
        self.stopped_run()
        for text in ('Approved', '  approved.', 'approved!'):
            with self.subTest(text=text):
                reply = self.prompt(text)
                self.assertEqual(self.receipt()['evidence']['prompt_sha256'], hashlib.sha256(text.encode()).hexdigest())
                self.assertEqual(self.receipt()['run'], self.raw()['run_id'])
                self.assertNotIn(text.strip(), json.dumps(self.receipt()))
                self.assertTrue(context(reply))

    def test_other_prompts_record_nothing(self):
        self.stopped_run()
        for text in ('Approved the plan, do B3', 'disapproved', 'please approved', 'approvedly', '', None, 5):
            with self.subTest(text=text):
                self.assertEqual(self.prompt(text), {})
                self.assertIsNone(self.receipt())

    def test_no_record_while_autonomy_is_active(self):
        self.arm()
        os.utime(self.engine.state_path, (self.now[0], self.now[0]))  # the injected clock sees a fresh state file
        reply = self.prompt('approved')
        self.assertTrue(self.raw()['autonomy']['active'])
        self.assertIsNone(self.receipt())
        self.assertIn('autonomy is active', context(reply))

    def test_record_after_stale_stop_when_the_deadline_passed(self):
        self.arm()
        self.now[0] += 7200
        self.prompt('approved')
        self.assertFalse(self.raw()['autonomy']['active'])
        self.assertEqual(self.raw()['autonomy']['report']['reason'], 'deadline')
        self.assertEqual(self.receipt()['run'], self.raw()['run_id'])

    def test_stale_stop_in_same_prompt_by_bound_session_records_nothing(self):
        self.arm()
        self.now[0] += 7200
        reply = self.prompt('approved', session=NIGHT)
        self.assertFalse(self.raw()['autonomy']['active'])  # the call did stop the run
        self.assertIsNone(self.receipt())
        self.assertIn('same', context(reply))
        self.prompt('approved', session=NIGHT)  # a second prompt finds it already stopped
        self.assertIsNotNone(self.receipt())

    def test_run_that_never_stopped_records_nothing(self):
        reply = self.prompt('approved')
        self.assertIsNone(self.receipt())
        self.assertIn('never stopped', context(reply))

    def test_no_run_at_all_is_silent(self):
        shutil.rmtree(self.state)
        self.assertEqual(handle_prompt(dict(prompt='approved', session_id=MORNING), self.state, self.repo), {})

    def test_zero_autonomous_prs_records_an_empty_receipt_and_ends_the_lock(self):
        self.stopped_run()
        self.assertTrue(approval.raw_unattended(self.raw()))
        self.prompt('approved')
        self.assertEqual((self.receipt()['prs'], self.receipt()['excluded']), ([], []))
        self.assertFalse(approval.raw_unattended(self.raw()))

    def test_moved_head_closed_and_unreviewed_head_are_excluded_with_a_reason(self):
        self.arm()
        for number in (3, 4, 5, 6):
            self.open_pr(number)
        self.reviewed(3, 4, 5)  # 6 is not reviewed
        self.engine.disarm_autonomy()
        self.pr(3)['headRefOid'] = 'f' * 40
        self.pr(4)['state'] = 'CLOSED'
        self.set_fake()
        self.prompt('approved')
        receipt = self.receipt()
        self.assertEqual([p['number'] for p in receipt['prs']], [5])
        reasons = {e['number']: e['reason'] for e in receipt['excluded']}
        self.assertEqual(sorted(reasons), [3, 4, 6])
        self.assertIn('head moved', reasons[3])
        self.assertIn('closed', reasons[4])
        self.assertIn('unreviewed', reasons[6])

    def test_merged_pr_is_excluded(self):
        self.stopped_run(3)
        self.pr(3)['state'] = 'MERGED'
        self.set_fake()
        self.prompt('approved')
        self.assertEqual(self.receipt()['prs'], [])
        self.assertIn('merged', self.receipt()['excluded'][0]['reason'])

    def test_three_pr_stack_is_ordered_bottom_first(self):
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        self.open_pr(5, base='feat/4')
        self.reviewed(3, 4, 5)
        self.engine.disarm_autonomy()
        self.live.reverse()  # the listing order must not decide the merge order
        self.set_fake()
        reply = self.prompt('approved')
        prs = self.receipt()['prs']
        self.assertEqual([(p['order'], p['number']) for p in prs], [(1, 3), (2, 4), (3, 5)])
        self.assertEqual([p['head_sha'] for p in prs], [self.sha[3], self.sha[4], self.sha[5]])
        text = context(reply)
        commands = ['gh pr merge %d --merge --delete-branch --match-head-commit %s' % (n, self.sha[n]) for n in (3, 4, 5)]
        self.assertEqual([text.index(c) for c in commands], sorted(text.index(c) for c in commands))

    def test_reply_carries_the_retarget_sentence(self):
        self.stopped_run(3)
        text = context(self.prompt('approved'))
        self.assertIn('gh pr edit N --base %s' % self.default_branch, text)
        self.assertIn('still shows a run branch as its base', text)

    def test_cycle_is_excluded(self):
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        self.reviewed(3, 4)
        self.engine.disarm_autonomy()
        self.pr(3)['baseRefName'] = 'feat/4'  # 3 and 4 now base on each other
        self.set_fake()
        self.prompt('approved')
        self.assertEqual(self.receipt()['prs'], [])
        self.assertEqual(sorted(e['number'] for e in self.receipt()['excluded']), [3, 4])

    def test_pr_missing_from_list_is_excluded_as_unreachable(self):
        self.stopped_run(3, 4)
        self.live[:] = [p for p in self.live if p['number'] != 4]
        self.set_fake()
        self.prompt('approved')
        self.assertEqual([p['number'] for p in self.receipt()['prs']], [3])
        self.assertIn('unreachable', self.receipt()['excluded'][0]['reason'])

    def test_one_gh_list_call_with_limit_1000(self):
        self.stopped_run(3, 4)
        self.log.unlink(missing_ok=True)
        self.prompt('approved')
        lists = [c for c in self.calls() if c[:2] == ['pr', 'list']]
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0][lists[0].index('--limit') + 1], '1000')

    def test_gh_missing_records_nothing_and_names_the_cause(self):
        self.stopped_run(3)
        empty = self.root / 'empty-path'
        empty.mkdir()
        with mock.patch.dict(os.environ, PATH=str(empty)):
            reply = self.prompt('approved')
        self.assertIsNone(self.receipt())
        self.assertIn('gh is not installed', context(reply))

    def test_gh_failing_records_nothing_and_names_the_cause(self):
        self.stopped_run(3)
        self.set_fake(list_exit=1)
        reply = self.prompt('approved')
        self.assertIsNone(self.receipt())
        self.assertIn('gh exited 1', context(reply))
        self.assertIn('type approved again', context(reply))

    def test_gh_timeout_is_six_seconds_or_less(self):
        self.stopped_run(3)
        seen = []

        def slow(*args, **kw):
            seen.append(kw.get('timeout'))
            raise subprocess.TimeoutExpired(args[0], kw.get('timeout'))

        fake = types.SimpleNamespace(run=slow, SubprocessError=subprocess.SubprocessError, DEVNULL=subprocess.DEVNULL)
        with mock.patch.object(approval, 'subprocess', fake):
            reply = self.prompt('approved')
        self.assertEqual(len(seen), 1)
        self.assertLessEqual(seen[0], 6)
        self.assertIsNone(self.receipt())
        self.assertIn('did not answer', context(reply))

    def test_state_busy_reply(self):
        self.stopped_run(3)
        engine = Engine(self.state, self.repo, clock=lambda: self.now[0], lock_wait=0.2)
        handle = (self.state / 'state.lock').open('a+')
        self.addCleanup(handle.close)
        portable.lock(handle, exclusive=True)
        try:
            reply = self.prompt('approved', engine=engine)
        finally:
            portable.unlock(handle)
        self.assertIsNone(self.receipt())
        self.assertIn('state busy, type approved again', context(reply))

    def test_reply_lists_the_exact_merge_commands(self):
        self.stopped_run(3)
        text = context(self.prompt('approved'))
        self.assertIn('gh pr merge 3 --merge --delete-branch --match-head-commit %s' % self.sha[3], text)

    def test_the_hook_entry_prints_the_reply_and_exits_zero(self):
        self.stopped_run(3)
        payload = dict(prompt='approved', session_id=MORNING, cwd=str(self.repo))
        with mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            code = main(['UserPromptSubmit', '--harness', 'claude'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())['hookSpecificOutput']['hookEventName'], 'UserPromptSubmit')
        self.assertEqual(self.receipt()['prs'][0]['number'], 3)

    def test_a_crash_prints_empty_json_and_exits_zero(self):
        for payload in ('not json', json.dumps(dict(prompt='approved', cwd=5)), json.dumps(dict(prompt='approved', cwd='/nonexistent-dir'))):
            with self.subTest(payload=payload):
                with mock.patch('sys.stdin', io.StringIO(payload)), mock.patch('sys.stdout', new_callable=io.StringIO) as out:
                    self.assertEqual(main(['UserPromptSubmit']), 0)
                self.assertEqual(json.loads(out.getvalue()), {})
        with mock.patch('sys.stdin', io.StringIO(json.dumps(dict(prompt='approved', cwd=str(self.repo))))), \
                mock.patch('orchestra_core.prompt_approval.handle_prompt', side_effect=RuntimeError('boom')), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(main(['UserPromptSubmit']), 0)
        self.assertEqual(json.loads(out.getvalue()), {})


class SchedulerApprovalTextTest(tp.PlaneFixture):
    FIELDS = {'CronCreate': 'prompt', 'ScheduleWakeup': 'prompt', 'RemoteTrigger': 'body', 'SendMessage': 'message'}

    def test_scheduler_and_sendmessage_with_approval_text_denied_in_every_mode(self):
        for tool, field in self.FIELDS.items():
            for mode in ('normal', 'protect'):
                for text in ('approved', ' Approved.', 'approved!'):
                    with self.subTest(tool=tool, mode=mode, text=text):
                        payload = dict(tool_name=tool, tool_input={field: text}, cwd=str(self.repo))
                        self.assertEqual(tp.verdict(handle_event('PreToolUse', payload, mode=mode)), 'deny')
        nested = dict(tool_name='RemoteTrigger', tool_input={'action': 'run', 'body': {'prompt': 'approved'}}, cwd=str(self.repo))
        self.assertEqual(tp.verdict(handle_event('PreToolUse', nested, mode='normal')), 'deny')
        self.arm()  # with a run active the answer is still a deny
        payload = dict(tool_name='SendMessage', tool_input={'message': 'approved'}, cwd=str(self.repo))
        self.assertEqual(tp.verdict(handle_event('PreToolUse', payload, mode='normal', engine=self.engine)), 'deny')

    def test_a_non_matching_text_is_allowed_for_sendmessage_in_every_mode(self):
        for mode in ('normal', 'protect'):
            for text in ('approved the plan', 'disapproved', 'status?'):
                with self.subTest(mode=mode, text=text):
                    payload = dict(tool_name='SendMessage', tool_input={'message': text}, cwd=str(self.repo))
                    self.assertEqual(handle_event('PreToolUse', payload, mode=mode).output, {})

    def test_a_non_matching_scheduler_text_keeps_the_ordinary_rules(self):
        payload = dict(tool_name='CronCreate', tool_input={'prompt': 'check the build'}, cwd=str(self.repo))
        self.assertEqual(handle_event('PreToolUse', payload, mode='normal').output, {})


class MergeGlueTest(tp.PlaneFixture):
    def decide(self, command, **kw):
        kw.setdefault('state_dir', self.state)
        return super().decide(command, **kw)

    def test_guard_allow_overrides_plane_for_run_base_pr(self):
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        command = self.merge(4)
        self.assertEqual(tp.verdict(self.decide('gh pr merge 99', engine=self.engine)), 'deny')  # unlisted: the guard denies
        result = self.decide(command, engine=self.engine, mode='normal')
        self.assertEqual(result.output, {})  # autonomy active, the base is a run branch: allowed
        self.assertTrue(self.engine.autonomy_active())

    def test_protect_mode_merge_allow_is_final_no_ask(self):
        self.arm()
        self.open_pr(3)
        self.open_pr(4, base='feat/3')
        self.engine.disarm_autonomy()
        self.engine.record_owner_approval([], [], tm.EVIDENCE)  # nothing is gated on the default branch now
        result = self.decide(self.merge(4), mode='protect', engine=self.engine)
        self.assertEqual(result.output, {})

    def test_approved_receipt_merge_is_allowed_and_a_wrong_sha_denied(self):
        self.approved_pair()
        self.assertEqual(self.decide(self.merge(3), mode='protect', engine=self.engine).output, {})
        wrong = self.decide(self.merge(3).replace(self.sha[3], 'a' * 40), mode='protect', engine=self.engine)
        self.assertEqual(tp.verdict(wrong), 'deny')
        self.assertIn(self.merge(3), tp.reason(wrong))

    def test_normal_mode_merge_makes_no_gh_call_without_autonomous_pr(self):
        self.log.unlink(missing_ok=True)
        result = self.decide('gh pr merge 7 --merge', mode='normal')
        self.assertEqual(result.output, {})
        self.assertEqual(self.calls(), [])

    def test_guard_none_falls_through_to_mode_rules(self):
        self.assertEqual(tp.verdict(self.decide('gh pr merge 7', mode='protect')), 'allow')  # no engine: unarmed
        self.arm()
        self.engine.disarm_autonomy()
        self.engine.record_owner_approval([], [], tm.EVIDENCE)
        self.assertEqual(tp.verdict(self.decide('gh pr merge 7', mode='protect', engine=self.engine)), 'ask')

    def test_release_multi_merge_command_reaches_the_guard(self):
        self.approved_pair()
        for command in (self.merge(3) + ' && git status', 'git status; ' + self.merge(3)):
            with self.subTest(command=command):
                result = self.decide(command, mode='normal', engine=self.engine)
                self.assertEqual(tp.verdict(result), 'deny')
                self.assertIn('one plain gh pr merge command', tp.reason(result))

    def test_unattended_denial_keeps_the_way_out_words(self):
        self.stop()
        result = self.decide('gh pr merge 3', mode='normal', unattended=True)
        self.assertEqual(tp.verdict(result), 'deny')
        self.assertIn('approved', tp.reason(result))


if __name__ == '__main__':
    unittest.main()
