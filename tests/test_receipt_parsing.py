"""F64 and F58: a review receipt's artifact string and gate receipt entries tolerate the prose a reviewer writes
around the sha and the id; F62 and F51: two refusals name the way on."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import test_engine as te
from orchestra_core.engine import EngineError


class ReceiptTextTests(te.EngineFixture):
    GATE = te.FindingsLedgerTests.GATE

    def setUp(self):
        super().setUp()
        self.task('a')
        self.engine.report('w-a', self.engine.dispatch('main', self.lease, 'a', 'w-a'), te.done('built'))
        self.head = self.git('rev-parse', 'HEAD').strip()

    def record(self, name='r', **extra):
        self.allow_review(name)
        path = self.root / (name + '.json')
        self.review(path, reviewer=name, tasks=['a'])
        body = json.loads(path.read_text())
        body.update(extra)
        path.write_text(json.dumps(body))
        return self.engine.record_review('main', self.lease, name, path, ['correctness'], ['a'])

    def test_an_artifact_string_with_notes_after_clean_records(self):
        receipt = self.record(artifact=self.head + ' clean (reviewed 3 files; no edits)')
        self.assertEqual('a', receipt['tasks'][0])
        self.assertEqual(self.head, receipt['artifact']['head'])

    def test_a_bare_clean_artifact_string_still_records(self):
        self.record(artifact=self.head[:7] + ' clean')

    def test_a_dirty_or_malformed_artifact_string_is_refused(self):
        for text in (self.head + ' dirty', self.head + ' cleanish', self.head + ' clean now', self.head + ' dirty clean', 'clean', self.head):
            with self.assertRaises(EngineError, msg=text):
                self.record(artifact=text)
        self.assertEqual([], self.engine.status()['reviews'])

    def test_a_gate_entry_with_prose_around_the_id_records_the_id(self):
        gate = self.engine.run_gate('main', self.lease, 'unit', self.GATE)
        entry = '%s passed at %s (log /tmp/x.log)' % (gate['id'], self.head)
        receipt = self.record(artifact=self.head + ' clean (notes)', gate_receipts=[entry])
        self.assertEqual([gate['id']], receipt['gate_receipts'])

    def test_a_gate_entry_without_a_32_hex_token_is_refused(self):
        self.engine.run_gate('main', self.lease, 'unit', self.GATE)
        for cited in (['passed at ' + self.head], ['deadbeef passed'], ['f' * 31], [3], 'not-a-list'):
            with self.assertRaises(EngineError, msg=cited):
                self.record(gate_receipts=cited)

    def test_a_long_hex_run_is_not_a_32_hex_token(self):
        gate = self.engine.run_gate('main', self.lease, 'unit', self.GATE)
        with self.assertRaises(EngineError):
            self.record(gate_receipts=[gate['id'] + 'ab'])


class RefusalTextTests(te.EngineFixture):
    def test_review_targets_not_reported_names_the_report_fallback(self):
        self.task('B1')
        self.engine.dispatch('main', self.lease, 'B1', 'w-B1')
        self.task('L1', role='code-reviewer', mode='final', files=[], review_of=['B1'])
        with self.assertRaisesRegex(EngineError, r'review targets not reported: B1; if B1.s worker finished, '
                                                  r'record its report with `report WORKER TOKEN FILE`'):
            self.engine.dispatch('main', self.lease, 'L1', 'w-L1')

    def test_review_covering_incomplete_work_names_the_unfinished_cards(self):
        self.allow_review('r')
        self.task('B1')
        self.engine.dispatch('main', self.lease, 'B1', 'w-B1')
        path = self.root / 'r.json'
        self.review(path, reviewer='r', tasks=['B1'])
        with self.assertRaisesRegex(EngineError, r'Review covers incomplete work: B1 \(running\)'):
            self.engine.record_review('main', self.lease, 'r', path, ['correctness'], ['B1'])


if __name__ == '__main__':
    unittest.main()
