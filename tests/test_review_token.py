import json
import sys
import unittest

from test_engine import ALL_CATEGORIES, EngineFixture, run_cli, done
from orchestra_core.engine import EngineError


class TokenFixture(EngineFixture):
    def setUp(self):
        super().setUp()
        (self.repo / 'B1').write_text('built')
        self.git('add', 'B1')
        self.git('commit', '-qm', 'B1')
        self.task('B1')
        self.engine.report('w-B1', self.engine.dispatch('main', self.lease, 'B1', 'w-B1'), done('Built B1.'))
        self.head = self.git('rev-parse', 'HEAD')

    def lens(self, name, review_of=('B1',), run=True):
        self.task(name, role='code-reviewer', mode='final', files=[], review_of=list(review_of))
        return self.engine.dispatch('main', self.lease, name, 'orchestra-' + name) if run else None

    def file(self, name, reviewer, tasks, **kw):
        path = self.root / name
        self.review(path, reviewer=reviewer, tasks=tasks, final=True, categories=ALL_CATEGORIES, **kw)
        body = json.loads(path.read_text())
        body['artifact'] = self.head + ' clean'
        path.write_text(json.dumps(body))
        return path


class SiblingLensTests(TokenFixture):
    def test_receipt_listing_only_its_own_side_is_recorded_with_the_sibling_lens_cards(self):
        t1, t2 = self.lens('l1'), self.lens('l2')
        self.engine.report('orchestra-l2', t2, 'Lens two.')
        path = self.file('f.json', 'orchestra-l1', ['B1', 'l1'])
        result = self.engine.review_with_token('main', self.lease, t1, path)
        self.assertEqual(['B1', 'l1', 'l2'], sorted(result['receipt']['tasks']))
        self.assertEqual(1, len(self.engine.status()['reviews']))

    def test_a_lens_card_that_reviews_other_cards_is_not_added(self):
        self.task('B2')
        t2 = self.engine.dispatch('main', self.lease, 'B2', 'w-B2')
        self.engine.report('w-B2', t2, done('Built B2.'))
        t1 = self.lens('l1')
        self.lens('other', review_of=['B2'], run=False)
        path = self.file('f.json', 'orchestra-l1', ['B1', 'B2', 'l1'])
        with self.assertRaisesRegex(EngineError, 'missing: other'):
            self.engine.review_with_token('main', self.lease, t1, path)
        self.assertEqual([], self.engine.status()['reviews'])


class NonFinalTokenTests(TokenFixture):
    def critic(self):
        self.task('C1', role='critic', mode='judge', files=[])
        return self.engine.dispatch('main', self.lease, 'C1', 'orchestra-C1')

    def test_critic_receipt_is_reported_recorded_and_accepted(self):
        token = self.critic()
        path = self.root / 'c.json'
        self.review(path, reviewer='orchestra-C1', tasks=['B1'])
        body = json.loads(path.read_text())
        body['artifact'] = self.head + ' clean'
        path.write_text(json.dumps(body))
        result = self.engine.review_with_token('main', self.lease, token, path)
        self.assertEqual((True, None, 'C1'), (result['accepted'], result['refusal'], result['card']))
        self.assertEqual('accepted', self.engine.status()['tasks']['C1']['state'])
        self.assertFalse(self.engine.status()['reviews'][0]['final'])

    def test_a_non_final_receipt_from_a_final_review_card_is_still_refused(self):
        token = self.lens('l1')
        path = self.root / 'n.json'
        self.review(path, reviewer='orchestra-l1', tasks=['B1'])
        with self.assertRaisesRegex(EngineError, 'final receipts only'):
            self.engine.review_with_token('main', self.lease, token, path)
        self.assertEqual(('running', []), (self.engine.status()['tasks']['l1']['state'], self.engine.status()['reviews']))


class DeferOutOfScopeTests(TokenFixture):
    def setUp(self):
        super().setUp()
        self.token = self.lens('l1')
        self.path = self.file('f.json', 'orchestra-l1', ['B1', 'l1'], )
        body = json.loads(self.path.read_text())
        body['out_of_scope'] = ['first item', 'second item']
        self.path.write_text(json.dumps(body))

    def test_flag_records_each_item_as_brief_with_the_reason(self):
        code, out, err = run_cli(self, '--lease', self.lease, 'review', str(self.path), '--token', self.token,
                                 '--defer-out-of-scope', 'later release')
        self.assertEqual((0, ''), (code, err), out)
        found = self.engine.list_findings()
        self.assertEqual([('first item', 'brief', 'later release'), ('second item', 'brief', 'later release')],
                         [(f['text'], f['disposition'], f['reason']) for f in found])
        self.assertEqual({'out_of_scope'}, {f['source']['kind'] for f in found})
        self.assertEqual('accepted', self.engine.status()['tasks']['l1']['state'])

    def test_without_the_flag_nothing_is_recorded(self):
        code, out, err = run_cli(self, '--lease', self.lease, 'review', str(self.path), '--token', self.token)
        self.assertEqual((0, ''), (code, err), out)
        self.assertEqual([], self.engine.list_findings())

    def test_an_empty_reason_exits_2_and_changes_nothing(self):
        for reason in ('', '   '):
            code, out, err = run_cli(self, '--lease', self.lease, 'review', str(self.path), '--token', self.token,
                                     '--defer-out-of-scope', reason)
            self.assertEqual(2, code, out)
            self.assertEqual(([], 'running'), (self.engine.status()['reviews'], self.engine.status()['tasks']['l1']['state']))
            self.assertEqual([], self.engine.list_findings())

    def test_flag_needs_a_token(self):
        code, out, err = run_cli(self, '--lease', self.lease, 'review', str(self.path), '--defer-out-of-scope', 'x')
        self.assertEqual(2, code, out)
        self.assertEqual([], self.engine.status()['reviews'])


if __name__ == '__main__':
    unittest.main()
