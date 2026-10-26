"""`finish --accept-reported`: finish first accepts every reported card whose accept would pass, then closes."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import EngineError


class FinishAcceptTests(te.EngineFixture):
    def built(self, name, criteria=None):
        (self.repo / name).write_text(name)
        self.git('add', name)
        self.git('commit', '-qm', name)
        self.task(name)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        self.engine.report('w-' + name, token, te.done('Built ' + name, criteria=criteria))

    def test_without_the_flag_finish_still_refuses_a_reported_card(self):
        self.built('B1')
        with self.assertRaisesRegex(EngineError, 'All tasks must be accepted: B1'):
            self.engine.close_session('main', self.lease)

    def test_the_flag_accepts_a_reported_card_and_keeps_it_when_finish_refuses_later(self):
        self.built('B1')
        with self.assertRaises(EngineError) as caught:
            self.engine.close_session('main', self.lease, accept_reported=True)
        self.assertNotIn('All tasks must be accepted', str(caught.exception))
        self.assertEqual('accepted', self.engine.status()['tasks']['B1']['state'])

    def test_the_flag_leaves_a_card_whose_accept_is_refused(self):
        self.built('B1', criteria=[{'criterion': 'check behavior', 'met': False, 'evidence': 'no'}])
        with self.assertRaisesRegex(EngineError, 'All tasks must be accepted: B1 \\(reported\\)'):
            self.engine.close_session('main', self.lease, accept_reported=True)
        self.assertEqual('reported', self.engine.status()['tasks']['B1']['state'])


if __name__ == '__main__':
    unittest.main()
