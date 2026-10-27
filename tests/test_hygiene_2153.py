import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_engine
from test_engine import EngineError


class StaleCheckpointName(unittest.TestCase):
    def test_no_checkpoint_word_in_engine_tests(self):
        text = (HERE / 'test_engine.py').read_text()
        lines = [n for n, line in enumerate(text.splitlines(), 1) if re.search('checkpoint', line, re.I)]
        self.assertEqual([], lines)


class ReviewOfRefusals(test_engine.EngineFixture):
    def refusal(self, **values):
        with self.assertRaises(EngineError) as caught:
            self.task('invalid', role='code-reviewer', mode='final', **values)
        return str(caught.exception)

    def test_review_of_with_dependency_is_refused_for_the_dependency(self):
        self.task('B1')
        self.assertIn('Use review_of instead of an accepted dependency',
                      self.refusal(review_of=['B1'], dependencies=['B1']))

    def test_review_of_with_a_non_name_is_refused_as_a_bad_target(self):
        self.task('B1')
        self.assertIn('Review targets must name existing tasks', self.refusal(review_of=[{}]))
