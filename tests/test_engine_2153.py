"""2.15.3 engine: a resumed card's range skips the commits made while it was reported (F112), a repair reserves only
its own files and the files its finding names (F114), and a newline is never the gap before a trailing note (RY)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
import test_engine_2152 as t2
import test_refusal_texts as tr
from orchestra_core.engine import Engine, EngineError


class ResumeGapTests(tr.RefusalFixture):
    def test_a_commit_made_while_the_card_was_reported_is_not_its_own(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        self.engine.report('w-a', token, tr.report_for(self.commit(a='first')))
        sibling = self.running('b', files=['b_file', 'shared'])
        self.engine.report('w-b', sibling, tr.report_for(self.commit(b_file='by b', shared='by b')))
        self.engine.accept('main', self.lease, 'b')
        self.engine.resume_card('main', self.lease, 'a')
        self.engine.own_add('main', self.lease, 'a', 'shared')
        self.engine.report('w-a', token, tr.report_for(self.commit(a='second', shared='by a')))
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.card()['state'])

    def test_the_cards_own_commits_on_both_sides_of_the_gap_still_count(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        self.engine.report('w-a', token, tr.report_for(self.commit(a='first', stray='x')))
        self.engine.resume_card('main', self.lease, 'a')
        self.engine.report('w-a', token, tr.report_for(self.commit(a='second', late='y')))
        self.assertIn('files outside the card: late, stray;', self.refusal(self.engine.accept, 'main', self.lease, 'a'))


@t2.own_tests_only
class RepairReservationTests(te.FinalBlockerTests):
    """F114: two repairs meet only on their own files, whatever their chains hold; any other card still meets the chain."""

    def setUp(self):
        super().setUp()
        self.release_setup()
        self.task('B1', files=['a', 'shared'])
        self.task('B2', files=['b'])
        self.task('B3', files=['c'])
        for card in ('B1', 'B2', 'B3'):
            token = self.engine.dispatch('main', self.lease, card, 'builder-' + card, serial='test')
            self.engine.report('builder-' + card, token, te.done('Result ' + card))
        self.record('blocked', ['B1', 'B2', 'B3'], findings=['Wrong output'])
        self.task('RA', mode='repair', repair_of='B1', files=['a'])
        self.task('RB', mode='repair', repair_of='B2', files=['b', 'shared'])
        self.engine.policy['max_workers'] = 3  # release_setup runs one worker; these tests need two side by side

    def test_a_repair_starts_beside_a_running_repair_whose_chain_shares_a_file(self):
        self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.assertEqual(['RB'], self.engine.ready('main', self.lease))
        self.engine.dispatch('main', self.lease, 'RB', 'repair-b')

    def test_a_non_repair_card_still_waits_for_the_whole_chain(self):
        self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.task('N', files=['shared'])
        self.assertNotIn('N', self.engine.ready('main', self.lease))

    def test_a_chain_file_another_repair_owns_is_outside(self):
        base = self.git('rev-parse', 'HEAD')
        token = self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.engine.record_bases('main', self.lease, ['RA'], base)
        (self.repo / 'shared').write_text('by RA')
        self.git('add', 'shared')
        self.git('commit', '-qm', 'RA edits shared')
        self.engine.report('repair-a', token, tr.report_for(self.git('rev-parse', 'HEAD')))
        self.assertEqual(['shared'], self.engine.status()['tasks']['RA'].get('outside_files'))

    def test_two_repairs_that_own_one_file_still_wait(self):
        self.task('RC', mode='repair', repair_of='B3', files=['a'])
        self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.assertNotIn('RC', self.engine.ready('main', self.lease))


class BareNewlineTests(unittest.TestCase):
    def test_a_newline_before_a_note_keeps_the_text(self):
        self.assertEqual('make a\n(make b)', Engine._bare('make a\n(make b)'))
        self.assertEqual('make full', Engine._bare('make full \t (full gate)'))


if __name__ == '__main__':
    unittest.main()


@t2.own_tests_only
class PrReviewedScopeTests(te.PullRequestTests):
    """N4: a PR counts as reviewed only from a clean review at its head that is final or covers every card it carries."""

    def test_a_narrow_clean_review_does_not_mark_the_pr_reviewed(self):
        self.view()
        self.built('c', files=['c.txt'])
        self.built('d', files=['d.txt'])
        self.reviewed('narrow', ['c'])
        self.assertFalse(self.engine.record_pr('main', self.lease, self.URL, tasks=['c', 'd'])[0]['reviewed'])

    def test_a_clean_review_of_every_carried_card_marks_it_reviewed(self):
        self.view()
        self.built('c', files=['c.txt'])
        self.built('d', files=['d.txt'])
        self.reviewed('both', ['c', 'd'])
        self.assertTrue(self.engine.record_pr('main', self.lease, self.URL, tasks=['c', 'd'])[0]['reviewed'])


class ReadOnlyReportTests(te.EngineFixture):
    """F116: an investigator card that owns no files is accepted on its report after the checkout moves on; its evidence
    names the commit it read. A builder report still goes stale."""

    def test_an_investigator_report_survives_later_edits(self):
        self.task('I', role='investigator', mode='code', files=[])
        token = self.engine.dispatch('main', self.lease, 'I', 'w-I')
        self.engine.report('w-I', token, 'Read the code.\nARTIFACT: fixture')
        (self.repo / 'a').write_text('edited after the report')
        self.engine.accept('main', self.lease, 'I')
        self.assertEqual('accepted', self.engine.status()['tasks']['I']['state'])

    def test_a_builder_report_still_goes_stale(self):
        self.task('B', files=['a'])
        token = self.engine.dispatch('main', self.lease, 'B', 'w-B')
        self.engine.report('w-B', token, te.done('Built.'))
        (self.repo / 'a').write_text('edited after the report')
        with self.assertRaisesRegex(EngineError, 'Reported artifact is stale'):
            self.engine.accept('main', self.lease, 'B')
