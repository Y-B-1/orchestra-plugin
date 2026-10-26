"""E1F: F70 red-first check matching ignores one trailing parenthetical; F84 queued repairs reserve only their own files."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import EngineError


def own_tests_only(cls):
    """Reuse a fixture class without rerunning the tests it inherits."""
    for name in dir(cls):
        if name.startswith('test_') and name not in vars(cls):
            setattr(cls, name, None)
    return cls


@own_tests_only
class CheckMatchTests(te.SelfReviewTests):
    def accepted(self, name, checks):
        self.engine.report('w-' + name, self.running(name), te.done('Built.', checks=checks))
        self.engine.accept('main', self.lease, name)
        return self.engine.status()['tasks'][name]['state']

    def test_a_trailing_parenthetical_on_either_side_still_matches(self):
        red = {'command': 'pytest t', 'exit_code': 1, 'expect': 'fail'}
        green = {'command': 'pytest t', 'exit_code': 0}
        for label, checks in {
                'note on the red run': [dict(red, command='pytest t (at base)'), green],
                'note on the green run': [red, dict(green, command='pytest t (after the fix)')],
                'note on both': [dict(red, command='pytest t (red)'), dict(green, command='pytest t (green)')]}.items():
            with self.subTest(label):
                self.assertEqual('accepted', self.accepted(label.replace(' ', '-'), checks))

    def test_only_one_trailing_parenthetical_is_stripped_and_a_different_command_never_matches(self):
        red = {'command': 'pytest t', 'exit_code': 1, 'expect': 'fail'}
        green = {'command': 'pytest t', 'exit_code': 0}
        for label, checks in {
                'two notes': [dict(red, command='pytest t (a) (b)'), green],
                'middle parenthetical': [dict(red, command='pytest (x) t'), green],
                'other command with a note': [red, {'command': 'ruff check (t)', 'exit_code': 0}]}.items():
            name = label.replace(' ', '-')
            self.engine.report('w-' + name, self.running(name), te.done('Built.', checks=checks))
            with self.subTest(label), self.assertRaisesRegex(EngineError, 'Self-review has a failing check'):
                self.engine.accept('main', self.lease, name)


@own_tests_only
class RepairReservationTests(te.FinalBlockerTests):
    def reported_pair(self, b1=('a', 'shared'), b2=('b',)):
        self.release_setup()
        self.task('B1', files=list(b1))
        self.task('B2', files=list(b2))
        for card in ('B1', 'B2'):
            token = self.engine.dispatch('main', self.lease, card, 'builder-' + card, serial='test')
            self.engine.report('builder-' + card, token, te.done('Result ' + card))
        self.record('blocked', ['B1', 'B2'], findings=['Wrong output'])

    def test_queued_repairs_with_disjoint_own_files_are_ready_together(self):
        self.reported_pair()
        self.task('RA', mode='repair', repair_of='B1', files=['a'])
        self.task('RB', mode='repair', repair_of='B2', files=['b', 'shared'])  # B1's chain shares 'shared'; RA's own files do not
        self.assertEqual(['RA', 'RB'], self.engine.ready('main', self.lease))

    def test_queued_repairs_with_overlapping_own_files_still_start_one_at_a_time(self):
        self.reported_pair(b1=('a',))
        self.task('RA', mode='repair', repair_of='B1', files=['a', 'x'])
        self.task('RB', mode='repair', repair_of='B2', files=['b', 'x'])
        self.assertEqual(['RA'], self.engine.ready('main', self.lease))

    def test_review_scope_stays_chain_wide(self):
        self.reported_pair()
        self.task('RA', mode='repair', repair_of='B1', files=['a'])
        self.assertEqual(['a', 'shared'], self.engine.scope_for(['RA']))


if __name__ == '__main__':
    unittest.main()
