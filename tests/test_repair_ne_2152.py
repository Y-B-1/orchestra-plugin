"""2.15.2 repair RN (RWC on NE): the main session's inline slot follows one rule in every check."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine_2152 as t2
from orchestra_core.engine import EngineError


class InlineSlotTests(t2.Fixture):
    def inline_reported(self, name):
        token = self.engine.start_inline('main', self.lease, name, serial='fixture: one card at a time')
        self.engine.report('main', token, t2.te.done('Built %s.' % name))

    def test_a_lone_inline_start_after_a_report_still_needs_the_whole_wave(self):
        for name in ('a', 'b', 'c'):
            self.task(name, files=[name])
        self.inline_reported('a')
        with self.assertRaisesRegex(EngineError, 'Start the whole wave'):
            self.engine.start_inline('main', self.lease, 'b')

    def test_resume_refuses_a_second_running_inline_card(self):
        self.task('a', files=['a'])
        self.task('b', files=['b'])
        self.inline_reported('a')
        self.engine.start_inline('main', self.lease, 'b', serial='fixture: one card at a time')
        with self.assertRaisesRegex(EngineError, 'inline card b'):
            self.engine.resume_card('main', self.lease, 'a')
        self.assertEqual('reported', self.cards()['a']['state'])


if __name__ == '__main__':
    unittest.main()
