"""Orchestra 2.15.2 F105: an acceptance line that wraps commands in markdown backticks is checked span by span, so a
quoted pattern followed by a closing backtick still matches its test file."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from test_refusal_texts import RefusalFixture


class BacktickAcceptanceTests(RefusalFixture):
    def setUp(self):
        super().setUp()
        (self.repo / 'tests').mkdir()
        (self.repo / 'tests' / 'test_packaging.py').write_text('')
        (self.repo / 'tests' / 'test_skill_routing.py').write_text('')

    def test_a_quoted_pattern_before_a_closing_backtick_matches(self):
        self.task('a', acceptance=["`python3 -B -m unittest discover -s tests -p 'test_packaging.py'` and "
                                   "`-p 'test_skill*.py'` exit 0."])

    def test_a_backtick_span_with_a_missing_file_is_still_refused(self):
        self.assertIn('Acceptance matches no test file', self.refusal(
            self.task, 'b', acceptance=["`python3 -m unittest discover -s tests -p 'test_gone.py'` exits 0."]))


if __name__ == '__main__':
    unittest.main()
