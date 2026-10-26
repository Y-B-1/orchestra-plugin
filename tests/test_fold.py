"""Model fit: inline work runs on the main session's model and effort, which cannot change per card. A card whose
config/models.json model family differs from the session's, or whose effort is above it, starts only on a worker; the
engine records the session model from the hooks. Unknown values refuse nothing, and parallel waves stay."""
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import Engine, EngineError


class ModelFitTests(te.EngineFixture):
    def setUp(self):
        super().setUp()
        self.engine = Engine(self.root / 'sized', self.repo)
        self.lease = self.engine.open_session('main', size='medium', asks=2)
        patcher = mock.patch.dict(os.environ, {'CLAUDE_EFFORT': ''})
        patcher.start()
        self.addCleanup(patcher.stop)

    def modes(self, task_id):
        with self.engine._state(False) as state:
            return set(self.engine._startable(state, 'main').get(task_id, set()))

    def test_card_model_reads_the_mode_preset_then_the_role(self):
        self.assertEqual(('claude-haiku-5-5', 'high'), Engine.card_model(dict(role='builder', mode='mechanical')))
        self.assertEqual(('claude-sonnet-5-5', 'medium'), Engine.card_model(dict(role='builder', mode='implementation')))
        self.assertEqual(('claude-opus-5-5', 'high'), Engine.card_model(dict(role='critic', mode='judge')))
        self.assertEqual((None, None), Engine.card_model(dict(role='nobody', mode='x')))

    def test_an_unknown_session_model_refuses_nothing(self):
        self.task('B1', mode='mechanical')
        self.assertEqual({'inline', 'worker'}, self.modes('B1'))

    def test_a_different_model_family_is_worker_only(self):
        self.assertTrue(self.engine.record_model('claude-opus-5-5[1m]', 'high'))
        self.task('B1')
        self.assertEqual({'worker'}, self.modes('B1'))
        with self.assertRaisesRegex(EngineError, 'Model fit: B1 needs claude-sonnet-5-5 medium and the main session runs claude-opus-5-5'):
            self.engine.start_inline('main', self.lease, 'B1')
        self.engine.dispatch('main', self.lease, 'B1', 'w-B1')

    def test_a_haiku_card_in_a_sonnet_session_is_worker_only(self):
        self.engine.record_model('claude-sonnet-5-5', 'medium')
        self.task('M1', mode='mechanical')
        self.task('I1')
        self.assertEqual({'worker'}, self.modes('M1'))
        self.assertEqual({'inline', 'worker'}, self.modes('I1'))

    def test_a_lower_session_effort_is_worker_only(self):
        self.engine.record_model('claude-sonnet-5-5', 'low')
        self.task('B1')
        self.assertEqual({'worker'}, self.modes('B1'))

    def test_the_effort_env_overrides_the_record(self):
        self.engine.record_model('claude-sonnet-5-5', 'low')
        self.task('B1')
        with mock.patch.dict(os.environ, {'CLAUDE_EFFORT': 'high'}):
            self.assertEqual({'inline', 'worker'}, self.modes('B1'))

    def test_an_investigator_on_another_model_is_worker_only(self):
        self.engine.record_model('claude-sonnet-5-5', 'medium')
        self.task('I1', role='investigator', mode='code')  # code discovery runs on Haiku
        self.assertEqual({'worker'}, self.modes('I1'))
        with self.assertRaisesRegex(EngineError, 'Model fit: I1 needs claude-haiku-5-5 high'):
            self.engine.start_inline('main', self.lease, 'I1')

    def test_a_designer_planner_on_another_model_is_worker_only(self):
        self.engine = Engine(self.root / 'large', self.repo)
        self.lease = self.engine.open_session('main', size='medium', asks=2, owner_request=True)  # a plan card needs an owner request
        self.engine.record_model('claude-opus-5-5', 'high')
        self.task('P1', role='designer-planner', mode='plan')
        self.assertEqual({'worker'}, self.modes('P1'))
        with self.assertRaisesRegex(EngineError, 'Model fit: P1 needs claude-sonnet-5-5 high'):
            self.engine.start_inline('main', self.lease, 'P1')

    def test_an_operator_on_another_model_is_worker_only(self):
        self.engine.record_model('claude-sonnet-5-5', 'high')
        self.task('O1', role='operator', mode='gate')
        self.assertEqual({'worker'}, self.modes('O1'))

    def test_a_matching_investigator_still_folds(self):
        self.engine.record_model('claude-sonnet-5-5', 'medium')
        self.task('I1', role='investigator', mode='docs')
        self.assertEqual({'inline', 'worker'}, self.modes('I1'))

    def test_a_tiny_card_still_folds_whatever_the_model(self):
        self.engine.record_model('claude-opus-5-5', 'high')
        self.task('T1', size='tiny', mode='mechanical')
        self.assertEqual({'inline'}, self.modes('T1'))

    def test_two_disjoint_cards_still_start_as_one_wave(self):
        self.engine.record_model('claude-sonnet-5-5', 'medium')
        self.task('B1')
        self.task('B2')
        with self.assertRaisesRegex(EngineError, 'Start the whole wave'):
            self.engine.start_inline('main', self.lease, 'B1')
        self.engine.wave('main', self.lease, ['B1', 'B2'], inline='B1')

    def test_a_mismatched_wave_runs_every_card_on_workers(self):
        self.engine.record_model('claude-opus-5-5', 'high')
        self.task('B1')
        self.task('B2')
        with self.assertRaisesRegex(EngineError, 'Model fit'):
            self.engine.wave('main', self.lease, ['B1', 'B2'], inline='B1')
        self.engine.wave('main', self.lease, ['B1', 'B2'])

    def test_record_model_ignores_junk_and_a_missing_run(self):
        for model, effort in (('', None), (5, None), ('x' * 101, None), (None, 'huge')):
            with self.subTest(model=model, effort=effort):
                self.assertFalse(self.engine.record_model(model, effort))
        self.assertTrue(self.engine.record_model('claude-sonnet-5-5'))
        self.assertFalse(self.engine.record_model('claude-sonnet-5-5'))
        self.assertEqual('claude-sonnet-5-5', self.engine.view()['session']['model'])
        self.assertFalse(Engine(self.root / 'none', self.repo).record_model('claude-opus-5-5'))
        self.assertFalse((self.root / 'none' / 'state.json').exists())

    def test_record_model_is_not_progress(self):
        before = self.engine.status().get('activity', 0)
        self.engine.record_model('claude-opus-5-5')
        self.assertEqual(before, self.engine.status().get('activity', 0))


if __name__ == '__main__':
    unittest.main()
