"""2.15.1 card H: delete globs, worktree removal shapes, the push-shape deny text, worker liveness, the model record
of a bystander session, the deadline stop on any prompt and the brief pointer. Each test goes through the public hook,
engine or CLI entry point."""
import json
import os
import pathlib
import re
import sys
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(HERE))

import test_autonomy_cleanup as ta
import test_briefs as tb
import test_guard_plane as tg
import test_model_record as tmr
import test_prompt_approval as tpa
from orchestra_core.engine import Engine
from orchestra_core.hooks import _leftovers, handle_event
from orchestra_core.prompt_approval import handle_prompt

CLAUDE_TMP = 'claude-%d' % (os.getuid() if hasattr(os, 'getuid') else 0)


class TempGlobTest(ta.CleanupFixture):
    def test_a_glob_that_empties_a_temp_root_or_a_session_root_is_denied(self):
        for command in ('rm -rf /tmp/*', 'rm -rf /private/tmp/*', 'rm -rf /private/tmp/%s/*' % CLAUDE_TMP,
                        'rm -rf /tmp/%s/*' % CLAUDE_TMP):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), 'deny')

    def test_a_glob_in_the_last_component_inside_one_scratchpad_is_allowed(self):
        for command in ('rm -rf /private/tmp/%s/proj/sess/scratchpad/*' % CLAUDE_TMP, 'rm -rf /tmp/x/*.log'):
            with self.subTest(command=command):
                self.assertIsNone(self.hook(command))


class WorktreeGlobTest(ta.CleanupFixture):
    def test_a_dot_dot_after_a_glob_is_denied(self):
        for command in ('rm -rf */../../x', 'rm -rf */..', 'rm -rf a/../../x*', 'rm -rf */x'):  # run inside the worktree
            with self.subTest(command=command):
                self.assertEqual(self.hook(command, cwd=self.wt), 'deny')

    def test_a_glob_in_the_last_component_stays_allowed(self):
        for command in ('rm -rf a/*', 'rm -rf *.o'):
            with self.subTest(command=command):
                self.assertIsNone(self.hook(command, cwd=self.wt))


class WorktreeOwnershipTest(ta.CleanupFixture):
    def mark_before_arm(self, branch):
        data = self.raw()
        data['autonomy']['local_branches_at_arm'].append(branch)
        self.engine.state_path.write_text(json.dumps(data))

    def test_a_worktree_of_a_branch_the_run_did_not_make_is_denied(self):
        self.run_worktree('o')
        self.assertIsNone(self.hook('git worktree remove .claude/worktrees/o'))  # a run branch: allowed
        self.mark_before_arm('run-o')  # the same branch, now one that existed when the run armed
        self.assertEqual(self.hook('git worktree remove .claude/worktrees/o'), 'deny')

    def test_a_worktree_holding_an_ignored_file_is_denied(self):
        path = self.run_worktree('ig')
        (path / '.gitignore').write_text('*.local\n')
        tg.subprocess.run(['git', '-C', str(path), 'add', '.gitignore'], check=True)
        tg.subprocess.run(['git', '-C', str(path), 'commit', '-qm', 'ignore'], check=True)
        self.merge('ig')
        self.assertIsNone(self.hook('git worktree remove .claude/worktrees/ig'))
        (path / '.env.e2e.local').write_text('secret')
        self.assertEqual(self.hook('git worktree remove .claude/worktrees/ig'), 'deny')


class WorktreeShapeTest(ta.CleanupFixture):
    def test_the_removal_holds_behind_a_cd_prefix_and_with_an_error_redirect(self):
        self.run_worktree('m1', commit=True)
        self.merge('m1')
        repo = '"%s"' % self.repo  # the fixture path holds spaces
        for command in ('git worktree remove .claude/worktrees/m1 2>&1',
                        'cd %s && git worktree remove .claude/worktrees/m1' % repo,
                        'cd %s && git worktree remove .claude/worktrees/m1 2>&1 | tail -2' % repo):
            with self.subTest(command=command):
                self.assertIsNone(self.hook(command))

    def test_an_unmerged_dirty_or_forced_removal_stays_denied_in_every_shape(self):
        self.run_worktree('u', commit=True)
        dirty = self.run_worktree('d', commit=True)
        self.merge('d')
        (dirty / 'x.txt').write_text('x')
        repo = '"%s"' % self.repo
        for command in ('cd %s && git worktree remove .claude/worktrees/u' % repo,
                        'cd %s && git worktree remove .claude/worktrees/d' % repo,
                        'git worktree remove .claude/worktrees/u 2>&1',
                        'git worktree remove .claude/worktrees/d 2>&1',
                        'cd %s && git worktree remove --force .claude/worktrees/d' % repo,
                        'cd %s; git worktree remove .claude/worktrees/d' % repo,
                        'cd %s && git worktree remove .claude/worktrees/d | tee out' % repo):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), 'deny')


class PushShapeTextTest(ta.CleanupFixture):
    def test_a_semicolon_chain_names_the_push_shape_rule(self):
        self.branch('run-m1')
        self.assertIsNone(self.hook('git push origin run-m1'))
        repo = '"%s"' % self.repo
        command = 'cd %s; git push origin run-m1 2>&1 | tail -4' % repo
        self.assertEqual(self.hook(command), 'deny')
        self.assertIn('plain single command', self.hook_reason(command))

    def test_a_push_the_shape_rule_does_not_excuse_keeps_the_release_text(self):
        reason = self.hook_reason('cd "%s"; git push origin %s 2>&1 | tail -4' % (self.repo, self.default_branch))
        self.assertIn('merges and releases wait for the owner', reason)
        self.assertNotIn('plain single command', reason)


class WorkerLivenessTest(tmr.ModelCase):
    def setUp(self):
        super().setUp()
        self.task('B1')
        self.task('B2')
        self.task('B3')
        for name in ('B1', 'B2', 'B3'):
            self.engine.dispatch('main', self.lease, name, 'w-' + name, serial='fixture: one card at a time')
        self.session = self.root / 'proj' / 'sess'
        self.sub = self.session / 'subagents'
        self.sub.mkdir(parents=True)

    def transcript(self, name, age):
        path = self.sub / name
        path.write_text('{}')
        os.utime(path, (time.time() - age, time.time() - age))

    def line(self, text, card):
        return re.search(r'\b' + card + r' \(([^)]*)\)', text).group(1)

    def test_each_running_card_says_alive_gone_or_unknown(self):
        self.transcript('agent-w-B1.jsonl', 5)
        self.transcript('agent-w-B2.jsonl', 3600)
        text = _leftovers(self.engine, str(self.session) + '.jsonl')
        self.assertIn('alive', self.line(text, 'B1'))
        self.assertIn('gone', self.line(text, 'B2'))
        self.assertIn('liveness unknown', self.line(text, 'B3'))

    def test_without_a_transcript_path_no_card_is_called_gone(self):
        text = _leftovers(self.engine, None)
        for card in ('B1', 'B2', 'B3'):
            self.assertIn('liveness unknown', self.line(text, card))
            self.assertNotIn('gone', self.line(text, card))


class BystanderModelTest(tmr.ModelCase):
    def bind(self):
        self.engine = Engine(self.root / 'bound', self.repo)
        self.lease = self.engine.open_session('main', 'OWNER')
        self.engine.record_model(tmr.SONNET, None)

    def test_a_stop_from_another_bound_session_leaves_the_model_unchanged(self):
        self.bind()
        handle_event('Stop', {'session_id': 'OTHER', 'model': tmr.HAIKU}, engine=self.engine,
                     state_dir=str(self.engine.state_dir))
        self.assertEqual(self.recorded(), tmr.SONNET)

    def test_a_session_start_from_another_bound_session_leaves_the_model_unchanged(self):
        self.bind()
        handle_event('SessionStart', {'session_id': 'OTHER', 'source': 'startup', 'model': tmr.HAIKU}, engine=self.engine,
                     state_dir=str(self.engine.state_dir))
        self.assertEqual(self.recorded(), tmr.SONNET)

    def test_the_bound_session_still_records(self):
        self.bind()
        handle_event('SessionStart', {'session_id': 'OWNER', 'source': 'startup', 'model': tmr.HAIKU}, engine=self.engine,
                     state_dir=str(self.engine.state_dir))
        self.assertEqual(self.recorded(), tmr.HAIKU)


class DeadlinePromptTest(tpa.PromptFixture):
    def active(self):
        return self.raw()['autonomy']['active']

    def test_a_plain_prompt_after_the_deadline_ends_the_armed_state(self):
        self.arm()
        self.assertEqual(self.prompt('keep going', session='NIGHT'), {})
        self.assertTrue(self.active())
        self.now[0] += 10 ** 7
        self.assertEqual(self.prompt('keep going', session='NIGHT'), {})
        self.assertFalse(self.active())
        self.assertEqual(self.raw()['autonomy']['last_stop_reason'], 'deadline')

    def test_a_plain_prompt_before_the_deadline_changes_nothing_even_from_another_session(self):
        self.arm()
        before = self.engine.state_path.read_bytes()
        self.assertEqual(self.prompt('hello'), {})
        self.assertEqual(before, self.engine.state_path.read_bytes())
        self.assertTrue(self.active())

    def test_a_chat_go_ahead_is_not_an_approval(self):
        self.stopped_run(1)
        self.assertEqual(self.prompt('yes merge them all'), {})
        self.assertNotIn('approval', self.raw())


class BriefPointerTest(tb.CliFixture):
    def test_a_started_card_is_pointed_at_the_card_command_not_a_state_path(self):
        self.task('a', outcome='Do a')
        entry = self.cli('wave', 'a', '--emit', '--serial', 'fixture: one card')['emit'][0]
        self.assertIn('orchestra.py card a', entry['prompt'])
        self.assertNotIn(str(self.engine.state_dir), entry['prompt'])
        self.assertNotIn(str(self.engine.state_dir), entry['agent_call'])
        self.assertTrue(pathlib.Path(entry['brief']).is_file())  # the entry keeps the file path

    def test_a_card_with_its_own_brief_file_keeps_that_path_in_the_prompt(self):
        brief = self.root / 'own.md'
        brief.write_text('Mode: implementation\n\n## Keep\nx\n\n## Remove\nnone\n')
        self.task('a', brief=str(brief))
        entry = self.cli('wave', 'a', '--emit', '--serial', 'fixture: one card')['emit'][0]
        self.assertIn(str(brief), entry['prompt'])


if __name__ == '__main__':
    unittest.main()
