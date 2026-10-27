"""2.15.2 cleanup after the final review RX: the Model fit line wording under policy `exact`, a model-fit error other
than EngineError skips that card and keeps the line, and a trailing note after more than one space is still a note."""
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine_2152 as t2
from orchestra_core import hooks
from orchestra_core.engine import Engine


@t2.own_tests_only
class ModelLineCleanupTests(t2.Fixture):
    def test_the_exact_policy_says_another_model(self):
        self.engine = Engine(self.root / 'exact', self.repo, dict(schema_version=1, model_fit='exact'))
        self.lease = self.engine.open_session('main')
        self.engine.record_model('claude-opus-5-5', 'high')
        self.task('b1', files=['b1'])
        text = hooks._model_line(self.engine, self.engine.view())
        self.assertIn('Cards that must go to a worker (another model): b1', text)

    def test_an_unexpected_error_skips_the_card_and_keeps_the_others(self):
        self.engine.record_model('claude-haiku-5-5', 'low')
        self.task('b1', files=['b1'])
        self.task('b2', files=['b2'])
        real = Engine._check_model_fit

        def broken(state, card, exact=False):
            if card['id'] == 'b1':
                raise KeyError('mode')
            return real(state, card, exact=exact)
        with mock.patch.object(Engine, '_check_model_fit', staticmethod(broken)):
            text = hooks._model_line(self.engine, self.engine.view())
        self.assertIn(': b2 (', text)
        self.assertNotIn('b1 (', text)


class BareNoteTests(unittest.TestCase):
    def test_a_note_after_more_than_one_space_is_dropped(self):
        self.assertEqual('make full', Engine._bare('make full  (full gate)'))
        self.assertEqual('make full', Engine._bare('make full (full gate)'))
        self.assertEqual('cd d &&  (make full)', Engine._bare('cd d &&  (make full)'))


if __name__ == '__main__':
    unittest.main()
