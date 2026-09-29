import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
from orchestra_core.engine import Engine, EngineError


class EngineFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='engine with spaces ')
        self.root = pathlib.Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'a').write_text('initial')
        self.git('add', 'a')
        self.git('commit', '-qm', 'initial')
        self.engine = Engine(self.root / 'state', self.repo)
        self.lease = self.engine.open_session('main')

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def task(self, name='a', **kw):
        task = dict(id=name, role='builder', mode='implementation', inputs=['spec'], acceptance=['check behavior'], files=[name], resources=[], dependencies=[])
        task.update(kw)
        self.engine.add_task('main', self.lease, task)

    def review(self, path, reviewer='reviewer', categories=None, tasks=None, findings=None, final=False, engine=None):
        engine = engine or self.engine
        path.write_text(json.dumps(dict(reviewer=reviewer, categories=categories or ['correctness'],
                                       tasks=tasks or [], findings=findings or [], final=final,
                                       verdict='BLOCKED' if findings else 'CLEAN', artifact=engine.artifact(),
                                       summary='Behavior checked against acceptance criteria.')))


class EngineTests(EngineFixture):
    def test_invalid_tasks_and_capacity(self):
        for kw in [dict(role='unknown'), dict(mode='unknown'), dict(acceptance=[]), dict(files=['../escape']), dict(dependencies=['missing'])]:
            with self.assertRaises(EngineError):
                self.task(**kw)
        self.task()
        self.task('b', files=['a/child'])
        self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.assertEqual([], self.engine.ready('main', self.lease))
        with self.assertRaises(EngineError):
            self.engine.dispatch('main', self.lease, 'b', 'other')

    def test_report_needs_coordinator_accept_and_review(self):
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        with self.assertRaises(EngineError):
            self.engine.report('worker', token, '')
        self.engine.report('worker', token, 'implemented')
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'a')
        report = self.root / 'review.txt'
        self.review(report, tasks=['a'])
        with self.assertRaises(EngineError):
            self.engine.record_review('main', self.lease, 'worker', report, ['correctness'], ['a'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'])
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def test_interrupt_rejects_late_report(self):
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.engine.interrupt('main', self.lease)
        with self.assertRaises(EngineError):
            self.engine.report('worker', token, 'done')
        with self.assertRaises(EngineError):
            self.engine.ready('main', self.lease)

    def test_artifact_content_and_policy_binding(self):
        before = self.engine.artifact()
        (self.repo / 'new').write_text('one')
        one = self.engine.artifact()
        (self.repo / 'new').write_text('two')
        self.assertNotEqual(before, one)
        self.assertNotEqual(one, self.engine.artifact())
        with self.assertRaises(EngineError):
            Engine(self.root / 'state', self.repo, {'max_workers': 1}).ready('main', self.lease)

    def test_gate_actual_exit_and_mutation(self):
        good = self.engine.run_gate('main', self.lease, 'good', [sys.executable, '-c', 'print("ok")'])
        self.assertTrue(good['passed'])
        bad = self.engine.run_gate('main', self.lease, 'bad', [sys.executable, '-c', 'raise SystemExit(3)'])
        self.assertEqual(3, bad['exit_code'])
        self.assertFalse(bad['passed'])
        changed = self.engine.run_gate('main', self.lease, 'mutation', [sys.executable, '-c', 'open("a","w").write("changed")'])
        self.assertFalse(changed['passed'])
        with self.assertRaises(EngineError):
            self.engine.run_gate('main', self.lease, 'fake', 'true')

    def test_release_requires_complete_current_evidence(self):
        policy = dict(required_checks=[dict(name='unit', argv=[sys.executable, '-c', 'print("passed")'])], release=dict(enabled=True, authorization='user request', remote='devops', target='main', argv=['git', 'push', 'devops', 'HEAD:main']))
        engine = Engine(self.root / 'release-state', self.repo, policy)
        lease = engine.open_session('main')
        with self.assertRaises(EngineError):
            engine.release_permit('main', lease, 'devops', 'main')
        report = self.root / 'final.txt'
        report.write_text('Independent whole artifact review: clean.')
        categories = ['requirements', 'correctness', 'security', 'tests', 'architecture', 'standards', 'cleanup']
        self.review(report, categories=categories, final=True, engine=engine)
        engine.record_review('main', lease, 'reviewer', report, categories, final=True)
        engine.run_gate('main', lease, 'unit', [sys.executable, '-c', 'print("passed")'])
        with self.assertRaises(EngineError):
            engine.check_release('devops', 'main')
        permit = engine.release_permit('main', lease, 'devops', 'main')
        self.assertEqual('release', permit['action'])
        self.assertEqual(permit, engine.check_release('devops', 'main'))
        with self.assertRaises(EngineError):
            engine.check_release('devops', 'main', argv=['git', 'push', 'devops', 'other'])
        with self.assertRaises(EngineError):
            engine.release_permit('main', lease, 'origin', 'main')
        report.write_text('altered')
        with self.assertRaises(EngineError):
            engine.release_permit('main', lease, 'devops', 'main')

class MoreEngineTests(EngineFixture):
    def test_continuous_ready_and_dependency(self):
        self.task()
        self.task('b')
        self.task('c', dependencies=['a'])
        token = self.engine.dispatch('main', self.lease, 'a', 'builder-a')
        self.assertEqual(['b'], self.engine.ready('main', self.lease))
        self.engine.report('builder-a', token, 'built a')
        report = self.root / 'review'
        self.review(report, tasks=['a'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'])
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual(['b', 'c'], self.engine.ready('main', self.lease))

    def test_stale_review_and_gate_log(self):
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'builder')
        self.engine.report('builder', token, 'done')
        report = self.root / 'review'
        self.review(report, tasks=['a'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'])
        (self.repo / 'a').write_text('new state')
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'a')
        gate = self.engine.run_gate('main', self.lease, 'check', [sys.executable, '-c', 'print("ok")'])
        pathlib.Path(gate['path']).write_text('altered')
        self.assertFalse(self.engine._intact(gate))

    def test_repair_needs_findings(self):
        with self.assertRaises(EngineError):
            self.task(mode='repair')
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'builder')
        self.engine.report('builder', token, 'done')
        report = self.root / 'review'
        self.review(report, tasks=['a'], findings=['Behavior fails for empty input'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'], findings=['Behavior fails for empty input'])
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'a')
        self.task('repair', mode='repair', files=['repair'], repair_of='a')

    def test_review_metadata_and_nonbuilder_accept(self):
        self.task(role='investigator', mode='code')
        token = self.engine.dispatch('main', self.lease, 'a', 'investigator')
        self.engine.report('investigator', token, 'Code symbols inspected; evidence attached.')
        self.engine.accept('main', self.lease, 'a')
        report = self.root / 'review'
        report.write_text('BLOCKED')
        with self.assertRaises(EngineError):
            self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'])
        self.review(report, tasks=['a'])
        body = json.loads(report.read_text())
        body['verdict'] = 'BLOCKED'
        report.write_text(json.dumps(body))
        with self.assertRaises(EngineError):
            self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'])

    def test_explicit_capped_stop(self):
        self.task()
        self.assertIsNone(self.engine.hook_stop())
        ledger = self.root / 'ledger'
        ledger.write_text('Goal: finish a; acceptance: checked review; bounded ownership a.')
        with self.assertRaises(EngineError):
            self.engine.enable_autonomy('main', self.lease, ledger, 21, 2)
        self.engine.enable_autonomy('main', self.lease, ledger, 20, 2)
        self.assertIsInstance(self.engine.hook_stop(), str)
        self.assertIsNone(self.engine.hook_stop())
        self.engine.enable_autonomy('main', self.lease, ledger, 20, 2)
        self.engine.interrupt('main', self.lease)
        self.assertIsNone(self.engine.hook_stop())

    def test_lock_preserves_concurrent_cards(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda n: self.task('task-' + str(n)), range(12)))
        self.assertEqual(12, len(self.engine.status()['tasks']))


if __name__ == '__main__':
    unittest.main()
