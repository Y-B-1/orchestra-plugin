"""LADR2: repairs per chain from the autonomy ledger, and sibling repairs that do not wait on a parent reservation."""
import json
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import EngineError, parse_ledger

TEMPLATE = SCRIPTS.parent / 'config' / 'autonomy-template.md'
LINE = '- Repairs: up to %s per chain'


class SiblingRepairTests(te.HoldFixture):
    """F30: a reported repair holds its parent reservation against non-repair cards, not against a disjoint sibling repair."""

    def setUp(self):
        super().setUp()
        self.allow_review()
        self.built('B1', files=['b1', 'shared'])
        self.built('B2', files=['b2'])
        self.reviewed('final', ['B1', 'B2'], findings=['f', 'g'], task_findings={'B1': ['f'], 'B2': ['g']}, final=True)
        self.task('R1', mode='repair', repair_of='B1', files=['b1'])
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), te.done('Repaired'))

    def test_a_sibling_repair_with_disjoint_own_files_starts_while_the_first_awaits_its_re_review(self):
        self.task('R2', mode='repair', repair_of='B2', files=['b2', 'shared'])  # B1's file, not R1's own
        self.assertIn('R2', self.engine.ready('main', self.lease))
        self.engine.report('r2', self.engine.dispatch('main', self.lease, 'R2', 'r2'), te.done('Repaired'))

    def test_a_sibling_repair_whose_own_files_overlap_the_first_repair_waits(self):
        self.task('R2', mode='repair', repair_of='B2', files=['b2', 'b1'])
        self.assertNotIn('R2', self.engine.ready('main', self.lease))

    def test_a_non_repair_card_still_waits_on_the_parent_reservation(self):
        self.task('N1', files=['shared'])
        self.assertNotIn('N1', self.engine.ready('main', self.lease))


class LedgerLineTests(te.AutonomyFixture):
    def test_the_line_sets_repairs_and_absent_means_one(self):
        self.assertEqual(1, parse_ledger(TEMPLATE.read_text().replace('<one line goal>', 'g').replace(
            '<NAME: argv...>', 'c: true').replace('<ISO 8601 time with a UTC offset, in the future>', te.iso(te.T0 + 3600)),
            te.T0).get('repairs', 1))
        for n in (1, 2, 3):
            with self.subTest(n=n):
                self.arm(extra=LINE % n)
                self.assertEqual(n, self.auto()['repairs'])
                self.engine.disarm_autonomy()
        self.arm()
        self.assertNotIn('repairs', self.auto())

    def test_another_form_or_value_is_refused_and_arms_nothing(self):
        for bad in ('- Repairs: up to 0 per chain', '- Repairs: up to 4 per chain', '- Repairs: 2',
                    '- Repairs: up to 2 per chain.', '- Repairs: up to two per chain', '- Repairs:',
                    LINE % 2 + '\n' + LINE % 3):
            with self.subTest(bad=bad):
                self.ledger(extra=bad)
                with self.assertRaisesRegex(EngineError, 'Repairs'):
                    self.engine.arm_autonomy()
                self.assertIsNone(self.auto())

    def test_the_template_carries_the_line_with_one(self):
        self.assertEqual(1, TEMPLATE.read_text().splitlines().count(LINE % 1))

    def test_a_ledger_edit_after_arm_stops_the_loop(self):
        self.arm(passes='9', extra=LINE % 2)
        self.task('x')
        self.assertIsNotNone(self.engine.hook_stop())
        text = (self.state / 'autonomy.md').read_text()
        (self.state / 'autonomy.md').write_text(text.replace(LINE % 2, LINE % 3))
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(('ledger-tampered', False), (self.auto()['last_stop_reason'], self.auto()['active']))


class RepairRungTests(te.AutonomyFixture, te.HoldFixture):
    """F15: the ladder allows the ledger's number of repair rungs before hold."""

    def chain(self, extra=None):
        self.arm(extra=extra) if extra else self.arm()
        self.allow_review()
        self.built('B1')
        self.reviewed('final', ['B1'], findings=['f'], task_findings={'B1': ['f']}, final=True)
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), te.done('Repaired'))
        self.reviewed('check1', ['R1', 'B1'], findings=['g'], task_findings={'R1': ['g'], 'B1': []}, repair_check=True)

    def test_two_rungs_then_hold(self):
        self.chain(LINE % 2)
        self.task('R2', mode='repair', repair_of='R1', files=['B1'])
        self.engine.report('r2', self.engine.dispatch('main', self.lease, 'R2', 'r2'), te.done('Repaired'))
        self.reviewed('check2', ['R2', 'R1', 'B1'], findings=['h'], task_findings={'R2': ['h'], 'R1': [], 'B1': []},
                      repair_check=True)
        with self.assertRaisesRegex(EngineError, 'Escalation ends at 2 repairs; hold the chain'):
            self.task('R3', mode='repair', repair_of='R2', files=['B1'])
        self.assertEqual(['R2', 'R1', 'B1'], self.engine.hold('main', self.lease, 'R2', 'h')['held'])

    def test_three_rungs_allow_a_third_repair(self):
        self.chain(LINE % 3)
        self.task('R2', mode='repair', repair_of='R1', files=['B1'])
        self.engine.report('r2', self.engine.dispatch('main', self.lease, 'R2', 'r2'), te.done('Repaired'))
        self.reviewed('check2', ['R2', 'R1', 'B1'], findings=['h'], task_findings={'R2': ['h'], 'R1': [], 'B1': []},
                      repair_check=True)
        self.task('R3', mode='repair', repair_of='R2', files=['B1'])
        self.assertIn('R3', self.engine.status()['tasks'])

    def test_an_absent_line_keeps_the_single_rung(self):
        self.chain()
        with self.assertRaisesRegex(EngineError, 'Escalation ends at one repair; hold the chain'):
            self.task('R2', mode='repair', repair_of='R1', files=['B1'])


if __name__ == '__main__':
    unittest.main()
