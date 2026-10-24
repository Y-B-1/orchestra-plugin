"""EMIT: `ledger` rows and the `package` directory, written from engine facts; neither edits a repository file."""
import json
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from test_briefs import CliFixture

HEADER = '| Card | Role | Commit | Evidence | Status |'


class LedgerFixture(CliFixture):
    def built(self, name, **kw):
        """A builder card reported with the current HEAD commit and accepted."""
        self.task(name, outcome='Outcome of ' + name, **kw)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name, serial='fixture: one card at a time')
        head = self.head()
        self.engine.report('w-' + name, token, te.done('Built ' + name + '.').replace('ARTIFACT: fixture', 'ARTIFACT: %s clean' % head))
        self.engine.accept('main', self.lease, name)
        return head


class LedgerTests(LedgerFixture):
    def test_rows_come_from_accepted_cards_only(self):
        head = self.built('a')
        self.task('queued')
        lines = self.cli('ledger', lease=False)['ledger'].splitlines()
        self.assertEqual(HEADER, lines[0])
        self.assertEqual('| --- | --- | --- | --- | --- |', lines[1])
        rows = lines[2:]
        self.assertEqual(1, len(rows), rows)
        self.assertTrue(rows[0].startswith('| a | builder implementation | %s |' % head[:7]), rows[0])
        self.assertIn('Outcome of a', rows[0])
        self.assertIn('1 check, exit 0', rows[0])
        self.assertIn('no review', rows[0])
        self.assertTrue(rows[0].endswith('| accepted |'))

    def test_a_covering_review_verdict_is_named_and_cards_can_be_chosen(self):
        self.built('a')
        self.built('b')
        self.allow_review('reviewer')
        path = self.root / 'r.json'
        self.review(path, tasks=['a'])
        self.engine.record_review('main', self.lease, 'reviewer', str(path), ['correctness'], ['a'], False, [])
        rows = self.cli('ledger', '--cards', 'a', lease=False)['ledger'].splitlines()[2:]
        self.assertEqual(1, len(rows))
        self.assertIn('review CLEAN', rows[0])

    def test_pipes_and_newlines_cannot_break_a_row(self):
        self.built('a')
        state = json.loads(self.engine.state_path.read_text())
        state['tasks']['a']['outcome'] = 'one | two\nthree'
        self.engine.state_path.write_text(json.dumps(state))
        row = self.cli('ledger', lease=False)['ledger'].splitlines()[2]
        self.assertIn('one / two three', row)

    def test_an_unknown_or_unaccepted_card_is_refused(self):
        self.task('queued')
        self.assertIn('Unknown task', self.cli('ledger', '--cards', 'nope', expected=2, lease=False)['error'])
        self.assertIn('not accepted', self.cli('ledger', '--cards', 'queued', expected=2, lease=False)['error'])

    def test_ledger_edits_no_repository_file(self):
        self.built('a')
        before = self.git('status', '--porcelain')
        self.cli('ledger', lease=False)
        self.assertEqual(before, self.git('status', '--porcelain'))


class PackageTests(LedgerFixture):
    def test_package_writes_brief_report_self_review_and_diffstat_under_the_state_directory(self):
        (self.repo / 'a').write_text('changed')
        self.git('commit', '-qam', 'built a')
        head = self.built('a')
        before = self.git('status', '--porcelain')
        result = self.cli('package', 'a', lease=False)
        out = self.engine.state_dir / 'packages' / 'a'
        self.assertEqual(str(out), result['package'])
        self.assertEqual(['brief.md', 'diffstat.txt', 'report.md', 'self-review.json'], sorted(p.name for p in out.iterdir()))
        self.assertRegex((out / 'brief.md').read_text(), r'(?m)^Mode: implementation$')
        self.assertIn('Built a.', (out / 'report.md').read_text())
        self.assertEqual('check behavior', json.loads((out / 'self-review.json').read_text())['criteria'][0]['criterion'])
        stat = (out / 'diffstat.txt').read_text()
        self.assertIn(head[:7], stat)
        self.assertIn('a | 2', stat)
        self.assertEqual(before, self.git('status', '--porcelain'))

    def test_a_card_without_a_report_or_an_unknown_card_is_refused(self):
        self.task('queued')
        self.assertIn('no report', self.cli('package', 'queued', expected=2, lease=False)['error'])
        self.assertIn('Unknown task', self.cli('package', 'nope', expected=2, lease=False)['error'])


if __name__ == '__main__':
    unittest.main()
