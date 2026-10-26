"""2.15.1 scheduling: `waves` and `board --view` carry the track (the cards the main session runs inline, in order,
with the cards workers run beside each), and a plain `start` never takes a run from another harness session."""
import pathlib
import sys
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import Engine, EngineError

COORDINATOR = 'prepare briefs and review reports'


class TrackFixture(te.EngineFixture):
    def engine_with(self, policy=None, model=('claude-sonnet-5-5', 'medium')):
        self.engine = Engine(self.root / ('state-%d' % time.monotonic_ns()), self.repo, policy)
        self.lease = self.engine.open_session('main', size='medium', asks=2)
        if model:
            self.engine.record_model(*model)

    def track(self):
        return [dict(card=s['card'], side=s['side']) for s in self.engine.waves()['track']]


class TrackTests(TrackFixture):
    def setUp(self):
        super().setUp()
        self.engine_with()

    def test_dependencies_come_first_and_the_card_that_unblocks_most_leads(self):
        self.task('a')
        self.task('b', dependencies=['a'])
        self.task('c', dependencies=['a'])
        self.task('d', dependencies=['b'])
        self.assertEqual(self.track(), [dict(card='a', side=[]), dict(card='b', side=['c']), dict(card='d', side=[])])

    def test_the_card_that_unblocks_more_beats_an_earlier_card(self):
        self.task('p', files=['x'])
        self.task('q', files=['x'])
        self.task('r', dependencies=['q'])
        self.assertEqual(self.track(), [dict(card='q', side=[]), dict(card='p', side=['r'])])

    def test_a_card_that_fits_the_session_model_runs_inline_before_one_that_does_not(self):
        self.task('m1', mode='mechanical')  # Haiku: not the session's model
        self.task('i1')
        self.assertEqual(self.track(), [dict(card='i1', side=['m1'])])

    def test_no_card_fitting_the_session_model_names_the_coordinator_work(self):
        self.engine.record_model('claude-opus-5-5', 'high')
        self.task('a')
        self.task('b')
        out = self.engine.waves()['track']
        self.assertEqual([(s['card'], s['coordinator'], s['side']) for s in out], [(None, COORDINATOR, ['a', 'b'])])

    def test_side_cards_are_disjoint_from_the_inline_card_and_fit_the_worker_cap(self):
        self.engine_with(dict(schema_version=1, max_workers=2))
        self.task('a')
        self.task('b')
        self.task('c')
        self.task('a2', files=['a'])
        self.assertEqual(self.track(), [dict(card='a', side=['b']), dict(card='c', side=['a2'])])

    def test_an_unknown_session_model_fits_every_card(self):
        self.engine_with(model=None)
        self.task('a')
        self.assertEqual(self.track(), [dict(card='a', side=[])])

    def test_an_empty_board_has_an_empty_track(self):
        self.assertEqual(self.engine.waves()['track'], [])

    def test_a_card_behind_a_parked_one_is_left_off(self):
        self.task('a')
        self.task('b', dependencies=['a'])
        self.engine.park('main', self.lease, 'a', 'boundary')
        self.assertEqual(self.track(), [])

    def test_the_board_view_carries_the_first_three_steps(self):
        self.task('a')
        self.task('b', dependencies=['a'])
        self.task('c', dependencies=['b'])
        self.task('d', dependencies=['c'])
        view = self.engine.view()
        self.assertEqual([s['card'] for s in view['track']], ['a', 'b', 'c'])
        self.assertEqual([s['card'] for s in self.engine.waves()['track']], ['a', 'b', 'c', 'd'])


class TakeOverTests(te.EngineFixture):
    def setUp(self):
        super().setUp()
        self.engine = Engine(self.root / 'bound', self.repo)
        self.lease = self.engine.open_session('main', 'S1')
        self.task('B1')
        self.engine.dispatch('main', self.lease, 'B1', 'w-B1')
        self.engine.interrupt('main', self.lease)

    def progress(self):
        path = self.engine.state_dir / 'progress.md'
        return path.read_text() if path.exists() else ''

    def test_a_plain_start_under_another_harness_session_refuses_and_names_take_over(self):
        with self.assertRaisesRegex(EngineError, r'belongs to session S1.*start --recover --take-over'):
            self.engine.open_session('main', 'S2')
        status = self.engine.status()
        self.assertEqual((status['session']['harness_session'], status['session']['active']), ('S1', False))
        self.assertEqual(status['tasks']['B1']['state'], 'running')  # nothing was requeued

    def test_the_same_harness_session_still_resumes_silently(self):
        self.engine.open_session('main', 'S1')
        self.assertEqual(self.engine.requeued, ['B1'])
        self.assertNotIn('took over', self.progress())

    def test_take_over_moves_the_run_and_logs_it(self):
        self.engine.recover_lease('main', 'S2', take_over=True)
        self.assertEqual(self.engine.status()['session']['harness_session'], 'S2')
        self.assertIn('session S2 took over the run from S1', self.progress())


if __name__ == '__main__':
    unittest.main()
