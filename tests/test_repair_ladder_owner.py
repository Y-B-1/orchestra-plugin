"""F61: a repair of a held chain carries the owner's words. F63: a CLEAN fix re-review covers its own review cards."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import EngineError

WORDS = 'owner: take the repair of R1'


class OwnerApprovalTests(te.HoldFixture):
    def held_chain(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')

    def test_a_repair_of_a_held_chain_needs_owner_approval(self):
        self.held_chain()
        with self.assertRaisesRegex(EngineError, "A held chain needs the owner's approval: add owner_approval with the owner's words"):
            self.task('R2', mode='repair', repair_of='R1', files=['B1'])
        self.assertNotIn('R2', self.engine.status()['tasks'])
        self.assertEqual(['held', 'held'], self.states('R1', 'B1'))

    def test_owner_approval_is_stored_and_logged(self):
        self.held_chain()
        self.task('R2', mode='repair', repair_of='R1', files=['B1'], owner_approval=WORDS)
        self.assertEqual(WORDS, self.engine.status()['tasks']['R2']['owner_approval'])
        self.assertIn('- owner approved repair R2 of R1: ' + WORDS, self.progress())
        self.assertEqual(['repairing', 'repairing'], self.states('R1', 'B1'))

    def test_owner_approval_must_be_a_short_nonempty_string(self):
        self.held_chain()
        for bad in ('', '   ', 5, ['x'], 'x' * 1001):
            with self.subTest(bad=bad), self.assertRaisesRegex(EngineError, 'owner_approval'):
                self.task('R2', mode='repair', repair_of='R1', files=['B1'], owner_approval=bad)
        self.assertNotIn('R2', self.engine.status()['tasks'])
        self.assertNotIn('owner approved', self.progress())
        self.task('R2', mode='repair', repair_of='R1', files=['B1'], owner_approval='x' * 1000)

    def test_owner_approval_on_a_repair_of_a_card_that_is_not_held_is_refused(self):
        self.built('B2')
        self.reviewed('crit', ['B2'], findings=['f'], task_findings={'B2': ['f']})
        with self.assertRaisesRegex(EngineError, 'owner_approval is only for a repair of a held chain'):
            self.task('R2', mode='repair', repair_of='B2', files=['B2'], owner_approval=WORDS)
        self.assertNotIn('R2', self.engine.status()['tasks'])
        self.task('R2', mode='repair', repair_of='B2', files=['B2'])

    def test_owner_approval_on_a_card_that_is_not_a_repair_is_refused(self):
        with self.assertRaisesRegex(EngineError, 'owner_approval is only for a repair of a held chain'):
            self.task('N1', owner_approval=WORDS)


class AutonomyOwnerApprovalTests(te.AutonomyFixture, te.HoldFixture):
    def test_a_repair_of_a_held_chain_is_refused_while_autonomy_is_armed_even_with_approval(self):
        self.arm()
        self.allow_review()
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        with self.assertRaisesRegex(EngineError, 'waits for the owner'):
            self.task('R2', mode='repair', repair_of='R1', files=['B1'], owner_approval=WORDS)
        self.assertNotIn('R2', self.engine.status()['tasks'])
        self.assertNotIn('owner approved', self.progress())


class FixReviewCardCoverageTests(te.HoldFixture):
    def setUp(self):
        super().setUp()
        self.allow_review()

    def review_card(self, name, of):
        self.task(name, role='code-reviewer', mode='final', files=[], review_of=of)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        self.engine.report('w-' + name, token, 'Reviewed the fix diff.')

    def coverage(self):
        with self.engine._state(False) as state:
            return self.engine._review_verdicts(state, {}, final=True, keep=True)

    def live_order_until_hold(self):
        """Final review F BLOCKED on B1; repair R1; fix re-review X1 BLOCKED; hold."""
        (self.repo / 'B1').write_text('first')
        self.built('B1')
        self.reviewed('F', ['B1'], findings=['f'], task_findings={'B1': ['f']}, final=True)
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        (self.repo / 'B1').write_text('repaired')
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), te.done('Repaired'))
        self.review_card('X1', ['R1'])
        self.reviewed('check1', ['R1', 'B1'], findings=['g'], task_findings={'R1': ['g'], 'B1': []}, repair_check=True)
        self.engine.accept('main', self.lease, 'X1')
        self.engine.hold('main', self.lease, 'R1', 'g')

    def test_finish_succeeds_after_the_owner_approved_repair_is_cleanly_re_reviewed(self):
        self.live_order_until_hold()
        self.task('R2', mode='repair', repair_of='R1', files=['B1'], owner_approval=WORDS)
        (self.repo / 'B1').write_text('repaired again')
        self.engine.report('r2', self.engine.dispatch('main', self.lease, 'R2', 'r2'), te.done('Repaired'))
        self.review_card('X2', ['R2'])
        self.reviewed('check2', ['R2', 'R1', 'B1'], repair_check=True)
        self.engine.accept('main', self.lease, 'X2')
        for name in ('R2', 'R1', 'B1'):
            self.engine.accept('main', self.lease, name)
        self.engine.check_completion('main', self.lease)

    def test_a_final_review_stays_uncovered_while_a_later_fix_re_review_has_findings(self):
        self.live_order_until_hold()
        self.assertEqual({}, self.coverage())


if __name__ == '__main__':
    unittest.main()
