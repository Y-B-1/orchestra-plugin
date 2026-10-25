"""`criterion`: the coordinator records evidence on one unmet self-review criterion of a reported worker card."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_acceptance as ta
from orchestra_core.engine import EngineError


class CriterionTests(ta.CliFixture):
    def record(self, text='check behavior', evidence='Ran it by hand; output matched.', task='a'):
        return self.engine.record_criterion('main', self.lease, task, text, evidence)

    def test_evidence_meets_the_criterion_writes_the_audit_line_and_accept_passes(self):
        self.reported_with_gap()
        with self.assertRaisesRegex(EngineError, 'unmet'):
            self.engine.accept('main', self.lease, 'a')
        self.record(text='  check behavior ')
        criterion = self.state_of()['self_review']['criteria'][0]
        self.assertTrue(criterion['met'])
        self.assertEqual('Ran it by hand; output matched.', criterion['evidence'])
        self.assertEqual('coordinator', criterion['by'])
        self.assertTrue(criterion['at'])
        self.assertIn('- coordinator evidence on a: "check behavior": Ran it by hand; output matched. (at ', self.progress())
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.state_of()['state'])

    def test_each_refusal_has_its_own_text(self):
        self.reported_with_gap()
        self.reported_with_gap('f', checks=[{'command': 'make test', 'exit_code': 1}], files=['f'])
        self.task('q', files=['q'])
        self.task('i', files=['i'])
        token = self.engine.start_inline('main', self.lease, 'i', serial=ta.SERIAL)
        self.engine.report('main', token, ta.report_text([('check behavior', False)]))
        cases = [
            ('missing card', lambda: self.record(task='nope'), 'Unknown task'),
            ('empty evidence', lambda: self.record(evidence='  '), 'needs nonempty evidence'),
            ('long evidence', lambda: self.record(evidence='x' * 1001), 'at most 1000'),
            ('other text', lambda: self.record(text='something else'), 'No unmet criterion "something else".*check behavior'),
            ('failing check', lambda: self.record(task='f'), 'failing check.*make test'),
            ('not reported', lambda: self.record(task='q'), 'not reported'),
            ('inline', lambda: self.record(task='i'), 'inline card'),
        ]
        for name, call, pattern in cases:
            with self.subTest(name), self.assertRaisesRegex(EngineError, pattern):
                call()
        self.assertFalse(self.state_of()['self_review']['criteria'][0]['met'])
        self.assertFalse(self.state_of('i')['self_review']['criteria'][0]['met'])

    def test_a_met_criterion_is_not_unmet(self):
        token = self.running('a')
        self.engine.report('w-a', token, ta.report_text([('check behavior', True)]))
        with self.assertRaisesRegex(EngineError, 'No unmet criterion'):
            self.record()

    def test_cli_command_needs_evidence_and_takes_the_lease(self):
        self.reported_with_gap()
        code, _, err = self.cli('criterion', 'a', 'check behavior', '--evidence', '')
        self.assertEqual(2, code)
        self.assertIn('nonempty evidence', err)
        code, out, _ = self.cli('criterion', 'a', 'check behavior', '--evidence', 'Seen by hand.')
        self.assertEqual(0, code)
        self.assertEqual('a', out['criterion'])
        code, _, _ = self.cli('accept', 'a')
        self.assertEqual(0, code)


if __name__ == '__main__':
    unittest.main()
