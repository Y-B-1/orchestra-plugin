"""2.15.2 track: the main session runs the main path inline. A card may run inline when the session model ranks at or
above the card's (opus > sonnet > haiku) and, on the same family, its effort is at or above the card's; only a weaker
session sends a card to a worker. Policy `model_fit: "exact"` keeps the 2.15.1 exact-family rule. Track step 1 names
only cards that can start now."""
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core import delta
from orchestra_core.engine import Engine, EngineError


class StrongerSessionTests(te.EngineFixture):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {'CLAUDE_EFFORT': ''})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.fresh()

    def fresh(self, policy=None, model=('claude-opus-5-5', 'medium')):
        self.engine = Engine(self.root / ('state-%d' % len(os.listdir(self.root))), self.repo, policy)
        self.lease = self.engine.open_session('main', size='medium', asks=2)
        self.engine.record_model(*model)

    def test_an_opus_session_runs_a_sonnet_builder_card_inline(self):
        self.task('B1')
        self.assertEqual(self.engine.waves()['track'][0]['card'], 'B1')
        self.engine.start_inline('main', self.lease, 'B1')

    def test_an_opus_session_runs_a_haiku_mechanical_card_inline(self):
        self.task('M1', mode='mechanical')
        self.engine.start_inline('main', self.lease, 'M1')

    def test_a_haiku_session_sends_a_sonnet_card_to_a_worker(self):
        self.fresh(model=('claude-haiku-5-5', 'high'))
        self.task('B1')
        with self.assertRaisesRegex(EngineError, 'Model fit: B1 needs claude-sonnet-5-5 medium'):
            self.engine.start_inline('main', self.lease, 'B1')
        step = self.engine.waves()['track'][0]
        self.assertIsNone(step['card'])
        self.assertIn('coordinator', step)

    def test_a_lower_effort_on_the_same_family_still_sends_the_card_to_a_worker(self):
        self.fresh(model=('claude-sonnet-5-5', 'low'))
        self.task('B1')
        with self.assertRaisesRegex(EngineError, 'Model fit'):
            self.engine.start_inline('main', self.lease, 'B1')

    def test_a_stronger_family_ignores_the_effort(self):
        self.fresh(model=('claude-opus-5-5', 'low'))
        self.task('B1')
        self.engine.start_inline('main', self.lease, 'B1')

    def test_policy_exact_keeps_the_family_rule(self):
        self.fresh(policy=dict(schema_version=1, model_fit='exact'))
        self.task('B1')
        with self.assertRaisesRegex(EngineError, 'Model fit'):
            self.engine.start_inline('main', self.lease, 'B1')

    def test_an_invalid_model_fit_policy_is_refused(self):
        with self.assertRaises(EngineError):
            self.fresh(policy=dict(schema_version=1, model_fit='loose'))


class StepOneTests(te.EngineFixture):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {'CLAUDE_EFFORT': ''})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.engine = Engine(self.root / 'track', self.repo)
        self.lease = self.engine.open_session('main', size='medium', asks=2)
        self.engine.record_model('claude-opus-5-5', 'medium')

    def steps(self):
        return self.engine.waves()['track']

    def run_card(self, name, **kw):
        self.task(name, **kw)
        return self.engine.dispatch('main', self.lease, name, 'w-' + name, serial='fixture: one card at a time')

    def test_a_card_whose_dependency_is_running_is_not_step_one(self):
        self.run_card('a')
        self.task('b', dependencies=['a'])
        self.task('c')
        first = self.steps()[0]
        self.assertNotEqual(first['card'], 'b')
        self.assertNotIn('b', first['side'])
        self.assertEqual(first['card'], 'c')

    def test_a_card_sharing_a_file_with_a_running_card_is_not_step_one(self):
        self.run_card('a', files=['x'])
        self.task('b', files=['x'])
        self.task('c', files=['y'])
        first = self.steps()[0]
        self.assertEqual(first['card'], 'c')
        self.assertNotIn('b', first['side'])

    def test_a_card_waiting_on_a_reported_dependency_is_not_step_one(self):
        token = self.run_card('a')
        self.engine.report('w-a', token, te.done('Implemented a.'))
        self.task('b', dependencies=['a'])
        steps = self.steps()
        self.assertTrue(not steps or steps[0]['card'] != 'b')

    def test_later_steps_still_plan_the_blocked_card(self):
        self.run_card('a')
        self.task('b', dependencies=['a'])
        self.task('c')
        self.assertIn('b', [s['card'] for s in self.steps()] + [x for s in self.steps() for x in s['side']])

    def test_the_board_line_names_a_card_that_inline_starts(self):
        self.run_card('a', files=['x'])
        self.task('b', files=['x'])
        self.task('c', files=['y'])
        line = delta.track_text(self.engine.view())
        self.assertIn('you run c', line)
        self.engine.start_inline('main', self.lease, 'c')


class LayeringTests(unittest.TestCase):
    def test_the_engine_does_not_import_the_hook_adapter(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts/orchestra_core/engine.py').read_text()
        self.assertNotIn('from .hooks import', source)
        self.assertNotIn('from . import hooks', source)


if __name__ == '__main__':
    unittest.main()
