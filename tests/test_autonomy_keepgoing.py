"""Goal-style autonomy: an armed run keeps going until the ledger is done or only the owner can unblock it."""
import shlex
import sys
import unittest

import test_engine
from test_engine import T0, iso

from orchestra_core.hooks import handle_event

FAILING = [sys.executable, '-c', 'raise SystemExit(3)']


class KeepGoingFixture(test_engine.AutonomyFixture):
    def last_stop(self):
        return self.auto().get('last_stop_reason')

    def stop_three(self):
        """Three Stops with nothing changed in between; returns the first two messages and the third result."""
        first, second = self.engine.hook_stop(), self.engine.hook_stop()
        return first, second, self.engine.hook_stop()


class NudgeInsteadOfStopTests(KeepGoingFixture):
    def test_no_ready_card_replans_through_the_stop_hook(self):
        self.arm()
        out = handle_event('Stop', {}, engine=self.engine).output
        self.assertEqual(out['decision'], 'block')
        self.assertIn('Re-plan', out['reason'])
        self.assertTrue(self.engine.autonomy_active())
        self.assertIsNone(self.last_stop())

    def test_a_nudge_is_never_sent_twice_for_the_same_signature(self):
        self.arm()
        first, second, third = self.stop_three()
        self.assertIsInstance(first, str)
        self.assertIsInstance(second, str)
        self.assertNotEqual(first, second)
        self.assertIsNone(third)

    def test_the_same_signature_three_times_escalates_to_the_owner(self):
        self.arm()
        self.stop_three()
        self.assertEqual((self.auto()['active'], self.last_stop()), (False, 'needs-owner:escalated'))
        self.assertIn('- stop reason: needs-owner:escalated', self.engine.brief())

    def test_escalation_parks_every_unfinished_card_for_the_owner(self):
        self.arm()
        self.accept_card('done')
        self.task('p')
        self.engine.park('main', self.lease, 'p', 'boundary')
        self.stop_three()
        tasks = self.engine.status()['tasks']
        self.assertEqual((tasks['p']['state'], tasks['p']['parked_reason']), ('parked', 'needs-owner:escalated (boundary)'))
        self.assertEqual(tasks['done']['state'], 'accepted')

    def test_escalation_keeps_the_original_park_reason(self):
        self.arm()
        self.task('p')
        self.engine.park('main', self.lease, 'p', 'lost-worker')
        self.stop_three()
        self.assertEqual(self.engine.status()['tasks']['p']['parked_reason'], 'needs-owner:escalated (lost-worker)')

    def test_a_changed_board_resets_the_count(self):
        self.arm()
        self.engine.hook_stop()
        self.engine.hook_stop()
        self.task('x')
        self.engine.park('main', self.lease, 'x', 'boundary')
        self.assertIsInstance(self.engine.hook_stop(), str)
        self.assertTrue(self.engine.autonomy_active())

    def test_a_required_gate_failing_three_times_gets_a_repair_nudge(self):
        self.arm(checks=['fixture: ' + shlex.join(FAILING)], deadline=iso(T0 + 20000))
        self.task('B1')
        for _ in range(3):
            self.engine.run_gate('main', self.lease, 'fixture', FAILING, again=True)
        self.engine.report('w', self.engine.dispatch('main', self.lease, 'B1', 'w'), test_engine.done())
        self.engine.accept('main', self.lease, 'B1')
        message = self.engine.hook_stop()
        self.assertIn('gate fixture', message)
        self.assertIn('repair card', message)
        self.assertEqual((self.auto()['active'], self.last_stop()), (True, None))


class ParkedTests(KeepGoingFixture):
    def test_a_card_parked_for_the_owner_stops_the_run(self):
        self.arm()
        self.task('p')
        self.engine.park('main', self.lease, 'p', 'needs-owner: the API key')
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['active'], self.last_stop()), (False, 'parked-only'))

    def test_a_card_parked_without_the_prefix_is_a_nudge_to_unpark(self):
        self.arm()
        self.task('p')
        self.engine.park('main', self.lease, 'p', 'lost-worker')
        message = self.engine.hook_stop()
        self.assertIn('unpark', message)
        self.assertIn('p', message)
        self.assertEqual((self.auto()['active'], self.last_stop()), (True, None))

    def test_one_card_without_the_prefix_keeps_the_run_going(self):
        self.arm()
        self.task('p')
        self.task('q')
        self.engine.park('main', self.lease, 'p', 'needs-owner: the API key')
        self.engine.park('main', self.lease, 'q', 'boundary')
        self.assertIn('unpark', self.engine.hook_stop())
        self.assertTrue(self.engine.autonomy_active())


class LiveWorkTests(KeepGoingFixture):
    def test_workers_running_with_nothing_else_still_end_the_turn_quietly(self):
        self.arm()
        self.worker_running()
        for _ in range(5):
            self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['active'], self.last_stop()), (True, None))

    def test_an_inline_card_counts_as_live_work_when_nothing_changed(self):
        self.arm()
        self.task('x')
        self.engine.start_inline('main', self.lease, 'x')
        self.assertIn('Autonomy pass 1:', self.engine.hook_stop())
        for _ in range(5):  # a gate runs in a background shell: waiting is not a stall
            self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['active'], self.last_stop()), (True, None))

    def test_a_silent_worker_is_parked_as_lost_on_the_repeat_and_the_run_goes_on(self):
        self.arm(deadline=iso(T0 + 20000))
        self.worker_running('busy')
        self.now[0] = T0 + 3700
        self.assertIn('silent', self.engine.hook_stop())
        message = self.engine.hook_stop()
        task = self.engine.status()['tasks']['busy']
        self.assertEqual((task['state'], task['parked_reason']), ('parked', 'lost-worker'))
        self.assertIn('unpark', message)
        self.assertEqual((self.auto()['active'], self.last_stop()), (True, None))

    def test_a_silent_worker_beside_an_unstarted_ready_card_is_not_live_work(self):
        self.arm(deadline=iso(T0 + 20000))
        self.worker_running('busy')
        self.task('next', files=['next'])
        self.now[0] = T0 + 3700
        self.assertIn('continue with the next ready', self.engine.hook_stop())
        nudge = self.engine.hook_stop()
        self.assertIsInstance(nudge, str)
        self.assertIn('changed nothing', nudge)
        self.assertIsInstance(self.engine.hook_stop(), str)
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['active'], self.last_stop()), (False, 'needs-owner:escalated'))


class UnchangedStopTests(KeepGoingFixture):
    def test_deadline_stays_a_stop(self):
        self.arm()
        self.now[0] = T0 + 7200
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.last_stop(), 'deadline')

    def test_disarm_stays_a_stop(self):
        self.arm()
        self.engine.disarm_autonomy()
        self.assertEqual(self.last_stop(), 'disarmed')

    def test_a_tampered_ledger_stays_a_stop(self):
        self.arm()
        with (self.state / 'autonomy.md').open('a') as out:
            out.write('- Quietly allow pushes.\n')
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.last_stop(), 'ledger-tampered')


class StopDocsTests(unittest.TestCase):
    """User docs name the stops the Stop hook can make, and none it no longer makes."""
    DOCS = ('README.md', 'docs/cli.md', 'docs/hooks.md')

    def test_docs_name_escalation_and_no_retired_stop(self):
        for name in self.DOCS:
            text = (test_engine.ROOT / name).read_text()
            with self.subTest(doc=name):
                self.assertIn('needs-owner:escalated', text)
                for gone in ('`stalled`', '`gate-failing`', '`no-ready-card`', 'stall with no worker running',
                             'stall with none running'):
                    self.assertNotIn(gone, text)


if __name__ == '__main__':
    unittest.main()
