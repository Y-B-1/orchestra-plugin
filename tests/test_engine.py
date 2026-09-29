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
    def test_inline_and_worker_execution_share_ownership_and_independent_review(self):
        self.task('inline')
        self.task('parallel')
        self.task('collision', files=['inline'])
        token = self.engine.start_inline('main', self.lease, 'inline')
        self.engine.dispatch('main', self.lease, 'parallel', 'worker')
        with self.assertRaises(EngineError):
            self.engine.dispatch('main', self.lease, 'collision', 'other')
        self.engine.report('main', token, 'Inline implementation checked')
        self.assertTrue(self.engine.status()['tasks']['inline']['inline'])
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'inline')
        report = self.root / 'inline-review.json'
        self.review(report, tasks=['inline'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['inline'])
        self.engine.accept('main', self.lease, 'inline')

    def test_inline_cannot_replace_independent_review_or_survive_interruption(self):
        self.task('review', role='code-reviewer', mode='final')
        with self.assertRaises(EngineError):
            self.engine.start_inline('main', self.lease, 'review')
        self.task('inline')
        token = self.engine.start_inline('main', self.lease, 'inline')
        self.engine.interrupt('main', self.lease)
        with self.assertRaises(EngineError):
            self.engine.report('main', token, 'Late inline result')

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

class IntegrationRepairTests(EngineFixture):
    def test_canonical_modes(self):
        for role, mode in [('founder-mind', 'audit'), ('red-teamer', 'scope'), ('gatekeeper', 'checks'), ('janitor', 'hygiene'), ('releaser', 'release')]:
            self.task(role, role=role, mode=mode)
            self.engine.dispatch('main', self.lease, role, role + '-worker')
        with self.assertRaises(EngineError):
            self.task('old-mode', role='gatekeeper', mode='default')

    def test_gate_guard_and_timeout(self):
        for argv in [['git', 'reset', '--hard'], ['git', 'push', 'origin', 'main'], ['bash', '-c', 'git stash']]:
            with self.assertRaises(EngineError):
                self.engine.run_gate('main', self.lease, 'unsafe', argv)
        engine = Engine(self.root / 'bounded', self.repo, {'gate_timeout_seconds': 0.05})
        lease = engine.open_session('main')
        receipt = engine.run_gate('main', lease, 'hang', [sys.executable, '-c', 'import time; time.sleep(10)'])
        self.assertEqual(124, receipt['exit_code'])
        self.assertFalse(receipt['passed'])

    def test_bad_state_is_engine_error(self):
        for value in [[], {}, {'repo': str(self.repo)}, {'version': 1, 'repo': str(self.repo), 'policy': self.engine.policy_hash, 'tasks': []}]:
            self.engine.state_path.write_text(json.dumps(value))
            with self.assertRaises(EngineError):
                self.engine.status()
        self.engine.state_path.write_text('{')
        with self.assertRaises(EngineError):
            self.engine.status()

    def test_final_review_requires_explicit_task_coverage(self):
        self.task(role='investigator', mode='code')
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.engine.report('worker', token, 'checked')
        self.engine.accept('main', self.lease, 'a')
        report = self.root / 'final.json'
        self.review(report, final=True)
        with self.assertRaises(EngineError):
            self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], final=True)

    def test_method_missing_and_changed_contract_invalidates_run(self):
        from unittest.mock import patch
        import shutil
        package = self.root / 'package'
        source = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra'
        shutil.copytree(source, package)
        with patch('orchestra_core.engine.PACKAGE_ROOT', package):
            engine = Engine(self.root / 'contracts', self.repo)
            lease = engine.open_session('main')
            task = dict(id='a', role='builder', mode='implementation', inputs=['https://example.com'], acceptance=['done'], files=['a'], resources=[], dependencies=[])
            engine.add_task('main', lease, task)
            method = package / 'skills/orchestra/references/building.md'
            method.write_text(method.read_text() + '\nNew binding rule.\n')
            with self.assertRaises(EngineError):
                engine.dispatch('main', lease, 'a', 'worker')
            with self.assertRaises(EngineError):
                Engine(self.root / 'contracts', self.repo).status()
            method.unlink()
            with self.assertRaises(EngineError):
                Engine(self.root / 'new-contracts', self.repo)

    def test_invalid_timeout_and_optional_brief(self):
        for timeout in [0, -1, True, '300', float('inf')]:
            with self.assertRaises(EngineError):
                Engine(self.root / 'invalid', self.repo, {'gate_timeout_seconds': timeout})
        for values in [dict(objective=' '), dict(brief='missing'), dict(inputs=[' '])]:
            with self.assertRaises(EngineError):
                self.task(**values)
        brief = self.root / 'brief.md'
        brief.write_text('Objective and bounded acceptance criteria.')
        self.task(brief=str(brief))
        brief.unlink()
        with self.assertRaises(EngineError):
            self.engine.dispatch('main', self.lease, 'a', 'worker')

    def test_scanner_availability_and_required_release_evidence(self):
        receipt = self.engine.run_secret_scan('main', self.lease)
        self.assertEqual(126, receipt['exit_code'])
        self.assertFalse(receipt['passed'])
        command = [sys.executable, '-c', 'print("scanned")']
        policy = dict(required_checks=[dict(name='unit', argv=command)],
                      secret_scan=dict(required=True, argv=command),
                      release=dict(enabled=True, authorization='user', remote='origin', target='main', argv=['git', 'push', 'origin', 'HEAD:main']))
        engine = Engine(self.root / 'scanner', self.repo, policy)
        lease = engine.open_session('main')
        report = self.root / 'final.json'
        from orchestra_core.engine import CATEGORIES
        self.review(report, categories=CATEGORIES, final=True, engine=engine)
        engine.record_review('main', lease, 'reviewer', report, CATEGORIES, final=True)
        engine.run_gate('main', lease, 'unit', command)
        with self.assertRaisesRegex(EngineError, 'secret-scan'):
            engine.release_permit('main', lease, 'origin', 'main')
        engine.run_secret_scan('main', lease)
        engine.release_permit('main', lease, 'origin', 'main')
        (self.repo / 'new').write_text('uncommitted')
        with self.assertRaisesRegex(EngineError, 'clean working tree'):
            engine.release_permit('main', lease, 'origin', 'main')
        policy['secret_scan']['argv'] = []
        engine = Engine(self.root / 'missing-scanner', self.repo, policy)
        lease = engine.open_session('main')
        with self.assertRaisesRegex(EngineError, 'unavailable'):
            engine.run_secret_scan('main', lease)


class CompletionTests(EngineFixture):
    def test_finish_needs_final_current_review_and_configured_gates(self):
        from orchestra_core.engine import CATEGORIES
        command = [sys.executable, '-c', 'print("checked")']
        self.engine = Engine(self.root / 'completion', self.repo,
                             dict(required_checks=[dict(name='unit', argv=command)],
                                  secret_scan=dict(required=True, argv=command)))
        self.lease = self.engine.open_session('main')
        self.task(role='investigator', mode='code')
        with self.assertRaises(EngineError):
            self.engine.close_session('main', self.lease)
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.engine.report('worker', token, 'checked')
        self.engine.accept('main', self.lease, 'a')
        with self.assertRaisesRegex(EngineError, 'final review'):
            self.engine.close_session('main', self.lease)
        report = self.root / 'final.json'
        self.review(report, categories=CATEGORIES, tasks=['a'], final=True)
        self.engine.record_review('main', self.lease, 'reviewer', report, CATEGORIES, ['a'], final=True)
        with self.assertRaisesRegex(EngineError, 'unit'):
            self.engine.check_completion('main', self.lease)
        self.engine.run_gate('main', self.lease, 'unit', command)
        with self.assertRaisesRegex(EngineError, 'secret-scan'):
            self.engine.close_session('main', self.lease)
        self.engine.run_secret_scan('main', self.lease)
        before = self.engine.state_path.read_bytes()
        self.engine.check_completion('main', self.lease)
        self.assertEqual(before, self.engine.state_path.read_bytes())
        report.write_text('altered')
        with self.assertRaisesRegex(EngineError, 'final review'):
            self.engine.close_session('main', self.lease)
        self.assertTrue(self.engine.status()['session']['active'])
        self.review(report, categories=CATEGORIES, tasks=['a'], final=True)
        self.engine.close_session('main', self.lease)
        state = self.engine.status()
        self.assertFalse(state['session']['active'])
        self.assertEqual('completed', state['session']['outcome'])
        self.assertEqual([], state['permits'])
        self.assertIsNone(state['autonomy'])

    def test_finish_without_configured_checks_still_needs_final_review(self):
        from orchestra_core.engine import CATEGORIES
        self.task(role='investigator', mode='code')
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.engine.report('worker', token, 'checked')
        self.engine.accept('main', self.lease, 'a')
        with self.assertRaises(EngineError):
            self.engine.check_completion('main', self.lease)
        report = self.root / 'final.json'
        self.review(report, categories=CATEGORIES, tasks=['a'], final=True)
        self.engine.record_review('main', self.lease, 'reviewer', report, CATEGORIES, ['a'], final=True)
        self.engine.close_session('main', self.lease)

    def test_empty_run_can_close_and_interrupt_is_distinct(self):
        self.engine.close_session('main', self.lease)
        self.assertEqual('completed', self.engine.status()['session']['outcome'])
        lease = self.engine.open_session('main')
        self.engine.interrupt('main', lease)
        self.assertNotEqual('completed', self.engine.status()['session'].get('outcome'))


class FinalBlockerTests(EngineFixture):
    def record(self, name, tasks, categories=None, findings=None, final=False):
        from orchestra_core.engine import CATEGORIES
        categories = categories or CATEGORIES
        path = self.root / (name + '.json')
        self.review(path, reviewer=name, tasks=tasks, categories=categories, findings=findings, final=final)
        return self.engine.record_review('main', self.lease, name, path, categories,
                                         tasks, final=final, findings=findings)

    def release_setup(self, argv=None):
        command = [sys.executable, '-c', 'print("checked")']
        self.engine = Engine(self.root / 'release', self.repo, dict(
            max_workers=1, required_checks=[dict(name='unit', argv=command)],
            release=dict(enabled=True, authorization='user', remote='authorized', target='main',
                         argv=argv or ['git', 'push', 'authorized', 'HEAD:main'])))
        self.lease = self.engine.open_session('main')
        self.engine.run_gate('main', self.lease, 'unit', command)

    def test_repair_transfers_reservations_and_retains_history(self):
        self.release_setup()
        self.task('B1', files=['a'])
        self.task('D1', files=['d'], dependencies=['B1'], role='investigator', mode='code')
        token = self.engine.dispatch('main', self.lease, 'B1', 'first-builder')
        self.engine.report('first-builder', token, 'Original result')
        self.record('blocked', ['B1'], findings=['Incorrect empty input'])
        self.task('R1', mode='repair', repair_of='B1', files=['a'])
        self.assertEqual(['R1'], self.engine.ready('main', self.lease))
        repair_token = self.engine.dispatch('main', self.lease, 'R1', 'repair-builder')
        with self.assertRaises(EngineError):
            self.engine.report('first-builder', token, 'late original report')
        self.engine.report('repair-builder', repair_token, 'Repaired behavior')
        self.record('clean', ['B1', 'R1'])
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'B1')
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')
        state = self.engine.status()
        self.assertEqual('Original result', state['tasks']['B1']['report'])
        self.assertEqual('first-builder', state['tasks']['B1']['worker'])
        self.assertEqual(['Incorrect empty input'], state['reviews'][0]['findings'])
        self.assertEqual(['D1'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'D1', 'investigator')
        self.engine.report('investigator', token, 'Dependent completed')
        self.engine.accept('main', self.lease, 'D1')
        self.record('final', ['B1', 'R1', 'D1'], final=True)
        self.engine.release_permit('main', self.lease, 'authorized', 'main')

    def test_latest_final_blocked_revokes_old_clean_and_permit(self):
        self.release_setup()
        self.record('clean-final', [], final=True)
        self.engine.release_permit('main', self.lease, 'authorized', 'main')
        self.record('blocked-final', [], categories=['security'], findings=['Credential leak'], final=True)
        with self.assertRaises(EngineError):
            self.engine.check_completion('main', self.lease)
        with self.assertRaises(EngineError):
            self.engine.check_release('authorized', 'main')
        self.record('unrelated-final', [], categories=['tests'], final=True)
        with self.assertRaises(EngineError):
            self.engine.release_permit('main', self.lease, 'authorized', 'main')
        self.record('resolved-final', [], categories=['security'], final=True)
        self.engine.release_permit('main', self.lease, 'authorized', 'main')

    def test_latest_checkpoint_blocked_prevents_accept_and_completion(self):
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.engine.report('worker', token, 'done')
        self.record('clean', ['a'])
        self.record('blocked', ['a'], categories=['security'], findings=['unsafe'])
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'a')
        self.record('resolved', ['a'], categories=['security'])
        self.engine.accept('main', self.lease, 'a')
        self.record('final', ['a'], final=True)
        self.record('later-checkpoint', ['a'], categories=['tests'], findings=['failing'])
        with self.assertRaises(EngineError):
            self.engine.check_completion('main', self.lease)

    def test_state_cannot_be_inside_plugin_or_via_symlink(self):
        from unittest.mock import patch
        package = self.root / 'plugin'
        package.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(package, target_is_directory=True)
        from orchestra_core.engine import _contracts
        contracts = _contracts()
        with patch('orchestra_core.engine.PACKAGE_ROOT', package), patch('orchestra_core.engine._contracts', return_value=contracts):
            for path in [package / 'state', alias / 'nested' / 'state', package]:
                with self.assertRaises(EngineError):
                    Engine(path, self.repo)
        self.assertEqual([], list(package.iterdir()))

    def test_release_rejects_known_git_destination_mismatch(self):
        self.release_setup(['git', 'push', 'authorized', 'HEAD:other'])
        self.record('final', [], final=True)
        with self.assertRaises(EngineError):
            self.engine.release_permit('main', self.lease, 'authorized', 'main')

    def test_review_card_uses_reported_work_without_consuming_writer_capacity(self):
        self.release_setup()
        self.task('B1', files=['a'])
        self.task('V1', role='code-reviewer', mode='checkpoint', files=['a'], review_of=['B1'])
        self.assertEqual(['B1'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'B1', 'builder')
        self.engine.report('builder', token, 'Built')
        self.assertEqual(['V1'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'V1', 'review-worker')
        self.engine.report('review-worker', token, 'Reviewed builder output')
        self.record('review-worker', ['B1'])
        self.engine.accept('main', self.lease, 'V1')
        self.engine.accept('main', self.lease, 'B1')
        self.record('review-worker', ['B1', 'V1'], final=True)
        self.engine.check_completion('main', self.lease)

    def test_second_repair_suspends_entire_same_file_chain(self):
        self.release_setup()
        self.task('B1', files=['a'])
        token = self.engine.dispatch('main', self.lease, 'B1', 'worker1')
        self.engine.report('worker1', token, 'First implementation')
        self.record('blocked1', ['B1'], findings=['bug1'])
        self.task('R1', mode='repair', repair_of='B1', files=['a'])
        token = self.engine.dispatch('main', self.lease, 'R1', 'worker2')
        self.engine.report('worker2', token, 'First repair')
        self.record('blocked2', ['B1', 'R1'], findings=['bug2'])
        self.task('R2', mode='repair', repair_of='R1', files=['a'])
        self.assertEqual(['R2'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'R2', 'worker3')
        self.engine.report('worker3', token, 'Second repair')
        self.record('clean2', ['R1', 'R2'])
        for name in ['R2', 'R1']:
            self.engine.accept('main', self.lease, name)
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'B1')
        self.record('fresh-original', ['B1'])
        self.engine.accept('main', self.lease, 'B1')
        self.assertTrue(all(t['state'] == 'accepted' for t in self.engine.status()['tasks'].values()))

    def test_review_targets_reject_wrong_role_and_dependency_cycle(self):
        self.task('B1')
        for values in [dict(review_of=['missing']), dict(review_of=['B1']),
                       dict(role='code-reviewer', mode='checkpoint', review_of=['B1'], dependencies=['B1']),
                       dict(role='code-reviewer', mode='checkpoint', review_of=[{}])]:
            with self.assertRaises(EngineError):
                self.task('invalid', **values)

    def test_builder_cannot_disable_independent_review(self):
        self.task(review_required=False)
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.engine.report('worker', token, 'done')
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'a')

    def test_repair_survives_interrupt_and_preserves_original_reservation(self):
        self.release_setup()
        self.task('B1', files=['a'])
        token = self.engine.dispatch('main', self.lease, 'B1', 'builder')
        self.engine.report('builder', token, 'Original result')
        self.record('blocked', ['B1'], findings=['bug'])
        self.task('R1', mode='repair', repair_of='B1', files=['a'])
        self.task('outsider', files=['a'])
        self.assertEqual(['R1'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'R1', 'repairer')
        self.engine.interrupt('main', self.lease)
        self.lease = self.engine.open_session('main')
        self.assertEqual(['R1'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'R1', 'repairer2')
        self.engine.report('repairer2', token, 'Repair result')
        self.engine.interrupt('main', self.lease)
        self.lease = self.engine.open_session('main')
        self.record('clean', ['B1', 'R1'])
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')
        self.assertEqual(['outsider'], self.engine.ready('main', self.lease))

    def test_releaser_card_runs_after_pre_release_review_then_closes(self):
        self.release_setup()
        self.task('B1', files=['a'])
        self.task('L1', role='releaser', mode='release', files=[], dependencies=['B1'])
        token = self.engine.dispatch('main', self.lease, 'B1', 'builder')
        self.engine.report('builder', token, 'Built')
        self.record('checkpoint', ['B1'])
        self.engine.accept('main', self.lease, 'B1')
        self.record('final', ['B1'], final=True)
        with self.assertRaises(EngineError):
            self.engine.release_permit('main', self.lease, 'authorized', 'main')
        with self.assertRaises(EngineError):
            self.task('L2', role='releaser', mode='release', files=[])
        token = self.engine.dispatch('main', self.lease, 'L1', 'release-worker')
        permit = self.engine.release_permit('main', self.lease, 'authorized', 'main')
        self.assertEqual(permit, self.engine.check_release('authorized', 'main'))
        with self.assertRaises(EngineError):
            self.engine.check_completion('main', self.lease)
        self.engine.report('release-worker', token, 'Release command completed; observed remote evidence attached')
        self.engine.accept('main', self.lease, 'L1')
        self.engine.close_session('main', self.lease)

    def test_release_exemption_never_skips_queued_builder(self):
        self.release_setup()
        self.task('B1', files=['a'])
        self.task('L1', role='releaser', mode='release', files=[])
        with self.assertRaises(EngineError):
            self.record('too-early', ['B1'], final=True)
        with self.assertRaises(EngineError):
            self.engine.release_permit('main', self.lease, 'authorized', 'main')

    def test_ownership_rejects_globs(self):
        for path in ['src/**', 'file?.py', 'src/[ab].py']:
            with self.assertRaises(EngineError):
                self.task(files=[path])

    def test_git_release_rejects_dry_run_multiple_and_unknown_destinations(self):
        for argv in [
            ['git', 'push', '--dry-run', 'authorized', 'HEAD:main'],
            ['git', 'push', 'authorized', 'HEAD:main', 'HEAD:other'],
            ['git', '-C', str(self.repo), 'push', 'authorized', 'HEAD:main'],
            ['git', 'push', 'other-remote', 'HEAD:main'],
        ]:
            with self.subTest(argv=argv):
                self.release_setup(argv)
                self.record('final-' + str(len(argv)), [], final=True)
                with self.assertRaises(EngineError):
                    self.engine.release_permit('main', self.lease, 'authorized', 'main')
                self.engine.interrupt('main', self.lease)
                # Each recipe has a different policy and needs separate durable state.
                self.engine.state_path.unlink()

    def test_git_release_source_must_be_reviewed_head(self):
        self.git('branch', 'unchecked')
        (self.repo / 'a').write_text('reviewed current commit')
        self.git('add', 'a')
        self.git('commit', '-qm', 'reviewed commit')
        self.release_setup(['git', 'push', 'authorized', 'unchecked:main'])
        self.record('final', [], final=True)
        with self.assertRaises(EngineError):
            self.engine.release_permit('main', self.lease, 'authorized', 'main')

    def test_git_release_rechecks_source_after_permit(self):
        old = self.git('rev-parse', 'HEAD')
        (self.repo / 'a').write_text('reviewed current commit')
        self.git('add', 'a')
        self.git('commit', '-qm', 'reviewed commit')
        self.git('branch', 'candidate')
        self.release_setup(['git', 'push', 'authorized', 'candidate:main'])
        self.record('final', [], final=True)
        permit = self.engine.release_permit('main', self.lease, 'authorized', 'main')
        self.assertEqual(permit, self.engine.check_release('authorized', 'main'))
        self.git('update-ref', 'refs/heads/candidate', old)
        with self.assertRaises(EngineError):
            self.engine.check_release('authorized', 'main')

    def test_altered_latest_final_review_cannot_restore_older_approval(self):
        self.release_setup()
        self.record('old-clean', [], final=True)
        self.engine.release_permit('main', self.lease, 'authorized', 'main')
        for field in ['source', 'path']:
            for findings in [['new blocker'], []]:
                with self.subTest(field=field, findings=findings):
                    latest = self.record('latest-' + field, [], categories=['security'],
                                         findings=findings, final=True)
                    pathlib.Path(latest[field]).write_text('altered evidence')
                    for check in [lambda: self.engine.check_completion('main', self.lease),
                                  lambda: self.engine.check_release('authorized', 'main'),
                                  lambda: self.engine.release_permit('main', self.lease, 'authorized', 'main')]:
                        with self.assertRaises(EngineError):
                            check()
                    self.record('replacement-' + field, [], categories=['security'], final=True)
                    self.engine.check_release('authorized', 'main')

    def test_altered_latest_checkpoint_cannot_restore_older_approval(self):
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.engine.report('worker', token, 'done')
        self.record('old-clean', ['a'])
        latest = self.record('latest-blocked', ['a'], categories=['security'], findings=['unsafe'])
        pathlib.Path(latest['source']).unlink()
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'a')
        self.record('replacement', ['a'], categories=['security'])
        self.engine.accept('main', self.lease, 'a')

    def test_known_git_release_rejects_wrappers_and_context_redirection(self):
        other = self.root / 'other-repo'
        subprocess.check_call(['git', 'clone', '-q', str(self.repo), str(other)])
        push = ['git', 'push', 'authorized', 'HEAD:main']
        recipes = [
            ['env', '-C', str(other), *push],
            ['env', '--chdir', str(other), *push],
            ['env', 'GIT_DIR=' + str(other / '.git'), *push],
            ['env', 'GIT_WORK_TREE=' + str(other), *push],
            ['GIT_DIR=' + str(other / '.git'), *push],
            ['env', *push],
            ['sh', '-c', 'git push authorized HEAD:main'],
            ['git', '-c', 'core.worktree=' + str(other), *push[1:]],
            ['git', 'push', '--repo=' + str(other), 'authorized', 'HEAD:main'],
            ['git', 'push', '--repo', str(other), 'authorized', 'HEAD:main'],
        ]
        for recipe in recipes:
            with self.subTest(recipe=recipe):
                (self.root / 'release' / 'state.json').unlink(missing_ok=True)
                self.release_setup(recipe)
                self.record('final', [], final=True)
                with self.assertRaises(EngineError):
                    self.engine.release_permit('main', self.lease, 'authorized', 'main')
                self.engine.interrupt('main', self.lease)
                self.engine.state_path.unlink()

    def test_known_git_release_accepts_only_engine_git_executable(self):
        import shutil
        git = str(pathlib.Path(shutil.which('git')).resolve())
        remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True, capture_output=True)
        self.git('remote', 'add', 'authorized', str(remote))
        alternate = self.root / 'alternate' / 'git'
        alternate.parent.mkdir()
        alternate.write_text('#!/bin/sh\nexit 0\n')
        alternate.chmod(0o755)
        for executable in ['git', git, str(alternate)]:
            with self.subTest(executable=executable):
                self.release_setup([executable, 'push', 'authorized', 'HEAD:main'])
                self.record('final', [], final=True)
                if executable == str(alternate):
                    with self.assertRaises(EngineError):
                        self.engine.release_permit('main', self.lease, 'authorized', 'main')
                else:
                    permit = self.engine.release_permit('main', self.lease, 'authorized', 'main')
                    self.assertEqual(permit, self.engine.check_release('authorized', 'main'))
                    subprocess.run(self.engine.policy['release']['argv'], cwd=self.repo, check=True, capture_output=True)
                    pushed = subprocess.check_output(['git', '--git-dir', str(remote), 'rev-parse', 'refs/heads/main'], text=True).strip()
                    self.assertEqual(self.git('rev-parse', 'HEAD'), pushed)
                self.engine.interrupt('main', self.lease)
                self.engine.state_path.unlink()

    def test_public_lease_validation(self):
        self.engine.validate_lease('main', self.lease)
        for actor, lease in [('worker', self.lease), ('main', 'stale')]:
            with self.assertRaises(EngineError):
                self.engine.validate_lease(actor, lease)
        self.engine.interrupt('main', self.lease)
        with self.assertRaises(EngineError):
            self.engine.validate_lease('main', self.lease)


if __name__ == '__main__':
    unittest.main()
