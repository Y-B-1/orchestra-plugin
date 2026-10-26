"""2.15.2 card HK: temp deletes keep every other session's scratchpad, temp file globs, the own-worktree check after a
cd, ignored caches in cleanup, the bound-session check on PostModelSwitch, no uid literal in source, a resumed
worker's second report, running gates and live worktree processes in the restart note, and one model-fit rule for
the prompt line. Each test goes through the public hook or the function the hook calls."""
import json
import os
import pathlib
import re
import sys
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(HERE))

import test_autonomy_cleanup as ta
import test_capture as tc
import test_engine as te
import test_guard_plane as tg
import test_model_record as tmr
from orchestra_core import hooks as hooks_module
from orchestra_core.engine import Engine
from orchestra_core.hooks import _leftovers, handle_event

UID = os.getuid() if hasattr(os, 'getuid') else 0
ROOTS = ('/private/tmp/claude-%d' % UID, '/tmp/claude-%d' % UID)
OWN, OTHER = 'sess-own-1', 'sess-other-2'


class ScratchpadDeleteTest(ta.CleanupFixture):
    def test_the_claude_temp_root_a_project_and_another_session_are_denied(self):
        for root in ROOTS:
            for command in ('rm -rf %s' % root, 'rm -rf %s/' % root, 'rm -rf %s/proj' % root, 'rm -rf %s/proj/*' % root,
                            'rm -rf %s/proj/s*' % root, 'rm -rf %s/proj/%s' % (root, OWN),
                            'rm -rf %s/proj/%s/scratchpad/x' % (root, OTHER),
                            'rm -rf %s/proj/%s/scratchpad/x %s/proj' % (root, OWN, root)):
                with self.subTest(command=command):
                    self.assertEqual(self.hook(command, session=OWN), 'deny')

    def test_inside_the_sessions_own_directory_is_allowed(self):
        for root in ROOTS:
            for command in ('rm -rf %s/proj/%s/scratchpad/x' % (root, OWN),
                            'rm -rf %s/proj/%s/scratchpad/*' % (root, OWN),
                            'rm -rf %s/proj/%s/scratchpad/run/sub' % (root, OWN),
                            'rm -f %s/proj/%s/tasks/t.output' % (root, OWN)):
                with self.subTest(command=command):
                    self.assertIsNone(self.hook(command, session=OWN))

    def test_without_a_session_id_only_a_session_scratchpad_below_a_session_is_allowed(self):
        root = ROOTS[0]
        self.assertIsNone(self.hook('rm -rf %s/proj/sess/scratchpad/x' % root))
        self.assertEqual(self.hook('rm -rf %s/proj' % root), 'deny')


class ScratchpadCaseTest(ta.CleanupFixture):
    def test_a_differently_cased_claude_directory_is_denied(self):
        for command in ('rm -rf /tmp/CLAUDE-%d' % UID, 'rm -rf /private/tmp/Claude-%d/p' % UID,
                        'rm -rf /private/tmp/Claude-%d/proj/%s' % (UID, OTHER), 'rm -rf /tmp/Claude-*', 'rm -rf /tmp/CLA*',
                        'rm -f /tmp/Cl*.log', 'rm -rf /tmp/claude-%d/proj/*' % UID):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command, session=OWN), 'deny')


class TempFileGlobTest(ta.CleanupFixture):
    def test_a_file_glob_with_a_prefix_that_cannot_be_claude_is_allowed(self):
        for command in ('rm -f /tmp/foo*.log', 'rm -f /private/tmp/orchestra-check.*', 'rm -rf /tmp/x/*.log'):
            with self.subTest(command=command):
                self.assertIsNone(self.hook(command, session=OWN))

    def test_a_glob_that_can_match_a_claude_directory_is_denied(self):
        for command in ('rm -rf /tmp/*', 'rm -f /tmp/c*', 'rm -f /tmp/cl*.log', 'rm -rf /tmp/claude*', 'rm -rf /tmp/claude-*',
                        'rm -rf /private/tmp/*', 'rm -f /tmp/.x*', 'rm -f /tmp/?oo'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command, session=OWN), 'deny')


class OwnWorktreeAfterCdTest(ta.CleanupFixture):
    def test_a_cd_to_the_main_checkout_does_not_hide_the_sessions_own_worktree(self):
        own = self.run_worktree('own', commit=True)
        self.merge('own')
        command = 'cd "%s" && git worktree remove .claude/worktrees/own' % self.repo
        self.assertEqual(self.hook(command, cwd=own), 'deny')
        self.assertIsNone(self.hook(command, cwd=self.repo))


class IgnoredCacheCleanupTest(ta.CleanupFixture):
    def test_python_caches_do_not_block_removal_but_other_ignored_files_do(self):
        path = self.run_worktree('pc')
        (path / '.gitignore').write_text('__pycache__/\n*.pyc\n*.local\n')
        tg.subprocess.run(['git', '-C', str(path), 'add', '.gitignore'], check=True)
        tg.subprocess.run(['git', '-C', str(path), 'commit', '-qm', 'ignore'], check=True)
        self.merge('pc')
        (path / 'pkg' / '__pycache__').mkdir(parents=True)
        (path / 'pkg' / '__pycache__' / 'm.cpython-313.pyc').write_bytes(b'x')
        (path / 'loose.pyc').write_bytes(b'x')
        self.assertIsNone(self.hook('git worktree remove .claude/worktrees/pc'))
        (path / 'secret.local').write_text('x')
        self.assertEqual(self.hook('git worktree remove .claude/worktrees/pc'), 'deny')


class IgnoredFolderFileTest(ta.CleanupFixture):
    def test_a_non_cache_file_inside_an_ignored_cache_folder_blocks_removal(self):
        path = self.run_worktree('pf')
        (path / '.gitignore').write_text('__pycache__/\n*.pyc\n')
        tg.subprocess.run(['git', '-C', str(path), 'add', '.gitignore'], check=True)
        tg.subprocess.run(['git', '-C', str(path), 'commit', '-qm', 'ignore'], check=True)
        self.merge('pf')
        (path / 'pkg' / '__pycache__').mkdir(parents=True)
        (path / 'pkg' / '__pycache__' / 'm.cpython-313.pyc').write_bytes(b'x')
        self.assertIsNone(self.hook('git worktree remove .claude/worktrees/pf'))
        (path / 'pkg' / '__pycache__' / 'notes.md').write_text('keep me')
        self.assertEqual(self.hook('git worktree remove .claude/worktrees/pf'), 'deny')


class ModelSwitchSessionTest(tmr.ModelCase):
    def bind(self):
        self.engine = Engine(self.root / 'bound', self.repo)
        self.lease = self.engine.open_session('main', 'OWNER')
        self.engine.record_model(tmr.SONNET, None)

    def test_a_switch_in_another_bound_session_leaves_the_model_unchanged(self):
        self.bind()
        self.run_hook('_model_switch', {'session_id': 'OTHER', 'to_model': tmr.HAIKU})
        self.assertEqual(self.recorded(), tmr.SONNET)

    def test_a_switch_in_the_bound_session_records(self):
        self.bind()
        self.run_hook('_model_switch', {'session_id': 'OWNER', 'to_model': tmr.HAIKU})
        self.assertEqual(self.recorded(), tmr.HAIKU)


class NoUidLiteralTest(unittest.TestCase):
    def test_no_source_or_test_names_a_numeric_claude_temp_directory(self):
        pattern = re.compile(r'/tmp/claude-[0-9]+')
        files = [HERE.parent / 'plugins/orchestra/scripts/orchestra_core/hooks.py', *sorted(HERE.glob('test_*.py'))]
        found = [str(p.name) for p in files if pattern.search(p.read_text(errors='replace'))]
        self.assertEqual(found, [])


class ResumedReportTest(tc.CaptureCase):
    def test_a_second_final_message_after_a_report_replaces_the_report(self):
        self.stop()
        self.assertEqual(self.task_state(), 'reported')
        newer = 'STATUS: PASS\nARTIFACT: def456 clean\nFixed the two lines.'
        self.assertEqual(self.stop(message=newer), {})
        self.assertEqual((self.reports / (self.token + '.md')).read_text(), newer)
        self.assertEqual(self.task_state(), 'reported')
        self.assertIn('def456', json.dumps(self.engine.status()['tasks']['c']))


class RestartGateTest(te.EngineFixture):
    def test_a_gate_log_with_no_receipt_and_a_recent_write_is_named(self):
        log = self.engine.state_dir / 'gate-0123456789abcdef0123456789abcdef.log'
        log.write_text('....')
        text = _leftovers(self.engine, None)
        self.assertIn('gate', text)
        self.assertIn('do not start a second gate', text)

    def test_an_old_or_finished_gate_log_is_not_named(self):
        log = self.engine.state_dir / 'gate-fedcba9876543210fedcba9876543210.log'
        log.write_text('done')
        os.utime(log, (time.time() - 3600, time.time() - 3600))
        self.assertNotIn('second gate', _leftovers(self.engine, None))


class LiveWorktreeProcessTest(te.EngineFixture):
    def test_a_worktree_with_a_live_process_is_named_and_kept(self):
        inside = self.repo / '.claude' / 'worktrees' / 'agent-x'
        inside.mkdir(parents=True)
        with mock.patch.object(hooks_module, '_process_cwds', return_value=[str(inside / 'sub')]):
            text = _leftovers(self.engine, None)
        self.assertIn('agent-x', text)
        self.assertIn('do not remove', text)

    def test_the_process_lookup_sees_this_process(self):
        cwds = hooks_module._process_cwds()
        if cwds is None:
            self.skipTest('no process lookup on this system')
        self.assertIn(os.path.realpath(os.getcwd()), [os.path.realpath(c) for c in cwds])


class ModelLineRuleTest(te.EngineFixture):
    def setUp(self):
        super().setUp()
        self.engine = Engine(self.root / 'sized', self.repo)
        self.lease = self.engine.open_session('main', size='medium', asks=2)
        self.task('B1')

    def line(self):
        return hooks_module._model_line(self.engine, self.engine.view())

    def test_a_stronger_session_lists_no_card(self):
        self.engine.record_model('claude-opus-5-5', 'medium')
        self.assertIsNone(self.line())

    def test_a_weaker_session_lists_the_card(self):
        self.engine.record_model('claude-haiku-5-5', 'high')
        self.assertIn('B1', self.line() or '')


if __name__ == '__main__':
    unittest.main()
