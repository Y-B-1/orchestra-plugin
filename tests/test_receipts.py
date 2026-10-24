import unittest

import test_engine as te
from orchestra_core.engine import EngineError


class ReceiptTests(te.HoldFixture):
    """Review receipts: less hand normalization, and every refusal names the key and both values."""

    def test_non_final_out_of_scope_is_folded_into_notes(self):
        self.built('B1')
        receipt = self.reviewed('r', ['B1'], mutate=lambda body: body.update(out_of_scope=['Dead code in util']))
        self.assertEqual([], receipt['out_of_scope'])
        self.assertTrue(any('Dead code in util' in note for note in receipt['notes']), receipt['notes'])
        with self.assertRaisesRegex(EngineError, 'Invalid out-of-scope findings'):
            self.reviewed('bad', ['B1'], mutate=lambda body: body.update(out_of_scope=['ok', '']))

    def test_final_out_of_scope_stays_in_its_own_field(self):
        self.built('B1')
        receipt = self.reviewed('f', ['B1'], final=True, mutate=lambda body: body.update(out_of_scope=['Stale doc']))
        self.assertEqual(['Stale doc'], receipt['out_of_scope'])

    def test_a_single_covered_card_derives_task_findings(self):
        self.built('B1')
        receipt = self.reviewed('r', ['B1'], findings=['f'])
        self.assertEqual({'B1': ['f']}, receipt['task_findings'])

    def test_derivation_needs_exactly_one_card_and_a_finding(self):
        self.built('B1')
        self.built('B2')
        self.assertNotIn('task_findings', self.reviewed('two', ['B1', 'B2'], findings=['f']))
        self.assertNotIn('task_findings', self.reviewed('clean', ['B1']))

    def test_an_empty_task_findings_entry_is_accepted(self):
        self.built('B1')
        self.assertEqual({'B1': []}, self.reviewed('r', ['B1'], task_findings={'B1': []})['task_findings'])

    def test_empty_cleared_list_or_object_means_none_when_nothing_is_held(self):
        self.built('B1')
        for name, empty in (('list', []), ('object', {})):
            receipt = self.reviewed('f-' + name, ['B1'], final=True, mutate=lambda body, v=empty: body.update(cleared=v))
            self.assertEqual({}, receipt['cleared'], name)

    def test_empty_cleared_with_a_held_tip_is_still_refused(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        for name, empty in (('list', []), ('object', {})):
            with self.assertRaisesRegex(EngineError, 'Final receipt must address held tip R1', msg=name):
                self.reviewed('f-' + name, ['B1', 'R1'], final=True, mutate=lambda body, v=empty: body.update(cleared=v))

    def test_cleared_that_is_not_a_held_tip_names_the_keys_and_the_held_tips(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        with self.assertRaises(EngineError) as ctx:
            self.reviewed('f', ['B1', 'R1'], final=True, cleared={'R1': 'ok', 'B1': 'ancestor'})
        message = str(ctx.exception)
        self.assertIn('Invalid cleared entries', message)
        self.assertIn('B1', message.split('held tips')[0])
        self.assertIn('held tips: R1', message)

    def mismatch(self, mutate):
        with self.assertRaises(EngineError) as ctx:
            self.reviewed('m', ['B1'], mutate=mutate)
        message = str(ctx.exception)
        self.assertIn('does not match', message)
        return message

    def test_mismatch_names_each_key_with_both_values(self):
        self.built('B1')
        cases = {
            'reviewer': (lambda b: b.update(reviewer='someone-else'), "'reviewer'", "'someone-else'"),
            'categories': (lambda b: b.update(categories=['security']), "['correctness']", "['security']"),
            'tasks': (lambda b: b.update(tasks=['B2']), "['B1']", "['B2']"),
            'findings': (lambda b: b.update(findings=['stray']), '[]', "['stray']"),
            'verdict': (lambda b: b.update(verdict='BLOCKED'), "'CLEAN'", "'BLOCKED'"),
            'final': (lambda b: b.update(final=True), 'False', 'True'),
        }
        for key, (mutate, call, file) in cases.items():
            message = self.mismatch(mutate)
            with self.subTest(key):
                self.assertIn(key, message)
                self.assertIn('call ' + call, message)
                self.assertIn('file ' + file, message)

    def test_artifact_mismatch_names_only_the_differing_fields(self):
        self.built('B1')

        def mutate(body):
            body['artifact']['head'] = '0' * 40
            body['artifact']['status'] = 'changed'
        message = self.mismatch(mutate)
        self.assertIn('artifact', message)
        self.assertIn('head', message)
        self.assertIn('status', message)
        self.assertIn('0' * 40, message)
        for same in ('tree', 'fingerprint', 'index', 'policy', 'repo'):
            self.assertNotIn(same + ':', message)

    def test_artifact_that_is_not_an_object_is_named_with_its_value(self):
        self.built('B1')
        message = self.mismatch(lambda b: b.update(artifact='nonsense'))
        self.assertIn('artifact', message)
        self.assertIn("'nonsense'", message)


if __name__ == '__main__':
    unittest.main()
