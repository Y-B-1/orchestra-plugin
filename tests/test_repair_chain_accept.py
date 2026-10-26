"""F65: a CLEAN fix re-review recorded with `review --token` also accepts the repair chain it closes."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te


class ChainAcceptTests(te.HoldFixture):
    def setUp(self):
        super().setUp()
        self.allow_review()

    def repaired(self, report=None):
        """B1 blocked by the final review, R1 its repair, reported; nothing re-reviewed yet."""
        (self.repo / 'B1').write_text('first')
        self.built('B1')
        self.reviewed('first-final', ['B1'], findings=['f'], task_findings={'B1': ['f']}, final=True)
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        (self.repo / 'B1').write_text('repaired')
        token = self.engine.dispatch('main', self.lease, 'R1', 'r1')
        self.engine.report('r1', token, report or te.done('Repaired'))

    def fix_review(self, findings=()):
        self.task('FX', role='code-reviewer', mode='final', files=[], review_of=['R1'])
        token = self.engine.dispatch('main', self.lease, 'FX', 'orchestra-FX')
        path = self.root / 'fx.json'
        self.review(path, reviewer='orchestra-FX', tasks=['R1', 'B1'], findings=list(findings), repair_check=True,
                    task_findings={'R1': list(findings), 'B1': []} if findings else None)
        return self.engine.review_with_token('main', self.lease, token, path)

    def test_a_clean_fix_re_review_accepts_the_repair_and_its_ancestor(self):
        self.repaired()
        result = self.fix_review()
        self.assertTrue(result['accepted'], result['refusal'])
        self.assertEqual(['R1', 'B1'], result['chain_accepted'])
        self.assertEqual(['accepted', 'accepted', 'accepted'], self.states('FX', 'R1', 'B1'))

    def test_a_blocked_fix_re_review_accepts_nothing_of_the_chain(self):
        self.repaired()
        result = self.fix_review(findings=['still wrong'])
        self.assertEqual([], result['chain_accepted'])
        self.assertNotEqual('accepted', self.states('R1')[0])
        self.assertNotEqual('accepted', self.states('B1')[0])

    def test_a_repair_whose_self_review_fails_stays_reported(self):
        bad = te.done('Repaired', checks=[{'command': 'python3 -m unittest', 'exit_code': 1}])
        self.repaired(report=bad)
        result = self.fix_review()
        self.assertEqual([], result['chain_accepted'])
        self.assertEqual('reported', self.states('R1')[0])
        self.assertNotEqual('accepted', self.states('B1')[0])


if __name__ == '__main__':
    unittest.main()
