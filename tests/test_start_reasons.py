"""A refused start names the blocking card and the exact cause; `waves` never pairs two cards that cannot start together."""
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import Engine, EngineError

PREFIX = '^Task is not ready or capacity is exhausted: '


class StartReasonTests(te.EngineFixture):
    def refusal(self, task_id, engine=None):
        engine = engine or self.engine
        with self.assertRaises(EngineError) as caught:
            engine.dispatch('main', self.lease, task_id, 'w-' + task_id)
        return str(caught.exception)

    def run_card(self, name, **kw):
        self.task(name, **kw)
        return self.engine.dispatch('main', self.lease, name, 'w-' + name, serial='fixture: one card at a time')

    def test_capacity_is_named_as_capacity(self):
        self.engine = Engine(self.root / 'capacity', self.repo, dict(schema_version=1, max_workers=1))
        self.lease = self.engine.open_session('main')
        self.run_card('a')
        self.task('c', files=['c'])
        self.assertRegex(self.refusal('c'), PREFIX + r'capacity: 1 of 1 workers running$')

    def test_a_shared_resource_names_the_resource_and_the_holder(self):
        self.run_card('a', resources=['db'])
        self.task('c', files=['c'], resources=['db'])
        self.assertRegex(self.refusal('c'), PREFIX + r'resource db held by a \(running\)$')

    def test_overlapping_files_name_the_path_and_the_holder(self):
        self.run_card('a', files=['src'])
        self.task('c', files=['src/inner'])
        self.assertRegex(self.refusal('c'), PREFIX + r'files overlap: src with a \(running\)$')

    def test_an_open_dependency_names_the_card_and_its_state(self):
        self.task('a')
        self.task('b', dependencies=['a'])
        self.assertRegex(self.refusal('b'), PREFIX + r'dependency a not accepted \(queued\)$')

    def test_a_reported_holder_says_it_is_not_yet_accepted(self):
        token = self.run_card('a', files=['src'])
        self.engine.report('w-a', token, te.done('Implemented a.'))
        self.task('c', files=['src'])
        self.assertRegex(self.refusal('c'), PREFIX + r'a is reported and not yet accepted; it holds src$')

    def test_a_repair_chain_reservation_names_the_repair_card(self):
        token = self.run_card('a', files=['orig'])
        self.engine.report('w-a', token, te.done('Implemented a.'))
        self.allow_review()
        report = self.root / 'r.json'
        self.review(report, tasks=['a'], findings=['bug'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'], findings=['bug'])
        self.task('fix', mode='repair', files=['fix'], repair_of='a')
        self.task('c', files=['orig'])
        text = self.refusal('c')
        self.assertIn('files overlap: orig with fix (repairing) through repair chain card a', text)

    def test_several_blockers_are_listed_and_capped_at_five(self):
        self.engine = Engine(self.root / 'many', self.repo, dict(schema_version=1, max_workers=8, max_worktrees=8))
        self.lease = self.engine.open_session('main')
        for n in range(7):
            self.run_card('h%d' % n, files=['h%d' % n], resources=['r%d' % n])
        self.task('c', files=['c'], resources=['r%d' % n for n in range(7)])
        text = self.refusal('c')
        listed = ['resource r%d held by h%d (running)' % (n, n) for n in range(5)]
        self.assertTrue(text.endswith('; '.join(listed) + '; +2'), text)

    def test_the_worktree_cap_names_the_running_builder_cards(self):
        engine = Engine(self.root / 'wt', self.repo, dict(schema_version=1, max_worktrees=2))
        lease = engine.open_session('main')
        for name in ('b1', 'b2', 'b3'):
            engine.add_task('main', lease, dict(id=name, role='builder', mode='implementation', inputs=['spec'],
                                                acceptance=['x'], files=[name], resources=[], dependencies=[]))
        for name in ('b1', 'b2'):
            engine.dispatch('main', lease, name, 'w' + name, serial='fixture: one card at a time')
        with self.assertRaisesRegex(EngineError, r'Worktree cap: 2 builder cards are already running \(b1, b2\)'):
            engine.dispatch('main', lease, 'b3', 'wb3')


if __name__ == '__main__':
    unittest.main()
