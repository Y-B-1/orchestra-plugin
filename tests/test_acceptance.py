"""GATE: a builder report answers every acceptance line, `accept --ruling` rules on an unmet criterion and
`report --accept` closes an inline card in one call."""
import contextlib
import io
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))

import orchestra
import test_engine as te
from orchestra_core.engine import EngineError

SERIAL = 'fixture: one card at a time'


def report_text(criteria, checks=None):
    return te.done('Built.', checks=checks, criteria=[dict(criterion=c, met=met, evidence='seen') for c, met in criteria])


class GateFixture(te.EngineFixture):
    def running(self, name='a', **kw):
        self.task(name, **kw)
        return self.engine.dispatch('main', self.lease, name, 'w-' + name)

    def state_of(self, name='a'):
        return self.engine.status()['tasks'][name]

    def reported_with_gap(self, name='a', checks=None, **kw):
        token = self.running(name, **kw)
        self.engine.report('w-' + name, token, report_text([('check behavior', False)], checks))
        return token

    def progress(self):
        return (self.engine.state_dir / 'progress.md').read_text()


class AcceptanceMatchTests(GateFixture):
    def test_missing_acceptance_line_is_refused_and_listed(self):
        token = self.running('a', acceptance=['first line', 'second line', 'third line'])
        with self.assertRaises(EngineError) as ctx:
            self.engine.report('w-a', token, report_text([('first line', True)]))
        self.assertIn('second line', str(ctx.exception))
        self.assertIn('third line', str(ctx.exception))
        self.assertNotIn('first line', str(ctx.exception))
        self.assertEqual('running', self.state_of()['state'])

    def test_whitespace_is_collapsed_and_extra_criteria_are_allowed(self):
        token = self.running('a', acceptance=['two  words\n here '])
        self.engine.report('w-a', token, report_text([('  two words   here', True), ('an extra', True)]))
        self.assertEqual('reported', self.state_of()['state'])
        self.engine.accept('main', self.lease, 'a')

    def test_other_roles_are_unaffected(self):
        for role, mode in (('investigator', 'code'), ('critic', 'judge')):
            name = 'x-' + role
            self.task(name, role=role, mode=mode, files=[], acceptance=['never listed'])
            token = self.engine.dispatch('main', self.lease, name, 'w-' + role)
            self.engine.report('w-' + role, token, 'Inspected, no self review.')
            self.assertEqual('reported', self.state_of(name)['state'])

    def test_repair_card_is_checked_against_its_own_acceptance(self):
        token = self.running('a')
        self.engine.report('w-a', token, report_text([('check behavior', True)]))
        self.allow_review()
        path = self.root / 'review'
        self.review(path, tasks=['a'], findings=['Fails on empty input'])
        self.engine.record_review('main', self.lease, 'reviewer', path, ['correctness'], ['a'], findings=['Fails on empty input'])
        self.task('r', mode='repair', repair_of='a', files=['r'], acceptance=['fix empty input'])
        repair = self.engine.dispatch('main', self.lease, 'r', 'w-r')
        with self.assertRaisesRegex(EngineError, 'fix empty input'):
            self.engine.report('w-r', repair, report_text([('check behavior', True)]))
        self.engine.report('w-r', repair, report_text([('fix empty input', True)]))
        self.assertEqual('reported', self.state_of('r')['state'])


class RulingTests(GateFixture):
    def test_ruling_accepts_a_card_whose_only_gap_is_an_unmet_criterion(self):
        self.reported_with_gap()
        with self.assertRaisesRegex(EngineError, 'unmet'):
            self.engine.accept('main', self.lease, 'a')
        self.engine.accept('main', self.lease, 'a', ruling='Out of reach this release; owner agrees.')
        card = self.state_of()
        self.assertEqual('accepted', card['state'])
        self.assertEqual('Out of reach this release; owner agrees.', card['ruling']['text'])
        self.assertTrue(card['ruling']['at'])
        self.assertIn('Out of reach this release; owner agrees.', self.progress())

    def test_empty_ruling_is_refused(self):
        self.reported_with_gap()
        for ruling in ('', '   ', 5):
            with self.subTest(ruling), self.assertRaisesRegex(EngineError, 'ruling'):
                self.engine.accept('main', self.lease, 'a', ruling=ruling)
        self.assertEqual('reported', self.state_of()['state'])

    def test_failing_check_is_never_rulable(self):
        self.reported_with_gap(checks=[{'command': 'make test', 'exit_code': 1}])
        with self.assertRaisesRegex(EngineError, 'make test'):
            self.engine.accept('main', self.lease, 'a', ruling='Ignore the failing check.')
        self.assertEqual('reported', self.state_of()['state'])

    def test_unmatched_red_first_check_is_never_rulable(self):
        self.reported_with_gap(checks=[{'command': 'make test', 'exit_code': 1, 'expect': 'fail'}])
        with self.assertRaisesRegex(EngineError, 'no later passing run'):
            self.engine.accept('main', self.lease, 'a', ruling='Ignore the red check.')
        self.assertEqual('reported', self.state_of()['state'])

    def test_current_review_finding_is_not_rulable(self):
        self.reported_with_gap()
        self.allow_review()
        path = self.root / 'review'
        self.review(path, tasks=['a'], findings=['Fails on empty input'])
        self.engine.record_review('main', self.lease, 'reviewer', path, ['correctness'], ['a'], findings=['Fails on empty input'])
        with self.assertRaisesRegex(EngineError, 'review findings'):
            self.engine.accept('main', self.lease, 'a', ruling='Rule past the finding.')
        self.assertEqual('reported', self.state_of()['state'])

    def test_a_ruling_on_a_card_with_no_gap_accepts_it(self):
        token = self.running()
        self.engine.report('w-a', token, report_text([('check behavior', True)]))
        self.engine.accept('main', self.lease, 'a', ruling='Nothing to rule on.')
        self.assertEqual('accepted', self.state_of()['state'])

    def test_inline_card_cannot_be_ruled_on(self):
        self.task('a')
        token = self.engine.start_inline('main', self.lease, 'a', serial=SERIAL)
        self.engine.report('main', token, report_text([('check behavior', False)]))
        with self.assertRaisesRegex(EngineError, 'inline'):
            self.engine.accept('main', self.lease, 'a', ruling='Self ruling.')
        self.assertEqual('reported', self.state_of()['state'])


class CliFixture(GateFixture):
    def cli(self, *args, lease=True):
        raw = ['--repo', str(self.repo), '--state', str(self.engine.state_dir)]
        raw += ['--lease', self.lease] if lease else []
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = orchestra.main(raw + list(args))
        return code, (json.loads(out.getvalue()) if out.getvalue().strip() else None), err.getvalue()

    def file(self, text):
        path = self.root / 'report.txt'
        path.write_text(text)
        return str(path)


class ReportAcceptTests(CliFixture):
    def inline(self, name='a', **kw):
        self.task(name, **kw)
        return self.engine.start_inline('main', self.lease, name, serial=SERIAL)

    def test_inline_report_accept_records_and_accepts_in_one_call(self):
        token = self.inline()
        code, out, _ = self.cli('report', 'main', token, self.file(report_text([('check behavior', True)])), '--accept')
        self.assertEqual(0, code)
        self.assertEqual('accepted', self.state_of()['state'])
        self.assertTrue(out['accepted'])

    def test_lease_after_accept_is_read(self):
        token = self.inline()
        code, out, _ = self.cli('report', 'main', token, self.file(report_text([('check behavior', True)])), '--accept',
                                '--lease', self.lease, lease=False)
        self.assertEqual(0, code)
        self.assertEqual('accepted', self.state_of()['state'])

    def test_refused_accept_keeps_the_report_and_prints_the_refusal(self):
        token = self.inline()
        code, out, _ = self.cli('report', 'main', token, self.file(report_text([('check behavior', False)])), '--accept')
        self.assertEqual(0, code)
        self.assertFalse(out['accepted'])
        self.assertIn('unmet', out['refusal'])
        self.assertEqual('reported', self.state_of()['state'])
        self.assertIn('Built.', self.state_of()['report'])

    def test_accept_without_a_lease_exits_2(self):
        token = self.inline()
        code, _, err = self.cli('report', 'main', token, self.file(report_text([('check behavior', True)])), '--accept', lease=False)
        self.assertEqual(2, code)
        self.assertIn('lease', err)
        self.assertEqual('running', self.state_of()['state'])

    def test_worker_card_refuses_accept_naming_the_rule(self):
        token = self.running()
        code, _, err = self.cli('report', 'w-a', token, self.file(report_text([('check behavior', True)])), '--accept')
        self.assertEqual(2, code)
        self.assertIn('inline', err)
        self.assertEqual('running', self.state_of()['state'])

    def test_plain_report_stays_lease_free(self):
        token = self.running()
        code, out, _ = self.cli('report', 'w-a', token, self.file(report_text([('check behavior', True)])), lease=False)
        self.assertEqual(0, code)
        self.assertEqual('reported', self.state_of()['state'])

    def test_ruling_flag_reaches_accept(self):
        self.reported_with_gap()
        code, out, _ = self.cli('accept', 'a', '--ruling', 'Owner agrees.')
        self.assertEqual(0, code)
        self.assertEqual('accepted', self.state_of()['state'])


if __name__ == '__main__':
    unittest.main()
