"""A restart of the same conversation must not strand the coordinator: the session's own end is revived at the next
SessionStart with the same id (same lease, nothing armed), `start --recover` revives it too, every lease refusal names the
owner and the right command, and a forked session reads only unless it takes the run over explicitly."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import Engine, EngineError
from orchestra_core.hooks import handle_event, CONTEXT

OWNER, FORK = 'sess-owner', 'sess-fork'


class LeaseRestartTests(te.EngineFixture):
    def setUp(self):
        super().setUp()
        self.engine = Engine(self.root / 'bound', self.repo)
        self.lease = self.engine.open_session('main', OWNER)
        self.task('B1')

    def session(self):
        return self.engine.status()['session']

    def restart(self, session_id=OWNER, source='resume'):
        handle_event('SessionEnd', {'session_id': OWNER, 'reason': 'other'}, engine=self.engine, state_dir=str(self.engine.state_dir))
        return handle_event('SessionStart', {'session_id': session_id, 'source': source}, engine=self.engine,
                            state_dir=str(self.engine.state_dir))

    def test_a_restart_of_the_same_conversation_keeps_the_lease_working(self):
        self.restart()
        self.assertTrue(self.session()['active'])
        self.engine.dispatch('main', self.lease, 'B1', 'w-B1')  # the old lease still works

    def test_the_revival_arms_nothing(self):
        self.restart()
        self.assertFalse((self.engine.status().get('autonomy') or {}).get('active'))
        self.assertEqual([], self.engine.status()['permits'])

    def test_recover_revives_a_run_the_same_session_ended(self):
        handle_event('SessionEnd', {'session_id': OWNER, 'reason': 'other'}, engine=self.engine, state_dir=str(self.engine.state_dir))
        lease = self.engine.recover_lease('main', OWNER)
        self.assertTrue(self.session()['active'])
        self.engine.dispatch('main', lease, 'B1', 'w-B1')
        self.assertFalse((self.engine.status().get('autonomy') or {}).get('active'))

    def test_recover_after_finish_says_use_start(self):
        self.engine.cancel('main', self.lease, 'B1', 'not needed') if hasattr(self.engine, 'cancel') else None
        self.engine.close_session('main', self.lease)
        with self.assertRaisesRegex(EngineError, r'finished.*`start`'):
            self.engine.recover_lease('main', OWNER)

    def test_the_refusal_names_the_owner_and_recover_when_the_session_ended(self):
        handle_event('SessionEnd', {'session_id': OWNER, 'reason': 'other'}, engine=self.engine, state_dir=str(self.engine.state_dir))
        with self.assertRaises(EngineError) as caught:
            self.engine.dispatch('main', self.lease, 'B1', 'w-B1')
        text = str(caught.exception)
        self.assertIn(OWNER, text)
        self.assertIn('ended', text)
        self.assertIn('start --recover --harness-session ' + OWNER, text)

    def test_the_refusal_says_replaced_when_another_lease_was_issued(self):
        self.engine.recover_lease('main', OWNER)
        with self.assertRaisesRegex(EngineError, 'replaced'):
            self.engine.dispatch('main', self.lease, 'B1', 'w-B1')

    def test_the_refusal_says_start_when_the_run_finished(self):
        self.engine.cancel('main', self.lease, 'B1', 'not needed') if hasattr(self.engine, 'cancel') else None
        self.engine.close_session('main', self.lease)
        with self.assertRaises(EngineError) as caught:
            self.engine.dispatch('main', self.lease, 'B1', 'w-B1')
        self.assertIn('`start`', str(caught.exception))
        self.assertNotIn('--recover', str(caught.exception))

    def test_a_fork_does_not_revive_or_take_the_run(self):
        self.restart(session_id=FORK, source='fork')
        self.assertFalse(self.session()['active'])
        with self.assertRaisesRegex(EngineError, OWNER):
            self.engine.recover_lease('main', FORK)

    def test_a_fork_takes_an_ended_run_only_with_take_over_and_logs_it(self):
        handle_event('SessionEnd', {'session_id': OWNER, 'reason': 'other'}, engine=self.engine, state_dir=str(self.engine.state_dir))
        lease = self.engine.recover_lease('main', FORK, take_over=True)
        self.assertEqual(FORK, self.session()['harness_session'])
        self.assertIn('took over the run from ' + OWNER, (self.engine.state_dir / 'progress.md').read_text())
        self.engine.dispatch('main', lease, 'B1', 'w-B1')

    def test_take_over_is_refused_while_the_owner_is_active(self):
        with self.assertRaisesRegex(EngineError, 'active'):
            self.engine.recover_lease('main', FORK, take_over=True)

    def test_session_start_says_recovery_arms_nothing(self):
        self.assertIn('arms no autonomy', CONTEXT)


class SessionStartMarkerTests(te.EngineFixture):
    """A restart shows what the dead workers left, and the stored brief's age next to the live board."""
    def setUp(self):
        super().setUp()
        self.engine = Engine(self.root / 'bound', self.repo)
        self.lease = self.engine.open_session('main', OWNER)
        self.task('B1')

    def context(self):
        reply = handle_event('SessionStart', {'session_id': OWNER, 'source': 'resume'}, engine=self.engine,
                             state_dir=str(self.engine.state_dir))
        return reply.output['hookSpecificOutput']['additionalContext']

    def test_running_worker_cards_and_dirty_run_worktrees_are_named(self):
        import subprocess
        self.engine.dispatch('main', self.lease, 'B1', 'w-B1')
        tree = self.repo / '.claude' / 'worktrees' / 'wf-x'
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-q', '-b', 'wt-x', str(tree)], check=True)
        (tree / 'half.txt').write_text('half-edited')
        text = self.context()
        self.assertIn('B1 (worker w-B1', text)
        self.assertIn('wf-x', text)
        self.assertIn('1 uncommitted', text)

    def test_a_restart_says_how_many_worker_transcripts_are_still_being_written(self):
        self.engine.dispatch('main', self.lease, 'B1', 'w-B1')
        session = self.root / 'proj' / 'sess-owner'
        (session / 'subagents' / 'workflows' / 'wf_x').mkdir(parents=True)
        (session / 'subagents' / 'workflows' / 'wf_x' / 'agent-1.jsonl').write_text('{}')
        (session / 'subagents' / 'agent-old.jsonl').write_text('{}')
        import os, time
        old = time.time() - 3600
        os.utime(session / 'subagents' / 'agent-old.jsonl', (old, old))
        reply = handle_event('SessionStart', {'session_id': OWNER, 'source': 'resume',
                                              'transcript_path': str(session) + '.jsonl'},
                             engine=self.engine, state_dir=str(self.engine.state_dir))
        text = reply.output['hookSpecificOutput']['additionalContext']
        self.assertIn('1 worker transcript written in the last 2 minutes', text)

    def test_the_stored_brief_shows_its_age_and_the_live_counts(self):
        with self.engine._state() as state:
            self.engine._write_brief(state, 'stalled')
        text = self.context()
        self.assertIn('Run brief (stalled, written', text)
        self.assertIn('live board: queued 1', text)


if __name__ == '__main__':
    unittest.main()
