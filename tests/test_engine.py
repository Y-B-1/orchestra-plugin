import hashlib
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'
sys.path.insert(0, str(SCRIPTS))
from pathlib import Path

from orchestra_core.paths import push_url_digest
from orchestra_core import portable
from orchestra_core.engine import AUTONOMY_FIXED, ENGINE_TASK_KEYS, Engine, EngineError, StateBusy, autonomy_preconditions, ensure_remote_heads

ROOT = SCRIPTS.parents[2]
STATE_2_3 = pathlib.Path(__file__).resolve().parent / 'fixtures/state-2.3.json'
STATE_2_4 = pathlib.Path(__file__).resolve().parent / 'fixtures/state-2.4.json'


def load_2_3_state(root, repo, name='state-2.3'):
    """A state.json written by the 2.3 engine (`start`, no policy), bound to `repo`; returns (state dir, lease)."""
    data = json.loads(STATE_2_3.read_text())
    data['repo'] = str(pathlib.Path(repo).resolve())
    state = pathlib.Path(root) / name
    state.mkdir()
    (state / 'state.json').write_text(json.dumps(data))
    return state, data['session']['lease']


def load_2_4_state(root, repo, name='state-2.4'):
    """A state.json written by the 2.4 engine (`start --items 3`), bound to `repo` and its HEAD; returns (state dir, lease)."""
    data = json.loads(STATE_2_4.read_text())
    data['repo'] = str(pathlib.Path(repo).resolve())
    data['session']['base'] = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    state = pathlib.Path(root) / name
    state.mkdir()
    (state / 'state.json').write_text(json.dumps(data))
    return state, data['session']['lease']


def done(text='done', checks=None, criteria=None):
    """A builder report body with its single SELF_REVIEW line."""
    review = {'checks': checks if checks is not None else [{'command': 'python3 -m unittest', 'exit_code': 0}],
              'criteria': criteria if criteria is not None else [{'criterion': 'check behavior', 'met': True, 'evidence': 'checked'}]}
    return text + '\nARTIFACT: fixture\nSELF_REVIEW: ' + json.dumps(review)


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

    def allow_review(self, *reviewers):
        """A non-final receipt is recorded only from a critic card's worker (contract item 4): give each name one."""
        for name in reviewers or ('reviewer',):
            card = 'critic-' + name
            if any(t['role'] == 'critic' and t.get('worker') == name for t in self.engine.status()['tasks'].values()):
                continue
            self.task(card, role='critic', mode='judge', files=[])
            token = self.engine.dispatch('main', self.lease, card, name)
            self.engine.report(name, token, 'Judged.')
            self.engine.accept('main', self.lease, card)

    def task(self, name='a', **kw):
        task = dict(id=name, role='builder', mode='implementation', inputs=['spec'], acceptance=['check behavior'], files=[name], resources=[], dependencies=[])
        task.update(kw)
        self.engine.add_task('main', self.lease, task)

    def review(self, path, reviewer='reviewer', categories=None, tasks=None, findings=None, final=False, engine=None,
               task_findings=None, repair_check=None, cleared=None):
        engine = engine or self.engine
        artifact = engine.artifact() if final or not tasks else engine.artifact(engine.scope_for(tasks))
        body = dict(reviewer=reviewer, categories=categories or ['correctness'],
                    tasks=tasks or [], findings=findings or [], final=final,
                    issues=[dict(text=f, severity='blocking', impact='Fixture impact: a named requirement is unmet.')
                            for f in findings or []],
                    verdict='BLOCKED' if findings else 'CLEAN', artifact=artifact,
                    summary='Behavior checked against acceptance criteria.')
        if task_findings is not None:
            body['task_findings'] = task_findings
        if repair_check is not None:
            body['repair_check'] = repair_check
        if cleared is not None:
            body['cleared'] = cleared
        path.write_text(json.dumps(body))


class EngineTests(EngineFixture):
    def test_inline_and_worker_execution_share_ownership(self):
        self.task('inline')
        self.task('parallel')
        self.task('collision', files=['inline'])
        token = self.engine.start_inline('main', self.lease, 'inline', serial='fixture: one card at a time')
        self.engine.dispatch('main', self.lease, 'parallel', 'worker')
        with self.assertRaises(EngineError):
            self.engine.dispatch('main', self.lease, 'collision', 'other')
        self.engine.report('main', token, done('Inline implementation checked'))
        self.assertTrue(self.engine.status()['tasks']['inline']['inline'])
        self.engine.accept('main', self.lease, 'inline')

    def test_inline_cannot_replace_independent_review_or_survive_interruption(self):
        self.task('built')
        self.task('review', role='code-reviewer', mode='final', review_of=['built'])
        with self.assertRaises(EngineError):
            self.engine.start_inline('main', self.lease, 'review')
        self.task('inline')
        token = self.engine.start_inline('main', self.lease, 'inline', serial='fixture: one card at a time')
        self.engine.interrupt('main', self.lease)
        with self.assertRaises(EngineError):
            self.engine.report('main', token, done('Late inline result'))

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

    def test_report_needs_coordinator_accept(self):
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        with self.assertRaises(EngineError):
            self.engine.report('worker', token, '')
        self.engine.report('worker', token, done('implemented'))
        with self.assertRaises(EngineError):
            self.engine.accept('main', 'not-the-lease', 'a')
        self.engine.accept('main', self.lease, 'a')  # a builder card needs no independent review
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def test_interrupt_rejects_late_report(self):
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.engine.interrupt('main', self.lease)
        with self.assertRaises(EngineError):
            self.engine.report('worker', token, done('done'))
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
        token = self.engine.dispatch('main', self.lease, 'a', 'builder-a', serial='fixture: one card at a time')
        self.assertEqual(['b'], self.engine.ready('main', self.lease))
        self.engine.report('builder-a', token, done('built a'))
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual(['b', 'c'], self.engine.ready('main', self.lease))

    def test_stale_review_and_gate_log(self):
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'builder')
        self.engine.report('builder', token, done('done'))
        (self.repo / 'a').write_text('new state')
        with self.assertRaisesRegex(EngineError, 'Reported artifact is stale'):
            self.engine.accept('main', self.lease, 'a')
        gate = self.engine.run_gate('main', self.lease, 'check', [sys.executable, '-c', 'print("ok")'])
        pathlib.Path(gate['path']).write_text('altered')
        self.assertFalse(self.engine._intact(gate))

    def test_repair_needs_findings(self):
        with self.assertRaises(EngineError):
            self.task(mode='repair')
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'builder')
        self.engine.report('builder', token, done('done'))
        self.allow_review()
        report = self.root / 'review'
        self.review(report, tasks=['a'], findings=['Behavior fails for empty input'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'], findings=['Behavior fails for empty input'])
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'a')
        self.task('repair', mode='repair', files=['repair'], repair_of='a')

    def test_review_metadata_and_nonbuilder_accept(self):
        self.task(role='investigator', mode='code')
        token = self.engine.dispatch('main', self.lease, 'a', 'investigator')
        self.engine.report('investigator', token, done('Code symbols inspected; evidence attached.'))
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

    def test_lock_preserves_concurrent_cards(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda n: self.task('task-' + str(n)), range(12)))
        self.assertEqual(12, len(self.engine.status()['tasks']))

class IntegrationRepairTests(EngineFixture):
    def test_canonical_modes(self):
        for role, mode in [('designer-planner', 'product'), ('critic', 'surface'), ('critic', 'scope'),
                           ('operator', 'gate'), ('operator', 'cleanup'), ('operator', 'release')]:
            name = role + '-' + mode
            self.task(name, role=role, mode=mode)
            self.engine.dispatch('main', self.lease, name, name + '-worker')
        with self.assertRaises(EngineError):
            self.task('old-mode', role='operator', mode='default')

    def test_old_role_names_are_unavailable(self):
        for role, mode in [('founder-mind', 'audit'), ('red-teamer', 'scope'), ('auditor', 'spec'),
                           ('gatekeeper', 'checks'), ('janitor', 'hygiene'), ('releaser', 'release')]:
            with self.assertRaises(EngineError, msg=role):
                self.task(role, role=role, mode=mode)

    def test_builder_cleanup_needs_no_repair_of(self):
        self.task('clean', mode='cleanup')
        self.engine.dispatch('main', self.lease, 'clean', 'cleanup-worker')

    def test_critic_review_of_and_no_inline_execution(self):
        self.task('B1')
        self.task('C1', role='critic', mode='spec', files=[], review_of=['B1'])
        self.task('C2', role='critic', mode='judge', files=[])
        with self.assertRaises(EngineError):
            self.engine.start_inline('main', self.lease, 'C2')
        token = self.engine.dispatch('main', self.lease, 'B1', 'builder', serial='fixture: one card at a time')
        self.engine.report('builder', token, done('Built'))
        self.assertIn('C1', self.engine.ready('main', self.lease))
        modes = {'investigator': 'code', 'designer-planner': 'plan', 'operator': 'gate', 'builder': 'implementation'}
        for role, mode in modes.items():
            with self.assertRaises(EngineError, msg=role):
                self.task('bad-' + role, role=role, mode=mode, review_of=['B1'])

    def test_gate_guard_and_timeout(self):
        for argv in [['git', 'reset', '--hard'], ['git', 'push', 'origin', 'main'], ['bash', '-c', 'git stash']]:
            with self.assertRaises(EngineError):
                self.engine.run_gate('main', self.lease, 'unsafe', argv)
        engine = Engine(self.root / 'bounded', self.repo, {'gate_timeout_seconds': 0.05})
        lease = engine.open_session('main')
        receipt = engine.run_gate('main', lease, 'hang', [sys.executable, '-c', 'import time; time.sleep(10)'])
        self.assertEqual(124, receipt['exit_code'])
        self.assertFalse(receipt['passed'])

    def test_a_gate_stops_the_background_processes_it_leaves_behind(self):
        if not Path('/proc/self/stat').exists():
            self.skipTest('needs /proc to see whether the process is still running')
        code = ('import subprocess, sys\n'
                'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])\n'
                'print(child.pid, flush=True)\n')
        receipt = self.engine.run_gate('main', self.lease, 'leaves-a-child', [sys.executable, '-c', code])
        log = Path(receipt['path']).read_text()
        pid = int(log.split()[0])
        self.assertIn('Gate left background processes running; stopped them', log)

        def running():  # a killed orphan stays a zombie until init reaps it; that is not running
            try:
                return Path('/proc/%d/stat' % pid).read_text().rsplit(')', 1)[1].split()[0] != 'Z'
            except OSError:
                return False

        deadline = time.time() + 5
        while running() and time.time() < deadline:
            time.sleep(0.05)
        self.assertFalse(running())
        self.assertTrue(receipt['passed'])  # the tree did not change, so the gate still passes
        clean = self.engine.run_gate('main', self.lease, 'clean', [sys.executable, '-c', 'print("ok")'])
        self.assertNotIn('background processes', Path(clean['path']).read_text())

    def test_gate_timeout_overrides_the_policy_for_one_run(self):
        receipt = self.engine.run_gate('main', self.lease, 'hang', [sys.executable, '-c', 'import time; time.sleep(10)'],
                                       timeout=0.05)
        self.assertEqual(124, receipt['exit_code'])
        receipt = self.engine.run_gate('main', self.lease, 'quick', [sys.executable, '-c', 'pass'], timeout=30)
        self.assertTrue(receipt['passed'])
        for timeout in (0, -1, float('nan'), float('inf'), True, '5'):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(EngineError, 'Gate timeout must be positive and finite'):
                self.engine.run_gate('main', self.lease, 'bad', [sys.executable, '-c', 'pass'], timeout=timeout)

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
        self.engine.report('worker', token, done('checked'))
        self.engine.accept('main', self.lease, 'a')
        report = self.root / 'final.json'
        self.review(report, final=True)
        with self.assertRaises(EngineError):
            self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], final=True)

    def package_copy(self):
        import shutil
        package = self.root / 'package'
        shutil.copytree(pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra', package)
        return package

    def test_method_missing_and_changed_contract_invalidates_run(self):
        from unittest.mock import patch
        package = self.package_copy()
        with patch('orchestra_core.engine.PACKAGE_ROOT', package):
            engine = Engine(self.root / 'contracts', self.repo)
            lease = engine.open_session('main')
            task = dict(id='a', role='builder', mode='implementation', inputs=['https://example.com'], acceptance=['done'], files=['a'], resources=[], dependencies=[])
            engine.add_task('main', lease, task)
            method = package / 'skills/orchestra-build/SKILL.md'
            # An edited method keeps the live run (SPEC 11.1 item 5).
            method.write_text(method.read_text() + '\nNew binding rule.\n')
            engine.dispatch('main', lease, 'a', 'worker')
            self.assertEqual('running', Engine(self.root / 'contracts', self.repo).status()['tasks']['a']['state'])
            # A missing method still fails validation.
            method.unlink()
            with self.assertRaises(EngineError):
                engine.status()
            with self.assertRaises(EngineError):
                Engine(self.root / 'new-contracts', self.repo)

    def test_added_mode_invalidates_run(self):
        from unittest.mock import patch
        package = self.package_copy()
        with patch('orchestra_core.engine.PACKAGE_ROOT', package):
            engine = Engine(self.root / 'contracts', self.repo)
            lease = engine.open_session('main')
            roles = json.loads((package / 'config/roles.json').read_text())
            next(r for r in roles['roles'] if r['id'] == 'builder')['modes'].append('extra-mode')
            (package / 'config/roles.json').write_text(json.dumps(roles))
            with self.assertRaisesRegex(EngineError, 'start a new run'):
                engine.status()
            with self.assertRaisesRegex(EngineError, 'start a new run'):
                engine.add_task('main', lease, dict(id='a', role='builder', mode='implementation', inputs=['x'], acceptance=['y'], files=['a'], resources=[], dependencies=[]))

    def test_added_orchestrator_mode_invalidates_run(self):
        from unittest.mock import patch
        package = self.package_copy()
        with patch('orchestra_core.engine.PACKAGE_ROOT', package):
            engine = Engine(self.root / 'contracts', self.repo)
            engine.open_session('main')
            roles = json.loads((package / 'config/roles.json').read_text())
            next(r for r in roles['roles'] if r['id'] == 'orchestrator')['modes'].append('extra-mode')
            (package / 'config/roles.json').write_text(json.dumps(roles))
            with self.assertRaisesRegex(EngineError, 'start a new run'):
                engine.status()

    def test_status_has_no_lease_key_anywhere(self):
        self.task('a')
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.assertNotIn('"lease"', json.dumps(self.engine.status()))
        self.assertTrue(self.engine.status()['session']['active'])
        self.assertEqual('running', self.engine.status()['tasks']['a']['state'])
        # The stored state keeps both leases; redaction is on the read path only.
        raw = json.loads(self.engine.state_path.read_text())
        self.assertEqual(self.lease, raw['session']['lease'])
        self.assertEqual(self.lease, raw['tasks']['a']['lease'])
        self.engine.report('worker', token, done('checked'))

    def test_narrowed_categories_accepted_and_empty_or_unknown_rejected(self):
        for bad in ([], ['nonsense'], ['correctness', 'nonsense'], 'correctness'):
            with self.assertRaises(EngineError):
                Engine(self.root / 'bad', self.repo, {'required_review_categories': bad})
        def accepted(engine, lease):
            task = dict(id='a', role='investigator', mode='code', inputs=['spec'], acceptance=['check'], files=['a'], resources=[], dependencies=[])
            engine.add_task('main', lease, task)
            engine.report('worker', engine.dispatch('main', lease, 'a', 'worker'), done('checked'))
            engine.accept('main', lease, 'a')

        report = self.root / 'final.json'
        policy = {'required_review_categories': ['correctness', 'tests']}
        engine = Engine(self.root / 'narrow', self.repo, policy)
        lease = engine.open_session('main')
        accepted(engine, lease)
        self.review(report, categories=['correctness', 'tests'], tasks=['a'], final=True, engine=engine)
        engine.record_review('main', lease, 'reviewer', report, ['correctness', 'tests'], ['a'], final=True)
        engine.check_completion('main', lease)
        # A narrowed policy still demands its own categories.
        engine2 = Engine(self.root / 'narrow2', self.repo, policy)
        lease2 = engine2.open_session('main')
        accepted(engine2, lease2)
        self.review(report, categories=['correctness'], tasks=['a'], final=True, engine=engine2)
        engine2.record_review('main', lease2, 'reviewer', report, ['correctness'], ['a'], final=True)
        with self.assertRaisesRegex(EngineError, 'coverage'):
            engine2.check_completion('main', lease2)

    def test_old_policy_with_removed_keys_still_loads(self):
        engine = Engine(self.root / 'old', self.repo, {'reserved_ports': [1], 'denied_tools': ['x']})
        engine.open_session('main')

    def test_invalid_timeout_and_optional_brief(self):
        for timeout in [0, -1, True, '300', float('inf')]:
            with self.assertRaises(EngineError):
                Engine(self.root / 'invalid', self.repo, {'gate_timeout_seconds': timeout})
        for values in [dict(objective=' '), dict(brief='missing'), dict(inputs=[' '])]:
            with self.assertRaises(EngineError):
                self.task(**values)
        brief = self.root / 'brief.md'
        brief.write_text('Mode: implementation\nObjective and bounded acceptance criteria.\n## Keep\nnone\n## Remove\nnone\n')
        self.task(brief=str(brief))
        brief.unlink()
        with self.assertRaises(EngineError):
            self.engine.dispatch('main', self.lease, 'a', 'worker')

    def test_brief_file_needs_the_cards_mode_line(self):
        cases = {'no-mode.md': 'Objective and bounded acceptance criteria.',
                 'wrong-mode.md': 'Mode: repair\nObjective.',
                 'inline-mention.md': 'The card runs Mode: implementation somewhere in prose.',
                 'other-prefix.md': 'Mode: implementation-extra\nObjective.'}
        for name, text in cases.items():
            brief = self.root / name
            brief.write_text(text)
            with self.assertRaises(EngineError, msg=name):
                self.task(name, brief=str(brief))
        ok = self.root / 'ok.md'
        ok.write_text('# Brief\nMode: implementation\nObjective.\n## Keep\nnone\n## Remove\nnone\n')
        self.task('with-brief', brief=str(ok))
        self.task('without-brief')
        cleanup = self.root / 'cleanup.md'
        cleanup.write_text('Mode: cleanup\n## Keep\nnone\n## Remove\nnone\n')
        self.task('cleanup-brief', mode='cleanup', brief=str(cleanup))

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
        self.engine.report('worker', token, done('checked'))
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
        self.engine.report('worker', token, done('checked'))
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
    def record(self, name, tasks, categories=None, findings=None, final=False, task_findings=None, repair_check=None):
        from orchestra_core.engine import CATEGORIES
        categories = categories or CATEGORIES
        if final:  # the final review covers every pre-release card, the critic cards of earlier receipts included
            tasks = [i for i, t in self.engine.status()['tasks'].items() if not (t['role'] == 'operator' and t['mode'] == 'release')]
        else:
            self.allow_review(name)
        path = self.root / (name + '.json')
        self.review(path, reviewer=name, tasks=tasks, categories=categories, findings=findings, final=final,
                    task_findings=task_findings, repair_check=repair_check)
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

    def test_overlapping_queued_repairs_do_not_deadlock(self):
        # F29: two repairs whose inherited reservations overlap; the lowest id starts, the other waits for it.
        self.release_setup()
        self.task('B1', files=['a', 'shared'])
        self.task('B2', files=['b'])
        for card in ('B1', 'B2'):
            token = self.engine.dispatch('main', self.lease, card, 'builder-' + card, serial='test')
            self.engine.report('builder-' + card, token, done('Result ' + card))
        self.record('blocked', ['B1', 'B2'], findings=['Wrong output'])
        self.task('RA', mode='repair', repair_of='B1', files=['a'])
        self.task('RB', mode='repair', repair_of='B2', files=['b', 'shared'])
        self.assertEqual(['RA'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.assertEqual([], self.engine.ready('main', self.lease))  # RB still overlaps the running RA
        self.engine.report('repair-a', token, done('Repaired A'))
        self.assertEqual(['RB'], self.engine.ready('main', self.lease))  # F30: RA's own files are disjoint from RB's

    def test_repair_transfers_reservations_and_retains_history(self):
        self.release_setup()
        self.task('B1', files=['a'])
        self.task('D1', files=['d'], dependencies=['B1'], role='investigator', mode='code')
        token = self.engine.dispatch('main', self.lease, 'B1', 'first-builder')
        self.engine.report('first-builder', token, done('Original result'))
        self.record('blocked', ['B1'], findings=['Incorrect empty input'])
        self.task('R1', mode='repair', repair_of='B1', files=['a'])
        self.assertEqual(['R1'], self.engine.ready('main', self.lease))
        repair_token = self.engine.dispatch('main', self.lease, 'R1', 'repair-builder')
        with self.assertRaises(EngineError):
            self.engine.report('first-builder', token, done('late original report'))
        self.engine.report('repair-builder', repair_token, done('Repaired behavior'))
        self.record('clean', ['B1', 'R1'])
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'B1')
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')
        state = self.engine.status()
        self.assertTrue(state['tasks']['B1']['report'].startswith('Original result'))
        self.assertEqual('first-builder', state['tasks']['B1']['worker'])
        self.assertEqual(['Incorrect empty input'], state['reviews'][0]['findings'])
        self.assertEqual(['D1'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'D1', 'investigator')
        self.engine.report('investigator', token, done('Dependent completed'))
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

    def test_latest_blocked_receipt_prevents_accept_and_completion(self):
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.engine.report('worker', token, done('done'))
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
        self.task('V1', role='critic', mode='judge', files=['a'], review_of=['B1'])
        self.assertEqual(['B1'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'B1', 'builder')
        self.engine.report('builder', token, done('Built'))
        self.assertEqual(['V1'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'V1', 'review-worker')
        self.engine.report('review-worker', token, done('Reviewed builder output'))
        self.record('review-worker', ['B1'])
        self.engine.accept('main', self.lease, 'V1')
        self.engine.accept('main', self.lease, 'B1')
        self.record('review-worker', [], final=True)
        self.engine.check_completion('main', self.lease)

    def test_second_repair_suspends_entire_same_file_chain(self):
        self.release_setup()
        self.task('B1', files=['a'])
        token = self.engine.dispatch('main', self.lease, 'B1', 'worker1')
        self.engine.report('worker1', token, done('First implementation'))
        self.record('blocked1', ['B1'], findings=['bug1'])
        self.task('R1', mode='repair', repair_of='B1', files=['a'])
        token = self.engine.dispatch('main', self.lease, 'R1', 'worker2')
        self.engine.report('worker2', token, done('First repair'))
        self.record('blocked2', ['B1', 'R1'], findings=['bug2'], task_findings={'R1': ['bug2']})
        self.engine.hold('main', self.lease, 'R1', 'bug2 persists after the first repair')
        self.task('R2', mode='repair', repair_of='R1', owner_approval='owner: take the repair', files=['a'])
        self.assertEqual(['R2'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'R2', 'worker3')
        self.engine.report('worker3', token, done('Second repair'))
        self.record('clean2', ['R1', 'R2'])
        for name in ['R2', 'R1']:
            self.engine.accept('main', self.lease, name)
        self.engine.accept('main', self.lease, 'B1')  # the accepted repair chain carries the original
        self.assertTrue(all(t['state'] == 'accepted' for t in self.engine.status()['tasks'].values()))

    def test_review_targets_reject_wrong_role_and_dependency_cycle(self):
        self.task('B1')
        for values in [dict(review_of=['missing']), dict(review_of=['B1']),
                       dict(role='code-reviewer', mode='checkpoint', review_of=['B1'], dependencies=['B1']),
                       dict(role='code-reviewer', mode='checkpoint', review_of=[{}])]:
            with self.assertRaises(EngineError):
                self.task('invalid', **values)

    def test_add_refuses_code_reviewer_without_review_of(self):
        self.task('B1')
        for values in [dict(), dict(review_of=[]), dict(dependencies=['B1'])]:
            with self.subTest(values), self.assertRaisesRegex(EngineError, 'review_of'):
                self.task('R1', role='code-reviewer', mode='final', **values)

    def test_builder_accepts_without_independent_review(self):
        for name, extra in (('a', {}), ('b', dict(review_required=True)), ('c', dict(review_required=False))):
            self.task(name, **extra)
            token = self.engine.dispatch('main', self.lease, name, 'worker-' + name)
            self.engine.report('worker-' + name, token, done('done'))
            self.engine.accept('main', self.lease, name)
            self.assertEqual('accepted', self.engine.status()['tasks'][name]['state'])
        self.assertEqual([], self.engine.status()['reviews'])

    def test_repair_survives_interrupt_and_preserves_original_reservation(self):
        self.release_setup()
        self.task('B1', files=['a'])
        token = self.engine.dispatch('main', self.lease, 'B1', 'builder')
        self.engine.report('builder', token, done('Original result'))
        self.record('blocked', ['B1'], findings=['bug'])
        self.task('R1', mode='repair', repair_of='B1', files=['a'])
        self.task('outsider', files=['a'])
        self.assertEqual(['R1'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'R1', 'repairer')
        self.engine.interrupt('main', self.lease)
        self.lease = self.engine.open_session('main')
        self.assertEqual(['R1'], self.engine.ready('main', self.lease))
        token = self.engine.dispatch('main', self.lease, 'R1', 'repairer2')
        self.engine.report('repairer2', token, done('Repair result'))
        self.engine.interrupt('main', self.lease)
        self.lease = self.engine.open_session('main')
        self.record('clean', ['B1', 'R1'])
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')
        self.assertEqual(['outsider'], self.engine.ready('main', self.lease))

    def test_operator_release_card_runs_after_pre_release_review_then_closes(self):
        self.release_setup()
        self.task('B1', files=['a'])
        self.task('L1', role='operator', mode='release', files=[], dependencies=['B1'])
        token = self.engine.dispatch('main', self.lease, 'B1', 'builder')
        self.engine.report('builder', token, done('Built'))
        self.record('checkpoint', ['B1'])
        self.engine.accept('main', self.lease, 'B1')
        self.record('final', ['B1'], final=True)
        with self.assertRaises(EngineError):
            self.engine.release_permit('main', self.lease, 'authorized', 'main')
        with self.assertRaises(EngineError):
            self.task('L2', role='operator', mode='release', files=[])
        token = self.engine.dispatch('main', self.lease, 'L1', 'release-worker')
        permit = self.engine.release_permit('main', self.lease, 'authorized', 'main')
        self.assertEqual(permit, self.engine.check_release('authorized', 'main'))
        with self.assertRaises(EngineError):
            self.engine.check_completion('main', self.lease)
        self.engine.report('release-worker', token, done('Release command completed; observed remote evidence attached'))
        self.engine.accept('main', self.lease, 'L1')
        self.engine.close_session('main', self.lease)

    def test_release_exemption_never_skips_queued_builder(self):
        self.release_setup()
        self.task('B1', files=['a'])
        self.task('L1', role='operator', mode='release', files=[])
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

    def test_altered_latest_receipt_cannot_restore_older_approval(self):
        self.task()
        token = self.engine.dispatch('main', self.lease, 'a', 'worker')
        self.engine.report('worker', token, done('done'))
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

    @unittest.skipIf(portable.IS_WINDOWS, 'POSIX-only: the alternate Git is an extensionless script')
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


class HarnessSessionTests(EngineFixture):
    """B-F5: harness-session binding, release on session end, rebind. The clock is injected."""

    def setUp(self):
        super().setUp()
        self.now = [1000.0]
        self.engine.interrupt('main', self.lease)
        self.engine = Engine(self.root / 'state', self.repo, clock=lambda: self.now[0])
        self.rebound()

    def rebound(self):
        """A fresh active run bound to harness session S."""
        self.now[0] = 1000.0
        if self.engine.status()['session']['active']:
            self.engine.interrupt('main', self.raw_lease())
        self.lease = self.engine.open_session('main', harness_session='S')

    def session(self):
        return self.engine.status()['session']

    def raw_lease(self):
        return json.loads(self.engine.state_path.read_text())['session']['lease']

    def test_interrupt_active_needs_no_lease_and_is_idempotent(self):
        self.assertTrue(self.engine.interrupt_active())
        self.assertFalse(self.session()['active'])
        self.assertFalse(self.engine.interrupt_active())
        with self.assertRaisesRegex(EngineError, 'lease'):
            self.engine.validate_lease('main', self.lease)

    def test_interrupt_active_clears_permits_and_autonomy(self):
        state = json.loads(self.engine.state_path.read_text())
        state['permits'] = [dict(id='p', action='release', remote='r', target='t', argv=[], artifact={}, lease=self.lease)]
        self.engine.state_path.write_text(json.dumps(state))
        self.engine.interrupt_active()
        state = self.engine.status()
        self.assertEqual((state['permits'], state['autonomy']), ([], None))
        self.assertEqual(json.loads(self.engine.state_path.read_text())['permits'], [])

    def test_end_writes_wait_for_a_lock_held_past_lock_wait(self):
        """Interrupt and SessionEnd records survive a busy lock: they wait instead of raising StateBusy."""
        import threading
        for method, args, reason in [('interrupt_active', (), 'interrupted'), ('end_harness_session', ('S',), 'ended')]:
            with self.subTest(method=method):
                self.rebound()
                hook_engine = Engine(self.root / 'state', self.repo, clock=lambda: self.now[0], lock_wait=0.2)
                handle = (self.root / 'state' / 'state.lock').open('a+')
                self.addCleanup(handle.close)
                portable.lock(handle, exclusive=True)
                timer = threading.Timer(0.8, portable.unlock, [handle])
                timer.start()
                self.addCleanup(timer.cancel)
                self.assertTrue(getattr(hook_engine, method)(*args))
                self.assertFalse(self.session()['active'])
                self.assertEqual(self.engine.status()['last_brief']['reason'], reason)
                timer.join()
                handle.close()  # Windows cannot delete the state directory while the lock file is open

    def test_interrupt_active_on_inactive_run_leaves_state_unwritten(self):
        self.engine.interrupt_active()
        before = self.stat()
        self.assertFalse(self.engine.interrupt_active())
        self.assertEqual(before, self.stat())

    def test_interrupt_active_with_no_state_file_does_not_create_one(self):
        engine = Engine(self.root / 'fresh', self.repo)
        self.assertFalse(engine.interrupt_active())
        self.assertFalse(engine.state_path.exists())

    def stat(self):
        info = self.engine.state_path.stat()
        return (info.st_ino, info.st_mtime_ns)

    def test_no_op_session_end_and_rebind_do_not_rewrite_state(self):
        before = self.stat()
        self.assertFalse(self.engine.end_harness_session('other'))
        self.assertFalse(self.engine.mark_harness_rebind('other'))
        self.assertEqual(before, self.stat())
        self.engine.interrupt_active()
        before = self.stat()
        self.assertFalse(self.engine.end_harness_session('S'))
        self.assertFalse(self.engine.mark_harness_rebind('S'))
        self.assertEqual(before, self.stat())
        self.engine.open_session('main')  # unbound run
        before = self.stat()
        self.assertFalse(self.engine.end_harness_session('S'))
        self.assertFalse(self.engine.mark_harness_rebind('S'))
        self.assertEqual(before, self.stat())

    def test_matching_session_end_still_writes(self):
        before = self.stat()
        self.assertTrue(self.engine.end_harness_session('S'))
        self.assertNotEqual(before, self.stat())

    def test_open_session_records_harness_session_and_keeps_it_optional(self):
        self.assertEqual(self.session()['harness_session'], 'S')
        self.engine.interrupt('main', self.lease)
        self.engine.open_session('main')
        self.assertNotIn('harness_session', self.session())
        self.engine.interrupt('main', self.raw_lease())
        for bad in ('', 5, True):
            with self.assertRaises(EngineError):
                self.engine.open_session('main', harness_session=bad)

    def test_end_harness_session_does_what_interrupt_does_and_is_idempotent(self):
        self.assertTrue(self.engine.end_harness_session('S'))
        session = self.session()
        self.assertFalse(session['active'])
        self.assertEqual(session['outcome'], 'ended')
        self.assertEqual(session['harness_session'], 'S')
        state = self.engine.status()
        self.assertEqual((state['permits'], state['autonomy']), ([], None))
        self.assertFalse(self.engine.end_harness_session('S'))
        self.assertFalse(self.session()['active'])

    def test_end_harness_session_ignores_other_ids_and_unbound_runs(self):
        self.assertFalse(self.engine.end_harness_session('other'))
        self.assertTrue(self.session()['active'])
        self.engine.interrupt('main', self.lease)
        self.engine.open_session('main')
        self.assertFalse(self.engine.end_harness_session('S'))
        self.assertTrue(self.session()['active'])

    def test_mark_rebind_records_only_for_the_bound_id(self):
        self.assertFalse(self.engine.mark_harness_rebind('other'))
        self.assertNotIn('pending_rebind', self.session())
        self.assertTrue(self.engine.mark_harness_rebind('S'))
        self.assertEqual(self.session()['pending_rebind'], {'from': 'S', 'at': 1000.0})
        self.assertTrue(self.session()['active'])

    def test_apply_rebind_binds_once_inside_the_window(self):
        self.engine.mark_harness_rebind('S')
        self.now[0] = 1000.5
        self.assertTrue(self.engine.apply_harness_rebind('S2'))
        self.assertEqual(self.session()['harness_session'], 'S2')
        self.assertNotIn('pending_rebind', self.session())
        self.assertFalse(self.engine.apply_harness_rebind('S3'))
        self.assertEqual(self.session()['harness_session'], 'S2')

    def test_apply_rebind_window_edges_and_stale_entries(self):
        for offset, applied in [(0, True), (60, True), (60.5, False), (-1, False)]:
            with self.subTest(offset=offset):
                self.rebound()
                self.engine.mark_harness_rebind('S')
                self.now[0] = 1000.0 + offset
                self.assertEqual(self.engine.apply_harness_rebind('S2'), applied)
                self.assertNotIn('pending_rebind', self.session())
                self.assertEqual(self.session()['harness_session'], 'S2' if applied else 'S')

    def test_apply_rebind_without_pending_changes_nothing(self):
        before = self.engine.state_path.read_bytes()
        self.assertFalse(self.engine.apply_harness_rebind('S2'))
        self.assertEqual(self.engine.state_path.read_bytes(), before)

    def test_release_removes_pending_rebind_and_keeps_harness_session(self):
        self.engine.mark_harness_rebind('S')
        self.assertTrue(self.engine.end_harness_session('S'))
        self.assertNotIn('pending_rebind', self.session())
        self.assertEqual(self.session()['harness_session'], 'S')

    def test_malformed_harness_fields_are_rejected(self):
        state = json.loads(self.engine.state_path.read_text())
        for patch in [{'harness_session': 3}, {'harness_session': ''}, {'pending_rebind': 'x'},
                      {'pending_rebind': {'from': 'S', 'at': 'now'}}, {'pending_rebind': {'from': 'S', 'at': True}}]:
            with self.subTest(patch=patch):
                bad = json.loads(json.dumps(state))
                bad['session'].update(patch)
                self.engine.state_path.write_text(json.dumps(bad))
                with self.assertRaises(EngineError):
                    self.engine.status()



class ScopedEvidenceTests(EngineFixture):
    def setUp(self):
        super().setUp()
        for name in ('b', 'c'):
            (self.repo / name).write_text('initial')
        self.git('add', 'b', 'c')
        self.git('commit', '-qm', 'more')
        self.engine = Engine(self.root / 'state2', self.repo)
        self.lease = self.engine.open_session('main')
        self.allow_review()

    def reported(self, name='a', **kw):
        if 'role' not in kw:  # a builder needs no independent review; a card that asks for one does
            kw.update(role='investigator', mode='code', review_required=True)
        self.task(name, **kw)
        self.engine.report('w' + name, self.engine.dispatch('main', self.lease, name, 'w' + name), done('checked'))

    def checkpoint(self, name='a', findings=None):
        report = self.root / (name + '-review.json')
        self.review(report, tasks=[name], findings=findings)
        return self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], [name], findings=findings)

    def test_scoped_artifact_binds_scope_and_ignores_outside_edits(self):
        base = self.engine.artifact(['a'])
        self.assertEqual(['a'], base['scope'])
        self.assertNotIn('scope', self.engine.artifact())
        (self.repo / 'b').write_text('sibling edit')
        (self.repo / 'new-untracked').write_text('x')
        self.assertEqual(base, self.engine.artifact(['a']))
        self.assertNotEqual(self.engine.artifact(), self.engine.artifact(['a']))
        (self.repo / 'a').write_text('inside edit')
        self.assertNotEqual(base, self.engine.artifact(['a']))

    def test_scoped_artifact_directory_scope_covers_children(self):
        (self.repo / 'd').mkdir()
        (self.repo / 'd' / 'f').write_text('1')
        base = self.engine.artifact(['d'])
        (self.repo / 'd' / 'f').write_text('2')
        self.assertNotEqual(base, self.engine.artifact(['d']))

    def test_edit_outside_scope_keeps_scoped_verdict_current(self):
        self.reported('a')
        self.checkpoint('a')
        (self.repo / 'b').write_text('sibling uncommitted edit')
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def test_edit_inside_scope_stales_scoped_verdict(self):
        self.reported('a')
        self.checkpoint('a')
        (self.repo / 'a').write_text('edited after review')
        with self.assertRaisesRegex(EngineError, 'independent review'):
            self.engine.accept('main', self.lease, 'a')

    def test_new_commit_outside_the_scope_keeps_scoped_verdict_current(self):
        # Q7: a scoped receipt binds its files, index, status and policy, not HEAD and tree.
        self.reported('a')
        self.checkpoint('a')
        (self.repo / 'b').write_text('committed elsewhere')
        self.git('commit', '-qam', 'elsewhere')
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def test_new_commit_outside_the_scope_keeps_scoped_report_current(self):
        self.reported('r', role='investigator', mode='code', files=['b'])
        (self.repo / 'a').write_text('committed elsewhere')
        self.git('commit', '-qam', 'elsewhere')
        self.engine.accept('main', self.lease, 'r')
        self.assertEqual('accepted', self.engine.status()['tasks']['r']['state'])

    def test_commit_of_a_scoped_file_stales_scoped_verdict(self):
        self.reported('a')
        self.checkpoint('a')
        (self.repo / 'a').write_text('committed inside the scope')
        self.git('commit', '-qam', 'inside')
        with self.assertRaisesRegex(EngineError, 'independent review'):
            self.engine.accept('main', self.lease, 'a')

    def test_staged_scoped_file_stales_scoped_verdict(self):
        self.reported('a')
        self.checkpoint('a')
        (self.repo / 'a').write_text('staged inside the scope')
        self.git('add', 'a')
        with self.assertRaisesRegex(EngineError, 'independent review'):
            self.engine.accept('main', self.lease, 'a')

    def test_untracked_scoped_file_stales_scoped_status(self):
        (self.repo / 'd').mkdir()
        (self.repo / 'd' / 'f').write_text('1')
        self.git('add', 'd')
        self.git('commit', '-qm', 'd')
        base = self.engine.artifact(['d'])
        (self.repo / 'd' / 'g').write_text('untracked inside the scope')
        self.assertFalse(self.engine._same(base, self.engine.artifact(['d'])))

    def test_changed_policy_stales_scoped_artifact(self):
        base = self.engine.artifact(['a'])
        self.assertTrue(self.engine._same(base, dict(base, head='moved', tree='moved')))
        self.assertFalse(self.engine._same(base, dict(base, policy='another policy')))

    def test_whole_repository_receipts_go_stale_on_any_new_commit(self):
        gate = self.engine.run_gate('main', self.lease, 'check', [sys.executable, '-c', 'print("ok")'])
        self.reported('a')
        final = self.root / 'final.json'
        ids = sorted(self.engine.status()['tasks'])
        self.review(final, reviewer='final-reviewer', tasks=ids, final=True, task_findings={})
        self.engine.record_review('main', self.lease, 'final-reviewer', final, ['correctness'], ids, final=True)
        whole = self.engine.artifact()
        self.assertTrue(self.engine._same(gate['artifact'], whole))
        (self.repo / 'b').write_text('committed elsewhere')
        self.git('commit', '-qam', 'elsewhere')
        self.assertFalse(self.engine._same(gate['artifact'], self.engine.artifact()))
        self.assertFalse(self.engine._same(whole, self.engine.artifact()))
        with self.engine._state(False) as state:
            self.assertEqual({}, self.engine._review_verdicts(state, {}, final=True))

    def test_scoped_report_artifact_survives_outside_edit_and_stales_inside(self):
        self.reported('r', role='investigator', mode='code', files=['b'])
        self.assertEqual(['b'], self.engine.status()['tasks']['r']['report_artifact']['scope'])
        (self.repo / 'a').write_text('outside edit')
        self.engine.accept('main', self.lease, 'r')
        self.reported('s', role='investigator', mode='code', files=['c'])
        (self.repo / 'c').write_text('inside edit')
        with self.assertRaisesRegex(EngineError, 'stale'):
            self.engine.accept('main', self.lease, 's')

    def test_review_receipt_stores_scope_union_of_covered_tasks(self):
        self.reported('a')
        self.reported('b')
        report = self.root / 'union.json'
        self.review(report, tasks=['a', 'b'])
        receipt = self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a', 'b'])
        self.assertEqual(['a', 'b'], receipt['scope'])
        self.assertEqual(['a', 'b'], receipt['artifact']['scope'])

    def test_review_with_wrong_scope_is_rejected(self):
        self.reported('a')
        report = self.root / 'whole.json'
        self.review(report, tasks=['a'], final=True)  # whole-repo artifact
        report.write_text(json.dumps({**json.loads(report.read_text()), 'final': False}))
        with self.assertRaisesRegex(EngineError, 'does not match'):
            self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'])

    def test_repair_chain_files_join_the_scope(self):
        self.reported('a', role='builder', mode='implementation')
        self.checkpoint('a', findings=['bug'])
        self.task('fix', mode='repair', repair_of='a', files=['c'])
        self.assertEqual(['a', 'c'], self.engine.scope_for(['fix']))

    def test_stale_newer_blocked_receipt_does_not_restore_older_clean(self):
        self.reported('a')
        self.reported('b')
        self.checkpoint('a')
        report = self.root / 'wide.json'
        self.review(report, tasks=['a', 'b'], findings=['bug in a'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a', 'b'], findings=['bug in a'])
        with self.assertRaisesRegex(EngineError, 'findings'):
            self.engine.accept('main', self.lease, 'a')
        (self.repo / 'b').write_text('edit inside the newer scope only')
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'a')
        self.assertEqual('reported', self.engine.status()['tasks']['a']['state'])

    def test_stale_final_blocked_receipt_does_not_restore_scoped_clean(self):
        self.reported('a')
        self.checkpoint('a')
        report = self.root / 'final-blocked.json'
        ids = sorted(self.engine.status()['tasks'])
        self.review(report, reviewer='final-reviewer', tasks=ids, findings=['bug in a'], final=True,
                    task_findings={'a': ['bug in a'], 'critic-reviewer': []})
        receipt = self.engine.record_review('main', self.lease, 'final-reviewer', report, ['correctness'], ids, final=True, findings=['bug in a'])
        self.assertIsNone(receipt['scope'])
        with self.assertRaisesRegex(EngineError, 'findings'):
            self.engine.accept('main', self.lease, 'a')
        (self.repo / 'b').write_text('edit outside the checkpoint scope')
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'a')
        self.assertEqual('reported', self.engine.status()['tasks']['a']['state'])

    def receipt(self, name, tasks, categories, findings=None):
        report = self.root / (name + '.json')
        self.review(report, tasks=tasks, categories=categories, findings=findings)
        return self.engine.record_review('main', self.lease, 'reviewer', report, categories, tasks, findings=findings)

    def test_cross_category_stale_blocked(self):
        # O22: a stale non-CLEAN newest receipt voids every category for the tasks it covers.
        self.reported('a')
        self.reported('b')
        self.receipt('r1', ['a'], ['correctness', 'security'])
        self.receipt('r2', ['a', 'b'], ['correctness'], findings=['bug in a'])
        with self.assertRaisesRegex(EngineError, 'findings'):
            self.engine.accept('main', self.lease, 'a')
        (self.repo / 'b').write_text('edit inside the blocking scope only')
        with self.assertRaisesRegex(EngineError, 'Review with findings is stale; re-review'):
            self.engine.accept('main', self.lease, 'a')
        self.assertEqual('reported', self.engine.status()['tasks']['a']['state'])

    def test_disjoint_category_stale_blocked(self):
        self.reported('a')
        self.reported('b')
        self.receipt('r1', ['a'], ['security'])
        self.receipt('r2', ['a', 'b'], ['correctness'], findings=['bug in a'])
        (self.repo / 'b').write_text('edit inside the blocking scope only')
        with self.assertRaisesRegex(EngineError, 'Review with findings is stale; re-review'):
            self.engine.accept('main', self.lease, 'a')
        self.assertEqual('reported', self.engine.status()['tasks']['a']['state'])

    def test_stale_clean_newest_only_removes_its_own_category(self):
        self.reported('a')
        self.reported('b')
        self.receipt('r1', ['a'], ['security'])
        self.receipt('r2', ['a', 'b'], ['correctness'])
        (self.repo / 'b').write_text('edit inside the clean wide scope only')
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def test_newer_receipt_lifts_stale_blocked_void(self):
        self.reported('a')
        self.reported('b')
        self.receipt('r1', ['a'], ['security'])
        self.receipt('r2', ['a', 'b'], ['correctness'], findings=['bug in a'])
        (self.repo / 'b').write_text('edit inside the blocking scope only')
        self.receipt('r3', ['a', 'b'], ['correctness'])
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def test_review_covering_a_no_file_task_uses_whole_repo_artifact(self):
        self.reported('a')
        self.reported('n', files=[])
        self.assertIsNone(self.engine.scope_for(['a', 'n']))
        report = self.root / 'mixed.json'
        self.review(report, tasks=['a', 'n'])
        receipt = self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a', 'n'])
        self.assertIsNone(receipt['scope'])
        self.assertNotIn('scope', receipt['artifact'])
        (self.repo / 'b').write_text('edit outside [a]')
        with self.assertRaisesRegex(EngineError, 'independent review'):
            self.engine.accept('main', self.lease, 'n')
        with self.assertRaisesRegex(EngineError, 'independent review'):
            self.engine.accept('main', self.lease, 'a')

    def test_task_without_reserved_files_gets_whole_repo_artifact(self):
        self.reported('n', role='investigator', mode='code', files=[])
        self.assertIsNone(self.engine.scope_for(['n']))
        task = self.engine.status()['tasks']['n']
        self.assertNotIn('scope', task['report_artifact'])
        self.assertEqual(self.engine.artifact(), task['report_artifact'])
        (self.repo / 'b').write_text('any edit')
        with self.assertRaisesRegex(EngineError, 'stale'):
            self.engine.accept('main', self.lease, 'n')

    def test_final_review_still_binds_whole_repo(self):
        self.reported('a')
        self.checkpoint('a')
        self.engine.accept('main', self.lease, 'a')
        cats = ['requirements', 'correctness', 'security', 'tests', 'architecture', 'standards', 'cleanup']
        report = self.root / 'final.json'
        ids = sorted(self.engine.status()['tasks'])
        self.review(report, reviewer='final-reviewer', categories=cats, tasks=ids, final=True)
        receipt = self.engine.record_review('main', self.lease, 'final-reviewer', report, cats, ids, final=True)
        self.assertNotIn('scope', receipt['artifact'])
        self.assertIsNone(receipt.get('scope'))
        (self.repo / 'b').write_text('outside edit stales final evidence')
        with self.assertRaises(EngineError):
            self.engine.check_completion('main', self.lease)


T0 = 1_800_000_000.0  # 2027-01-15T08:00:00Z; the injected clock never sleeps
PASS_ARGV = [sys.executable, '-c', 'print("ok")']


def iso(ts):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


ALL_CATEGORIES = ['requirements', 'correctness', 'security', 'tests', 'architecture', 'standards', 'cleanup']


class AutonomyFixture(EngineFixture):
    """Engine on an injected clock; nothing sleeps."""

    def setUp(self):
        super().setUp()
        self.default_branch = self.git('branch', '--show-current')
        self.git('switch', '-qc', 'work')  # arming refuses on the default branch
        self.now = [T0]
        self.state = self.root / 'state'
        self.engine = Engine(self.state, self.repo, clock=lambda: self.now[0])

    def fresh(self, policy):
        shutil.rmtree(self.state)
        self.engine = Engine(self.state, self.repo, policy, clock=lambda: self.now[0])
        self.lease = self.engine.open_session('main')

    def ledger(self, goal='ship the fixture', passes=None, stalls=None, deadline=None, checks=None, boundaries=None, extra=''):
        checks = ['fixture: ' + shlex.join(PASS_ARGV)] if checks is None else checks
        caps = [line for line in ('max_passes: ' + passes if passes is not None else None,
                                  'max_stalls: ' + stalls if stalls is not None else None) if line]
        text = ['# Autonomy ledger', '', 'goal: ' + goal, *caps,
                'deadline: ' + (deadline or iso(T0 + 3600)), '', '## Completion checks', '', *checks, '',
                '## Approval boundaries', '', *(AUTONOMY_FIXED if boundaries is None else boundaries), extra]
        (self.state / 'autonomy.md').write_text('\n'.join(text) + '\n')

    def arm(self, **kw):
        self.ledger(**kw)
        return self.engine.arm_autonomy()

    def auto(self):
        return self.engine.status()['autonomy']

    def worker_running(self, name='busy'):
        """A dispatched card: while it runs, an unchanged turn ends quietly instead of stopping as stalled."""
        self.task(name, files=[name])
        self.engine.dispatch('main', self.lease, name, 'w-' + name, serial='fixture: one card at a time')

    def accept_card(self, name):
        self.task(name, role='investigator', mode='code')
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name, serial='fixture: one card at a time')
        self.engine.report('w-' + name, token, 'Inspected ' + name + '.')
        self.engine.accept('main', self.lease, name)

    def final_review(self):
        """An all-category final review of every card, on the current artifact (SPEC 5.8 item 3)."""
        ids = sorted(self.engine.status()['tasks'])
        path = self.root / ('final-%d.json' % len(ids))
        self.review(path, reviewer='reviewer', tasks=ids, categories=ALL_CATEGORIES, final=True)
        self.engine.record_review('main', self.lease, 'reviewer', path, ALL_CATEGORIES, ids, final=True)

    def stops(self, n):
        """n Stops, each preceded by a newly accepted card so the loop never stalls."""
        for i in range(n):
            self.accept_card('prog-%d-%d' % (len(self.engine.status()['tasks']), i))
            self.assertIsInstance(self.engine.hook_stop(), str)


class AutonomyArmTests(AutonomyFixture):
    def test_arm_refuses_without_an_active_run(self):
        fresh = Engine(self.root / 'other-state', self.repo)
        with self.assertRaisesRegex(EngineError, 'run'):
            fresh.arm_autonomy()
        self.assertFalse((self.root / 'other-state' / 'state.json').exists())
        self.engine.interrupt('main', self.lease)
        self.ledger()
        with self.assertRaisesRegex(EngineError, 'run'):
            self.engine.arm_autonomy()

    def test_missing_ledger_writes_the_template_and_refuses(self):
        with self.assertRaisesRegex(EngineError, 'fill the ledger, then arm again') as raised:
            self.engine.arm_autonomy()
        self.assertIn(str((self.state / 'autonomy.md').resolve()), str(raised.exception))
        text = (self.state / 'autonomy.md').read_text()
        for line in AUTONOMY_FIXED:
            self.assertIn(line, text)
        self.assertIsNone(self.auto())
        with self.assertRaisesRegex(EngineError, 'goal'):  # the template's own placeholders refuse
            self.engine.arm_autonomy()

    def test_placeholder_or_bad_field_refuses_and_names_the_field(self):
        cases = [(dict(goal='<one line goal>'), 'goal'), (dict(passes='<integer>'), 'max_passes'),
                 (dict(passes='0'), 'max_passes'), (dict(passes='21'), 'max_passes'), (dict(passes='two'), 'max_passes'),
                 (dict(stalls='3'), 'max_stalls'), (dict(stalls='0'), 'max_stalls'),
                 (dict(deadline='<ISO 8601 with UTC offset>'), 'deadline'), (dict(deadline='tomorrow'), 'deadline'),
                 (dict(deadline='2027-01-16T00:00:00'), 'deadline'),  # no UTC offset
                 (dict(deadline=iso(T0 - 1)), 'deadline'), (dict(deadline=iso(T0)), 'deadline'),
                 (dict(checks=[]), 'Completion checks'), (dict(checks=['<NAME: argv...>']), 'Completion checks'),
                 (dict(checks=['no colon here']), 'Completion checks'),
                 (dict(checks=['a: true', 'a: true']), 'Completion checks')]
        for kw, field in cases:
            with self.subTest(kw=kw):
                self.ledger(**kw)
                with self.assertRaisesRegex(EngineError, field):
                    self.engine.arm_autonomy()
                self.assertIsNone(self.auto())

    def test_missing_field_refuses(self):
        self.ledger()
        path = self.state / 'autonomy.md'
        path.write_text(path.read_text().replace('goal: ship the fixture\n', ''))
        with self.assertRaisesRegex(EngineError, 'goal'):
            self.engine.arm_autonomy()

    def test_each_fixed_boundary_line_is_required_and_added_lines_are_fine(self):
        for line in AUTONOMY_FIXED:
            with self.subTest(line=line):
                self.ledger(boundaries=[l for l in AUTONOMY_FIXED if l != line])
                with self.assertRaisesRegex(EngineError, 'Approval boundaries'):
                    self.engine.arm_autonomy()
        self.ledger(extra='- Never touch the billing module.')
        self.assertTrue(self.engine.arm_autonomy()['active'])

    def remote(self, name='origin', head=True):
        """A bare remote holding main, fetched, with its HEAD recorded locally or not."""
        bare = self.root / (name + '.git')
        self.git('init', '-q', '--bare', '-b', 'main', str(bare))
        self.git('remote', 'add', name, str(bare))
        self.git('push', '-q', name, 'HEAD:refs/heads/main')
        self.git('fetch', '-q', name)
        if not head:
            subprocess.run(['git', '-C', str(self.repo), 'symbolic-ref', '-d', 'refs/remotes/%s/HEAD' % name],
                           capture_output=True)

    def test_arm_records_a_missing_remote_default_branch(self):
        self.remote(head=False)
        self.ledger()
        heads = self.engine.arm_autonomy()['preconditions']['remote_heads']
        self.assertEqual(heads, 'origin: default branch main (recorded now)')
        self.assertEqual(self.git('symbolic-ref', '--short', 'refs/remotes/origin/HEAD'), 'origin/main')
        self.assertEqual(self.auto()['remote_defaults'], {'origin': 'main'})
        self.assertEqual(self.auto()['remote_push_urls'], {'origin': push_url_digest(str(self.root / 'origin.git'))})  # a digest: URLs may hold tokens
        self.assertEqual(ensure_remote_heads(self.repo), ('origin: default branch main (confirmed)', {'origin': 'main'}))

    def test_arm_refreshes_a_stale_recorded_default_branch(self):
        self.remote()
        self.git('push', '-q', 'origin', 'HEAD:refs/heads/develop')
        subprocess.run(['git', '-C', str(self.root / 'origin.git'), 'symbolic-ref', 'HEAD', 'refs/heads/develop'], check=True)
        self.git('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main')  # the local record is stale
        self.ledger()
        heads = self.engine.arm_autonomy()['preconditions']['remote_heads']
        self.assertEqual(heads, 'origin: default branch develop (was main, updated)')
        self.assertEqual(self.auto()['remote_defaults'], {'origin': 'develop'})

    def test_arm_reports_an_unreachable_remote_and_still_arms(self):
        self.git('remote', 'add', 'gone', str(self.root / 'missing.git'))
        self.git('update-ref', 'refs/remotes/gone/main', 'HEAD')
        self.git('symbolic-ref', 'refs/remotes/gone/HEAD', 'refs/remotes/gone/main')  # recorded, but never trusted alone
        self.ledger()
        receipt = self.engine.arm_autonomy()
        self.assertTrue(receipt['active'])
        self.assertIn('gone: default branch not confirmed', receipt['preconditions']['remote_heads'])
        self.assertIn('pull request pushes to gone are refused', receipt['preconditions']['remote_heads'])
        self.assertEqual(self.auto()['remote_defaults'], {})

    def test_an_arm_whose_session_changed_while_asking_the_remotes_is_refused(self):
        self.ledger()

        def replace_session(repo):  # another coordinator takes over the run during the network step
            self.engine.interrupt('main', self.lease)
            self.engine.open_session('main')
            return 'no remote configured: pull request pushes are refused', {}

        with mock.patch('orchestra_core.engine.ensure_remote_heads', side_effect=replace_session):
            with self.assertRaisesRegex(EngineError, 'session changed while arming'):
                self.engine.arm_autonomy()
        self.assertFalse(self.engine.autonomy_active())

    def test_a_ledger_saved_with_windows_line_ends_arms(self):
        self.ledger()
        path = self.state / 'autonomy.md'
        path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        self.arm()
        self.assertTrue(self.engine.autonomy_active())

    def test_a_second_arm_that_loses_the_race_during_the_remote_step_changes_nothing(self):
        self.ledger()

        def arm_meanwhile(repo):  # another arm completes while this one asks the remotes
            with mock.patch('orchestra_core.engine.ensure_remote_heads', return_value=('none', {})):
                self.engine.arm_autonomy()
            return 'none', {}

        with mock.patch('orchestra_core.engine.ensure_remote_heads', side_effect=arm_meanwhile):
            with self.assertRaisesRegex(EngineError, 'already armed'):
                self.engine.arm_autonomy()
        armed_at = self.auto()['armed_at']
        self.assertTrue(self.engine.autonomy_active())
        self.assertEqual(self.auto()['armed_at'], armed_at)

    def test_a_mismatched_release_pre_authorization_is_refused_before_the_remotes_are_asked(self):
        self.ledger(boundaries=[('- Release: pre-authorized origin elsewhere' if line.startswith('- Release:') else line)
                                for line in AUTONOMY_FIXED])
        before = sorted(p.name for p in self.state.iterdir())
        with mock.patch('orchestra_core.engine.ensure_remote_heads') as ask:
            with self.assertRaisesRegex(EngineError, 'must match policy.release'):
                self.engine.arm_autonomy()
        ask.assert_not_called()
        self.assertEqual(sorted(p.name for p in self.state.iterdir()), before)  # nothing written, no ledger copy

    def test_an_arm_interrupted_while_asking_the_remotes_leaves_autonomy_off(self):
        self.ledger()
        with mock.patch('orchestra_core.engine.ensure_remote_heads', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.engine.arm_autonomy()
        self.assertFalse(self.engine.autonomy_active())
        self.assertIsNone(self.engine.status()['autonomy'])

    def test_arm_without_a_remote_says_pull_requests_are_refused(self):
        self.ledger()
        self.assertEqual(self.engine.arm_autonomy()['preconditions']['remote_heads'],
                         'no remote configured: pull request pushes are refused')
        self.assertEqual(self.auto()['remote_defaults'], {})

    def test_arm_snapshots_stores_fields_and_prints_preconditions(self):
        receipt = self.arm(passes='5', stalls='1')
        self.assertTrue(receipt['active'])
        auto = self.auto()
        self.assertEqual((auto['active'], auto['passes'], auto['stalls'], auto['max_passes'], auto['max_stalls']),
                         (True, 0, 0, 5, 1))
        self.assertEqual(auto['goal'], 'ship the fixture')
        self.assertEqual(auto['deadline'], iso(T0 + 3600))
        self.assertEqual(auto['checks'], [dict(name='fixture', argv=PASS_ARGV)])
        self.assertTrue(Path(auto['ledger']['path']).is_file())
        self.assertIn('permission_mode', receipt['preconditions'])
        self.assertIn('keep-awake', receipt['preconditions']['keep_awake'])

    def test_arm_again_resets_counters_and_clears_the_old_report(self):
        self.arm(deadline=iso(T0 + 60))
        self.task('left-queued')
        self.accept_card('c')
        self.engine.hook_stop()
        self.now[0] = T0 + 61
        self.assertIsNone(self.engine.hook_stop())  # the deadline ends the run; the queued card does not
        self.assertEqual(self.auto()['last_stop_reason'], 'deadline')
        self.assertIsNotNone(self.engine.autonomy_report())
        self.arm()
        self.assertIsNone(self.engine.autonomy_report())
        self.assertEqual((self.auto()['passes'], self.auto()['active']), (0, True))

    def test_status_has_the_documented_keys_and_never_the_lease(self):
        idle = self.engine.autonomy_status()
        self.assertRegex(idle.pop('signature'), r'^[0-9a-f]{64}$')
        self.assertEqual(idle, dict(active=False, passes=None, max_passes=None, stalls=None,
                         max_stalls=None, deadline=None, parked=[], last_stop_reason=None, pull_requests=False,
                         running=0, silent=[]))
        self.arm(passes='4')
        self.task('p')
        self.engine.park('main', self.lease, 'p', 'needs a push')
        status = self.engine.autonomy_status()
        self.assertEqual(set(status), {'active', 'passes', 'max_passes', 'stalls', 'max_stalls', 'deadline', 'parked',
                                       'last_stop_reason', 'signature', 'pull_requests', 'running', 'silent'})
        self.assertEqual((status['active'], status['max_passes'], status['parked']), (True, 4, [{'id': 'p', 'reason': 'needs a push'}]))
        self.assertNotIn(self.lease, json.dumps(status))

    def test_template_carries_the_fields_and_the_fixed_lines(self):
        template = (Path(__file__).resolve().parents[1] / 'plugins/orchestra/config/autonomy-template.md').read_text()
        for line in AUTONOMY_FIXED:
            self.assertIn(line, template)
        for field in ('goal:', 'deadline:', '## Completion checks', '## Approval boundaries'):
            self.assertIn(field, template)
        self.assertNotIn('max_passes', template)
        self.assertNotIn('max_stalls', template)
        self.assertIn('The Release line overrides Push and Engine-gated actions for that remote and target only.', template)
        self.assertEqual(len(AUTONOMY_FIXED), 6)
        for old in ('no deletion of files, branches or tags', 'push only a feature branch', 'no pull request merge'):
            self.assertNotIn(old, template)  # the pre-2.11 Merge, Push and Deletion lines are gone


class AutonomyLoopTests(AutonomyFixture):
    def test_a_recorded_pull_request_is_listed_for_the_owner(self):
        self.arm()
        for bad in ('not a url', 'https:///pull/1', 'https://?', 'ftp://example.invalid/pull/1', 'https://host/a b', ''):
            with self.subTest(url=bad), self.assertRaisesRegex(EngineError, 'http'):
                self.engine.record_pr('main', self.lease, bad)
        with self.assertRaisesRegex(EngineError, 'lease|Lease|coordinator'):
            self.engine.record_pr('main', 'wrong', 'https://example.invalid/pull/1')
        url = 'https://example.invalid/pull/1'
        with mock.patch('orchestra_core.engine.shutil.which', return_value=None):  # no gh: recorded, unverified
            first = self.engine.record_pr('main', self.lease, url)
            self.assertEqual([e['url'] for e in first], [url])
            self.assertEqual(self.engine.record_pr('main', self.lease, url + ' '), first)  # once
        self.engine.disarm_autonomy()
        self.assertIn('  - review and merge pull request ' + url, self.engine.status()['last_brief']['text'])

    def test_a_stalled_stop_lists_the_unfinished_cards(self):
        self.arm()
        self.task('x')
        self.assertIsInstance(self.engine.hook_stop(), str)
        self.assertIn('x queued', self.engine.hook_stop())  # the nudge carries the board
        self.assertIn('x queued', self.engine.hook_stop())
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.auto()['last_stop_reason'], 'needs-owner:escalated')
        brief = self.engine.status()['last_brief']['text']
        self.assertIn('- stop reason: needs-owner:escalated', brief)
        self.assertIn('x: needs-owner:escalated', brief)

    def test_stop_continues_inside_the_bounds_and_counts_passes(self):
        self.arm(passes='3')
        self.task('x')
        reason = self.engine.hook_stop()
        self.assertIn('Autonomy pass 1', reason)
        self.assertNotIn('of 3', reason)
        self.assertIn('park any card that reaches an approval boundary', reason)
        self.assertEqual(self.auto()['passes'], 1)

    def test_unarmed_and_inactive_stop_is_silent_and_writes_nothing(self):
        self.task('x')
        before = self.engine.state_path.read_bytes()
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(before, self.engine.state_path.read_bytes())

    def test_a_newly_accepted_card_resets_the_stall_count(self):
        self.arm(passes='9', stalls='2')
        self.task('x')
        self.worker_running()
        self.engine.hook_stop()
        self.engine.hook_stop()  # stalls 1
        self.assertEqual(self.auto()['stalls'], 1)
        self.accept_card('z')
        self.assertIsNotNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['stalls'], self.auto()['active']), (0, True))

    def test_deadline_stops(self):
        self.arm(deadline=iso(T0 + 60))
        self.task('x')
        self.assertIsNotNone(self.engine.hook_stop())
        self.now[0] = T0 + 60.5
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.auto()['last_stop_reason'], 'deadline')

    def test_completion_stops_only_with_a_passed_intact_gate_on_the_current_artifact(self):
        def not_complete():  # every card accepted but not complete: the final phase continues the turn
            self.assertIn('every card is accepted', self.engine.hook_stop())
            self.assertEqual((self.auto()['active'], self.auto().get('last_stop_reason')), (True, None))

        self.arm(passes='9')
        self.accept_card('x')  # SPEC 5.8 item 3: every card accepted and a final review, so only the gate decides
        self.final_review()
        not_complete()  # no gate receipt yet
        other = self.engine.run_gate('main', self.lease, 'fixture', [sys.executable, '-c', 'print("different")'])
        self.assertTrue(other['passed'])
        not_complete()  # same name, different argv
        self.engine.run_gate('main', self.lease, 'unrelated', PASS_ARGV)
        not_complete()  # same argv, different name
        self.assertTrue(self.engine.run_gate('main', self.lease, 'fixture', PASS_ARGV)['passed'])
        (self.repo / 'a').write_text('edited after the gate')
        self.final_review()
        not_complete()  # stale: the artifact moved on
        self.assertTrue(self.engine.run_gate('main', self.lease, 'fixture', PASS_ARGV)['passed'])
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.auto()['last_stop_reason'], 'complete')

    def test_a_tampered_gate_log_is_not_completion(self):
        self.arm(passes='9')
        self.task('x')
        receipt = self.engine.run_gate('main', self.lease, 'fixture', PASS_ARGV)
        Path(receipt['path']).write_text('forged')
        self.assertIsNotNone(self.engine.hook_stop())

    def test_a_failed_gate_is_not_completion(self):
        self.arm(passes='9', checks=['fixture: ' + shlex.join([sys.executable, '-c', 'raise SystemExit(3)'])])
        self.task('x')
        receipt = self.engine.run_gate('main', self.lease, 'fixture', [sys.executable, '-c', 'raise SystemExit(3)'])
        self.assertFalse(receipt['passed'])
        self.assertIsNotNone(self.engine.hook_stop())

    def test_parked_only_stops(self):
        self.arm(passes='9')
        self.accept_card('done')
        self.task('p')
        self.engine.park('main', self.lease, 'p', 'needs-owner: a push')
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.auto()['last_stop_reason'], 'parked-only')

    def test_a_card_blocked_behind_a_parked_dependency_is_parked_only(self):
        self.arm(passes='9')
        self.task('p')
        self.task('dep', dependencies=['p'])
        self.engine.park('main', self.lease, 'p', 'needs-owner: boundary')
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.auto()['last_stop_reason'], 'parked-only')

    def test_no_ready_card_replans_and_only_then_hands_the_run_to_the_owner(self):
        self.arm(passes='9')  # an empty board and no change since the base: nothing to do
        self.assertIn('Re-plan', self.engine.hook_stop())
        self.assertIsNone(self.auto().get('last_stop_reason'))
        self.assertIn('still nothing to do', self.engine.hook_stop())
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.auto()['last_stop_reason'], 'needs-owner:escalated')

    def test_every_card_accepted_continues_into_the_final_phase_then_escalates(self):
        self.arm(passes='9')
        self.accept_card('done')
        reason = self.engine.hook_stop()
        self.assertIn('Autonomy pass 1: every card is accepted; commit the work, run the final review', reason)
        self.assertIn('open the pull request', reason)
        self.assertIn('changed nothing', self.engine.hook_stop())  # nothing changed and no worker runs: a different nudge
        self.assertIn('still nothing changed', self.engine.hook_stop())
        self.assertIsNone(self.engine.hook_stop())  # still unchanged: the owner takes over, with a brief
        self.assertEqual((self.auto()['active'], self.auto()['last_stop_reason']), (False, 'needs-owner:escalated'))
        self.assertIn('- stop reason: needs-owner:escalated', self.engine.brief())

    def test_empty_board_with_changed_files_owes_the_final_phase(self):
        self.arm(passes='9')
        (self.repo / 'a').write_text('inline work without a card')
        self.assertIn('every card is accepted', self.engine.hook_stop())

    def test_inline_card_is_actionable_not_running(self):
        self.arm()
        self.task('x')
        self.engine.start_inline('main', self.lease, 'x')
        self.assertIn('Autonomy pass 1: continue', self.engine.hook_stop())

    def test_reported_card_under_a_running_reviewer_waits_quietly(self):
        self.arm()
        self.task('B1')
        self.engine.report('w', self.engine.dispatch('main', self.lease, 'B1', 'w'), done())
        self.task('crit', role='critic', mode='judge', files=[], review_of=['B1'])
        self.engine.dispatch('main', self.lease, 'crit', 'critic-w')
        self.assertIsNone(self.engine.hook_stop())
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['passes'], self.auto()['stalls'], self.auto()['active']), (0, 0, True))

    def test_park_then_unpark_in_one_turn_is_progress(self):
        self.arm()
        self.task('x')
        self.task('y')
        self.assertIn('Autonomy pass 1:', self.engine.hook_stop())
        self.engine.park('main', self.lease, 'x', 'boundary')
        self.engine.unpark('main', self.lease, 'x')
        self.assertIn('Autonomy pass 2:', self.engine.hook_stop())
        self.assertEqual(self.auto()['stalls'], 0)

    def test_running_cards_end_the_turn_and_reported_cards_continue_it(self):
        self.arm(passes='9')
        self.task('x')
        token = self.engine.dispatch('main', self.lease, 'x', 'w')
        self.assertIsNone(self.engine.hook_stop())  # only a worker running: the harness wakes the session later
        self.assertEqual((self.auto()['passes'], self.auto()['active'], self.auto().get('last_stop_reason')), (0, True, None))
        self.engine.report('w', token, done('Inspected x.'))
        self.assertIn('Autonomy pass 1:', self.engine.hook_stop())

    def test_a_continuation_is_not_repeated_for_an_unchanged_board(self):
        self.arm()
        self.task('x')
        self.worker_running()
        self.assertIn('Autonomy pass 1:', self.engine.hook_stop())
        self.assertIsNone(self.engine.hook_stop())  # nothing changed: the turn ends instead of the same re-prompt
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['passes'], self.auto()['stalls'], self.auto()['active']), (1, 2, True))
        self.task('y')
        self.assertIn('Autonomy pass 2:', self.engine.hook_stop())
        self.assertEqual(self.auto()['stalls'], 0)

    def test_tampered_ledger_stops(self):
        self.arm(passes='9')
        self.task('x')
        self.assertIsNotNone(self.engine.hook_stop())
        with (self.state / 'autonomy.md').open('a') as out:
            out.write('- Quietly allow pushes.\n')
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['last_stop_reason'], self.auto()['active']), ('ledger-tampered', False))

    def test_a_deleted_snapshot_stops_as_tampered(self):
        self.arm(passes='9')
        self.task('x')
        Path(self.auto()['ledger']['path']).unlink()
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.auto()['last_stop_reason'], 'ledger-tampered')


class AutonomyParkTests(AutonomyFixture):
    def test_park_drops_assignment_reservation_and_capacity(self):
        self.task('a1', files=['shared'])
        self.task('a2', files=['shared'])
        self.task('dep', dependencies=['a1'])
        token = self.engine.dispatch('main', self.lease, 'a1', 'w1')
        self.assertEqual(self.engine.ready('main', self.lease), [])  # a2 collides with the running a1
        self.engine.park('main', self.lease, 'a1', 'needs a push')
        card = self.engine.status()['tasks']['a1']
        self.assertEqual((card['state'], card['parked_reason']), ('parked', 'needs a push'))
        for key in ('assignment', 'worker', 'inline', 'report'):
            self.assertNotIn(key, card)
        self.assertEqual(self.engine.ready('main', self.lease), ['a2'])  # reservation released, dep still blocked
        with self.assertRaises(EngineError):
            self.engine.report('w1', token, done('late report'))
        self.engine.dispatch('main', self.lease, 'a2', 'w1')  # the worker name is free again

    def test_park_a_reported_card_and_unpark_returns_it_to_the_queue(self):
        self.task('a')
        token = self.engine.dispatch('main', self.lease, 'a', 'w')
        self.engine.report('w', token, done('Inspected a.'))
        self.engine.park('main', self.lease, 'a', 'boundary')
        self.assertNotIn('report', self.engine.status()['tasks']['a'])
        self.engine.unpark('main', self.lease, 'a')
        card = self.engine.status()['tasks']['a']
        self.assertEqual(card['state'], 'queued')
        self.assertNotIn('parked_reason', card)
        self.assertEqual(self.engine.ready('main', self.lease), ['a'])

    def test_park_and_unpark_validate(self):
        self.task('a')
        self.accept_card('done')
        for args in [('done', 'why'), ('nope', 'why'), ('a', ''), ('a', '   ')]:
            with self.subTest(args=args), self.assertRaises(EngineError):
                self.engine.park('main', self.lease, *args)
        with self.assertRaises(EngineError):
            self.engine.park('main', 'wrong-lease', 'a', 'why')
        with self.assertRaises(EngineError):
            self.engine.unpark('main', self.lease, 'a')  # not parked
        self.engine.park('main', self.lease, 'a', 'why')
        with self.assertRaises(EngineError):
            self.engine.park('main', self.lease, 'a', 'again')
        with self.assertRaises(EngineError):
            self.engine.unpark('main', 'wrong-lease', 'a')

    def test_a_card_under_repair_cannot_be_parked(self):
        self.task('a')
        token = self.engine.dispatch('main', self.lease, 'a', 'w')
        self.engine.report('w', token, done('Implemented a.'))
        self.allow_review()
        report = self.root / 'r.json'
        self.review(report, tasks=['a'], findings=['bug'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'], findings=['bug'])
        self.task('fix', mode='repair', files=['fix'], repair_of='a')
        with self.assertRaises(EngineError):
            self.engine.park('main', self.lease, 'a', 'why')

    def repaired(self):
        """A reported card whose repair card `repair-of-a` has reported too: `a` is reported with `repaired_by`."""
        self.task('a')
        token = self.engine.dispatch('main', self.lease, 'a', 'w')
        self.engine.report('w', token, done('Implemented a.'))
        self.allow_review()
        report = self.root / 'r.json'
        self.review(report, tasks=['a'], findings=['bug'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'], findings=['bug'])
        self.task('repair-of-a', mode='repair', files=['fix'], repair_of='a')
        token = self.engine.dispatch('main', self.lease, 'repair-of-a', 'w2')
        self.engine.report('w2', token, done('Repaired a.'))
        self.assertEqual(self.engine.status()['tasks']['a']['state'], 'reported')

    def test_o30_parking_a_reported_card_under_repair_names_its_open_repair(self):
        self.repaired()
        with self.assertRaisesRegex(EngineError, 'repair-of-a'):
            self.engine.park('main', self.lease, 'a', 'why')
        self.assertEqual(self.engine.status()['tasks']['a']['state'], 'reported')

    def test_o30_a_card_whose_open_repair_is_parked_stops_parked_only(self):
        self.arm(passes='9')
        self.repaired()
        self.engine.park('main', self.lease, 'repair-of-a', 'needs-owner: a push')
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.auto()['last_stop_reason'], 'parked-only')

    def test_unparking_a_parked_reported_repair_card_resumes_the_chain(self):
        self.repaired()
        self.engine.park('main', self.lease, 'repair-of-a', 'needs a push')
        self.assertEqual(self.engine.status()['tasks']['a']['state'], 'repairing')
        self.engine.unpark('main', self.lease, 'repair-of-a')
        self.assertEqual(self.engine.ready('main', self.lease), ['repair-of-a'])
        token = self.engine.dispatch('main', self.lease, 'repair-of-a', 'w3')
        self.engine.report('w3', token, done('Repaired a again.'))
        report = self.root / 'clean.json'
        self.review(report, tasks=['a', 'repair-of-a'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a', 'repair-of-a'])
        self.engine.accept('main', self.lease, 'repair-of-a')
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual(self.engine.status()['tasks']['a']['state'], 'accepted')

    def test_parked_cards_block_finish(self):
        self.task('a', role='investigator', mode='code')
        self.engine.park('main', self.lease, 'a', 'why')
        with self.assertRaisesRegex(EngineError, 'accepted'):
            self.engine.close_session('main', self.lease)
        self.assertTrue(self.engine.status()['session']['active'])


class AutonomyBoundaryTests(AutonomyFixture):
    def setUp(self):
        super().setUp()
        self.fresh(dict(release=dict(enabled=True, authorization='user request', remote='devops', target='main',
                                     argv=['git', 'push', 'devops', 'HEAD:main'])))

    def test_permit_and_release_refuse_while_autonomy_is_active(self):
        self.arm()
        self.assertTrue(self.engine.autonomy_active())
        with self.assertRaisesRegex(EngineError, 'autonomy'):
            self.engine.release_permit('main', self.lease, 'devops', 'main')
        with self.assertRaisesRegex(EngineError, 'autonomy'):
            self.engine.check_release('devops', 'main', argv=['git', 'push', 'devops', 'HEAD:main'])
        self.engine.disarm_autonomy()
        self.assertFalse(self.engine.autonomy_active())
        with self.assertRaises(EngineError) as raised:  # now the ordinary evidence refusal
            self.engine.release_permit('main', self.lease, 'devops', 'main')
        self.assertNotIn('autonomy', str(raised.exception))

    def test_autonomy_active_needs_an_active_session(self):
        self.arm()
        self.engine.interrupt('main', self.lease)
        self.assertFalse(self.engine.autonomy_active())

    def test_interrupt_and_session_end_stop_autonomy_and_keep_the_report(self):
        def stopped(reason):
            auto = self.auto()
            self.assertEqual((auto['active'], auto['last_stop_reason'], auto['report']['reason']), (False, reason, reason))

        self.arm()
        self.engine.interrupt('main', self.lease)
        stopped('interrupted')
        self.engine.open_session('main', harness_session='S')
        self.arm()  # a new arm replaces the kept report
        self.engine.end_harness_session('S')
        stopped('ended')
        self.engine.open_session('main')
        self.arm()
        self.engine.interrupt_active()
        stopped('interrupted')


class AutonomyReportTests(AutonomyFixture):
    def test_stop_writes_the_morning_report_with_accepted_parked_and_failures(self):
        self.engine.run_gate('main', self.lease, 'old-failure', [sys.executable, '-c', 'raise SystemExit(4)'])
        self.arm(deadline=iso(T0 + 60))
        self.accept_card('done')
        self.task('p')
        self.engine.park('main', self.lease, 'p', 'needs a push')
        self.task('b')
        token = self.engine.dispatch('main', self.lease, 'b', 'wb')
        self.engine.report('wb', token, done('Implemented b.'))
        report = self.root / 'r.json'
        self.review(report, reviewer='rev-1', tasks=['b'], findings=['off by one'])
        self.allow_review('rev-1')
        self.engine.record_review('main', self.lease, 'rev-1', report, ['correctness'], ['b'], findings=['off by one'])
        self.assertFalse(self.engine.run_gate('main', self.lease, 'unit', [sys.executable, '-c', 'raise SystemExit(3)'])['passed'])
        self.assertIsNotNone(self.engine.hook_stop())
        self.now[0] = T0 + 61
        self.assertIsNone(self.engine.hook_stop())
        progress = (self.state / 'progress.md').read_text()
        self.assertIn('## Run brief 2027-01-15T08:01:01', progress)
        for fragment in ('deadline', 'passes: 1', 'done (investigator/code)', 'p: needs a push',
                         'unit', 'exit 3', 'BLOCKED', 'rev-1', 'off by one'):
            self.assertIn(fragment, progress)
        self.assertNotIn('old-failure', progress)  # failures recorded before arm are not this run's
        stored = self.engine.autonomy_report()
        self.assertEqual(stored['reason'], 'deadline')
        self.assertEqual(stored['text'], progress[progress.index('## Run brief'):].strip())  # the fixture's serial start comes first
        self.assertEqual(stored['path'], str(self.engine.state_dir / 'progress.md'))

    def test_report_appends_and_keeps_earlier_progress_lines(self):
        (self.state / 'progress.md').write_text('# Plan X\nearlier line\n')
        self.arm(deadline=iso(T0 + 60))
        self.task('left-queued')
        self.accept_card('done')
        self.engine.hook_stop()
        self.now[0] = T0 + 61
        self.engine.hook_stop()
        text = (self.state / 'progress.md').read_text()
        self.assertTrue(text.startswith('# Plan X\nearlier line\n'))
        self.assertEqual(text.count('## Run brief'), 1)

    def test_disarm_records_the_reason_writes_the_report_and_clears_the_shown_one(self):
        self.arm(deadline=iso(T0 + 60))
        self.task('left-queued')
        self.accept_card('done')
        self.engine.hook_stop()
        self.now[0] = T0 + 61
        self.engine.hook_stop()  # the deadline report is now shown
        self.assertIsNotNone(self.engine.autonomy_report())
        self.assertFalse(self.engine.disarm_autonomy()['was_active'])
        self.assertIsNone(self.engine.autonomy_report())
        self.assertEqual(self.engine.autonomy_status()['last_stop_reason'], 'deadline')
        self.assertEqual((self.state / 'progress.md').read_text().count('## Run brief'), 1)
        self.arm(deadline=iso(self.now[0] + 3600))
        result = self.engine.disarm_autonomy()
        self.assertTrue(result['was_active'])
        self.assertIn('disarmed', result['text'])
        self.assertEqual((self.engine.autonomy_status()['active'], self.engine.autonomy_status()['last_stop_reason']), (False, 'disarmed'))
        self.assertEqual((self.state / 'progress.md').read_text().count('## Run brief'), 2)
        stored = self.engine.autonomy_report()  # SPEC 12.6: the disarm report is stored like any stop's
        self.assertEqual((stored['reason'], stored['text']), ('disarmed', result['text']))
        self.assertFalse(self.engine.disarm_autonomy()['was_active'])  # a later disarm clears it
        self.assertIsNone(self.engine.autonomy_report())

    def test_disarm_is_safe_at_any_time(self):
        fresh = Engine(self.root / 'fresh-state', self.repo)
        self.assertFalse(fresh.disarm_autonomy()['was_active'])
        self.assertFalse((self.root / 'fresh-state' / 'state.json').exists())
        before = self.engine.state_path.read_bytes()
        self.assertFalse(self.engine.disarm_autonomy()['was_active'])
        self.assertEqual(before, self.engine.state_path.read_bytes())
        self.assertFalse((self.state / 'progress.md').exists())

    def test_report_survives_interrupt_until_the_next_arm(self):
        self.arm(deadline=iso(T0 + 60))
        self.task('left-queued')
        self.accept_card('done')
        self.engine.hook_stop()
        self.now[0] = T0 + 61
        self.engine.hook_stop()
        stop_brief = self.engine.status()['last_brief']
        self.engine.interrupt('main', self.lease)
        self.assertEqual(self.engine.autonomy_report()['reason'], 'deadline')
        self.assertEqual(self.engine.status()['last_brief'], stop_brief)  # SPEC 5.9 item 2: the kept stop brief stays
        self.assertEqual(stop_brief['reason'], 'deadline')
        self.assertEqual(self.engine.status()['last_brief']['reason'], 'deadline')
        self.assertFalse(self.engine.autonomy_active())
        self.assertFalse(self.engine.autonomy_status()['active'])

    def test_a_malformed_autonomy_state_is_rejected(self):
        state = json.loads(self.engine.state_path.read_text())
        state['autonomy'] = {'active': 'yes'}
        self.engine.state_path.write_text(json.dumps(state))
        with self.assertRaises(EngineError):
            self.engine.status()


class MaterialityTests(EngineFixture):
    """SPEC 5.6 items 2 to 4, 5.13 items 1 and 2, and 5.17."""

    def reported(self, name='a', **kw):
        self.task(name, **kw)
        self.engine.report('w' + name, self.engine.dispatch('main', self.lease, name, 'w' + name), done('checked'))

    def issues_review(self, name, tasks, issues, findings=None, verdict=None):
        path = self.root / (name + '.json')
        blocking = [i['text'] for i in issues or [] if i.get('severity') == 'blocking']
        findings = blocking if findings is None else findings
        body = dict(reviewer='reviewer', categories=['correctness'], tasks=tasks, findings=findings, final=False,
                    verdict=verdict or ('BLOCKED' if findings else 'CLEAN'),
                    artifact=self.engine.artifact(self.engine.scope_for(tasks)),
                    summary='Behavior checked against acceptance criteria.')
        if issues is not None:
            body['issues'] = issues
        path.write_text(json.dumps(body))
        return path, findings

    def record(self, name, tasks, issues, findings=None, verdict=None):
        self.allow_review()
        path, findings = self.issues_review(name, tasks, issues, findings, verdict)
        return self.engine.record_review('main', self.lease, 'reviewer', path, ['correctness'], tasks, findings=findings)

    def brief(self, name, text):
        path = self.root / name
        path.write_text(text)
        return str(path)

    def drop_rev(self, name):
        state = json.loads(self.engine.state_path.read_text())
        state['tasks'][name].pop('rev')
        self.engine.state_path.write_text(json.dumps(state))

    def test_notes_only_report_is_clean_and_accepts(self):
        self.reported('a')
        notes = [dict(text='Rename helper', severity='note'), dict(text='Trailing comment', severity='note')]
        receipt = self.record('r', ['a'], notes)
        self.assertEqual([], receipt['findings'])
        self.assertEqual(['Rename helper', 'Trailing comment'], receipt['notes'])
        self.assertEqual('CLEAN', json.loads(Path(receipt['path']).read_text())['verdict'])
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def test_blocking_issue_needs_impact(self):
        self.reported('a')
        for impact in ['', '  ', None]:
            issue = dict(text='Bug', severity='blocking')
            if impact is not None:
                issue['impact'] = impact
            with self.assertRaisesRegex(EngineError, 'impact'):
                self.record('r', ['a'], [issue])
        self.record('ok', ['a'], [dict(text='Bug', severity='blocking', impact='Named test fails')])

    def test_issues_must_match_findings_and_verdict(self):
        self.reported('a')
        blocking = dict(text='Bug', severity='blocking', impact='Named requirement unmet')
        with self.assertRaisesRegex(EngineError, 'blocking'):
            self.record('differs', ['a'], [blocking], findings=['Other text'])
        with self.assertRaises(EngineError):
            self.record('clean-with-blocking', ['a'], [blocking], findings=[], verdict='CLEAN')
        with self.assertRaises(EngineError):
            self.record('note-as-finding', ['a'], [dict(text='Nit', severity='note')], findings=['Nit'])
        with self.assertRaises(EngineError):
            self.record('bad-severity', ['a'], [dict(text='Nit', severity='major', impact='x')])
        self.assertEqual([], self.engine.status()['reviews'])

    def test_repair_refused_for_notes_only(self):
        self.reported('a')
        self.record('r', ['a'], [dict(text='Nit', severity='note')])
        with self.assertRaisesRegex(EngineError, 'Repair needs earlier checked coding findings'):
            self.task('fix', mode='repair', files=['a'], repair_of='a')

    def test_review_of_2_2_card_without_issues_refused(self):
        self.reported('a')
        self.assertEqual('2.2', self.engine.status()['tasks']['a']['rev'])
        with self.assertRaisesRegex(EngineError, 'Review needs `issues`'):
            self.record('r', ['a'], None)
        with self.assertRaisesRegex(EngineError, 'Review needs `issues`'):
            self.record('r2', ['a'], None, findings=['bug'])

    def test_review_of_migrated_card_keeps_string_findings(self):
        self.reported('a')
        self.drop_rev('a')
        receipt = self.record('r', ['a'], None, findings=['bug'])
        self.assertEqual(['bug'], receipt['findings'])
        self.assertEqual([], receipt['notes'])
        with self.assertRaisesRegex(EngineError, 'findings'):
            self.engine.accept('main', self.lease, 'a')

    def test_clean_report_with_empty_issues_accepts(self):
        self.reported('a')
        receipt = self.record('r', ['a'], [])
        self.assertEqual([], receipt['findings'])
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def test_builder_brief_without_keep_remove_refused_at_add(self):
        for name, text, missing in [('none.md', 'Mode: implementation\nObjective.\n', '## Keep'),
                                    ('keep-only.md', 'Mode: implementation\n## Keep\nnone\n', '## Remove'),
                                    ('remove-only.md', 'Mode: implementation\n## Remove\nnone\n', '## Keep')]:
            with self.assertRaisesRegex(EngineError, missing, msg=name):
                self.task(name, brief=self.brief(name, text))
        self.assertEqual({}, self.engine.status()['tasks'])

    def test_builder_brief_with_none_lists_accepted(self):
        self.task('a', brief=self.brief('ok.md', 'Mode: implementation\nObjective.\n## Keep\nnone\n## Remove\nnone\n'))
        self.assertIn('a', self.engine.status()['tasks'])

    def test_queued_2_1_builder_without_headings_still_dispatches(self):
        path = self.brief('old.md', 'Mode: implementation\nObjective.\n')
        self.task('old')  # stored without a brief, then given a 2.1 brief that has no headings
        state = json.loads(self.engine.state_path.read_text())
        state['tasks']['old'].update(brief=path)
        state['tasks']['old'].pop('rev')
        self.engine.state_path.write_text(json.dumps(state))
        self.engine.dispatch('main', self.lease, 'old', 'worker')
        self.assertEqual('running', self.engine.status()['tasks']['old']['state'])

    def test_reviewer_brief_needs_no_keep_remove(self):
        self.task('B1')
        self.task('V1', role='code-reviewer', mode='final', files=[], review_of=['B1'],
                  brief=self.brief('rev.md', 'Mode: final\nObjective.\n'))
        self.assertIn('V1', self.engine.status()['tasks'])

    def two_reviews(self, resources1=(), resources2=()):
        self.reported('B1')
        self.task('V1', role='critic', mode='spec', files=['a'], resources=list(resources1), review_of=['B1'])
        self.task('V2', role='critic', mode='spec', files=['a'], resources=list(resources2), review_of=['B1'])
        self.engine.dispatch('main', self.lease, 'V1', 'review-1', serial='fixture: one card at a time')

    def test_two_read_only_reviews_on_same_file_do_not_collide(self):
        self.two_reviews()
        self.assertEqual(['V2'], self.engine.ready('main', self.lease))
        self.engine.dispatch('main', self.lease, 'V2', 'review-2')

    def test_read_only_reviews_sharing_a_resource_still_collide(self):
        self.two_reviews(['db'], ['db'])
        self.assertEqual([], self.engine.ready('main', self.lease))
        with self.assertRaises(EngineError):
            self.engine.dispatch('main', self.lease, 'V2', 'review-2')

    def test_review_still_collides_with_running_writer(self):
        self.task('B0', files=['x'])
        self.engine.report('w0', self.engine.dispatch('main', self.lease, 'B0', 'w0'), done('checked'))
        self.task('W', files=['a'])
        self.engine.dispatch('main', self.lease, 'W', 'writer')
        self.task('V', role='critic', mode='spec', files=['a'], review_of=['B0'])
        self.assertEqual([], self.engine.ready('main', self.lease))


class AutonomyPreconditionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home'
        self.repo = Path(self.tmp.name) / 'repo'
        for d in (self.home / '.claude', self.repo / '.claude'):
            d.mkdir(parents=True)

    def report(self):
        return autonomy_preconditions(self.repo, home=self.home)

    def write(self, where, mode):
        path = {'user': self.home / '.claude/settings.json', 'project': self.repo / '.claude/settings.json',
                'local': self.repo / '.claude/settings.local.json'}[where]
        path.write_text(json.dumps({'permissions': {'defaultMode': mode}}))

    def test_unknown_when_no_settings_name_a_mode(self):
        out = self.report()
        self.assertTrue(out['permission_mode'].startswith('unknown'))
        self.assertIn('warning', out['permission_mode'].lower())
        self.assertIn('keep-awake', out['keep_awake'])

    def test_local_beats_project_beats_user(self):
        self.write('user', 'default')
        self.assertIn('default', self.report()['permission_mode'])
        self.write('project', 'acceptEdits')
        self.assertIn('acceptEdits', self.report()['permission_mode'])
        self.write('local', 'bypassPermissions')
        out = self.report()['permission_mode']
        self.assertIn('bypassPermissions', out)
        self.assertNotIn('warning', out.lower())

    def test_a_prompting_mode_warns_and_a_skipping_mode_does_not(self):
        self.write('user', 'default')
        self.assertIn('warning', self.report()['permission_mode'].lower())
        self.write('user', 'bypassPermissions')
        self.assertNotIn('warning', self.report()['permission_mode'].lower())

    def test_unreadable_settings_are_skipped_and_nothing_is_written(self):
        (self.repo / '.claude/settings.local.json').write_text('{not json')
        self.write('user', 'bypassPermissions')
        before = sorted(p.name for p in self.repo.rglob('*'))
        self.assertIn('bypassPermissions', self.report()['permission_mode'])
        self.assertEqual(before, sorted(p.name for p in self.repo.rglob('*')))

    def test_report_names_only_the_claude_permission_mode_and_keep_awake(self):
        self.assertEqual(sorted(self.report()), ['keep_awake', 'permission_mode'])


if __name__ == '__main__':
    unittest.main()


class FindingsLedgerTests(EngineFixture):
    """SPEC 5.12, 5.7 items 2 to 4, 5.11 items 1 and 2, 5.4 item 3, 5.14 item 5."""

    GATE = [sys.executable, '-c', 'print("ok")']

    def reported(self, name='a'):
        self.task(name)
        token = self.engine.dispatch('main', self.lease, name, 'worker-' + name)
        self.engine.report('worker-' + name, token, done('done'))

    def record(self, name, tasks, final=False, findings=None, categories=None, **extra):
        from orchestra_core.engine import CATEGORIES
        categories = categories or (CATEGORIES if final else ['correctness'])
        if final:
            tasks = sorted(self.engine.status()['tasks'])
        else:
            self.allow_review(name)
        path = self.root / (name + '.json')
        self.review(path, reviewer=name, tasks=tasks, categories=categories, findings=findings, final=final)
        body = json.loads(path.read_text())
        body.update(extra)
        path.write_text(json.dumps(body))
        return self.engine.record_review('main', self.lease, name, path, categories, tasks,
                                         final=final, findings=findings)

    def final_with_items(self, items, name='final'):
        self.reported()
        return self.record(name, ['a'], final=True, out_of_scope=items)

    def test_finding_add_requires_lease_and_known_review(self):
        self.reported()
        receipt = self.record('r', ['a'], findings=['Empty input crashes'])
        with self.assertRaises(EngineError):
            self.engine.add_finding('main', 'wrong-lease', receipt['id'], 'finding', 0, 'rejected', 'not a bug')
        with self.assertRaises(EngineError):
            self.engine.add_finding('main', self.lease, 'missing', 'finding', 0, 'rejected', 'not a bug')
        entry = self.engine.add_finding('main', self.lease, receipt['id'], 'finding', 0, 'rejected', 'not a bug')
        self.assertEqual('Empty input crashes', entry['text'])
        self.assertEqual({'review': receipt['id'], 'kind': 'finding', 'index': 0}, entry['source'])
        self.assertEqual([entry], self.engine.list_findings())

    def test_finding_list_for_brief_renders_known_findings(self):
        self.reported()
        receipt = self.record('r', ['a'], findings=['Empty input crashes'])
        entry = self.engine.add_finding('main', self.lease, receipt['id'], 'finding', 0, 'deferred', 'wait for the schema')
        block = self.engine.list_findings(for_brief=True)
        for part in ('Known findings', entry['id'], 'Empty input crashes', 'deferred', 'wait for the schema'):
            self.assertIn(part, block)

    def test_rejected_finding_does_not_allow_accept(self):
        self.reported()
        receipt = self.record('r', ['a'], findings=['Empty input crashes'])
        self.engine.add_finding('main', self.lease, receipt['id'], 'finding', 0, 'rejected', 'not a bug')
        with self.assertRaisesRegex(EngineError, 'current review findings'):
            self.engine.accept('main', self.lease, 'a')

    def test_2_1_state_without_findings_loads(self):
        self.reported()
        state = json.loads(self.engine.state_path.read_text())
        self.assertNotIn('findings', state)
        self.assertEqual([], self.engine.list_findings())
        self.assertIn('Known findings', self.engine.list_findings(for_brief=True))
        state['findings'] = []
        self.engine.state_path.write_text(json.dumps(state))
        self.assertEqual([], self.engine.list_findings())

    def test_finding_add_rejects_bad_disposition_and_index(self):
        self.reported()
        receipt = self.record('r', ['a'], findings=['Empty input crashes'])
        for kind, index, disposition in [('finding', 0, 'inline-fixed'), ('finding', 0, 'brief-later'),
                                         ('finding', 1, 'rejected'), ('finding', -1, 'rejected'),
                                         ('finding', True, 'rejected'), ('finding', '0', 'rejected'),
                                         ('out_of_scope', 0, 'inline'), ('nonsense', 0, 'rejected')]:
            with self.assertRaises(EngineError, msg=(kind, index, disposition)):
                self.engine.add_finding('main', self.lease, receipt['id'], kind, index, disposition, 'why')
        with self.assertRaises(EngineError):
            self.engine.add_finding('main', self.lease, receipt['id'], 'finding', 0, 'rejected', '  ')
        self.reported('b')
        final = self.record('f', ['a', 'b'], final=True, out_of_scope=['Dead code in util'])
        for disposition in ('rejected', 'deferred'):
            with self.assertRaises(EngineError, msg=disposition):
                self.engine.add_finding('main', self.lease, final['id'], 'out_of_scope', 0, disposition, 'why')
        self.assertEqual([], self.engine.list_findings())
        self.engine.add_finding('main', self.lease, final['id'], 'out_of_scope', 0, 'card', 'later', card='X1')

    def test_checkpoint_review_with_out_of_scope_folds_into_notes(self):
        self.reported()
        receipt = self.record('r', ['a'], out_of_scope=['Dead code in util'])
        self.assertEqual([], receipt['out_of_scope'])
        self.assertEqual(['out of scope: Dead code in util'], receipt['notes'])
        self.assertEqual([], self.engine.list_findings())  # never enters the triage ledger

    def test_final_out_of_scope_does_not_block_verdict(self):
        receipt = self.final_with_items(['Dead code in util', 'Stale doc'])
        self.assertEqual([], receipt['findings'])
        self.assertEqual(['Dead code in util', 'Stale doc'], receipt['out_of_scope'])
        with self.assertRaises(EngineError):
            self.record('bad', ['a'], final=True, out_of_scope=['ok', ''])

    def test_completion_requires_triage_of_out_of_scope(self):
        receipt = self.final_with_items(['Dead code in util', 'Stale doc'])
        self.engine.accept('main', self.lease, 'a')
        with self.assertRaisesRegex(EngineError, 'triage'):
            self.engine.check_completion('main', self.lease)
        self.engine.add_finding('main', self.lease, receipt['id'], 'out_of_scope', 0, 'inline', 'fixed in place')
        with self.assertRaisesRegex(EngineError, 'triage'):
            self.engine.check_completion('main', self.lease)
        self.engine.add_finding('main', self.lease, receipt['id'], 'out_of_scope', 1, 'brief', 'for the user')
        self.engine.check_completion('main', self.lease)

    def test_triage_carries_forward_by_fingerprint(self):
        first = self.final_with_items(['Dead code in util'])
        self.engine.add_finding('main', self.lease, first['id'], 'out_of_scope', 0, 'brief', 'for the user')
        self.engine.accept('main', self.lease, 'a')
        second = self.record('final2', ['a'], final=True, out_of_scope=['Dead   code in\nutil'])
        self.assertNotEqual(first['id'], second['id'])
        self.engine.check_completion('main', self.lease)
        third = self.record('final3', ['a'], final=True, out_of_scope=['Dead code in util', 'A new item'])
        with self.assertRaisesRegex(EngineError, 'triage'):
            self.engine.check_completion('main', self.lease)
        self.assertNotEqual(first['id'], third['id'])

    def test_fingerprint_collapses_whitespace(self):
        import hashlib
        from orchestra_core.engine import _fingerprint
        self.assertEqual(hashlib.sha256(b'a b c').hexdigest(), _fingerprint('  a \n b\tc '))

    def test_gate_repeat_on_same_artifact_refused_without_again(self):
        first = self.engine.run_gate('main', self.lease, 'unit', self.GATE)
        self.assertTrue(first['passed'])
        with self.assertRaisesRegex(EngineError, 'Gate unit already passed on this artifact \\(receipt %s\\); pass --again to rerun' % first['id']):
            self.engine.run_gate('main', self.lease, 'unit', self.GATE)
        again = self.engine.run_gate('main', self.lease, 'unit', self.GATE, again=True)
        self.assertNotEqual(first['id'], again['id'])
        self.engine.run_gate('main', self.lease, 'other', self.GATE)
        (self.repo / 'a').write_text('changed')
        self.engine.run_gate('main', self.lease, 'unit', self.GATE)

    def test_failed_gate_rerun_allowed(self):
        bad = [sys.executable, '-c', 'raise SystemExit(3)']
        one = self.engine.run_gate('main', self.lease, 'bad', bad)
        two = self.engine.run_gate('main', self.lease, 'bad', bad)
        self.assertFalse(one['passed'] or two['passed'])
        self.assertNotEqual(one['id'], two['id'])

    def test_review_cites_stale_gate_refused(self):
        self.reported()
        gate = self.engine.run_gate('main', self.lease, 'unit', self.GATE)
        (self.repo / 'a').write_text('changed')
        with self.assertRaisesRegex(EngineError, 'stale gate receipt'):
            self.record('r', ['a'], gate_receipts=[gate['id']])

    def test_review_cites_current_passed_gate_accepted(self):
        self.reported()
        gate = self.engine.run_gate('main', self.lease, 'unit', self.GATE)
        receipt = self.record('r', ['a'], gate_receipts=[gate['id']])
        self.assertEqual([gate['id']], receipt['gate_receipts'])
        for cited in (['missing'], 'not-a-list', [3]):
            with self.assertRaises(EngineError, msg=cited):
                self.record('bad', ['a'], gate_receipts=cited)
        pathlib.Path(gate['path']).write_text('altered')
        with self.assertRaisesRegex(EngineError, 'altered gate receipt'):
            self.record('bad2', ['a'], gate_receipts=[gate['id']])

    def test_clean_review_citing_failed_gate_refused(self):
        self.reported()
        gate = self.engine.run_gate('main', self.lease, 'unit', [sys.executable, '-c', 'raise SystemExit(1)'])
        with self.assertRaisesRegex(EngineError, 'A failed gate receipt needs a blocking finding'):
            self.record('r', ['a'], gate_receipts=[gate['id']])
        receipt = self.record('r2', ['a'], findings=['unit gate fails'], gate_receipts=[gate['id']])
        self.assertEqual(['unit gate fails'], receipt['findings'])

    def test_gate_refuses_merged_delete_and_boundary_argv(self):
        for argv in (['git', 'branch', '-d', 'x'], ['git', 'worktree', 'remove', 'x'], ['git', 'branch', '-D', 'x']):
            before = len(self.engine.status()['gates'])
            with self.assertRaises(EngineError, msg=argv):
                self.engine.run_gate('main', self.lease, 'unsafe', argv)
            self.assertEqual(before, len(self.engine.status()['gates']))
        with self.assertRaisesRegex(EngineError, 'boundary actions run only through the guarded hook'):
            self.engine.run_gate('main', self.lease, 'unsafe', ['git', 'branch', '-d', 'x'])


class FixReviewTests(EngineFixture):
    """Per-task findings, the non-final critic receipt and the fix re-review ladder (contract items 4 and 5)."""
    LENSES = ['requirements', 'correctness', 'tests', 'architecture']

    def setUp(self):
        super().setUp()
        self.allow_review()

    def built(self, name, **kw):
        self.task(name, **kw)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        self.engine.report('w-' + name, token, done('Built ' + name))

    def reviewed(self, name, tasks, findings=None, task_findings=None, repair_check=None, categories=None,
                 final=False, reviewer='reviewer'):
        path = self.root / (name + '.json')
        self.review(path, reviewer=reviewer, tasks=tasks, findings=findings, task_findings=task_findings,
                    repair_check=repair_check, categories=categories, final=final)
        return self.engine.record_review('main', self.lease, reviewer, path, categories or ['correctness'],
                                         tasks, final=final, findings=findings)

    def final(self, name, findings=None, task_findings=None):
        return self.reviewed(name, sorted(self.engine.status()['tasks']), findings=findings,
                             task_findings=task_findings, categories=self.LENSES, final=True, reviewer='final-reviewer')

    def blocked_chain(self):
        """B1 and B2 built; the final review blocks B1; R1 repairs it. Returns once R1 has reported."""
        (self.repo / 'B1').write_text('first')
        self.built('B1')
        self.built('B2')
        self.final('final', findings=['f'], task_findings={'B1': ['f'], 'B2': []})
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        (self.repo / 'B1').write_text('repaired')
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), done('Repaired'))

    def test_task_findings_block_only_named_card(self):
        self.built('B1')
        self.built('B2')
        self.reviewed('critic', ['B1', 'B2'], findings=['f'], task_findings={'B1': ['f'], 'B2': []})
        self.engine.accept('main', self.lease, 'B2')
        with self.assertRaisesRegex(EngineError, 'current review findings'):
            self.engine.accept('main', self.lease, 'B1')

    def test_task_findings_must_match_findings_union(self):
        self.built('B1')
        self.built('B2')
        for findings, task_findings, message in [
                (['f'], {'B1': ['g']}, 'Task findings must match'),
                (['f', 'g'], {'B1': ['f']}, 'Task findings must match'),
                (['f'], {'B1': ['f'], 'B9': []}, 'Task findings name an uncovered task'),
                (['f'], {'B1': 'f'}, 'Invalid task findings'),
                (['f'], ['f'], 'Invalid task findings')]:
            with self.assertRaisesRegex(EngineError, message):
                self.reviewed('bad', ['B1', 'B2'], findings=findings, task_findings=task_findings)
        self.assertEqual([], self.engine.status()['reviews'])
        receipt = self.reviewed('good', ['B1', 'B2'], findings=['f', 'g'], task_findings={'B1': ['f'], 'B2': ['g']})
        self.assertEqual({'B1': ['f'], 'B2': ['g']}, receipt['task_findings'])

    def test_review_without_task_findings_blocks_all_covered(self):
        self.built('B1')
        self.built('B2')
        receipt = self.reviewed('critic', ['B1', 'B2'], findings=['f'])
        self.assertNotIn('task_findings', receipt)
        for name in ('B1', 'B2'):
            with self.assertRaisesRegex(EngineError, 'current review findings'):
                self.engine.accept('main', self.lease, name)

    def test_repair_and_ancestor_wait_for_a_clean_fix_re_review_after_a_later_commit(self):
        self.blocked_chain()
        self.git('add', 'B1')
        self.git('commit', '-qm', 'repair committed')  # the final receipt is now stale
        for name, message in (('R1', 'fix re-review'), ('B1', 'repair must be accepted first')):
            with self.assertRaisesRegex(EngineError, message):
                self.engine.accept('main', self.lease, name)
        self.reviewed('check', ['R1', 'B1'], repair_check=True)
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')

    def test_clean_fix_re_review_accepts_the_chain_and_keeps_the_final_review_current(self):
        self.blocked_chain()
        self.engine.accept('main', self.lease, 'B2')
        check = self.reviewed('check', ['R1', 'B1'], repair_check=True)
        self.assertIs(True, check['repair_check'])
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')
        self.assertEqual(['accepted'] * 3, [self.engine.status()['tasks'][i]['state'] for i in ('B1', 'B2', 'R1')])
        self.engine.check_completion('main', self.lease)  # the repaired file is inside the clean re-review's scope

    def test_cleanup_card_after_the_final_review_stays_inside_the_clean_fix_re_review_scope(self):
        self.blocked_chain()
        self.engine.accept('main', self.lease, 'B2')
        (self.repo / 'C1').write_text('tidied after the final review')
        self.built('C1', mode='cleanup')
        self.reviewed('check', ['R1', 'B1', 'C1'], repair_check=True)
        for name in ('R1', 'B1', 'C1'):
            self.engine.accept('main', self.lease, name)
        self.engine.check_completion('main', self.lease)  # the cleanup file is inside the clean re-review's scope

    def test_edit_outside_the_fix_re_review_scope_voids_the_final_review(self):
        self.blocked_chain()
        self.engine.accept('main', self.lease, 'B2')
        self.reviewed('check', ['R1', 'B1'], repair_check=True)
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')
        (self.repo / 'B2').write_text('edited after the final review')
        with self.assertRaisesRegex(EngineError, 'Current final review coverage is incomplete'):
            self.engine.check_completion('main', self.lease)

    def test_blocked_fix_re_review_leads_to_hold(self):
        self.blocked_chain()
        self.engine.accept('main', self.lease, 'B2')
        self.reviewed('check', ['R1', 'B1'], findings=['g'], task_findings={'R1': ['g'], 'B1': []}, repair_check=True)
        with self.assertRaisesRegex(EngineError, 'current review findings'):
            self.engine.accept('main', self.lease, 'R1')
        self.engine.hold('main', self.lease, 'R1', 'g')
        self.assertEqual(['held', 'held'], [self.engine.status()['tasks'][i]['state'] for i in ('R1', 'B1')])

    def test_one_repair_per_chain(self):
        self.blocked_chain()
        self.reviewed('check', ['R1', 'B1'], findings=['g'], task_findings={'R1': ['g'], 'B1': []}, repair_check=True)
        with self.assertRaisesRegex(EngineError, 'Escalation ends at one repair; hold the chain'):
            self.task('R2', mode='repair', repair_of='R1', files=['B1'])

    def test_fix_re_review_finding_on_ancestor_refused(self):
        self.blocked_chain()
        with self.assertRaisesRegex(EngineError, 'Attribute repair-diff findings to the chain tip R1'):
            self.reviewed('check', ['R1', 'B1'], findings=['g'], task_findings={'B1': ['g']}, repair_check=True)
        with self.assertRaisesRegex(EngineError, 'Attribute repair-diff findings to the chain tip'):
            self.reviewed('check', ['R1', 'B1'], findings=['g'], repair_check=True)
        receipt = self.reviewed('check', ['R1', 'B1'], findings=['g'], task_findings={'R1': ['g'], 'B1': []},
                                repair_check=True)
        self.assertEqual({'R1': ['g'], 'B1': []}, receipt['task_findings'])

    def test_fix_re_review_covers_only_repairs_of_final_findings(self):
        self.built('B1')
        self.reviewed('critic', ['B1'], findings=['f'])
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), done('Repaired'))
        with self.assertRaisesRegex(EngineError, 'A fix re-review covers repair cards of a final-review finding'):
            self.reviewed('check', ['R1', 'B1'], repair_check=True)

    def test_record_review_stores_repair_check_marker(self):
        self.blocked_chain()
        receipt = self.reviewed('marked', ['R1', 'B1'], repair_check=True)
        self.assertIs(True, receipt['repair_check'])
        self.assertIs(True, self.engine.status()['reviews'][-1]['repair_check'])
        for value in (False, 'true', 1, None):
            path = self.root / 'bad.json'
            self.review(path, tasks=['R1', 'B1'])
            body = json.loads(path.read_text())
            body['repair_check'] = value
            path.write_text(json.dumps(body))
            with self.assertRaisesRegex(EngineError, 'repair_check must be true on a non-final fix re-review'):
                self.engine.record_review('main', self.lease, 'reviewer', path, ['correctness'], ['R1', 'B1'])
        with self.assertRaisesRegex(EngineError, 'repair_check must be true on a non-final fix re-review'):
            self.reviewed('final2', sorted(self.engine.status()['tasks']), final=True, repair_check=True,
                          categories=self.LENSES, reviewer='final-reviewer')

    def test_absent_task_findings_key_is_clean_at_every_reader(self):
        self.built('B')
        self.built('C')
        self.reviewed('critic', ['B', 'C'], findings=['f'], task_findings={'B': ['f']})
        with self.assertRaisesRegex(EngineError, 'Repair needs earlier checked coding findings'):
            self.task('RC', mode='repair', repair_of='C', files=['C'])
        self.engine.accept('main', self.lease, 'C')
        self.task('R1', mode='repair', repair_of='B', files=['B'])
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), done('Repaired'))
        self.reviewed('recheck', ['R1', 'B'])
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B')
        # C's newest receipt for its task is the critic review, whose findings are for B only.
        self.final('final')
        self.engine.check_completion('main', self.lease)

    def test_stale_newest_receipt_with_findings_for_other_task_keeps_verdict(self):
        self.built('B')
        self.built('C')
        self.reviewed('c-security', ['C'], categories=['security'])
        self.reviewed('critic', ['B', 'C'], findings=['f'], task_findings={'B': ['f'], 'C': []})
        (self.repo / 'B').write_text('edited after review')
        self.engine.accept('main', self.lease, 'C')
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'B')

    def commit_elsewhere(self):
        (self.repo / 'zz').write_text('unrelated')
        self.git('add', 'zz')
        self.git('commit', '-qm', 'unrelated')

    def test_stale_final_finding_starts_a_repair_that_a_fix_re_review_accepts(self):
        (self.repo / 'B1').write_text('first')
        self.built('B1')
        self.built('B2')
        self.final('final', findings=['f'], task_findings={'B1': ['f'], 'B2': []})
        self.commit_elsewhere()  # the final receipt is stale now
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        self.assertEqual(['f'], self.engine.status()['tasks']['R1']['final_findings'])
        (self.repo / 'B1').write_text('repaired')
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), done('Repaired'))
        with self.assertRaisesRegex(EngineError, 'fix re-review'):
            self.engine.accept('main', self.lease, 'R1')
        self.reviewed('check', ['R1', 'B1'], repair_check=True)
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')

    def test_stale_finding_a_newer_clean_receipt_superseded_starts_no_repair(self):
        (self.repo / 'B1').write_text('first')
        self.built('B1')
        self.built('B2')
        self.final('final', findings=['f'], task_findings={'B1': ['f'], 'B2': []})
        self.reviewed('clean', ['B1'], categories=self.LENSES)
        self.commit_elsewhere()
        with self.assertRaisesRegex(EngineError, 'Repair needs earlier checked coding findings'):
            self.task('R1', mode='repair', repair_of='B1', files=['B1'])

    def two_chains(self):
        """B1 and B2 both blamed by the final review; R1 and R2 repair them and have reported."""
        for name in ('B1', 'B2'):
            (self.repo / name).write_text('first')
            self.built(name)
        self.final('final', findings=['f', 'g'], task_findings={'B1': ['f'], 'B2': ['g']})
        for name in ('R1', 'R2'):
            self.task(name, mode='repair', repair_of='B' + name[1], files=['B' + name[1]])
        for name in ('R1', 'R2'):
            (self.repo / ('B' + name[1])).write_text('repaired')
            self.engine.report(name.lower(), self.engine.dispatch('main', self.lease, name, name.lower(), serial='fixture: one card at a time'), done('Repaired'))

    def test_fix_re_review_blaming_one_chain_still_accepts_the_other(self):
        self.two_chains()
        self.reviewed('check', ['R1', 'B1', 'R2', 'B2'], findings=['h'], task_findings={'R2': ['h']}, repair_check=True)
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')
        for name in ('R2', 'B2'):
            with self.assertRaises(EngineError):
                self.engine.accept('main', self.lease, name)

    def test_repair_dispatch_refused_only_by_overlapping_acceptable_cards(self):
        for name, files in (('I1', ['docs/x.md']), ('I2', [])):
            self.built(name, role='investigator', mode='code', files=files)
        self.built('B2', files=['b.py'])
        self.reviewed('first', ['B2'], findings=['f'])
        self.task('R2', mode='repair', repair_of='B2', files=['b.py'])
        with self.assertRaisesRegex(EngineError, r'Accept I2 first; a repair would make its evidence stale'):
            self.engine.dispatch('main', self.lease, 'R2', 'r2')
        self.engine.accept('main', self.lease, 'I2')
        self.engine.report('r2', self.engine.dispatch('main', self.lease, 'R2', 'r2'), done('Repaired'))  # I1 does not block
        (self.repo / 'b.py').write_text('repaired')
        self.assertEqual('reported', self.engine.status()['tasks']['I1']['state'])
        self.engine.accept('main', self.lease, 'I1')


class HoldFixture(EngineFixture):
    ALL = ['requirements', 'correctness', 'security', 'tests', 'architecture', 'standards', 'cleanup']
    BASE = ['requirements', 'correctness', 'tests', 'architecture']

    def built(self, name, **kw):
        self.task(name, **kw)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        self.engine.report('w-' + name, token, done('Built ' + name))

    def reviewed(self, name, tasks, findings=None, task_findings=None, repair_check=None, categories=None,
                 final=False, mutate=None, cleared=None, cover=True):
        if not final:
            self.allow_review()
        if final:  # a final review explicitly covers every task
            categories = categories or self.BASE
            if cover:
                tasks = sorted(set(tasks) | set(self.engine.status()['tasks']))
        reviewer = 'final-reviewer' if final else 'reviewer'
        path = self.root / (name + '.json')
        self.review(path, reviewer=reviewer, tasks=tasks, findings=findings, task_findings=task_findings,
                    repair_check=repair_check, categories=categories, final=final, cleared=cleared)
        if mutate:
            body = json.loads(path.read_text())
            mutate(body)
            path.write_text(json.dumps(body))
        return self.engine.record_review('main', self.lease, reviewer, path, categories or ['correctness'],
                                         tasks, final=final, findings=findings)

    def blocked_chain(self, check=True):
        """B1 blocked by the final review, repaired by R1, and R1 blocked by the fix re-review (or left reported)."""
        (self.repo / 'B1').write_text('first')
        self.built('B1')
        self.reviewed('first-final', ['B1'], findings=['f'], task_findings={'B1': ['f']}, final=True)
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        (self.repo / 'B1').write_text('repaired')
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), done('Repaired'))
        if check:
            self.reviewed('check', ['R1', 'B1'], findings=['g'], task_findings={'R1': ['g'], 'B1': []}, repair_check=True)

    def states(self, *ids):
        return [self.engine.status()['tasks'][i]['state'] for i in ids]

    def progress(self):
        path = self.engine.state_dir / 'progress.md'
        return path.read_text() if path.exists() else ''

class HoldTests(HoldFixture):
    """Repair ladder ending in hold, and held work at completion."""

    def test_hold_moves_whole_chain_and_logs(self):
        self.blocked_chain()
        result = self.engine.hold('main', self.lease, 'R1', 'g stays after one repair')
        self.assertEqual(['R1', 'B1'], result['held'])
        self.assertEqual(['held', 'held'], self.states('R1', 'B1'))
        self.assertEqual('g stays after one repair', self.engine.status()['tasks']['R1']['held_finding'])
        self.assertNotIn('held_finding', self.engine.status()['tasks']['B1'])
        self.assertIn('- held R1 (chain R1, B1): g stays after one repair', self.progress())
        with self.assertRaisesRegex(EngineError, 'Invalid or interrupted coordinator lease'):
            self.engine.hold('main', 'wrong', 'R1', 'x')

    def test_hold_refused_without_current_blocking_findings(self):
        self.blocked_chain(check=False)
        self.reviewed('clean', ['R1', 'B1'], repair_check=True)
        with self.assertRaisesRegex(EngineError, 'Hold needs'):
            self.engine.hold('main', self.lease, 'R1', 'clean repair')
        self.engine.accept('main', self.lease, 'R1')
        with self.assertRaisesRegex(EngineError, 'Hold needs'):
            self.engine.hold('main', self.lease, 'B1', 'has repaired_by')
        self.built('B2')
        self.reviewed('crit2', ['B2'], findings=['critic only'])
        with self.assertRaisesRegex(EngineError, 'Hold needs'):
            self.engine.hold('main', self.lease, 'B2', 'blocked only by a non-fix review')
        with self.assertRaisesRegex(EngineError, 'Hold needs a finding'):
            self.engine.hold('main', self.lease, 'B2', '  ')
        self.assertEqual('', self.progress())

    def test_dependency_on_held_card_is_ready(self):
        self.blocked_chain()
        self.task('C1', dependencies=['R1'], files=['C1'])
        self.assertNotIn('C1', self.engine.ready('main', self.lease))
        self.engine.hold('main', self.lease, 'R1', 'g')
        self.assertIn('C1', self.engine.ready('main', self.lease))

    def test_held_card_reserves_no_files(self):
        self.blocked_chain()
        self.task('N1', files=['B1'])
        self.assertNotIn('N1', self.engine.ready('main', self.lease))
        self.engine.hold('main', self.lease, 'R1', 'g')
        self.assertEqual(['N1'], self.engine.ready('main', self.lease))

    def test_repair_of_repair_refused_during_build(self):
        self.blocked_chain()
        with self.assertRaisesRegex(EngineError, 'Escalation ends at one repair; hold the chain'):
            self.task('R2', mode='repair', repair_of='R1', files=['B1'])
        self.assertNotIn('R2', self.engine.status()['tasks'])
        self.assertEqual('reported', self.states('R1')[0])

    def test_repair_of_held_tip_allowed_and_chain_repairing(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        self.task('R2', mode='repair', repair_of='R1', owner_approval='owner: take the repair', files=['B1'])
        self.assertEqual(['repairing', 'repairing'], self.states('R1', 'B1'))
        self.assertEqual('R2', self.engine.status()['tasks']['R1']['repaired_by'])

    def test_review_may_cover_held_cards(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        receipt = self.reviewed('final', ['B1', 'R1'], final=True, categories=self.ALL, cleared={'R1': 'no defect'})
        self.assertTrue({'B1', 'R1'} <= set(receipt['tasks']))
        self.task('V1', role='code-reviewer', mode='final', files=[], review_of=['R1'])
        self.assertIn('V1', self.engine.ready('main', self.lease))

    def test_accept_held_card_with_clean_current_verdict(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        with self.assertRaisesRegex(EngineError, 'current review findings'):
            self.engine.accept('main', self.lease, 'R1')
        self.reviewed('clean', ['R1', 'B1'])
        with self.assertRaisesRegex(EngineError, 'repair must be accepted first'):
            self.engine.accept('main', self.lease, 'B1')
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')
        self.assertEqual(['accepted', 'accepted'], self.states('R1', 'B1'))

    def test_first_repair_of_builder_still_allowed(self):
        self.built('B1')
        self.reviewed('crit', ['B1'], findings=['f'])
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        self.assertEqual('repairing', self.states('B1')[0])

    def test_hold_refused_for_notes_only(self):
        self.blocked_chain(check=False)
        note = lambda body: body.update(issues=[dict(text='nit', severity='note')])
        receipt = self.reviewed('notes', ['R1', 'B1'], repair_check=True, mutate=note)
        self.assertEqual(['nit'], receipt['notes'])
        with self.assertRaisesRegex(EngineError, 'Hold needs'):
            self.engine.hold('main', self.lease, 'R1', 'a note is not a finding')

    def test_completion_refuses_while_card_held(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        self.reviewed('final', ['B1', 'R1'], final=True, categories=self.ALL, cleared={'R1': 'no defect'})
        with self.assertRaisesRegex(EngineError, 'accepted'):
            self.engine.check_completion('main', self.lease)

class FinalReceiptTests(HoldFixture):
    """Final receipts, held tips, final repair rounds and `cleared`."""


    def test_contract_hash_unchanged_by_lens_change(self):
        from orchestra_core.engine import _contracts
        self.assertEqual('7b1f34b2bf297e6e95cdd59306a697f5a2b7410f5a84bc71feb7ffe0213439ed', _contracts()[1])

    def test_final_findings_need_task_findings_on_chain_tips(self):
        self.built('B1')
        self.reviewed('crit', ['B1'], findings=['f'])
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), done('Repaired'))
        with self.assertRaisesRegex(EngineError, 'Attribute final findings to the chain tip R1'):
            self.reviewed('bare', ['B1', 'R1'], findings=['h'], final=True)
        with self.assertRaisesRegex(EngineError, 'Attribute final findings to the chain tip R1'):
            self.reviewed('ancestor', ['B1', 'R1'], findings=['h'], final=True, task_findings={'B1': ['h'], 'R1': []})
        receipt = self.reviewed('tip', ['B1', 'R1'], findings=['h'], final=True, task_findings={'R1': ['h']})
        self.assertEqual({'R1': ['h']}, receipt['task_findings'])

    def accepted_b1_with_final_finding(self):
        self.built('B1')
        self.reviewed('clean', ['B1'])
        self.engine.accept('main', self.lease, 'B1')
        self.reviewed('final', ['B1'], findings=['f'], final=True, task_findings={'B1': ['f']})

    def test_repair_of_accepted_tip_with_final_finding_allowed(self):
        self.accepted_b1_with_final_finding()
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        self.assertEqual(['repairing'], self.states('B1'))

    def test_final_repair_card_stores_round_and_findings(self):
        self.accepted_b1_with_final_finding()
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        task = self.engine.status()['tasks']['R1']
        self.assertEqual((1, ['f']), (task['final_round'], task['final_findings']))

    def test_final_round_counts_up_only_after_a_card_of_the_round_reported(self):
        for name in ('B1', 'B2', 'B3'):
            self.built(name)
        self.reviewed('clean', ['B1', 'B2', 'B3'])
        for name in ('B1', 'B2', 'B3'):
            self.engine.accept('main', self.lease, name)
        self.reviewed('final', ['B1', 'B2', 'B3'], findings=['f1', 'f2', 'f3'], final=True,
                      task_findings={'B1': ['f1'], 'B2': ['f2'], 'B3': ['f3']})
        rounds = []
        for repair, target in (('R1', 'B1'), ('R2', 'B2')):
            self.task(repair, mode='repair', repair_of=target, files=[target])
            rounds.append(self.engine.status()['tasks'][repair]['final_round'])
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1', serial='fixture: one card at a time'), done('Repaired'))
        self.task('R3', mode='repair', repair_of='B3', files=['B3'])
        rounds.append(self.engine.status()['tasks']['R3']['final_round'])
        self.assertEqual([1, 1, 2], rounds)

    def test_build_phase_repair_has_no_final_fields(self):
        self.built('B1')
        self.reviewed('crit', ['B1'], findings=['f'])
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        task = self.engine.status()['tasks']['R1']
        self.assertNotIn('final_round', task)
        self.assertNotIn('final_findings', task)

    def test_final_receipt_must_address_every_held_tip(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        with self.assertRaisesRegex(EngineError, 'Final receipt must address held tip R1'):
            self.reviewed('omitted', ['B1', 'R1'], final=True)
        with self.assertRaisesRegex(EngineError, 'cleared'):
            self.reviewed('blank', ['B1', 'R1'], final=True, cleared={'R1': '  '})
        with self.assertRaisesRegex(EngineError, 'cleared'):
            self.reviewed('not held', ['B1', 'R1'], final=True, cleared={'R1': 'ok', 'B1': 'ancestor'})
        cleared = self.reviewed('cleared', ['B1', 'R1'], final=True, cleared={'R1': 'no security defect'})
        self.assertEqual({'R1': 'no security defect'}, cleared['cleared'])
        found = self.reviewed('found', ['B1', 'R1'], findings=['still g'], final=True, task_findings={'R1': ['still g']})
        self.assertEqual({}, found['cleared'])

    def test_final_receipt_with_falsy_cleared(self):
        # Code decides: a final receipt's `cleared` is an object, and `[]` means the same as `{}` (none); any other
        # falsy non-object is refused. A held tip still has to be addressed. A non-final receipt treats any falsy value as empty.
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        for name, falsy in (('none', None), ('empty-string', ''), ('zero', 0)):
            with self.assertRaisesRegex(EngineError, 'Invalid cleared entries', msg=name):
                self.reviewed('falsy-' + name, ['B1', 'R1'], final=True, mutate=lambda body, v=falsy: body.update(cleared=v))
        with self.assertRaisesRegex(EngineError, 'Final receipt must address held tip R1'):
            self.reviewed('empty-list', ['B1', 'R1'], final=True, mutate=lambda body: body.update(cleared=[]))
        with self.assertRaisesRegex(EngineError, 'Final receipt must address held tip R1'):
            self.reviewed('empty-object', ['B1', 'R1'], final=True, cleared={})
        receipt = self.reviewed('plain', ['B1', 'R1'], mutate=lambda body: body.update(cleared=[]))
        self.assertEqual({}, receipt['cleared'])

    def test_final_receipt_must_cover_every_task(self):
        self.built('B1')
        self.built('B2')
        self.reviewed('clean', ['B1', 'B2'])
        every = sorted(self.engine.status()['tasks'])
        with self.assertRaisesRegex(EngineError, 'Final review must explicitly cover every task'):
            self.reviewed('partial', ['B1'], final=True, cover=False)
        with self.assertRaisesRegex(EngineError, 'Final review must explicitly cover every task'):
            self.reviewed('repeated', every + ['B2'], final=True, cover=False)
        self.assertTrue(self.reviewed('whole', every, final=True, cover=False)['final'])

    def test_cleared_refused_on_non_final_receipt(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        with self.assertRaisesRegex(EngineError, 'Cleared entries are allowed only on final receipts'):
            self.reviewed('plain', ['B1', 'R1'], cleared={'R1': 'fine'})

    def test_held_tip_cleared_by_the_final_review_accepts_without_repair(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        self.reviewed('cleared', ['B1', 'R1'], final=True, cleared={'R1': 'the held finding no longer reproduces'})
        with self.assertRaisesRegex(EngineError, 'Repair needs earlier checked coding findings'):
            self.task('R2', mode='repair', repair_of='R1', files=['B1'])
        with self.assertRaisesRegex(EngineError, 'repair must be accepted first'):
            self.engine.accept('main', self.lease, 'B1')
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')
        self.assertEqual(['accepted', 'accepted'], self.states('R1', 'B1'))


class SelfReviewTests(EngineFixture):
    """Contract items 1 and 2: the SELF_REVIEW line and builder acceptance on it."""

    def running(self, name='a'):
        self.task(name)
        return self.engine.dispatch('main', self.lease, name, 'w-' + name)

    def test_builder_report_needs_exactly_one_self_review_line(self):
        token = self.running()
        good = {'checks': [{'command': 'pytest', 'exit_code': 0}],
                'criteria': [{'criterion': 'check behavior', 'met': True, 'evidence': 'e'}]}
        line = 'SELF_REVIEW: ' + json.dumps(good)
        bad = {'no line': 'Built a.',
               'two lines': 'Built a.\n' + line + '\n' + line,
               'not json': 'Built a.\nSELF_REVIEW: {nope',
               'not an object': 'Built a.\nSELF_REVIEW: []',
               'empty checks': 'Built a.\nSELF_REVIEW: ' + json.dumps(dict(good, checks=[])),
               'empty criteria': 'Built a.\nSELF_REVIEW: ' + json.dumps(dict(good, criteria=[])),
               'no criteria key': 'Built a.\nSELF_REVIEW: ' + json.dumps({'checks': good['checks']}),
               'exit code not an int': 'Built a.\nSELF_REVIEW: ' + json.dumps(
                   dict(good, checks=[{'command': 'pytest', 'exit_code': '0'}])),
               'met not a bool': 'Built a.\nSELF_REVIEW: ' + json.dumps(
                   dict(good, criteria=[{'criterion': 'c', 'met': 1, 'evidence': 'e'}]))}
        for label, text in bad.items():
            with self.subTest(label), self.assertRaisesRegex(EngineError, 'Builder report needs one SELF_REVIEW line'):
                self.engine.report('w-a', token, text)
        self.assertEqual('running', self.engine.status()['tasks']['a']['state'])
        self.engine.report('w-a', token, 'ARTIFACT: abc123\nBuilt a.\n' + line)
        self.assertEqual(good, self.engine.status()['tasks']['a']['self_review'])

    def test_builder_report_needs_a_nonempty_artifact_line(self):
        token = self.running()
        line = 'SELF_REVIEW: ' + json.dumps({'checks': [{'command': 'pytest', 'exit_code': 0}],
                                             'criteria': [{'criterion': 'check behavior', 'met': True, 'evidence': 'e'}]})
        for label, head in {'no line': 'Built a.', 'empty': 'ARTIFACT:\nBuilt a.', 'blank': 'ARTIFACT:   \nBuilt a.'}.items():
            with self.subTest(label), self.assertRaisesRegex(EngineError, 'Builder report needs a nonempty ARTIFACT line'):
                self.engine.report('w-a', token, head + '\n' + line)
        self.assertEqual('running', self.engine.status()['tasks']['a']['state'])
        self.engine.report('w-a', token, 'ARTIFACT: abc123\n' + line)
        self.assertEqual('reported', self.engine.status()['tasks']['a']['state'])

    def test_reported_card_takes_a_replacement_report_until_accepted(self):
        token = self.running()
        self.engine.report('w-a', token, done('First.', checks=[{'command': 'grep -q x a', 'exit_code': 1}]))
        with self.assertRaisesRegex(EngineError, 'Invalid assignment'):
            self.engine.report('w-other', token, done('Not mine.'))
        self.engine.report('w-a', token, done('Second.'))
        task = self.engine.status()['tasks']['a']
        self.assertEqual('reported', task['state'])
        self.assertIn('Second.', task['report'])
        self.assertEqual(0, task['self_review']['checks'][0]['exit_code'])
        self.engine.accept('main', self.lease, 'a')
        with self.assertRaisesRegex(EngineError, 'Invalid assignment'):
            self.engine.report('w-a', token, done('Late.'))

    def test_replacement_report_refused_once_a_review_covers_the_card(self):
        token = self.running()
        self.engine.report('w-a', token, done('First.'))
        path = self.root / 'final-a.json'
        self.review(path, tasks=['a'], categories=ALL_CATEGORIES, final=True)
        self.engine.record_review('main', self.lease, 'reviewer', path, ALL_CATEGORIES, ['a'], final=True)
        with self.assertRaisesRegex(EngineError, 'A review covers this report'):
            self.engine.report('w-a', token, done('Second.'))
        self.assertIn('First.', self.engine.status()['tasks']['a']['report'])

    def test_covered_report_takes_a_corrected_self_review_line_only(self):
        # F32: a red-first check whose command text carries a note never matches its green run. After a review covers
        # the report, the coordinator may correct only the SELF_REVIEW line; any other change still needs a repair card.
        token = self.running()
        red = [{'command': 'python3 -m unittest t (at base)', 'exit_code': 1, 'expect': 'fail'},
               {'command': 'python3 -m unittest t', 'exit_code': 0}]
        self.engine.report('w-a', token, done('First.', checks=red))
        path = self.root / 'final-a.json'
        self.review(path, tasks=['a'], categories=ALL_CATEGORIES, final=True)
        self.engine.record_review('main', self.lease, 'reviewer', path, ALL_CATEGORIES, ['a'], final=True)
        with self.assertRaisesRegex(EngineError, 'failing check'):
            self.engine.accept('main', self.lease, 'a')
        with self.assertRaisesRegex(EngineError, 'A review covers this report'):
            self.engine.report('w-a', token, done('Changed body.'))
        fixed = [dict(red[0], command='python3 -m unittest t'), red[1]]
        self.engine.report('w-a', token, done('First.', checks=fixed))
        self.assertIn('First.', self.engine.status()['tasks']['a']['report'])
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])

    def covered_report(self, checks=None, criteria=None):
        token = self.running()
        self.engine.report('w-a', token, done('First.', checks=checks, criteria=criteria))
        path = self.root / 'final-a.json'
        self.review(path, tasks=['a'], categories=ALL_CATEGORIES, final=True)
        self.engine.record_review('main', self.lease, 'reviewer', path, ALL_CATEGORIES, ['a'], final=True)
        return token

    def test_covered_report_cannot_refresh_a_stale_artifact(self):
        # PR4: re-sending the identical report after a file edit must not rebind the report to the new files.
        token = self.covered_report()
        (self.repo / 'a').write_text('changed after the review')
        with self.assertRaisesRegex(EngineError, 'Reported artifact is stale'):
            self.engine.accept('main', self.lease, 'a')
        with self.assertRaisesRegex(EngineError, 'A review covers this report'):
            self.engine.report('w-a', token, done('First.'))
        with self.assertRaisesRegex(EngineError, 'Reported artifact is stale'):
            self.engine.accept('main', self.lease, 'a')

    def test_covered_report_correction_cannot_flip_results(self):
        # PR4 note: after a review, only check command strings may change; exit codes and met flags stay as reviewed.
        failing = [{'command': 'python3 -m unittest t', 'exit_code': 1}]
        token = self.covered_report(checks=failing)
        with self.assertRaisesRegex(EngineError, 'A review covers this report'):
            self.engine.report('w-a', token, done('First.', checks=[dict(failing[0], exit_code=0)]))
        unmet = [{'criterion': 'check behavior', 'met': False, 'evidence': 'not yet'}]
        with self.assertRaisesRegex(EngineError, 'A review covers this report'):
            self.engine.report('w-a', token, done('First.', checks=failing, criteria=unmet))

    def test_non_builder_report_needs_no_self_review(self):
        self.task('look', role='investigator', mode='code', files=[])
        token = self.engine.dispatch('main', self.lease, 'look', 'w-look')
        self.engine.report('w-look', token, 'Inspected.')
        self.assertNotIn('self_review', self.engine.status()['tasks']['look'])

    def test_failing_check_or_unmet_criterion_refuses_accept(self):
        cases = {'failing check': dict(checks=[{'command': 'pytest', 'exit_code': 1}]),
                 'one of two checks failing': dict(checks=[{'command': 'a', 'exit_code': 0}, {'command': 'b', 'exit_code': 2}]),
                 'unmet criterion': dict(criteria=[{'criterion': 'check behavior', 'met': False, 'evidence': 'not done'}])}
        for label, kw in cases.items():
            name = label.replace(' ', '-')
            token = self.running(name)
            self.engine.report('w-' + name, token, done('Built.', **kw))
            with self.subTest(label), self.assertRaisesRegex(EngineError, 'Self-review has a failing check or unmet criterion'):
                self.engine.accept('main', self.lease, name)
            self.assertEqual('reported', self.engine.status()['tasks'][name]['state'])

    def test_red_first_check_needs_the_same_command_passing_after_it(self):
        red = {'command': 'pytest t', 'exit_code': 1, 'expect': 'fail'}
        green = {'command': 'pytest t', 'exit_code': 0}
        name = 'pair'
        self.engine.report('w-' + name, self.running(name), done('Built.', checks=[red, green]))
        self.engine.accept('main', self.lease, name)
        self.assertEqual('accepted', self.engine.status()['tasks'][name]['state'])
        refused = {'red alone': [red],
                   'red then a different passing command': [red, {'command': 'ruff check', 'exit_code': 0}],
                   'red then the same command failing': [red, dict(green, exit_code=1)],
                   'green before red': [green, red],
                   'red that exits 0': [dict(red, exit_code=0), green],
                   'green marked fail': [red, dict(green, expect='fail')]}
        for label, checks in refused.items():
            name = label.replace(' ', '-')
            self.engine.report('w-' + name, self.running(name), done('Built.', checks=checks))
            with self.subTest(label), self.assertRaisesRegex(EngineError, 'Self-review has a failing check or unmet criterion'):
                self.engine.accept('main', self.lease, name)

    def test_expect_key_takes_only_pass_or_fail(self):
        token = self.running()
        for value in ('maybe', True, 1, None, ''):
            checks = [{'command': 'pytest', 'exit_code': 0, 'expect': value}]
            with self.subTest(value), self.assertRaisesRegex(EngineError, 'Builder report needs one SELF_REVIEW line'):
                self.engine.report('w-a', token, done('Built.', checks=checks))
        self.engine.report('w-a', token, done('Built.', checks=[{'command': 'pytest', 'exit_code': 0, 'expect': 'pass'}]))
        self.engine.accept('main', self.lease, 'a')

    def test_builder_accepts_on_its_self_review_without_an_independent_review(self):
        token = self.running()
        self.engine.report('w-a', token, done('Built a.'))
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.engine.status()['tasks']['a']['state'])
        self.assertEqual([], self.engine.status()['reviews'])

    def test_stale_reported_artifact_refuses_accept(self):
        token = self.running()
        self.engine.report('w-a', token, done('Built a.'))
        (self.repo / 'a').write_text('edited after the report')
        with self.assertRaisesRegex(EngineError, 'Reported artifact is stale'):
            self.engine.accept('main', self.lease, 'a')


class RouteTests(EngineFixture):
    """Contract item 3: `start --items` and `route` decide who does builder work."""

    def run_with(self, items, name='state-items'):
        engine = Engine(self.root / name, self.repo)
        return engine, engine.open_session('main', items=items)

    def add(self, engine, lease, name, **kw):
        task = dict(id=name, role='builder', mode='implementation', inputs=['spec'], acceptance=['check behavior'],
                    files=[name], resources=[], dependencies=[])
        task.update(kw)
        engine.add_task('main', lease, task)

    def plan_card(self, engine, lease):
        self.add(engine, lease, 'plan', role='designer-planner', mode='plan', files=[])
        engine.report('planner', engine.dispatch('main', lease, 'plan', 'planner'), 'Plan: group the work.')
        engine.accept('main', lease, 'plan')

    def test_items_choose_the_route(self):
        for items, route in ((1, 'inline'), (5, 'inline'), (6, 'workflow'), (40, 'workflow')):
            engine, _ = self.run_with(items, 'state-%d' % items)
            session = engine.status()['session']
            self.assertEqual((items, route, []), (session['items'], session['route'], session['route_log']))

    def test_items_must_be_a_positive_integer(self):
        for bad in (0, -1, True, '3', 2.5):
            with self.subTest(bad), self.assertRaisesRegex(EngineError, 'Items must be an integer of 1 or more'):
                self.run_with(bad)

    def test_a_new_run_can_be_required_to_state_its_size(self):
        engine = Engine(self.root / 'needs-size', self.repo)
        with self.assertRaisesRegex(EngineError, 'A new run needs --size tiny, medium or large'):
            engine.open_session('main', require_size=True)
        lease = engine.open_session('main', size='medium', require_size=True)
        engine.interrupt('main', lease)
        lease = engine.open_session('main', require_size=True)  # a resumed run keeps its size
        self.assertEqual('medium', engine.status()['session']['size'])
        engine.interrupt('main', lease)
        with self.assertRaisesRegex(EngineError, 'apply to a new run'):
            engine.open_session('main', size='tiny')
        with self.assertRaisesRegex(EngineError, 'applies only to a new run'):
            engine.open_session('main', items=9)  # the 2.4 rule for items stays

    def test_inline_route_refuses_a_helper_without_a_reason(self):
        engine, lease = self.run_with(3)
        self.add(engine, lease, 'b')
        with self.assertRaisesRegex(EngineError, 'Inline route: the main session does this work; pass --helper REASON to dispatch a helper'):
            engine.dispatch('main', lease, 'b', 'helper')
        with self.assertRaisesRegex(EngineError, 'Inline route'):
            engine.dispatch('main', lease, 'b', 'helper', helper='  ')
        engine.dispatch('main', lease, 'b', 'helper', helper='a disjoint file the main session need not hold')
        self.assertEqual('a disjoint file the main session need not hold', engine.status()['tasks']['b']['helper_reason'])

    def test_inline_route_lets_the_main_session_do_the_work(self):
        engine, lease = self.run_with(3)
        self.add(engine, lease, 'b')
        token = engine.start_inline('main', lease, 'b')
        engine.report('main', token, done('Built b.'))
        engine.accept('main', lease, 'b')
        self.assertTrue(engine.status()['tasks']['b']['inline'])

    def test_inline_route_has_no_plan_card(self):
        engine, lease = self.run_with(5)
        with self.assertRaisesRegex(EngineError, 'Inline route: no plan card; the main session groups the work'):
            self.add(engine, lease, 'plan', role='designer-planner', mode='plan', files=[])
        self.add(engine, lease, 'product', role='designer-planner', mode='product', files=[])  # other modes stay

    def test_workflow_route_needs_an_accepted_plan_card_first(self):
        engine, lease = self.run_with(8)
        self.add(engine, lease, 'b')
        for label, action in (('dispatch', lambda: engine.dispatch('main', lease, 'b', 'w')),
                              ('inline', lambda: engine.start_inline('main', lease, 'b'))):
            with self.subTest(label), self.assertRaisesRegex(EngineError, 'Workflow route: accept the designer-planner plan card first'):
                action()
        self.add(engine, lease, 'plan', role='designer-planner', mode='plan', files=[])
        with self.assertRaisesRegex(EngineError, 'Workflow route: accept'):
            engine.dispatch('main', lease, 'b', 'w')  # a plan card that is only queued does not count
        engine.report('planner', engine.dispatch('main', lease, 'plan', 'planner'), 'Plan: group the work.')
        engine.accept('main', lease, 'plan')
        engine.report('w', engine.dispatch('main', lease, 'b', 'w'), done('Built b.'))
        engine.accept('main', lease, 'b')
        self.assertEqual('accepted', engine.status()['tasks']['b']['state'])

    def test_route_changes_items_and_route_and_logs_why(self):
        engine, lease = self.run_with(3)
        self.add(engine, lease, 'b')
        self.assertEqual({'items': 9, 'route': 'workflow'}, engine.set_route('main', lease, 9, 'the brief grew'))
        with self.assertRaisesRegex(EngineError, 'Workflow route'):
            engine.start_inline('main', lease, 'b')
        engine.set_route('main', lease, 2, 'most of it was one change')
        session = engine.status()['session']
        self.assertEqual((2, 'inline'), (session['items'], session['route']))
        self.assertEqual([(9, 'the brief grew'), (2, 'most of it was one change')],
                         [(e['items'], e['reason']) for e in session['route_log']])
        self.assertTrue(all(e['at'] for e in session['route_log']))
        engine.start_inline('main', lease, 'b')  # inline again

    def test_route_needs_a_reason_a_valid_count_and_the_lease(self):
        engine, lease = self.run_with(3)
        with self.assertRaisesRegex(EngineError, 'Route needs a reason'):
            engine.set_route('main', lease, 7, ' ')
        with self.assertRaisesRegex(EngineError, 'Items must be an integer'):
            engine.set_route('main', lease, 0, 'why')
        with self.assertRaisesRegex(EngineError, 'Invalid or interrupted coordinator lease'):
            engine.set_route('main', 'wrong', 7, 'why')
        self.assertEqual((3, 'inline', []), tuple(engine.status()['session'][k] for k in ('items', 'route', 'route_log')))

    def test_a_2_3_state_without_items_keeps_the_old_routing(self):
        state, lease = load_2_3_state(self.root, self.repo)
        engine = Engine(state, self.repo)
        self.assertNotIn('route', engine.status()['session'])
        self.add(engine, lease, 'b')
        self.add(engine, lease, 'plan', role='designer-planner', mode='plan', files=[])  # a plan card is allowed
        token = engine.dispatch('main', lease, 'b', 'w', serial='fixture: one card at a time')  # no --helper, no plan card
        engine.report('w', token, done('Built b.'))
        engine.accept('main', lease, 'b')
        self.add(engine, lease, 'c')
        engine.start_inline('main', lease, 'c', serial='fixture: one card at a time')


class SizeRouteTests(EngineFixture):
    """Contract items 2 to 6: a run routes by the size of its diff."""

    def run_with(self, size='medium', asks=None, owner_request=False, name='state-size'):
        engine = Engine(self.root / name, self.repo)
        return engine, engine.open_session('main', size=size, asks=asks, owner_request=owner_request, require_size=True)

    def add(self, engine, lease, name, **kw):
        task = dict(id=name, role='builder', mode='implementation', inputs=['spec'], acceptance=['check behavior'],
                    files=[name], resources=[], dependencies=[])
        task.update(kw)
        engine.add_task('main', lease, task)

    def test_new_run_without_size_is_refused_naming_size(self):
        engine = Engine(self.root / 'nosize', self.repo)
        with self.assertRaisesRegex(EngineError, 'A new run needs --size tiny, medium or large'):
            engine.open_session('main', require_size=True)
        self.assertIsNone(engine.status()['session'])

    def test_size_large_on_new_run_needs_owner_request_and_names_escalation(self):
        engine = Engine(self.root / 'large', self.repo)
        with self.assertRaisesRegex(EngineError, r'escalate with route --size large --reason TEXT, or pass --owner-request '
                                                 r'when the owner asked for a map'):
            engine.open_session('main', size='large', require_size=True)
        self.assertIsNone(engine.status()['session'])

    def test_owner_request_allows_large_start(self):
        engine, _ = self.run_with('large', owner_request=True)
        session = engine.status()['session']
        self.assertEqual(('large', 1, True), (session['size'], session['asks'], session['owner_request']))

    def test_unknown_size_and_bad_asks_are_refused(self):
        for bad in ('huge', '', 'Tiny', 3, True):
            with self.subTest(size=bad), self.assertRaises(EngineError):
                self.run_with(bad, name='bad-size')
        for bad in (0, -1, True, '2', 2.5):
            with self.subTest(asks=bad), self.assertRaisesRegex(EngineError, '--asks must be an integer, 1 or more'):
                self.run_with('tiny', asks=bad, name='bad-asks')

    def test_start_flags_on_a_resumed_run_are_refused(self):
        engine, lease = self.run_with('medium', asks=2)
        engine.interrupt('main', lease)
        for kw in (dict(size='tiny'), dict(asks=3), dict(owner_request=True)):
            with self.subTest(kw), self.assertRaisesRegex(
                    EngineError, r'--size, --asks and --owner-request apply to a new run; use start --new-run, or route --size '
                                 r'to change the tier'):
                engine.open_session('main', **kw)
        engine.open_session('main', require_size=True)  # a resumed run needs none of the flags
        self.assertEqual(('medium', 2), tuple(engine.status()['session'][k] for k in ('size', 'asks')))

    def test_session_records_size_asks_and_owner_request(self):
        engine, _ = self.run_with('tiny', asks=3)
        session = engine.status()['session']
        self.assertEqual(('tiny', 3, False, []), tuple(session[k] for k in ('size', 'asks', 'owner_request', 'route_log')))
        self.assertEqual(self.git('rev-parse', 'HEAD'), session['base'])
        self.assertNotIn('route', session)
        self.assertNotIn('items', session)

    def test_restart_keeps_size_asks_and_owner_request(self):
        engine, lease = self.run_with('large', asks=2, owner_request=True)
        engine.set_route('main', lease, None, 'it shrank', size='medium')
        engine.interrupt('main', lease)
        engine.open_session('main')
        session = engine.status()['session']
        self.assertEqual(('medium', 2, True), (session['size'], session['asks'], session['owner_request']))
        self.assertEqual(['it shrank'], [e['reason'] for e in session['route_log']])

    def mutate(self, name, change):
        engine, lease = self.run_with('medium', name=name)
        engine.interrupt('main', lease)
        path = engine.state_path
        data = json.loads(path.read_text())
        change(data['session'])
        path.write_text(json.dumps(data))
        return engine

    def test_state_with_items_and_size_together_is_invalid(self):
        engine = self.mutate('both', lambda s: s.update(items=2, route='inline'))
        with self.assertRaisesRegex(EngineError, 'Invalid session size'):
            engine.status()

    def test_bad_size_or_asks_in_state_is_invalid(self):
        changes = {'size': lambda s: s.update(size='huge'), 'asks0': lambda s: s.update(asks=0),
                   'asksbool': lambda s: s.update(asks=True), 'owner': lambda s: s.update(owner_request='yes'),
                   'log': lambda s: s.update(route_log=[{'size': 'huge', 'asks': 1, 'reason': 'r', 'at': 'x'}]),
                   'asks-no-size': lambda s: (s.pop('size'), s.update(asks=1))}
        for name, change in changes.items():
            with self.subTest(name), self.assertRaisesRegex(EngineError, 'Invalid session size'):
                self.mutate('bad-' + name, change).status()

    def test_bad_card_size_in_state_is_invalid(self):
        engine, lease = self.run_with('medium', name='card-size')
        self.add(engine, lease, 'b', size='tiny')
        engine.interrupt('main', lease)
        path = engine.state_path
        for bad in ('large', 'huge', None):
            data = json.loads(path.read_text())
            data['tasks']['b']['size'] = bad
            path.write_text(json.dumps(data))
            with self.subTest(bad), self.assertRaisesRegex(EngineError, 'Invalid task size'):
                engine.status()

    def test_route_size_logs_size_asks_reason(self):
        engine, lease = self.run_with('tiny', asks=2)
        self.assertEqual({'size': 'medium', 'asks': 3}, engine.set_route('main', lease, None, 'grew', size='medium', asks=3))
        session = engine.status()['session']
        self.assertEqual(('medium', 3), (session['size'], session['asks']))
        entry = session['route_log'][0]
        self.assertEqual(('medium', 3, 'grew'), (entry['size'], entry['asks'], entry['reason']))
        self.assertTrue(entry['at'])
        with self.assertRaisesRegex(EngineError, 'Route needs a reason'):
            engine.set_route('main', lease, None, ' ', size='tiny')
        with self.assertRaises(EngineError):
            engine.set_route('main', lease, None, 'why', size='huge')
        with self.assertRaisesRegex(EngineError, '--asks must be an integer'):
            engine.set_route('main', lease, None, 'why', size='tiny', asks=0)
        with self.assertRaisesRegex(EngineError, 'Invalid or interrupted coordinator lease'):
            engine.set_route('main', 'wrong', None, 'why', size='tiny')
        with self.assertRaisesRegex(EngineError, 'exactly one'):
            engine.set_route('main', lease, 3, 'why', size='tiny')
        with self.assertRaisesRegex(EngineError, 'exactly one'):
            engine.set_route('main', lease, None, 'why')
        self.assertEqual(1, len(engine.status()['session']['route_log']))

    def test_route_size_without_asks_keeps_the_current_count(self):
        engine, lease = self.run_with('tiny', asks=4)
        engine.set_route('main', lease, None, 'grew', size='medium')
        self.assertEqual(4, engine.status()['session']['asks'])
        self.assertEqual(4, engine.status()['session']['route_log'][0]['asks'])

    def test_route_size_can_escalate_to_large_without_owner_request(self):
        engine, lease = self.run_with('medium')
        engine.set_route('main', lease, None, 'grilling passed the ceiling', size='large')
        session = engine.status()['session']
        self.assertEqual(('large', False), (session['size'], session['owner_request']))
        engine.set_route('main', lease, None, 'it shrank', size='tiny')  # either direction
        self.assertEqual('tiny', engine.status()['session']['size'])

    def test_route_size_refused_on_items_run(self):
        state, lease = load_2_4_state(self.root, self.repo)
        engine = Engine(state, self.repo)
        with self.assertRaisesRegex(EngineError, 'This run routes by items; use route --items'):
            engine.set_route('main', lease, None, 'why', size='medium')

    def test_route_items_refused_on_size_run(self):
        engine, lease = self.run_with('medium')
        with self.assertRaisesRegex(EngineError, 'This run routes by size; use route --size'):
            engine.set_route('main', lease, 3, 'why')
        self.assertEqual([], engine.status()['session']['route_log'])

    def test_route_size_refused_on_2_3_run(self):
        state, lease = load_2_3_state(self.root, self.repo)
        engine = Engine(state, self.repo)
        with self.assertRaisesRegex(EngineError, 'This run has no route; start a new run with --size'):
            engine.set_route('main', lease, None, 'why', size='medium')
        engine.set_route('main', lease, 3, 'why')  # route --items behaves as in 2.4
        self.assertEqual('inline', engine.status()['session']['route'])

    def test_tiny_card_dispatch_needs_helper_reason(self):
        engine, lease = self.run_with('tiny')
        self.add(engine, lease, 'b')
        for helper in (None, '  '):
            with self.subTest(helper), self.assertRaisesRegex(
                    EngineError, 'Tiny unit: the main session does this work; pass --helper REASON to dispatch a helper'):
                engine.dispatch('main', lease, 'b', 'w', helper=helper)
        engine.dispatch('main', lease, 'b', 'w', helper='needs a second pair of hands')
        self.assertEqual('needs a second pair of hands', engine.status()['tasks']['b']['helper_reason'])

    def test_medium_card_dispatch_needs_no_helper(self):
        engine, lease = self.run_with('medium')
        self.add(engine, lease, 'b')
        engine.dispatch('main', lease, 'b', 'w')
        self.add(engine, lease, 'c')
        engine.dispatch('main', lease, 'c', 'x', helper='ignored')  # accepted and ignored on a medium card
        self.assertEqual('running', engine.status()['tasks']['c']['state'])

    def test_card_size_overrides_run_size(self):
        engine, lease = self.run_with('tiny')
        self.add(engine, lease, 'b', size='medium')
        engine.dispatch('main', lease, 'b', 'w')
        engine, lease = self.run_with('medium', name='other')
        self.add(engine, lease, 'b', size='tiny')
        with self.assertRaisesRegex(EngineError, 'Tiny unit'):
            engine.dispatch('main', lease, 'b', 'w')

    def test_card_without_size_reads_the_run_tier_at_dispatch(self):
        engine, lease = self.run_with('tiny')
        self.add(engine, lease, 'b')
        self.assertNotIn('size', engine.status()['tasks']['b'])
        engine.set_route('main', lease, None, 'it grew', size='medium')
        engine.dispatch('main', lease, 'b', 'w')  # no helper: the card now reads medium

    def test_large_run_card_defaults_to_medium(self):
        engine, lease = self.run_with('large', owner_request=True)
        self.add(engine, lease, 'b')
        engine.dispatch('main', lease, 'b', 'w')

    def test_invalid_card_size_is_refused(self):
        engine, lease = self.run_with('medium')
        for bad in ('large', 'huge', '', None, 3):
            with self.subTest(bad), self.assertRaisesRegex(EngineError, 'Invalid task size'):
                self.add(engine, lease, 'b', size=bad)
        self.assertEqual({}, engine.status()['tasks'])

    def test_card_size_on_items_and_2_3_runs_is_validated_and_ignored(self):
        for load, name in ((load_2_4_state, 'items'), (load_2_3_state, 'legacy')):
            state, lease = load(self.root, self.repo, name)
            engine = Engine(state, self.repo)
            with self.assertRaisesRegex(EngineError, 'Invalid task size'):
                self.add(engine, lease, 'x', size='huge')
            self.add(engine, lease, 'b', size='medium')
            self.add(engine, lease, 'c', size='tiny')
            if name == 'items':
                with self.assertRaisesRegex(EngineError, 'Inline route'):
                    engine.dispatch('main', lease, 'b', 'w')  # the 2.4 route check, not the card size, decides
            else:
                engine.dispatch('main', lease, 'b', 'w', serial='fixture: one card at a time')
            if name == 'legacy':
                engine.dispatch('main', lease, 'c', 'x')  # a tiny card on a 2.3 run needs no helper

    def test_inline_reservation_of_a_tiny_card_is_not_gated(self):
        engine, lease = self.run_with('tiny')
        self.add(engine, lease, 'b')
        token = engine.start_inline('main', lease, 'b')
        engine.report('main', token, done('Built b.'))
        engine.accept('main', lease, 'b')
        self.assertTrue(engine.status()['tasks']['b']['inline'])

    def test_plan_card_refused_on_tiny_and_medium_run(self):
        for size in ('tiny', 'medium'):
            engine, lease = self.run_with(size, name='plan-' + size)
            with self.subTest(size), self.assertRaisesRegex(
                    EngineError, 'Plan card needs a large run or an owner request; escalate with route --size large --reason TEXT'):
                self.add(engine, lease, 'plan', role='designer-planner', mode='plan', files=[])
            self.add(engine, lease, 'product', role='designer-planner', mode='product', files=[])  # other modes stay

    def test_plan_card_allowed_on_large_run(self):
        engine, lease = self.run_with('medium')
        engine.set_route('main', lease, None, 'grilling passed the ceiling', size='large')
        self.add(engine, lease, 'plan', role='designer-planner', mode='plan', files=[])
        self.add(engine, lease, 'b')  # a large run does not force a plan before builders
        engine.dispatch('main', lease, 'b', 'w', serial='fixture: one card at a time')

    def test_plan_card_allowed_with_session_owner_request(self):
        engine, lease = self.run_with('large', owner_request=True)
        engine.set_route('main', lease, None, 'shrank', size='medium')
        self.add(engine, lease, 'plan', role='designer-planner', mode='plan', files=[])

    def test_plan_card_allowed_with_task_owner_request(self):
        engine, lease = self.run_with('medium')
        self.add(engine, lease, 'plan', role='designer-planner', mode='plan', files=[], owner_request=True)
        self.assertTrue(engine.status()['tasks']['plan']['owner_request'])


class PrePrTests(EngineFixture):
    """Contract item 7: the read-only size check and reviewer choice."""

    def run_with(self, size='medium', asks=None, name='state-prepr', **kw):
        engine = Engine(self.root / name, self.repo)
        self.run_lease = engine.open_session('main', size=size, asks=asks, require_size=True, **kw)
        return engine

    def write(self, lines, path='big.txt'):
        (self.repo / path).write_text('x\n' * lines)

    def test_budget_is_guide_times_asks(self):
        for size, asks, budget in (('tiny', 1, 50), ('tiny', 3, 150), ('medium', 1, 400), ('medium', 2, 800)):
            engine = self.run_with(size, asks, name='b-%s-%d' % (size, asks))
            with self.subTest(size, asks=asks):
                out = engine.prepr()
                self.assertEqual((size, asks, budget, False), (out['size'], out['asks'], out['budget'], out['over_budget']))
                self.assertEqual(self.git('rev-parse', 'HEAD'), out['base'])

    def test_over_budget_warns_with_both_sizes_and_succeeds(self):
        engine = self.run_with('tiny', 2)
        self.write(101)
        out = engine.prepr()
        self.assertTrue(out['over_budget'])
        self.assertEqual(101, out['changed_lines'])
        self.assertEqual('Size warning: declared tiny with 2 ask(s) budgets 100 changed lines; the diff has 101. '
                         'Run route --size TIER --reason TEXT if the work grew.', out['warning'])

    def test_within_budget_has_no_warning(self):
        engine = self.run_with('tiny', 2)
        self.write(100)
        out = engine.prepr()
        self.assertEqual((100, False, None), (out['changed_lines'], out['over_budget'], out['warning']))

    def test_route_to_a_fitting_tier_clears_the_warning(self):
        engine = self.run_with('tiny')
        lease = self.run_lease
        self.write(120)
        self.assertIsNotNone(engine.prepr()['warning'])
        engine.set_route('main', lease, None, 'grew', size='tiny', asks=2)  # budget 100: still over
        self.assertIsNotNone(engine.prepr()['warning'])
        engine.set_route('main', lease, None, 'grew', size='medium')
        out = engine.prepr()
        self.assertEqual((800, None), (out['budget'], out['warning']))  # medium keeps the 2 asks

    def test_large_run_has_no_budget(self):
        engine = self.run_with('large', owner_request=True)
        self.write(900)
        out = engine.prepr()
        self.assertEqual(('large', None, False, None), (out['size'], out['budget'], out['over_budget'], out['warning']))

    def test_items_run_gets_no_size_check(self):
        state, _ = load_2_4_state(self.root, self.repo)
        self.write(900)
        out = Engine(state, self.repo).prepr()
        self.assertEqual((None, None, None, False, None, 900),
                         (out['size'], out['asks'], out['budget'], out['over_budget'], out['warning'], out['changed_lines']))

    def test_prepr_without_a_base_reports_nulls_and_the_full_reviewer(self):
        state, _ = load_2_3_state(self.root, self.repo)
        engine = Engine(state, self.repo)
        with mock.patch.object(Engine, '_changed', side_effect=AssertionError('read the diff without a base')):
            out = engine.prepr()
        self.assertEqual((None, None, 'full', 'orchestra:code-reviewer', None),
                         (out['base'], out['changed_lines'], out['reviewer'], out['agent'], out['warning']))
        self.assertEqual(['requirements', 'correctness', 'security', 'tests', 'architecture', 'standards', 'cleanup'],
                         out['lenses'])
        self.assertEqual((None, False), (out['budget'], out['over_budget']))

    def test_prepr_on_a_state_with_no_session_reports_nulls(self):
        engine = Engine(self.root / 'empty', self.repo)
        out = engine.prepr()
        self.assertEqual((None, None, None, 'full'), (out['base'], out['changed_lines'], out['size'], out['reviewer']))
        self.assertIsNone(out['warning'])

    def test_reviewer_bands_at_50_51_400_401(self):
        engine = self.run_with('large', owner_request=True)
        expected = ((50, 'medium', 'orchestra:code-reviewer-medium'), (51, 'medium', 'orchestra:code-reviewer-medium'),
                    (400, 'medium', 'orchestra:code-reviewer-medium'), (401, 'full', 'orchestra:code-reviewer'))
        for lines, reviewer, agent in expected:
            self.write(lines)
            out = engine.prepr()
            with self.subTest(lines):
                self.assertEqual((lines, reviewer, agent), (out['changed_lines'], out['reviewer'], out['agent']))

    def test_reviewer_follows_summed_lines_not_largest_ask(self):
        engine = self.run_with('tiny', 3)  # three tiny asks of 30 lines each: the sum is 90
        for i in range(3):
            self.write(30, 'ask%d.txt' % i)
        out = engine.prepr()
        self.assertEqual((90, 'medium'), (out['changed_lines'], out['reviewer']))

    def test_untracked_files_count_toward_changed_lines(self):
        engine = self.run_with('medium')
        (self.repo / 'a').write_text('initial\nmore\n')  # tracked: the unterminated line is rewritten, one more is added: 3
        self.write(10)  # untracked: 10
        self.assertEqual(13, engine.prepr()['changed_lines'])

    def test_prepr_writes_no_state(self):
        engine = self.run_with('tiny')
        self.write(80)
        before = engine.state_path.read_bytes()
        engine.prepr()
        self.assertEqual(before, engine.state_path.read_bytes())

    def test_the_cli_prints_the_warning_to_stderr_and_exits_zero(self):
        engine = self.run_with('tiny')
        self.write(80)
        result = subprocess.run([sys.executable, str(SCRIPTS / 'orchestra.py'), '--repo', str(self.repo),
                                 '--state', str(self.root / 'state-prepr'), 'prepr'], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out['warning'], result.stderr.strip())


class FileBudgetTests(EngineFixture):
    """prepr lists the run's changed text files that grew past policy `file_budget_bytes`, against the run base."""

    def setUp(self):
        super().setUp()
        (self.repo / 'old.txt').write_text('o' * 150)
        (self.repo / 'small.txt').write_text('s' * 10)
        self.git('add', 'old.txt', 'small.txt')
        self.git('commit', '-qm', 'files')

    def run_with(self, policy, name='state-budget'):
        engine = Engine(self.root / name, self.repo, policy=policy)
        engine.open_session('main', size='medium', require_size=True)
        return engine

    def budget(self, engine):
        return engine.prepr()['file_budget']

    def test_no_budget_means_no_listing(self):
        engine = self.run_with(None)
        (self.repo / 'new.txt').write_text('n' * 500)
        self.assertIsNone(self.budget(engine))
        self.assertIsNone(self.budget(self.run_with({'file_budget_bytes': None}, 'state-null')))

    def test_invalid_budget_is_refused(self):
        for value in (0, -1, True, 1.5, '100'):
            with self.subTest(value), self.assertRaisesRegex(EngineError, 'file_budget_bytes must be a positive integer'):
                Engine(self.root / 'bad', self.repo, policy={'file_budget_bytes': value})

    def test_waiver_needs_a_glob_and_a_reason(self):
        for waivers in ([], {'gen/**': ''}, {'gen/**': '  '}, {'gen/**': None}, {'': 'generated'}):
            with self.subTest(waivers), self.assertRaisesRegex(EngineError, 'file_budget_waivers must map globs to reasons'):
                Engine(self.root / 'bad', self.repo, policy={'file_budget_bytes': 100, 'file_budget_waivers': waivers})

    def test_new_file_over_budget_is_listed(self):
        engine = self.run_with({'file_budget_bytes': 100})
        (self.repo / 'new.txt').write_text('n' * 101)
        (self.repo / 'fits.txt').write_text('f' * 100)
        self.assertEqual({'bytes': 100, 'grew': [{'path': 'new.txt', 'base_bytes': 0, 'bytes': 101}], 'waived': []},
                         self.budget(engine))

    def test_over_budget_file_that_grows_is_listed(self):
        engine = self.run_with({'file_budget_bytes': 100})
        (self.repo / 'old.txt').write_text('o' * 151)
        self.assertEqual([{'path': 'old.txt', 'base_bytes': 150, 'bytes': 151}], self.budget(engine)['grew'])

    def test_file_that_crosses_the_budget_is_listed(self):
        engine = self.run_with({'file_budget_bytes': 100})
        (self.repo / 'small.txt').write_text('s' * 120)
        self.assertEqual([{'path': 'small.txt', 'base_bytes': 10, 'bytes': 120}], self.budget(engine)['grew'])

    def test_shrinking_unchanged_and_deleted_files_are_not_listed(self):
        engine = self.run_with({'file_budget_bytes': 100})
        (self.repo / 'old.txt').write_text('o' * 140)  # over budget, but smaller than at the base
        (self.repo / 'small.txt').unlink()
        self.assertEqual([], self.budget(engine)['grew'])
        (self.repo / 'old.txt').write_text('o' * 150)  # back to the base content: unchanged
        self.assertEqual([], self.budget(engine)['grew'])

    def test_a_rename_compares_with_the_old_path(self):
        engine = self.run_with({'file_budget_bytes': 100})
        self.git('mv', 'old.txt', 'moved.txt')
        self.assertEqual([], self.budget(engine)['grew'])
        (self.repo / 'moved.txt').write_text('o' * 149 + 'x' * 5)
        self.assertEqual([{'path': 'moved.txt', 'base_bytes': 150, 'bytes': 154}], self.budget(engine)['grew'])

    def test_waived_files_are_named_with_their_reason(self):
        engine = self.run_with({'file_budget_bytes': 100, 'file_budget_waivers': {'gen/**': 'generated by make gen'}})
        (self.repo / 'gen').mkdir()
        (self.repo / 'gen/out.txt').write_text('g' * 500)
        out = self.budget(engine)
        self.assertEqual([], out['grew'])
        self.assertEqual([{'path': 'gen/out.txt', 'reason': 'generated by make gen'}], out['waived'])

    def test_binary_files_are_skipped(self):
        engine = self.run_with({'file_budget_bytes': 100})
        (self.repo / 'image.bin').write_bytes(b'\x89PNG\0' + b'x' * 500)
        self.assertEqual([], self.budget(engine)['grew'])

    def test_a_large_file_is_measured_without_reading_it_whole(self):
        engine = self.run_with({'file_budget_bytes': 100})
        (self.repo / 'huge.txt').write_text('h' * 300_000)
        real = Path.read_bytes

        def guarded(path):
            if path.name == 'huge.txt':
                raise AssertionError('read a large file whole')
            return real(path)

        with mock.patch('orchestra_core.engine.LARGE_FILE_BYTES', 1000), mock.patch.object(Path, 'read_bytes', guarded):
            self.assertEqual([{'path': 'huge.txt', 'base_bytes': 0, 'bytes': 300_000}], self.budget(engine)['grew'])

    def test_work_already_in_the_tree_at_start_is_not_listed(self):
        (self.repo / 'old.txt').write_text('o' * 400)  # dirty before the run starts
        engine = self.run_with({'file_budget_bytes': 100})
        self.assertEqual([], self.budget(engine)['grew'])

    def test_a_run_without_a_base_has_no_listing(self):
        state, _ = load_2_3_state(self.root, self.repo)
        engine = Engine(state, self.repo)
        engine.policy['file_budget_bytes'] = 100  # a 2.3 state binds its own policy hash; set the budget after
        self.assertIsNone(engine.prepr()['file_budget'])


class LegacyStateTests(EngineFixture):
    """Contract item 3: a run state written by the 2.3 engine loads under 2.4; a real policy change still refuses."""

    def test_a_2_3_state_loads_interrupts_resumes_and_finishes(self):
        state, lease = load_2_3_state(self.root, self.repo)
        engine = Engine(state, self.repo)
        session = engine.status()['session']
        self.assertTrue(session['active'])
        self.assertNotIn('items', session)
        engine.interrupt('main', lease)
        lease = engine.open_session('main')  # a resumed 2.3 run needs no --items
        engine.close_session('main', lease)
        self.assertEqual('completed', engine.status()['session']['outcome'])

    def test_the_cli_status_interrupt_and_finish_load_a_2_3_state(self):
        state, lease = load_2_3_state(self.root, self.repo)
        cli = [sys.executable, str(SCRIPTS / 'orchestra.py'), '--repo', str(self.repo), '--state', str(state)]
        for command in (['status'], ['--lease', lease, 'interrupt']):
            result = subprocess.run(cli + command, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
        lease = json.loads(subprocess.run(cli + ['start'], capture_output=True, text=True, check=True).stdout)['lease']
        result = subprocess.run(cli + ['--lease', lease, 'finish'], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_policy_change_still_refuses_a_2_3_state(self):
        state, _ = load_2_3_state(self.root, self.repo)
        with self.assertRaisesRegex(EngineError, r'policy changed while a run is active.*Upgrade from 2\.3 to 2\.4'):
            Engine(state, self.repo, dict(max_workers=3)).status()

    def test_a_state_with_items_never_takes_the_2_3_binding(self):
        state, _ = load_2_3_state(self.root, self.repo)
        data = json.loads((state / 'state.json').read_text())
        data['session'].update(items=2, route='inline')
        (state / 'state.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(EngineError, 'policy changed while a run is active'):
            Engine(state, self.repo).status()

    def test_a_state_with_size_never_takes_the_2_3_binding(self):
        state, _ = load_2_3_state(self.root, self.repo)
        data = json.loads((state / 'state.json').read_text())
        data['session'].update(size='tiny', asks=1, owner_request=False, route_log=[])
        (state / 'state.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(EngineError, 'policy changed while a run is active'):
            Engine(state, self.repo).status()

    def test_2_4_state_loads_and_keeps_2_4_routing(self):
        state, lease = load_2_4_state(self.root, self.repo)
        engine = Engine(state, self.repo)
        session = engine.status()['session']
        self.assertEqual((3, 'inline'), (session['items'], session['route']))
        task = dict(id='b', role='builder', mode='implementation', inputs=['spec'], acceptance=['check behavior'],
                    files=['b'], resources=[], dependencies=[])
        engine.add_task('main', lease, task)
        with self.assertRaisesRegex(EngineError, 'Inline route: the main session does this work; pass --helper REASON'):
            engine.dispatch('main', lease, 'b', 'w')
        self.assertEqual({'items': 9, 'route': 'workflow'}, engine.set_route('main', lease, 9, 'grew'))
        engine.interrupt('main', lease)
        engine.open_session('main', require_size=True)  # a resumed 2.4 run needs no --size
        self.assertEqual(9, engine.status()['session']['items'])

    def test_2_4_fixture_holds_only_placeholders(self):
        data = json.loads(STATE_2_4.read_text())
        self.assertEqual(('@REPO@', '@BASE@'), (data['repo'], data['session']['base']))
        text = STATE_2_4.read_text()
        for needle in ('/Users', '/private', '/tmp'):
            self.assertNotIn(needle, text)

    def test_2_4_policy_and_contract_hash_are_pinned(self):
        engine = Engine(self.root / 'pinned', self.repo)
        self.assertEqual('4b1d85568cf17dffc8adb272d1df95decfaf2a03c18c9176ff17190e4d5fb74d', engine.policy_hash)
        self.assertEqual('7b1f34b2bf297e6e95cdd59306a697f5a2b7410f5a84bc71feb7ffe0213439ed', engine.contract_hash)

    def test_one_combined_receipt_covers_all_required_categories(self):
        (self.repo / 'src' / 'auth').mkdir(parents=True)
        (self.repo / 'src/auth/login.py').write_text('x\n')
        required = self.engine.status(lenses=True)['required_lenses']
        self.assertIn('security', required)
        self.task('B')
        self.engine.report('w', self.engine.dispatch('main', self.lease, 'B', 'w'), done('Built B.'))
        self.engine.accept('main', self.lease, 'B')
        every = sorted(self.engine.status()['tasks'])
        path = self.root / 'combined.json'
        self.review(path, reviewer='final-reviewer', tasks=every, categories=required, final=True)
        self.engine.record_review('main', self.lease, 'final-reviewer', path, required, every, final=True)
        self.engine.check_completion('main', self.lease)


class DerivedLensTests(EngineFixture):
    """Contract item 6: the review lenses a change needs."""
    BASE = ['requirements', 'correctness', 'tests', 'architecture']

    def lenses(self):
        return self.engine.status(lenses=True)['required_lenses']

    def write(self, path, lines=1):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('x\n' * lines)

    def test_the_hook_facing_status_never_reads_the_diff(self):
        self.write('src/auth/login.py', 300)
        with mock.patch.object(Engine, '_changed', side_effect=AssertionError('status read the diff')):
            self.assertNotIn('required_lenses', self.engine.status())

    def test_the_cli_status_shows_the_lenses(self):
        self.write('src/auth/login.py')
        result = subprocess.run([sys.executable, str(SCRIPTS / 'orchestra.py'), '--repo', str(self.repo),
                                 '--state', str(self.root / 'state'), 'status'], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(['requirements', 'correctness', 'security', 'tests', 'architecture'],
                         json.loads(result.stdout)['required_lenses'])

    def test_an_unchanged_repository_needs_the_four_base_lenses(self):
        self.assertEqual(self.BASE, self.lenses())

    def test_a_sensitive_path_adds_security(self):
        self.write('src/app.py')
        self.assertEqual(self.BASE, self.lenses())
        self.write('src/auth/login.py')
        self.assertEqual(['requirements', 'correctness', 'security', 'tests', 'architecture'], self.lenses())

    def test_size_above_the_threshold_adds_standards_and_cleanup(self):
        self.write('big.txt', 200)
        self.assertEqual(self.BASE, self.lenses())  # the threshold itself is not above it
        self.write('big.txt', 201)
        self.assertEqual(self.BASE + ['standards', 'cleanup'], self.lenses())

    def test_the_threshold_comes_from_policy(self):
        engine = Engine(self.root / 'small', self.repo, dict(standards_min_lines=5))
        engine.open_session('main')
        self.write('mid.txt', 6)
        self.assertEqual(self.BASE + ['standards', 'cleanup'], engine.status(lenses=True)['required_lenses'])

    def test_both_additions_together(self):
        self.write('migrations/0001.sql', 250)
        self.assertEqual(['requirements', 'correctness', 'security', 'tests', 'architecture', 'standards', 'cleanup'],
                         self.lenses())

    def test_an_explicit_category_list_overrides_the_derived_set(self):
        engine = Engine(self.root / 'explicit', self.repo, dict(required_review_categories=['correctness', 'tests']))
        engine.open_session('main')
        self.write('src/auth/login.py', 300)
        self.assertEqual(['correctness', 'tests'], engine.status(lenses=True)['required_lenses'])

    def test_completion_waits_for_a_derived_lens(self):
        self.write('src/auth/login.py')
        self.task('B')
        self.engine.report('w', self.engine.dispatch('main', self.lease, 'B', 'w'), done('Built B.'))
        self.engine.accept('main', self.lease, 'B')
        every = sorted(self.engine.status()['tasks'])

        def final(name, categories):
            path = self.root / (name + '.json')
            self.review(path, reviewer='final-reviewer', tasks=every, categories=categories, final=True)
            self.engine.record_review('main', self.lease, 'final-reviewer', path, categories, every, final=True)

        final('base', self.BASE)
        with self.assertRaises(EngineError):
            self.engine.check_completion('main', self.lease)
        final('security', ['security'])
        self.engine.check_completion('main', self.lease)


class RemovedFeatureTests(EngineFixture):
    """Contract items 4, 7 and 8: the pieces 2.4 removed, the one review kept, and the gate-id query."""

    def test_a_wave_key_is_refused(self):
        with self.assertRaisesRegex(EngineError, 'Waves are removed; use dependencies'):
            self.task('b', wave='W1')
        self.assertEqual({}, self.engine.status()['tasks'])

    def test_waves_and_supersede_are_gone(self):
        self.task('b')
        self.assertNotIn('waves', self.engine.status())
        self.assertFalse(hasattr(Engine, 'supersede'))
        self.assertFalse(hasattr(Engine, '_check_wave'))

    def test_only_the_pre_pr_review_and_the_fix_re_review_are_recorded(self):
        self.task('b')
        self.engine.report('w', self.engine.dispatch('main', self.lease, 'b', 'w'), done('Built b.'))
        path = self.root / 'r.json'
        self.review(path, reviewer='rando', tasks=['b'])
        with self.assertRaisesRegex(EngineError, 'Only the pre-PR review and the fix re-review are recorded'):
            self.engine.record_review('main', self.lease, 'rando', path, ['correctness'], ['b'])
        self.assertEqual([], self.engine.status()['reviews'])
        self.allow_review('rando')  # a critic card's receipt is still allowed
        self.engine.record_review('main', self.lease, 'rando', path, ['correctness'], ['b'])
        self.assertEqual(1, len(self.engine.status()['reviews']))

    def test_the_final_review_is_always_recorded(self):
        self.task('b')
        self.engine.report('w', self.engine.dispatch('main', self.lease, 'b', 'w'), done('Built b.'))
        path = self.root / 'final.json'
        self.review(path, reviewer='final-reviewer', tasks=['b'], final=True)
        self.assertTrue(self.engine.record_review('main', self.lease, 'final-reviewer', path, ['correctness'], ['b'],
                                                  final=True)['final'])

    def test_current_gate_ids(self):
        self.assertEqual([], self.engine.current_gate_ids())  # no receipt
        failed = self.engine.run_gate('main', self.lease, 'bad', [sys.executable, '-c', 'raise SystemExit(1)'])
        self.assertEqual([], self.engine.current_gate_ids())  # a failed receipt is not a passed one
        first = self.engine.run_gate('main', self.lease, 'unit', [sys.executable, '-c', 'pass'])
        second = self.engine.run_gate('main', self.lease, 'lint', [sys.executable, '-c', 'pass'])
        self.assertEqual(sorted([first['id'], second['id']]), sorted(self.engine.current_gate_ids()))
        self.assertNotIn(failed['id'], self.engine.current_gate_ids())
        (self.repo / 'a').write_text('edited after the gates')
        self.assertEqual([], self.engine.current_gate_ids())  # stale receipts
        fresh = self.engine.run_gate('main', self.lease, 'unit', [sys.executable, '-c', 'pass'])
        self.assertEqual([fresh['id']], self.engine.current_gate_ids())


HEADINGS = ('Needs you', 'Still failing / next phase', 'Held log', 'Final rounds', 'Notes', 'Deferred findings',
            'Parked', 'Accepted', 'Failures')


class RunBriefTests(AutonomyFixture, HoldFixture):
    """SPEC 5.9 (the run brief on every end path) and 5.16 item 5 (`write_busy_brief`)."""

    def brief_text(self):
        return self.engine.status()['last_brief']['text']

    @staticmethod
    def section(text, title):
        start = text.index('### ' + title + '\n')
        rest = text[start + len(title) + 5:]
        end = rest.find('### ')
        return rest if end < 0 else rest[:end]

    def held_run(self):
        """B1/R1 held, B2 accepted and blamed by a final receipt that clears R1; R2 is B2's final repair."""
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g stays after one repair')
        self.built('B2')
        self.reviewed('clean2', ['B2'])
        self.engine.accept('main', self.lease, 'B2')
        self.reviewed('final', ['B1', 'R1', 'B2'], findings=['f'], final=True, task_findings={'B2': ['f']},
                      cleared={'R1': 'no defect'})
        self.task('R2', mode='repair', repair_of='B2', files=['B2'])

    def test_run_brief_lists_held_log_and_final_rounds(self):
        self.held_run()
        self.engine.interrupt('main', self.lease)
        text = self.brief_text()
        held = self.section(text, 'Held log')
        self.assertIn('R1 (chain R1, B1): g stays after one repair', held)
        self.assertIn('cleared by a lens: no defect', held)
        rounds = self.section(text, 'Final rounds')
        self.assertIn('round 1', rounds)
        self.assertIn('R2 (chain B2, R2)', rounds)
        self.assertIn('f', rounds)
        self.assertNotIn('R1', self.section(text, 'Still failing / next phase'))

    def test_run_brief_lists_still_failing_held_tips(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g stays after one repair')
        self.engine.interrupt('main', self.lease)
        failing = self.section(self.brief_text(), 'Still failing / next phase')
        self.assertIn('R1 (chain R1, B1)', failing)
        self.assertIn('g stays after one repair', failing)
        self.assertNotIn('attributed', self.section(self.brief_text(), 'Held log'))

    def test_close_session_writes_run_brief(self):
        (self.state / 'progress.md').write_text('# Plan X\nearlier line\n')
        self.engine.close_session('main', self.lease)
        progress = (self.state / 'progress.md').read_text()
        self.assertTrue(progress.startswith('# Plan X\nearlier line\n'))
        self.assertEqual(progress.count('## Run brief 2027-01-15T08:00:00'), 1)
        self.assertIn('- stop reason: closed', progress)
        stored = self.engine.status()['last_brief']
        self.assertEqual((stored['reason'], stored['at']), ('closed', '2027-01-15T08:00:00+00:00'))
        self.assertEqual(stored['path'], str((self.state / 'progress.md').resolve()))
        self.assertTrue(stored['text'].startswith('## Run brief 2027-01-15T08:00:00'))
        self.assertIn(stored['text'], progress)

    def test_interrupt_and_harness_end_write_run_brief(self):
        self.engine.interrupt('main', self.lease)
        self.assertEqual(self.engine.status()['last_brief']['reason'], 'interrupted')
        self.assertIn('- stop reason: interrupted', (self.state / 'progress.md').read_text())
        self.lease = self.engine.open_session('main', harness_session='S')
        self.now[0] += 60
        self.assertTrue(self.engine.end_harness_session('S'))
        stored = self.engine.status()['last_brief']
        self.assertEqual(stored['reason'], 'ended')
        self.assertIn('- stop reason: ended', stored['text'])
        self.lease = self.engine.open_session('main')
        self.now[0] += 60
        self.assertTrue(self.engine.interrupt_active())
        self.assertEqual(self.engine.status()['last_brief']['reason'], 'interrupted')
        self.assertEqual((self.state / 'progress.md').read_text().count('## Run brief'), 3)

    def test_noop_end_paths_write_no_brief(self):
        self.engine.interrupt('main', self.lease)
        before = (self.state / 'progress.md').read_bytes()
        self.assertFalse(self.engine.interrupt_active())
        self.assertFalse(self.engine.end_harness_session('nobody'))
        self.assertEqual(before, (self.state / 'progress.md').read_bytes())

    def test_run_brief_lists_still_failing_on_deadline(self):
        self.arm()
        self.built('B2')
        self.reviewed('b2', ['B2'], findings=['b2 breaks the parser'])
        self.now[0] += 7200
        self.assertIsNone(self.engine.hook_stop())
        stored = self.engine.status()['last_brief']
        self.assertEqual(stored['reason'], 'deadline')
        failing = self.section(stored['text'], 'Still failing / next phase')
        self.assertIn('B2', failing)
        self.assertIn('b2 breaks the parser', failing)
        self.assertIn('- deadline: ', stored['text'])

    def test_brief_command_is_read_only(self):
        self.engine.interrupt('main', self.lease)
        state_before = self.engine.state_path.read_bytes()
        progress_before = (self.state / 'progress.md').read_bytes()
        self.assertEqual(self.engine.brief(), self.brief_text())
        self.assertEqual(state_before, self.engine.state_path.read_bytes())
        self.assertEqual(progress_before, (self.state / 'progress.md').read_bytes())

    def test_brief_is_empty_before_any_run_ends(self):
        self.assertIsNone(self.engine.brief())

    def test_run_brief_needs_you_precedes_accepted(self):
        self.accept_card('done')
        self.task('p')
        self.engine.park('main', self.lease, 'p', 'needs a push')
        self.engine.interrupt('main', self.lease)
        text = self.brief_text()
        positions = [text.index('### ' + title + '\n') for title in HEADINGS]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('p: needs a push', self.section(text, 'Needs you'))

    def test_run_brief_keeps_2_1_lines(self):
        self.engine.run_gate('main', self.lease, 'old-failure', [sys.executable, '-c', 'raise SystemExit(4)'])
        self.arm(passes='1', stalls='2', deadline=iso(T0 + 60))  # a 2.1 ledger: the caps are recorded, never enforced
        self.accept_card('done')
        self.task('p')
        self.engine.park('main', self.lease, 'p', 'needs a push')
        self.task('b')
        token = self.engine.dispatch('main', self.lease, 'b', 'wb')
        self.engine.report('wb', token, done('Implemented b.'))
        report = self.root / 'r.json'
        self.review(report, reviewer='rev-1', tasks=['b'], findings=['off by one'])
        self.allow_review('rev-1')
        self.engine.record_review('main', self.lease, 'rev-1', report, ['correctness'], ['b'], findings=['off by one'])
        self.engine.run_gate('main', self.lease, 'unit', [sys.executable, '-c', 'raise SystemExit(3)'])
        self.worker_running()
        self.engine.hook_stop()
        self.engine.hook_stop()
        self.now[0] = T0 + 61
        self.engine.hook_stop()
        text = self.brief_text()
        self.assertTrue(text.startswith('## Run brief 2027-01-15T08:01:01'))
        self.assertNotIn('Autonomy report', text)
        for fragment in ('- stop reason: deadline', '- passes: 1', '- stalls: 1', 'max_passes 1', 'max_stalls 2',
                         'recorded, not enforced', 'done (investigator/code)',
                         'p: needs a push', 'gate unit: exit 3', 'review rev-1: BLOCKED (off by one)'):
            self.assertIn(fragment, text)
        self.assertNotIn('old-failure', text)
        self.assertEqual(self.engine.autonomy_report()['text'], text)

    def test_unarmed_completed_run_brief_says_ready_to_release(self):
        self.engine.close_session('main', self.lease)
        self.assertIn('ready to release', self.section(self.brief_text(), 'Needs you'))
        self.lease = self.engine.open_session('main')
        self.engine.interrupt('main', self.lease)
        self.assertNotIn('ready to release', self.brief_text())

    def test_run_brief_marks_repaired_chains(self):
        self.blocked_chain(check=False)
        self.reviewed('clean', ['R1', 'B1'], repair_check=True)
        self.engine.accept('main', self.lease, 'R1')
        self.engine.accept('main', self.lease, 'B1')
        self.engine.interrupt('main', self.lease)
        accepted = self.section(self.brief_text(), 'Accepted')
        self.assertIn('repaired (B1, R1)', accepted)
        self.assertIn('R1 (builder/repair)', accepted)

    def test_run_brief_lists_notes(self):
        self.built('B1')
        note = lambda body: body.update(out_of_scope=['docs drift'], issues=body['issues'] + [dict(text='nit: rename x', severity='note')])
        receipt = self.reviewed('clean', ['B1'], mutate=note, final=True)
        self.engine.add_finding('main', self.lease, receipt['id'], 'out_of_scope', 0, 'brief', 'owner decides')
        self.built('B2')
        wave = self.reviewed('w', ['B2'], findings=['slow path'])
        self.engine.add_finding('main', self.lease, wave['id'], 'finding', 0, 'deferred', 'next sprint')
        self.engine.interrupt('main', self.lease)
        text = self.brief_text()
        self.assertIn('nit: rename x', self.section(text, 'Notes'))
        self.assertIn('slow path -- next sprint', self.section(text, 'Deferred findings'))
        needs = self.section(text, 'Needs you')
        self.assertIn('docs drift -- owner decides', needs)
        self.assertIn('slow path -- next sprint', needs)

    def test_progress_writes_are_single_appends(self):
        real_open, real_write, real_close = os.open, os.write, os.close
        opened, fds, writes, inject = [], set(), [], []

        def spy_open(path, flags, *args, **kwargs):
            if str(path).endswith('progress.md') and inject:
                other = real_open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
                real_write(other, inject.pop().encode())
                real_close(other)
            fd = real_open(path, flags, *args, **kwargs)
            if str(path).endswith('progress.md'):
                opened.append(flags)
                fds.add(fd)
            return fd

        def spy_write(fd, data):
            if fd in fds:
                writes.append(data)
            return real_write(fd, data)

        def spy_close(fd):
            fds.discard(fd)
            return real_close(fd)

        def single(label, action):
            opened.clear()
            writes.clear()
            with mock.patch.object(os, 'open', spy_open), mock.patch.object(os, 'write', spy_write), \
                    mock.patch.object(os, 'close', spy_close):
                action()
            self.assertEqual(len(opened), 1, label)
            self.assertTrue(opened[0] & os.O_APPEND, label)
            self.assertEqual(len(writes), 1, label)

        self.blocked_chain()
        single('hold', lambda: self.engine.hold('main', self.lease, 'R1', 'g'))
        self.fresh({})
        inject.append('line from another writer\n')
        single('close_session', lambda: self.engine.close_session('main', self.lease))
        text = (self.state / 'progress.md').read_text()
        self.assertLess(text.index('line from another writer'), text.index('## Run brief'))
        from orchestra_core.engine import write_busy_brief
        single('write_busy_brief', lambda: write_busy_brief(self.state, '2027-01-15T08:00:00+00:00'))
        text = (self.state / 'progress.md').read_text()
        self.assertIn('stop reason: state busy', text)
        self.assertIn('line from another writer', text)

    def test_write_busy_brief_leaves_state_json_alone(self):
        from orchestra_core.engine import write_busy_brief
        before = self.engine.state_path.read_bytes()
        write_busy_brief(self.state, '2027-01-15T08:00:00+00:00')
        self.assertEqual(before, self.engine.state_path.read_bytes())
        self.assertNotIn('last_brief', json.loads(before))

    def test_end_paths_keep_stopped_autonomy_brief(self):
        self.arm()
        self.now[0] += 7200
        self.assertIsNone(self.engine.hook_stop())
        stopped = self.engine.status()['last_brief']
        self.assertEqual(stopped['reason'], 'deadline')
        self.engine.interrupt('main', self.lease)
        self.lease = self.engine.open_session('main', harness_session='S2')
        self.assertTrue(self.engine.end_harness_session('S2'))
        progress = (self.state / 'progress.md').read_text()
        self.assertEqual(progress.count('## Run brief'), 3)
        self.assertIn('- stop reason: interrupted', progress)
        self.assertIn('- stop reason: ended', progress)
        self.assertEqual(self.engine.status()['last_brief'], stopped)
        self.lease = self.engine.open_session('main')
        self.arm(deadline=iso(self.now[0] + 3600))
        self.engine.interrupt('main', self.lease)
        self.assertEqual(self.engine.status()['last_brief']['reason'], 'interrupted')
        self.assertEqual((self.state / 'progress.md').read_text().count('## Run brief'), 4)

    def test_last_brief_must_be_well_formed(self):
        state = json.loads(self.engine.state_path.read_text())
        state['last_brief'] = {'reason': 'closed'}
        self.engine.state_path.write_text(json.dumps(state))
        with self.assertRaisesRegex(EngineError, 'Invalid last_brief'):
            self.engine.status()

    def test_lock_wait_raises_state_busy_and_default_blocks(self):
        from orchestra_core.engine import StateBusy
        busy = Engine(self.state, self.repo, lock_wait=0.3, clock=lambda: self.now[0])
        self.engine.status()  # creates state.lock
        with (self.state / 'state.lock').open('a+') as lock:
            portable.lock(lock, exclusive=True)
            with self.assertRaises(StateBusy):
                busy.status()
            self.assertTrue(issubclass(StateBusy, EngineError))
        self.assertIn('session', busy.status())  # free again: the same engine reads


class AutonomyNoCapTests(AutonomyFixture, HoldFixture):
    """SPEC 5.8 (no count stops the loop, held work is live, completion order) and section 8 (2.1 runs)."""

    @staticmethod
    def section(text, title):
        start = text.index('### ' + title + '\n')
        rest = text[start + len(title) + 5:]
        end = rest.find('### ')
        return rest if end < 0 else rest[:end]

    def passing_gate(self):
        self.assertTrue(self.engine.run_gate('main', self.lease, 'fixture', PASS_ARGV)['passed'])

    def finish_line(self):
        """B1 accepted, a final review over every category, and the ledger check passed on the current artifact."""
        self.built('B1')
        self.reviewed('clean', ['B1'])
        self.engine.accept('main', self.lease, 'B1')
        self.reviewed('final', ['B1'], final=True, categories=self.ALL)
        self.passing_gate()

    def last_stop(self):
        return self.auto().get('last_stop_reason')

    def test_hook_stop_completes_when_everything_holds(self):
        self.arm()
        self.finish_line()
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.last_stop(), 'complete')

    def test_stop_check_continues_while_final_finding_open_without_cards(self):
        self.arm()
        self.built('B1')
        self.reviewed('clean', ['B1'])
        self.engine.accept('main', self.lease, 'B1')
        self.reviewed('final', ['B1'], findings=['f'], final=True, task_findings={'B1': ['f']})
        reason = self.engine.hook_stop()
        self.assertIsInstance(reason, str)
        self.assertIn('start the final repair round', reason)
        self.assertIsNone(self.last_stop())
        self.assertTrue(self.engine.autonomy_active())

    def test_a_silent_worker_is_surfaced_and_a_repeat_parks_it_as_lost(self):
        self.arm(deadline=iso(T0 + 20000))
        self.worker_running('busy')
        self.assertIsNone(self.engine.hook_stop())  # a worker that just started: wait for the harness to wake us
        self.now[0] = T0 + 3700
        message = self.engine.hook_stop()
        self.assertIn('busy', message)
        self.assertIn('silent for over 60 minutes', message)
        self.assertIn('parked as lost-worker', self.engine.hook_stop())  # nothing changed since the nudge: park it and re-plan
        self.assertEqual(self.engine.status()['tasks']['busy']['parked_reason'], 'lost-worker')
        self.assertIsNone(self.last_stop())

    def test_a_sub_minute_stale_limit_is_worded_in_seconds(self):
        self.fresh({'worker_stale_seconds': 30})
        self.arm(deadline=iso(T0 + 20000))
        self.worker_running('busy')
        self.now[0] = T0 + 40
        message = self.engine.hook_stop()
        self.assertIn('silent for over 30 seconds', message)
        self.assertNotIn('0 minutes', message)

    def test_status_names_running_workers_and_a_silent_one_before_any_stop_event(self):
        # The Stop hook never fires while the session idles on a lost worker, so the status read the band polls
        # has to say it: running counts background cards, silent names those past the limit with their minutes.
        self.arm(deadline=iso(T0 + 20000))
        self.worker_running('busy')
        status = self.engine.autonomy_status()
        self.assertEqual((status['running'], status['silent']), (1, []))
        self.now[0] = T0 + 3700
        status = self.engine.autonomy_status()
        self.assertEqual((status['running'], status['silent']), (1, [{'id': 'busy', 'minutes': 62}]))
        self.assertTrue(status['active'])  # read-only: no stop, no state write
        before = self.engine.state_path.read_bytes()
        self.engine.autonomy_status()
        self.assertEqual(before, self.engine.state_path.read_bytes())

    def test_a_card_requeued_by_a_new_session_loses_its_start_time(self):
        self.arm(deadline=iso(T0 + 20000))
        self.worker_running('busy')
        self.assertIn('started_at', self.engine.status()['tasks']['busy'])
        self.engine.interrupt('main', self.lease)
        self.lease = self.engine.open_session('main')
        self.assertNotIn('started_at', self.engine.status()['tasks']['busy'])

    def test_a_required_gate_that_fails_three_times_in_a_row_asks_for_a_repair_card_then_escalates(self):
        failing = [sys.executable, '-c', 'raise SystemExit(3)']
        self.arm(checks=['fixture: ' + shlex.join(failing)], deadline=iso(T0 + 20000))
        self.built('B1')
        self.reviewed('clean', ['B1'])
        self.engine.accept('main', self.lease, 'B1')
        for _ in range(2):
            self.engine.run_gate('main', self.lease, 'fixture', failing, again=True)
        self.assertNotIn('repair card', self.engine.hook_stop())  # two failures are not yet a pattern
        self.engine.run_gate('main', self.lease, 'fixture', failing, again=True)
        self.assertIn('repair card', self.engine.hook_stop())
        self.assertIn('repair card', self.engine.hook_stop())
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.last_stop(), 'needs-owner:escalated')
        self.assertIn('required gate fixture failed 3 times in a row', self.engine.brief())
        log = self.engine.status()['gates'][-1]['path']
        self.assertIn('read its log %s' % log, self.engine.brief())  # the owner gets the path, not a search

    def test_hook_stop_never_stops_on_pass_count(self):
        self.arm()
        self.task('x')
        for n in range(1, 51):
            self.task('x%d' % n)  # each pass changes the board
            self.assertIn('Autonomy pass %d:' % n, self.engine.hook_stop())
        self.assertEqual((self.auto()['passes'], self.auto()['active'], self.last_stop()), (50, True, None))

    def test_hook_stop_never_stops_on_stalls(self):
        self.arm()
        self.task('x')
        self.worker_running()
        self.assertIsInstance(self.engine.hook_stop(), str)
        for _ in range(10):  # each unchanged turn ends quietly and counts a stall
            self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['stalls'], self.auto()['active'], self.last_stop()), (10, True, None))

    def test_hook_stop_continues_while_held_cards_remain(self):
        self.arm()
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        self.assertEqual(self.engine.ready('main', self.lease), [])
        reason = self.engine.hook_stop()
        self.assertIn('start or continue the final phase', reason)
        self.assertEqual((self.auto()['active'], self.last_stop()), (True, None))

    def test_hook_stop_parked_only_when_held_and_parked(self):
        self.arm()
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        self.task('P')
        self.engine.park('main', self.lease, 'P', 'needs-owner: a push')
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['active'], self.last_stop()), (False, 'parked-only'))
        needs = self.section(self.engine.status()['last_brief']['text'], 'Needs you')
        self.assertIn('P: needs-owner: a push', needs)
        self.assertIn('R1 (chain R1, B1)', needs)

    def test_complete_skips_ledger_checks_until_all_accepted(self):
        real, calls = Engine.artifact, []

        def counting(engine, scope=None):
            calls.append(scope)
            return real(engine, scope)

        self.arm()
        self.passing_gate()
        self.task('x', role='investigator', mode='code')
        with mock.patch.object(Engine, 'artifact', counting):
            self.assertIsInstance(self.engine.hook_stop(), str)
        self.assertEqual(calls, [])
        self.engine.report('w', self.engine.dispatch('main', self.lease, 'x', 'w'), done('Inspected x.'))
        self.engine.accept('main', self.lease, 'x')
        with mock.patch.object(Engine, 'artifact', counting):
            self.assertIn('every card is accepted', self.engine.hook_stop())  # no final review: not complete
        self.assertGreater(len(calls), 0)
        self.assertIsNone(self.last_stop())

    def test_hook_stop_not_complete_while_held(self):
        self.arm()
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        self.reviewed('final', ['B1', 'R1'], final=True, categories=self.ALL, cleared={'R1': 'no defect'})
        self.passing_gate()
        self.assertIn('Re-plan', self.engine.hook_stop())  # a current final receipt covers the held chain: re-plan, then the owner decides
        self.assertIn('still nothing to do', self.engine.hook_stop())
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['active'], self.last_stop()), (False, 'needs-owner:escalated'))

    def test_hook_stop_not_complete_while_final_finding_open(self):
        self.arm()
        self.built('B2')
        self.reviewed('clean', ['B2'])
        self.engine.accept('main', self.lease, 'B2')
        self.reviewed('final', ['B2'], findings=['f'], final=True, categories=self.ALL, task_findings={'B2': ['f']})
        self.passing_gate()
        self.engine.hook_stop()
        self.assertNotEqual(self.last_stop(), 'complete')

    def test_hook_stop_not_complete_while_card_repairing(self):
        self.arm()
        self.built('B2')
        self.reviewed('final', ['B2'], findings=['f'], final=True, task_findings={'B2': ['f']})
        self.task('R2', mode='repair', repair_of='B2', files=['B2'])
        self.assertEqual(self.states('B2'), ['repairing'])
        self.passing_gate()
        self.assertIsInstance(self.engine.hook_stop(), str)
        self.assertEqual((self.auto()['active'], self.last_stop()), (True, None))

    def test_hook_stop_deadline_still_stops(self):
        self.arm(deadline=iso(T0 + 60))
        self.task('x')
        self.assertIsInstance(self.engine.hook_stop(), str)
        self.now[0] = T0 + 61
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['active'], self.last_stop(), self.auto()['passes']), (False, 'deadline', 1))
        self.assertEqual(self.engine.status()['last_brief']['reason'], 'deadline')

    def test_ledger_without_caps_arms(self):
        self.assertTrue(self.arm()['active'])
        self.assertNotIn('max_passes', self.auto())
        self.assertNotIn('max_stalls', self.auto())
        status = self.engine.autonomy_status()
        self.assertEqual((status['active'], status['max_passes'], status['max_stalls']), (True, None, None))

    def test_2_1_ledger_with_caps_still_arms_and_caps_are_ignored(self):
        self.arm(passes='1', stalls='1')
        self.task('x')
        self.worker_running()
        for n in range(4):
            self.task('y%d' % n)
            self.assertIsInstance(self.engine.hook_stop(), str)
        for _ in range(3):
            self.assertIsNone(self.engine.hook_stop())
        auto = self.auto()
        self.assertEqual((auto['max_passes'], auto['max_stalls']), (1, 1))  # recorded
        self.assertEqual((auto['passes'], auto['stalls'], auto['active']), (4, 3, True))  # never enforced

    def test_signature_changes_on_report_hold_or_gate(self):
        self.arm()
        sig = lambda: self.engine.autonomy_status()['signature']
        seen = [sig()]
        self.assertRegex(seen[0], r'^[0-9a-f]{64}$')
        self.assertEqual(sig(), seen[0])  # a no-op leaves it

        def step(label, action):
            action()
            seen.append(sig())
            self.assertNotEqual(seen[-1], seen[-2], label)
            self.assertEqual(sig(), seen[-1], label + ' (read twice)')

        step('report', lambda: self.built('B1'))
        step('review', lambda: self.reviewed('final', ['B1'], findings=['f'], task_findings={'B1': ['f']}, final=True))
        step('repair card', lambda: self.task('R1', mode='repair', repair_of='B1', files=['B1']))
        step('repair report', lambda: self.engine.report(
            'r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), done('Repaired')))
        step('check', lambda: self.reviewed('check', ['R1', 'B1'], findings=['g'],
                                            task_findings={'R1': ['g'], 'B1': []}, repair_check=True))
        step('hold', lambda: self.engine.hold('main', self.lease, 'R1', 'g'))
        step('gate', self.passing_gate)

    def state_2_1(self, queued=True):
        """A 2.1 run: an accepted card, a parked card, optionally a queued one, a review, a passed gate and an armed
        ledger with caps. The engine writes it, then every key 2.1 never wrote is removed from the stored state."""
        self.accept_card('a')
        self.task('p')
        self.engine.park('main', self.lease, 'p', 'needs a push')
        if queued:
            self.task('q')
        self.arm(passes='1', stalls='2')
        self.passing_gate()
        raw = json.loads(self.engine.state_path.read_text())
        for key in ('signature', 'rev', 'seq', 'last_brief', 'held', 'last_signature'):
            raw['autonomy'].pop(key, None)
        for key in set(raw) - {'version', 'repo', 'policy', 'session', 'tasks', 'permits', 'reviews', 'gates', 'autonomy'}:
            raw.pop(key)
        self.engine.state_path.write_text(json.dumps(raw))
        return self.lease

    def test_2_1_state_fixture_loads_under_2_2(self):
        self.state_2_1()
        status = self.engine.status()
        self.assertEqual(sorted(status['tasks']), ['a', 'p', 'q'])
        self.assertEqual((status['autonomy']['max_passes'], status['autonomy']['passes']), (1, 0))
        self.assertTrue(self.engine.autonomy_active())
        for expected in (1, 2, 3, 4):  # past the old cap, which is recorded only
            self.task('n%d' % expected)
            self.assertIn('Autonomy pass %d:' % expected, self.engine.hook_stop())
        self.assertEqual((self.auto()['active'], self.auto()['max_passes'], self.auto()['passes']), (True, 1, 4))
        self.assertRegex(self.engine.autonomy_status()['signature'], r'^[0-9a-f]{64}$')

    def test_2_1_parked_card_keeps_park_semantics(self):
        lease = self.state_2_1(queued=False)
        self.engine.unpark('main', lease, 'p')
        self.engine.park('main', lease, 'p', 'needs-owner: a push')
        self.assertIsNone(self.engine.hook_stop())  # a card parked for the owner and nothing else live: the 2.1 stop
        self.assertEqual(self.last_stop(), 'parked-only')
        self.engine.unpark('main', lease, 'p')
        self.assertEqual(self.states('p'), ['queued'])
        self.engine.park('main', lease, 'p', 'needs a push again')
        with self.assertRaisesRegex(EngineError, 'accepted'):
            self.engine.close_session('main', lease)


UNIT_ARGV = [sys.executable, '-c', 'print("passed")']
RELEASE_POLICY = dict(required_checks=[dict(name='unit', argv=UNIT_ARGV)],
                      release=dict(enabled=True, authorization='user request', remote='devops', target='main',
                                   argv=['git', 'push', 'devops', 'HEAD:main']))
PREAUTH = '- Release: pre-authorized devops main'


class ReleasePreauthTests(AutonomyFixture, HoldFixture):
    """SPEC 5.8 item 8: the ledger's Release line, `autonomy.release`, and the exact-pair exemption."""

    def setUp(self):
        super().setUp()
        self.fresh(RELEASE_POLICY)

    def boundaries(self, release):
        return [release if line == AUTONOMY_FIXED[0] else line for line in AUTONOMY_FIXED]

    def release_evidence(self):
        """A clean final review and a passed required gate on the current artifact: what a release permit needs."""
        path = self.root / 'release-final.json'
        self.review(path, reviewer='reviewer', categories=self.ALL, final=True)
        self.engine.record_review('main', self.lease, 'reviewer', path, self.ALL, final=True)
        self.engine.run_gate('main', self.lease, 'unit', UNIT_ARGV)

    def arm_with(self, release):
        self.ledger(boundaries=self.boundaries(release))
        return self.engine.arm_autonomy()

    def test_arm_preauthorized_release_permits_exact_pair(self):
        self.release_evidence()
        self.arm_with(PREAUTH)
        self.assertEqual(self.auto()['release'], dict(remote='devops', target='main'))
        self.assertTrue(self.engine.autonomy_active())
        permit = self.engine.release_permit('main', self.lease, 'devops', 'main')
        self.assertEqual(permit['action'], 'release')
        self.assertEqual(permit, self.engine.check_release('devops', 'main', argv=['git', 'push', 'devops', 'HEAD:main']))
        for pair in (('devops', 'other'), ('origin', 'main')):  # any other pair stays an approval boundary
            with self.subTest(pair=pair):
                with self.assertRaisesRegex(EngineError, 'autonomy'):
                    self.engine.release_permit('main', self.lease, *pair)
                with self.assertRaisesRegex(EngineError, 'autonomy'):
                    self.engine.check_release(*pair)

    def test_permit_refused_under_autonomy_without_preauthorization(self):
        self.release_evidence()
        self.arm_with(AUTONOMY_FIXED[0])
        self.assertNotIn('release', self.auto())
        with self.assertRaisesRegex(EngineError, 'autonomy'):
            self.engine.release_permit('main', self.lease, 'devops', 'main')
        with self.assertRaisesRegex(EngineError, 'autonomy'):
            self.engine.check_release('devops', 'main')

    def test_preauthorization_mismatch_refused(self):
        for line in ('- Release: pre-authorized devops other', '- Release: pre-authorized origin main'):
            with self.subTest(line=line):
                self.ledger(boundaries=self.boundaries(line))
                with self.assertRaisesRegex(EngineError, 'Release pre-authorization must match policy.release'):
                    self.engine.arm_autonomy()
                self.assertIsNone(self.auto())
        disabled = dict(RELEASE_POLICY, release=dict(RELEASE_POLICY['release'], enabled=False))
        self.fresh(disabled)
        self.ledger(boundaries=self.boundaries(PREAUTH))
        with self.assertRaisesRegex(EngineError, 'Release pre-authorization must match policy.release'):
            self.engine.arm_autonomy()
        self.fresh(None)  # no release policy at all
        self.ledger(boundaries=self.boundaries(PREAUTH))
        with self.assertRaisesRegex(EngineError, 'Release pre-authorization must match policy.release'):
            self.engine.arm_autonomy()

    def test_arm_refuses_malformed_release_line(self):
        bad = ['- Release: pre-authorized origin', '- Release: pre-authorized devops main extra', '- Release: allowed',
               '- Release:', '- Release: no release, permit or deploy', '- Release: pre-authorized  ']
        for line in bad:
            with self.subTest(line=line):
                self.ledger(boundaries=self.boundaries(line))
                with self.assertRaisesRegex(EngineError, 'Approval boundaries need exactly one Release line'):
                    self.engine.arm_autonomy()
        for pair in ([AUTONOMY_FIXED[0], PREAUTH], [PREAUTH, PREAUTH]):
            with self.subTest(pair=pair):
                self.ledger(boundaries=[*pair, *AUTONOMY_FIXED[1:]])
                with self.assertRaisesRegex(EngineError, 'Approval boundaries need exactly one Release line'):
                    self.engine.arm_autonomy()

    def test_ledger_with_both_release_lines_refused(self):
        self.ledger(boundaries=[*AUTONOMY_FIXED, PREAUTH])
        with self.assertRaisesRegex(EngineError, 'Approval boundaries need exactly one Release line'):
            self.engine.arm_autonomy()
        self.assertIsNone(self.auto())

    def test_arm_from_shipped_template_accepts_fixed_release_line(self):
        template = (Path(__file__).resolve().parents[1] / 'plugins/orchestra/config/autonomy-template.md').read_text()
        filled = (template.replace('<one line goal>', 'ship the fixture')
                  .replace('<ISO 8601 time with a UTC offset, in the future>', iso(T0 + 3600))
                  .replace('<NAME: argv...>', 'fixture: ' + shlex.join(PASS_ARGV)))
        self.assertIn(AUTONOMY_FIXED[0], filled)
        (self.state / 'autonomy.md').write_text(filled)
        self.assertTrue(self.engine.arm_autonomy()['active'])
        self.assertNotIn('release', self.auto())
        self.engine.disarm_autonomy()
        (self.state / 'autonomy.md').write_text(filled.replace(AUTONOMY_FIXED[0], PREAUTH))
        self.assertTrue(self.engine.arm_autonomy()['active'])
        self.assertEqual(self.auto()['release'], dict(remote='devops', target='main'))

    def test_preauthorization_keeps_the_other_fixed_lines_required(self):
        for line in AUTONOMY_FIXED[1:]:
            with self.subTest(line=line):
                self.ledger(boundaries=[l for l in self.boundaries(PREAUTH) if l != line])
                with self.assertRaisesRegex(EngineError, 'Approval boundaries must keep the fixed line'):
                    self.engine.arm_autonomy()


class EngineOwnedKeyTests(AutonomyFixture):
    """A task file cannot set what the engine owns; a hand-edited state with broken links fails loudly."""

    def edit(self, change):
        path = self.state / 'state.json'
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data))

    def test_add_refuses_every_engine_owned_key(self):
        self.task('B1')
        for key in ENGINE_TASK_KEYS:
            with self.subTest(key=key), self.assertRaisesRegex(EngineError, 'engine-owned keys: ' + key):
                self.task('X', **{key: 'B1' if key == 'repaired_by' else 1})
        self.assertEqual(sorted(self.engine.status()['tasks']), ['B1'])

    def test_repair_of_only_on_a_builder_repair_card(self):
        self.task('B1')
        self.engine.report('w', self.engine.dispatch('main', self.lease, 'B1', 'w'), done())
        self.engine.accept('main', self.lease, 'B1')
        for name, kw in (('self', dict(repair_of='self')), ('ghost', dict(repair_of='ghost')), ('foreign', dict(repair_of='B1')),
                         ('critic', dict(role='critic', mode='judge', repair_of='B1'))):
            with self.subTest(name=name), self.assertRaisesRegex(EngineError, 'Only a builder repair card names repair_of'):
                self.task(name, **kw)
        with self.assertRaisesRegex(EngineError, 'Repair needs a specific earlier builder task'):
            self.task('R0', mode='repair', repair_of='R0')
        self.assertEqual(self.engine.status()['tasks']['B1']['state'], 'accepted')
        self.assertEqual(self.engine.ready('main', self.lease), [])

    def test_hand_edited_repair_links_and_review_since_fail_loudly(self):
        self.task('B1')
        self.task('B2', files=['B2'])
        edits = dict(
            self_cycle=lambda d: d['tasks']['B1'].update(repair_of='B1'),
            ghost_repair_of=lambda d: d['tasks']['B1'].update(repair_of='ghost'),
            ghost_repaired_by=lambda d: d['tasks']['B1'].update(repaired_by='ghost'),
            two_card_cycle=lambda d: (d['tasks']['B1'].update(repair_of='B2'), d['tasks']['B2'].update(repair_of='B1')),
            repaired_by_cycle=lambda d: (d['tasks']['B1'].update(repaired_by='B2'), d['tasks']['B2'].update(repaired_by='B1')),
            since_text=lambda d: d['tasks']['B1'].update(review_since='5'),
            since_negative=lambda d: d['tasks']['B1'].update(review_since=-1),
            since_bool=lambda d: d['tasks']['B1'].update(review_since=True))
        good = (self.state / 'state.json').read_text()
        for name, change in edits.items():
            with self.subTest(name=name):
                (self.state / 'state.json').write_text(good)
                self.edit(change)
                with self.assertRaisesRegex(EngineError, 'Malformed run state'):
                    self.engine.ready('main', self.lease)

    def test_repair_chain_walk_refuses_a_cycle(self):
        tasks = dict(a=dict(id='a', repair_of='b'), b=dict(id='b', repair_of='a'))
        with self.assertRaisesRegex(EngineError, 'cycles'):
            Engine._walk(tasks, tasks['a'], 'repair_of')
        tasks['b'].pop('repair_of')
        self.assertEqual([t['id'] for t in Engine._walk(tasks, dict(id='c', repair_of='a'), 'repair_of')], ['a', 'b'])

    def stale_blocked(self):
        """B1 blocked by a receipt that also covers B2; an edit to B2 alone makes the receipt stale."""
        self.allow_review()
        for name in ('B1', 'B2'):
            self.task(name)
            (self.repo / name).write_text(name + ' v1')
            self.engine.report('w-' + name, self.engine.dispatch('main', self.lease, name, 'w-' + name), done())
        report = self.root / 'stale.json'
        self.review(report, tasks=['B1', 'B2'], findings=['B1 is wrong'], task_findings={'B1': ['B1 is wrong'], 'B2': []})
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['B1', 'B2'], findings=['B1 is wrong'])

    def test_stale_blocking_receipt_refuses_accept(self):
        self.stale_blocked()
        with self.assertRaisesRegex(EngineError, 'current review findings'):
            self.engine.accept('main', self.lease, 'B1')
        (self.repo / 'B2').write_text('B2 v2')
        with self.assertRaisesRegex(EngineError, 'Review with findings is stale; re-review'):
            self.engine.accept('main', self.lease, 'B1')
        self.assertEqual(self.engine.status()['tasks']['B1']['state'], 'reported')

    def test_stale_blocking_receipt_refuses_completion(self):
        self.allow_review()
        for name in ('B1', 'B2'):
            self.task(name)
            (self.repo / name).write_text(name + ' v1')
            self.engine.report('w-' + name, self.engine.dispatch('main', self.lease, name, 'w-' + name), done())
            self.engine.accept('main', self.lease, name)
        report = self.root / 'late.json'
        self.review(report, tasks=['B1', 'B2'], findings=['B1 is wrong'], task_findings={'B1': ['B1 is wrong'], 'B2': []})
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['B1', 'B2'], findings=['B1 is wrong'])
        (self.repo / 'B2').write_text('B2 v2')
        with self.assertRaisesRegex(EngineError, 'Review with findings is stale; re-review: B1'):
            self.engine.check_completion('main', self.lease)

    def test_start_over_a_2_5_relaunch_state_does_not_rearm_autonomy(self):
        self.arm()
        self.edit(lambda d: (d['autonomy'].update(relaunch=True), d['session'].update(active=False, outcome='pass-exited')))
        self.assertFalse(self.engine.autonomy_active())
        self.lease = self.engine.open_session('main')
        self.assertFalse(self.engine.autonomy_active())
        self.assertIsNone(self.auto())
        self.task('x', role='investigator', mode='code', files=[])
        self.assertIsNone(self.engine.hook_stop())

    def test_start_after_a_stopped_run_keeps_only_its_report(self):
        self.arm()
        self.engine.disarm_autonomy()
        self.engine.interrupt('main', self.lease)
        self.lease = self.engine.open_session('main')
        auto = self.auto()
        self.assertFalse(auto['active'])
        self.assertIn('report', auto)
        self.assertFalse(self.engine.autonomy_active())


class AutonomyHarnessTests(AutonomyFixture, HoldFixture):
    """Pull-request permission from the Push line, and the held continuation only while no final receipt covers it."""

    def test_push_line_records_pull_requests(self):
        self.arm()
        self.assertIs(self.auto()['pull_requests'], True)
        self.assertIs(self.engine.autonomy_status()['pull_requests'], True)

    def test_ledger_legacy_push_line_refused(self):
        legacy = [l for l in AUTONOMY_FIXED if not l.startswith('- Push:')] + ['- Push: no push to any branch.']
        for boundaries in (legacy, list(AUTONOMY_FIXED) + ['- Push: no push to any branch.']):
            with self.subTest(boundaries=boundaries):
                self.ledger(boundaries=boundaries)
                with self.assertRaisesRegex(EngineError, 'pre-2.11 Approval boundaries'):
                    self.engine.arm_autonomy()
                self.assertIsNone(self.auto())

    def test_state_armed_before_pull_requests_reads_false(self):
        self.arm()
        raw = json.loads(self.engine.state_path.read_text())
        raw['autonomy'].pop('pull_requests')
        self.engine.state_path.write_text(json.dumps(raw))
        self.assertIs(self.engine.autonomy_status()['pull_requests'], False)
        raw['autonomy']['pull_requests'] = 'yes'
        self.engine.state_path.write_text(json.dumps(raw))
        with self.assertRaisesRegex(EngineError, 'Invalid autonomy state'):
            self.engine.status()

    def test_held_chain_without_a_covering_final_receipt_continues(self):
        self.arm()
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        self.assertIn('held work is still owed a final review', self.engine.hook_stop())
        self.reviewed('final', ['B1', 'R1'], final=True, categories=self.ALL, findings=['g'], task_findings={'R1': ['g'], 'B1': []})
        self.assertIn('Re-plan', self.engine.hook_stop())
        self.assertIn('still nothing to do', self.engine.hook_stop())
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['active'], self.auto().get('last_stop_reason')), (False, 'needs-owner:escalated'))


class RunHygieneTests(EngineFixture):
    """Run evidence and recovery paths from the 2.7.1 audit: unreviewed finishes, the start baseline, noise, commits
    before accept, blocked workers, lost leases and dropped cards."""

    def fresh(self, name='fresh', **kw):
        engine = Engine(self.root / name, self.repo)
        return engine, engine.open_session('main', **kw)

    def test_finish_needs_a_review_when_the_run_changed_files_without_a_card(self):
        (self.repo / 'new.txt').write_text('line\n' * 300)
        with self.assertRaisesRegex(EngineError, 'final review coverage is incomplete'):
            self.engine.check_completion('main', self.lease)
        with self.assertRaisesRegex(EngineError, 'final review coverage is incomplete'):
            self.engine.close_session('main', self.lease)

    def test_finish_without_any_change_still_closes(self):
        self.engine.close_session('main', self.lease)

    def test_work_already_in_the_tree_at_start_is_not_the_runs_work(self):
        (self.repo / 'before.txt').write_text('line\n' * 300)
        (self.repo / 'a').write_text('edited before the run')
        engine, lease = self.fresh()
        self.assertEqual(engine.prepr()['changed_lines'], 0)
        engine.close_session('main', lease)  # nothing of this run's own to review
        engine, lease = self.fresh('second')
        (self.repo / 'before.txt').write_text('line\n' * 300 + 'more\n')
        self.assertGreater(engine.prepr()['changed_lines'], 0)  # editing it during the run counts

    def test_interpreter_leftovers_do_not_change_the_evidence(self):
        before = self.engine.artifact()
        (self.repo / '__pycache__').mkdir()
        (self.repo / '__pycache__' / 'x.cpython-311.pyc').write_bytes(b'\0\1')
        (self.repo / '.DS_Store').write_bytes(b'x')
        self.assertEqual(before, self.engine.artifact())
        self.assertEqual(self.engine._changed(self.engine.status()['session']['base'])[0], [])
        (self.repo / 'real.txt').write_text('x')
        self.assertNotEqual(before, self.engine.artifact())

    def test_committing_or_staging_stales_whole_repo_evidence(self):
        (self.repo / 'a').write_text('reviewed')
        before = self.engine.artifact()
        self.assertTrue(Engine._same(before, self.engine.artifact()))
        self.git('add', 'a')
        self.assertFalse(Engine._same(before, self.engine.artifact()))  # staging moves the index: record the review again
        self.git('commit', '-qm', 'reviewed')
        self.assertFalse(Engine._same(before, self.engine.artifact()))

    def test_a_commit_that_changes_only_a_sparse_hidden_path_stales_whole_repo_evidence(self):
        (self.repo / 'b').write_text('hidden')
        self.git('add', 'b')
        self.git('commit', '-qm', 'b')
        side = self.root / 'side'
        self.git('worktree', 'add', '-q', '-b', 'side', str(side))
        (side / 'b').write_text('changed elsewhere')
        subprocess.check_call(['git', '-C', str(side), 'commit', '-qam', 'change b'])
        self.git('sparse-checkout', 'set', '--no-cone', '/a')  # b leaves the worktree
        self.assertFalse((self.repo / 'b').exists())
        before = self.engine.artifact()
        self.git('merge', '-q', '--ff-only', 'side')  # HEAD moves; only the hidden path changes; the tree stays clean
        after = self.engine.artifact()
        self.assertNotEqual(before['head'], after['head'])
        self.assertFalse(Engine._same(before, after))

    def test_work_the_run_leaves_only_in_the_index_counts(self):
        engine, lease = self.fresh('indexonly')
        (self.repo / 'a').write_text('x\n' * 300)
        self.git('add', 'a')
        self.git('checkout', '--', 'a')  # worktree back to HEAD; the 300 lines live only in the index
        paths, lines = engine._run_changed(engine.status())
        self.assertEqual(paths, ['a'])
        self.assertGreaterEqual(lines, 300)
        with self.assertRaisesRegex(EngineError, 'final review coverage is incomplete'):
            engine.close_session('main', lease)

    def test_staged_content_unlike_the_worktree_at_start_is_baseline_work(self):
        (self.repo / 'a').write_text('staged version')
        self.git('add', 'a')
        self.git('checkout', '--', 'a')  # worktree back to HEAD's content; the index still holds the staged one (MM-like)
        engine, lease = self.fresh('staged')
        self.assertEqual(engine._run_changed(engine.status()), ([], 0))
        self.git('reset', '-q', 'a')  # the run throws the owner's staged work away
        self.assertEqual(engine._run_changed(engine.status())[0], ['a'])
        with self.assertRaisesRegex(EngineError, 'final review coverage is incomplete'):
            engine.close_session('main', lease)

    def test_index_modes_are_part_of_the_baseline_and_of_hidden_path_binding(self):
        self.git('update-index', '--chmod=+x', 'a')  # staged-only mode change before the run
        engine, lease = self.fresh('mode')
        self.assertEqual(engine._run_changed(engine.status()), ([], 0))
        self.git('reset', '-q', 'a')  # the run discards it: same blob, different mode
        self.assertEqual(engine._run_changed(engine.status())[0], ['a'])
        self.git('update-index', '--chmod=+x', 'a')
        hidden_view = engine._baseline_view(['a'])['a']
        self.assertIn('100755', hidden_view)

    @unittest.skipIf(portable.IS_WINDOWS, 'Git for Windows has core.filemode off, so a mode change is not visible')
    def test_an_index_only_change_after_a_report_blocks_accept(self):
        self.task('a')
        token = self.engine.dispatch('main', self.lease, 'a', 'wa')
        self.engine.report('wa', token, done('built'))
        self.git('update-index', '--chmod=+x', 'a')  # staged only: the report never covered it
        with self.assertRaisesRegex(EngineError, 'stale'):
            self.engine.accept('main', self.lease, 'a')
        self.git('commit', '-qm', 'mode')  # committed, yet the worktree still differs from HEAD: not what was reported
        with self.assertRaisesRegex(EngineError, 'stale'):
            self.engine.accept('main', self.lease, 'a')

    def test_staged_and_worktree_changes_to_one_path_are_both_counted(self):
        engine, lease = self.fresh('both')
        (self.repo / 'a').write_text('x\n' * 500)
        self.git('add', 'a')
        (self.repo / 'a').write_text('one line\n')  # the worktree now differs little from HEAD, the index a lot
        self.assertGreaterEqual(engine._run_changed(engine.status())[1], 500)

    def test_a_staged_rename_at_start_is_not_run_work_and_pre_run_edits_are_not_charged(self):
        (self.repo / 'big').write_text('line\n' * 300)
        self.git('add', 'big')
        self.git('commit', '-qm', 'big')
        self.git('mv', 'big', 'renamed')  # staged: a deleted source and a new path
        (self.repo / 'a').write_text('x\n' * 300)  # tracked file rewritten before the run
        engine, lease = self.fresh('rename')
        self.assertEqual(engine._run_changed(engine.status()), ([], 0))
        with (self.repo / 'a').open('a') as stream:
            stream.write('one more\n')
        paths, lines = engine._run_changed(engine.status())
        self.assertEqual((paths, lines), (['a'], 1))  # only the appended line, not the earlier rewrite

    def test_reverting_pre_run_work_is_charged_by_the_lines_taken_out(self):
        (self.repo / 'a').write_text('x\n' * 500)
        engine, lease = self.fresh('revert')
        self.git('checkout', '--', 'a')  # back to HEAD: the 500-line pre-run rewrite is gone
        paths, lines = engine._run_changed(engine.status())
        self.assertEqual(paths, ['a'])
        self.assertGreaterEqual(lines, 500)

    def test_discarding_work_that_was_in_the_tree_at_start_is_a_run_change(self):
        (self.repo / 'before.txt').write_text('owner work\n')
        (self.repo / 'a').write_text('owner edit')
        engine, lease = self.fresh('discard')
        self.assertEqual(engine._run_changed(engine.status())[0], [])
        (self.repo / 'before.txt').unlink()
        self.git('checkout', '--', 'a')
        self.assertEqual(engine._run_changed(engine.status())[0], ['a', 'before.txt'])
        with self.assertRaisesRegex(EngineError, 'final review coverage is incomplete'):
            engine.close_session('main', lease)

    def test_a_card_can_be_accepted_after_the_work_is_committed_and_re_reviewed(self):
        self.allow_review()
        (self.repo / 'a').write_text('built')
        self.task('a', role='investigator', mode='code', review_required=True)
        self.engine.report('wa', self.engine.dispatch('main', self.lease, 'a', 'wa'), 'Looked.')
        report = self.root / 'r1.json'
        self.review(report, tasks=['a'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'])
        self.git('commit', '-qam', 'work')
        with self.assertRaisesRegex(EngineError, 'independent review'):
            self.engine.accept('main', self.lease, 'a')  # the review is of the old commit
        self.review(report, tasks=['a'])
        self.engine.record_review('main', self.lease, 'reviewer', report, ['correctness'], ['a'])
        self.engine.accept('main', self.lease, 'a')  # re-reviewed on the committed tree: no dead end
        self.assertEqual(self.engine.status()['tasks']['a']['state'], 'accepted')

    def test_a_blocked_worker_parks_its_card_with_the_reason(self):
        self.task('a')
        token = self.engine.dispatch('main', self.lease, 'a', 'wa')
        self.engine.report('wa', token, 'Tried.\nBLOCKED: the API key is not in the environment')
        task = self.engine.status()['tasks']['a']
        self.assertEqual(task['state'], 'parked')
        self.assertIn('API key', task['parked_reason'])
        self.engine.unpark('main', self.lease, 'a')

    def test_a_status_blocked_first_line_parks_a_card_that_needs_no_self_review(self):
        self.task('a')
        token = self.engine.dispatch('main', self.lease, 'a', 'wa')
        self.engine.report('wa', token, 'STATUS: BLOCKED\nNo credentials for the API.')
        task = self.engine.status()['tasks']['a']
        self.assertEqual(task['state'], 'parked')
        self.assertIn('STATUS: BLOCKED', task['parked_reason'])
        self.task('b', role='investigator', mode='code')
        token = self.engine.dispatch('main', self.lease, 'b', 'wb')
        self.engine.report('wb', token, 'STATUS: BLOCKED')
        self.assertEqual(self.engine.status()['tasks']['b']['state'], 'parked')

    def test_a_status_blocked_line_below_the_first_does_not_park(self):
        self.task('a', role='investigator', mode='code')
        token = self.engine.dispatch('main', self.lease, 'a', 'wa')
        self.engine.report('wa', token, 'Looked.\nSTATUS: BLOCKED is the marker for a stuck worker.')
        self.assertEqual(self.engine.status()['tasks']['a']['state'], 'reported')

    def test_max_worktrees_caps_running_non_inline_builder_cards(self):
        engine = Engine(self.root / 'wt', self.repo, {'schema_version': 1, 'max_worktrees': 2})
        lease = engine.open_session('main')
        add = lambda name, **kw: engine.add_task('main', lease, dict(
            id=name, role='builder', mode='implementation', inputs=['spec'], acceptance=['x'], files=[name],
            resources=[], dependencies=[], **kw))
        for name in ('b1', 'b2', 'b3'):
            add(name)
        engine.add_task('main', lease, dict(id='inv', role='investigator', mode='code', inputs=['s'], acceptance=['x'],
                                            files=[], resources=[], dependencies=[]))
        engine.dispatch('main', lease, 'b1', 'w1', serial='fixture: one card at a time')
        engine.dispatch('main', lease, 'b2', 'w2', serial='fixture: one card at a time')
        with self.assertRaisesRegex(EngineError, 'Worktree cap: 2'):
            engine.dispatch('main', lease, 'b3', 'w3')
        engine.dispatch('main', lease, 'inv', 'wi', serial='fixture: one card at a time')  # read-only roles do not count
        engine.start_inline('main', lease, 'b3')  # inline cards do not count
        self.assertEqual(engine.status()['tasks']['b3']['state'], 'running')

    def test_max_worktrees_defaults_to_three_and_must_be_a_positive_integer(self):
        for name in ('b1', 'b2', 'b3', 'b4'):
            self.task(name)
        for name in ('b1', 'b2', 'b3'):
            self.engine.dispatch('main', self.lease, name, 'w' + name, serial='fixture: one card at a time')
        with self.assertRaisesRegex(EngineError, 'Worktree cap: 3'):
            self.engine.dispatch('main', self.lease, 'b4', 'wb4')
        for value in (0, -1, True, 1.5, '3'):
            with self.assertRaisesRegex(EngineError, 'max_worktrees must be a positive integer'):
                Engine(self.root / 'bad', self.repo, {'max_worktrees': value})
        default = json.loads((ROOT / 'plugins/orchestra/config/policy.default.json').read_text())
        self.assertEqual(default['max_worktrees'], 3)

    def test_start_refuses_an_unknown_policy_key_by_name(self):
        engine = Engine(self.root / 'typo', self.repo, {'schema_version': 1, 'file_budget_byte': 5000})
        with self.assertRaisesRegex(EngineError, 'Unknown policy key: file_budget_byte'):
            engine.open_session('main', size='medium')
        with self.assertRaisesRegex(EngineError, 'Unknown policy key: file_budget_byte'):
            engine._check_start('medium', None, False)

    def test_start_accepts_every_key_of_the_older_schema(self):
        old = {'schema_version': 1, 'required_review_categories': ['correctness'], 'worker_stale_seconds': 60,
               'file_budget_bytes': 5000, 'file_budget_waivers': {}, 'check_commands': {}, 'release_timeout_seconds': 5,
               **json.loads((ROOT / 'plugins/orchestra/config/policy.default.json').read_text())}
        Engine(self.root / 'old', self.repo, old).open_session('main', size='medium')

    def test_a_lost_lease_is_taken_back_by_the_owning_session_only(self):
        engine, lease = self.fresh(harness_session='H1')
        engine.add_task('main', lease, dict(id='a', role='builder', mode='implementation', inputs=['s'], acceptance=['check behavior'],
                                            files=['a'], resources=[], dependencies=[]))
        token = engine.dispatch('main', lease, 'a', 'wa')
        for who, session in (('main', 'H2'), ('other', 'H1'), ('main', None)):
            with self.assertRaises(EngineError):
                engine.recover_lease(who, session)
        new = engine.recover_lease('main', 'H1')
        self.assertNotEqual(new, lease)
        with self.assertRaisesRegex(EngineError, 'lost its lease'):
            engine.ready('main', lease)
        engine.report('wa', token, done('built'))  # the running worker is not orphaned
        self.assertEqual(engine.status()['tasks']['a']['state'], 'reported')

    def test_a_card_that_should_never_run_can_be_dropped(self):
        self.task('a')
        self.task('b', dependencies=['a'])
        with self.assertRaisesRegex(EngineError, 'depend on it'):
            self.engine.cancel('main', self.lease, 'a', 'wrong plan')
        self.engine.cancel('main', self.lease, 'b', 'wrong plan')
        self.engine.dispatch('main', self.lease, 'a', 'wa')
        with self.assertRaisesRegex(EngineError, 'queued or parked'):
            self.engine.cancel('main', self.lease, 'a', 'too late')
        with self.assertRaisesRegex(EngineError, 'reason'):
            self.engine.cancel('main', self.lease, 'a', ' ')
        state = self.engine.status()
        self.assertNotIn('b', state['tasks'])
        self.assertEqual([c['id'] for c in state['cancelled']], ['b'])

    def test_a_huge_file_is_bound_by_size_mtime_and_samples_and_never_read_whole(self):
        import orchestra_core.engine as engine_module
        big = self.repo / 'big.bin'
        big.write_bytes(b'a' * 4096)
        original = pathlib.Path.read_bytes

        def guarded(path):
            if path.name == 'big.bin':
                raise AssertionError('read whole')
            return original(path)

        with mock.patch.object(engine_module, 'LARGE_FILE_BYTES', 1024), mock.patch.object(engine_module, 'SAMPLE_BYTES', 16), \
                mock.patch.object(pathlib.Path, 'read_bytes', guarded):
            before = self.engine.artifact()['fingerprint']
            self.assertEqual(self.engine._count_lines(big), 4096 // 40)
            info = big.stat()
            data = bytearray(b'a' * 4096)
            data[2000] = ord('b')  # in the middle, outside both samples
            big.write_bytes(data)
            os.utime(big, ns=(info.st_atime_ns, info.st_mtime_ns))
            self.assertEqual(self.engine.artifact()['fingerprint'], before)  # the documented limit
            data[0] = ord('c')  # a change inside a sample is seen
            big.write_bytes(data)
            os.utime(big, ns=(info.st_atime_ns, info.st_mtime_ns))
            self.assertNotEqual(self.engine.artifact()['fingerprint'], before)

    def test_push_urls_are_recorded_as_digests(self):
        from orchestra_core.paths import push_url_digest
        self.assertEqual(push_url_digest('https://user:secret@example.invalid/r.git')[:7], 'sha256:')
        self.assertNotIn('secret', push_url_digest('https://user:secret@example.invalid/r.git'))



GOLDEN_POLICY_2_10 = dict(max_workers=20, required_checks=[], gate_timeout_seconds=300,
                          secret_scan=dict(required=False, argv=[]),
                          release=dict(enabled=False, remote=None, target=None, argv=[]),
                          sensitive_paths=['**/auth/**', '**/security/**', '**/*secret*', '**/hooks/**', '**/guard*',
                                           '**/migrations/**', '.github/**'],
                          standards_min_lines=200)
GOLDEN_CONTRACT_2_10 = '7b1f34b2bf297e6e95cdd59306a697f5a2b7410f5a84bc71feb7ffe0213439ed'
GOLDEN_HASH_2_10 = '4b1d85568cf17dffc8adb272d1df95decfaf2a03c18c9176ff17190e4d5fb74d'  # computed at HEAD 8ae926f, before the new keys


def run_cli(fixture, *args):
    """The real CLI against the fixture's repository and state; returns (exit code, stdout, stderr)."""
    done = subprocess.run([sys.executable, str(SCRIPTS / 'orchestra.py'), '--repo', str(fixture.repo),
                           '--state', str(fixture.engine.state_dir), *args], capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout, done.stderr


class GuardPolicyTests(EngineFixture):
    """The policy keys `guard_mode` and `release_workflows`."""

    def engine_with(self, policy, name='other'):
        return Engine(self.root / name, self.repo, policy)

    def test_guard_mode_default_normal_protect_accepted_strict_refused(self):
        self.assertNotIn('guard_mode', self.engine.policy)  # absent means normal; the hook reads the file itself
        for mode in ('normal', 'protect'):
            self.assertEqual(self.engine_with(dict(guard_mode=mode)).policy['guard_mode'], mode)
        for bad in ('strict', 'Protect', '', None, True, ['protect']):
            with self.subTest(mode=bad), self.assertRaisesRegex(EngineError, 'Invalid guard mode'):
                self.engine_with(dict(guard_mode=bad))

    def test_guard_mode_change_keeps_policy_hash(self):
        normal = self.engine_with(dict(guard_mode='normal'), 'a')
        protect = self.engine_with(dict(guard_mode='protect'), 'b')
        self.assertEqual(normal.policy_hash, protect.policy_hash)
        self.assertEqual(self.engine_with(None, 'c').policy_hash, protect.policy_hash)
        lease = normal.open_session('main')  # a run started under one mode goes on under the other
        Engine(self.root / 'a', self.repo, dict(guard_mode='protect')).validate_lease('main', lease)
        self.assertNotEqual(self.engine_with(dict(guard_mode='protect', max_workers=3), 'd').policy_hash, normal.policy_hash)

    def test_release_workflows_validated(self):
        ok = ['release*', 'publish*']
        self.assertEqual(self.engine_with(dict(release_workflows=ok)).policy['release_workflows'], ok)
        self.assertEqual(self.engine_with(dict(release_workflows=[])).policy['release_workflows'], [])
        for bad in ('release*', [''], [1], ['ok', None], {'a': 'b'}, None):
            with self.subTest(value=bad), self.assertRaisesRegex(EngineError, 'release_workflows must be a list of globs'):
                self.engine_with(dict(release_workflows=bad))

    def test_start_accepts_both_new_keys_and_still_refuses_unknown(self):
        engine = self.engine_with(dict(guard_mode='protect', release_workflows=['deploy*']))
        self.assertTrue(engine.open_session('main'))
        for extra in (dict(guard_mode='protect', bogus=1), dict(release_workflow=['x'])):
            with self.subTest(policy=extra), self.assertRaisesRegex(EngineError, 'Unknown policy key'):
                self.engine_with(extra, 'third').open_session('main')

    def test_new_policy_keys_not_in_default_and_old_policy_hash_unchanged(self):
        import orchestra_core.engine as engine_module
        for key in ('guard_mode', 'release_workflows'):
            self.assertNotIn(key, engine_module.DEFAULT)
            self.assertIn(key, engine_module.POLICY_KEYS)
            self.assertNotIn(key, json.loads((ROOT / 'plugins/orchestra/config/policy.default.json').read_text()))
        self.assertEqual(self.engine.policy, GOLDEN_POLICY_2_10)
        modes = engine_module._contracts()[0]
        with mock.patch.object(engine_module, '_contracts', return_value=(modes, GOLDEN_CONTRACT_2_10)):
            plain = Engine(self.root / 'golden', self.repo)
            both = Engine(self.root / 'golden2', self.repo, dict(guard_mode='protect', release_workflows=['x*']))
        self.assertEqual(plain.policy_hash, GOLDEN_HASH_2_10)  # a policy with neither key hashes as it did before
        self.assertNotEqual(both.policy_hash, GOLDEN_HASH_2_10)  # release_workflows binds; guard_mode does not


class RunIdTests(EngineFixture):
    """`state['run_id']`: minted for a new run, stable after, archived with it."""

    def run_id(self, engine=None):
        return (engine or self.engine).status().get('run_id')

    def test_run_id_minted_on_new_run_stable_across_resume_and_recover(self):
        first = self.run_id()
        self.assertRegex(first, r'^[0-9a-f]{16}$')
        self.engine.interrupt('main', self.lease)
        self.engine.open_session('main', 'S1')  # resume
        self.assertEqual(self.run_id(), first)
        self.engine.recover_lease('main', 'S1')
        self.assertEqual(self.run_id(), first)
        other = Engine(self.root / 'other', self.repo)
        other.open_session('main')
        self.assertNotEqual(self.run_id(other), first)

    def test_run_id_archived_with_new_run(self):
        first = self.run_id()
        self.engine.interrupt('main', self.lease)
        self.assertEqual(run_cli(self, 'start', '--new-run', '--size', 'tiny')[0], 0)
        archived = [json.loads(p.read_text()) for p in (self.engine.state_dir / 'history').glob('run-*.json')]
        self.assertEqual([a['state']['run_id'] for a in archived], [first])
        second = self.run_id()
        self.assertRegex(second, r'^[0-9a-f]{16}$')
        self.assertNotEqual(second, first)

    def test_a_malformed_run_id_refuses(self):
        raw = json.loads(self.engine.state_path.read_text())
        for bad in ('xyz', 5, '', 'ABCDEF0123456789'):
            raw['run_id'] = bad
            self.engine.state_path.write_text(json.dumps(raw))
            with self.subTest(run_id=bad), self.assertRaisesRegex(EngineError, 'Invalid run state run_id'):
                self.engine.status()


GH_SCRIPT = '''import json, os, sys
args = sys.argv[1:]
with open(os.environ['FAKE_GH_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
data = json.load(open(os.environ['FAKE_GH_DATA']))
if args[:2] != ['pr', 'view'] or len(args) < 3 or args[2] not in data:
    sys.stderr.write('no pull request found\\n')
    sys.exit(1)
print(json.dumps(data[args[2]]))
'''


class FakeGh:
    """A `gh` on PATH from a temp directory: `gh pr view URL` answers from a JSON file keyed by URL; every call is logged."""

    def __init__(self, root):
        self.dir = Path(root) / 'fake-gh'
        self.dir.mkdir()
        self.data = self.dir / 'data.json'
        self.log = self.dir / 'calls.log'
        script = self.dir / 'gh.py'
        script.write_text(GH_SCRIPT)
        if os.name == 'nt':
            (self.dir / 'gh.cmd').write_text('@"%s" "%s" %%*\r\n' % (sys.executable, script))
        else:
            wrapper = self.dir / 'gh'
            wrapper.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, script))
            wrapper.chmod(0o755)
        self.log.write_text('')
        self.set({})

    def set(self, views):
        self.data.write_text(json.dumps(views))

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def env(self):
        return mock.patch.dict(os.environ, PATH=str(self.dir) + os.pathsep + os.environ.get('PATH', ''),
                               FAKE_GH_DATA=str(self.data), FAKE_GH_LOG=str(self.log))


class PullRequestFixture(AutonomyFixture, HoldFixture):
    URL = 'https://github.example/o/r/pull/7'

    def setUp(self):
        super().setUp()
        self.git('switch', '-qc', 'feat/x')
        self.commit('x.txt', 'one')
        self.gh = FakeGh(self.root)
        patcher = self.gh.env()
        patcher.start()
        self.addCleanup(patcher.stop)

    def commit(self, name, text):
        (self.repo / name).write_text(text)
        self.git('add', name)
        self.git('commit', '-qm', 'change ' + name)
        return self.git('rev-parse', 'HEAD')

    def view(self, url=None, number=7, **kw):
        view = dict(number=number, state='OPEN', baseRefName=self.default_branch, headRefName='feat/x',
                    isCrossRepository=False, headRefOid=self.git('rev-parse', 'refs/heads/feat/x'))
        view.update(kw)
        self.gh.set({url or self.URL: view})
        return view

    def add_view(self, url, **view):
        views = json.loads(self.gh.data.read_text())
        views[url] = view
        self.gh.set(views)

    def prs(self):
        return self.engine.status().get('pull_requests', [])

    def clean_review_here(self, name):
        """A clean final review of the work as committed now."""
        if 'c' not in self.engine.status()['tasks']:
            self.built('c', files=['c.txt'])
        return self.reviewed(name, ['c'], final=True)


class PullRequestTests(PullRequestFixture):
    def test_record_pr_stores_object_and_reads_legacy_string(self):
        legacy = 'https://github.example/o/r/pull/3'
        raw = json.loads(self.engine.state_path.read_text())
        raw['pull_requests'] = [legacy]  # a 2.10 state holds bare strings
        self.engine.state_path.write_text(json.dumps(raw))
        self.assertEqual(self.engine.status()['pull_requests'], [legacy])
        view = self.view()
        entries = self.engine.record_pr('main', self.lease, self.URL)
        self.assertEqual(entries[0], dict(url=legacy, autonomous=False, verified_at=None))
        entry = entries[1]
        self.assertEqual(set(entry), {'url', 'number', 'repo', 'head_ref', 'head_sha', 'base_ref', 'autonomous', 'tasks',
                                      'reviewed', 'verified_at', 'recorded_at'})
        self.assertEqual((entry['url'], entry['number'], entry['repo'], entry['head_ref'], entry['head_sha'], entry['base_ref']),
                         (self.URL, 7, 'o/r', 'feat/x', view['headRefOid'], self.default_branch))
        self.assertEqual((entry['autonomous'], entry['tasks'], entry['reviewed']), (False, [], False))
        self.assertRegex(entry['verified_at'], r'^20\d\d-')
        self.assertEqual(entries, self.prs())
        self.engine.interrupt('main', self.lease)
        brief = self.engine.brief()
        self.assertIn('review and merge pull request ' + legacy, brief)
        self.assertIn('review and merge pull request ' + self.URL, brief)
        self.assertEqual(self.gh.calls(), [['pr', 'view', self.URL, '--json',
                                           'number,state,baseRefName,headRefName,headRefOid,isCrossRepository']])

    def test_pr_marks_autonomous_and_tasks_when_armed(self):
        self.arm()
        self.view()
        self.task('t1')
        entry = self.engine.record_pr('main', self.lease, self.URL, tasks=['t1'])[0]
        self.assertEqual((entry['autonomous'], entry['tasks']), (True, ['t1']))
        with self.assertRaisesRegex(EngineError, 'Unknown task: nope'):
            self.engine.record_pr('main', self.lease, self.URL, tasks=['nope'])
        with self.assertRaisesRegex(EngineError, 'coordinator lease'):
            self.engine.record_pr('main', 'wrong', self.URL)
        self.assertEqual(len(self.prs()), 1)

    def test_pr_refuses_non_open_cross_repo_wrong_base_unpushed_head(self):
        self.git('branch', 'dev')
        self.arm()  # `dev` exists at arm, so it is not a run branch
        stale = self.git('rev-parse', 'HEAD~1')
        cases = [(dict(state='CLOSED'), 'not open'), (dict(state='MERGED'), 'not open'),
                 (dict(isCrossRepository=True), 'another repository'),
                 (dict(baseRefName='dev'), 'neither the default branch nor a run branch'),
                 (dict(baseRefName='nowhere'), 'neither the default branch nor a run branch'),
                 (dict(headRefOid=stale), 'not the local tip'),
                 (dict(headRefName='gone'), 'no local branch')]
        for change, text in cases:
            with self.subTest(change=change):
                self.view(**change)
                with self.assertRaisesRegex(EngineError, text):
                    self.engine.record_pr('main', self.lease, self.URL)
                self.assertEqual(self.prs(), [])
        self.view()
        self.assertEqual(len(self.engine.record_pr('main', self.lease, self.URL)), 1)

    def test_pr_base_may_be_a_recorded_head_or_a_branch_created_after_arm(self):
        self.arm()
        self.view()
        self.engine.record_pr('main', self.lease, self.URL)
        self.git('switch', '-qc', 'feat/y')
        self.commit('y.txt', 'y')
        tip = self.git('rev-parse', 'HEAD')
        url2, url3 = 'https://github.example/o/r/pull/8', 'https://github.example/o/r/pull/9'
        self.add_view(url2, number=8, state='OPEN', baseRefName='feat/x', headRefName='feat/y', isCrossRepository=False,
                      headRefOid=tip)
        self.assertEqual([e['base_ref'] for e in self.engine.record_pr('main', self.lease, url2)],
                         [self.default_branch, 'feat/x'])
        self.git('branch', 'run/z')  # created after arm: a run branch, though no pull request names it yet
        self.add_view(url3, number=9, state='OPEN', baseRefName='run/z', headRefName='feat/y', isCrossRepository=False,
                      headRefOid=tip)
        self.assertEqual(len(self.engine.record_pr('main', self.lease, url3)), 3)

    def test_pr_rerun_refreshes_head_and_reviewed(self):
        self.view()
        first = self.engine.record_pr('main', self.lease, self.URL)[0]
        self.assertFalse(first['reviewed'])
        self.clean_review_here('r1')
        self.now[0] += 60
        second = self.engine.record_pr('main', self.lease, self.URL)
        self.assertEqual(len(second), 1)
        self.assertTrue(second[0]['reviewed'])  # a clean review of exactly this head
        self.assertGreater(second[0]['verified_at'], first['verified_at'])
        self.assertEqual(second[0]['recorded_at'], first['recorded_at'])
        tip = self.commit('x.txt', 'two')  # the head moves; the earlier review no longer covers it
        self.view()
        self.now[0] += 60
        third = self.engine.record_pr('main', self.lease, self.URL)[0]
        self.assertEqual((third['head_sha'], third['reviewed']), (tip, False))
        self.clean_review_here('r2')
        self.assertTrue(self.engine.record_pr('main', self.lease, self.URL)[0]['reviewed'])

    def test_pr_review_with_findings_does_not_count(self):
        self.view()
        self.built('c', files=['c.txt'])
        self.reviewed('blocked', ['c'], findings=['f'], task_findings={'c': ['f']}, final=True)
        self.assertFalse(self.engine.record_pr('main', self.lease, self.URL)[0]['reviewed'])

    def test_pr_gh_missing_records_unverified(self):
        with mock.patch('orchestra_core.engine.shutil.which', return_value=None):
            entry = self.engine.record_pr('main', self.lease, self.URL)[0]
        self.assertEqual((entry['verified_at'], entry['head_sha'], entry['base_ref'], entry['reviewed']),
                         (None, None, None, False))
        self.assertEqual((entry['url'], entry['number'], entry['repo']), (self.URL, 7, 'o/r'))
        other = 'https://github.example/o/r/pull/9'  # gh runs but cannot find the pull request: also unverified
        self.assertIsNone(self.engine.record_pr('main', self.lease, other)[1]['verified_at'])
        self.view()  # a later run of the same command verifies the same entry in place
        entries = self.engine.record_pr('main', self.lease, self.URL)
        self.assertEqual(len(entries), 2)
        self.assertIsNotNone(entries[0]['verified_at'])


class BaseTests(PullRequestFixture):
    def stack(self):
        self.arm()
        self.task('a')
        self.task('b', dependencies=['a'])
        self.task('c', dependencies=['b'])

    def record(self, number, task, head):
        url = 'https://github.example/o/r/pull/%d' % number
        self.git('switch', '-q' if self.git('branch', '--list', head) else '-qc', head)
        self.add_view(url, number=number, state='OPEN', baseRefName=self.default_branch, headRefName=head,
                      isCrossRepository=False, headRefOid=self.git('rev-parse', 'HEAD'))
        self.engine.record_pr('main', self.lease, url, tasks=[task])
        return url

    def test_base_default_when_no_parent(self):
        self.stack()
        self.assertEqual(self.engine.base('a'), self.default_branch)
        self.assertEqual(self.engine.base('c'), self.default_branch)  # no dependency has a pull request
        with self.assertRaisesRegex(EngineError, 'Unknown task'):
            self.engine.base('nope')

    def test_base_one_open_parent_head_ref(self):
        self.stack()
        url = self.record(7, 'a', 'feat/a')
        self.assertEqual(self.engine.base('b'), 'feat/a')
        self.assertEqual(self.engine.base('c'), 'feat/a')  # walks past b, which has none
        self.add_view(url, number=7, state='MERGED', baseRefName=self.default_branch, headRefName='feat/a',
                      isCrossRepository=False, headRefOid=self.git('rev-parse', 'HEAD'))
        self.assertEqual(self.engine.base('b'), self.default_branch)  # a merged parent no longer stacks
        self.gh.set({})
        with self.assertRaisesRegex(EngineError, 'Could not read pull request 7'):
            self.engine.base('b')

    def test_base_two_open_parents_exit_2_deferred(self):
        self.arm()
        self.task('a')
        self.task('b')
        self.task('c', dependencies=['a', 'b'])
        self.record(7, 'a', 'feat/a')
        self.record(8, 'b', 'feat/b')
        with self.assertRaisesRegex(EngineError, r'^deferred: wait for pull request\(s\) 7, 8 to merge$'):
            self.engine.base('c')
        code, out, err = run_cli(self, 'base', 'c')
        self.assertEqual((code, out), (2, ''))
        self.assertIn('deferred: wait for pull request(s) 7, 8 to merge', err)
        self.assertEqual(run_cli(self, 'base', 'a')[:2], (0, self.default_branch + '\n'))  # one plain line

    def test_pr_cli_takes_task_and_prints_the_entries(self):
        self.arm()
        self.view()
        self.task('t1')
        code, out, err = run_cli(self, '--lease', self.lease, 'pr', self.URL, '--task', 't1')
        self.assertEqual(code, 0, err)
        entries = json.loads(out)['pull_requests']
        self.assertEqual([(e['url'], e['tasks'], e['autonomous']) for e in entries], [(self.URL, ['t1'], True)])


class LedgerLineTests(AutonomyFixture):
    PRE_2_11 = ['- Merge: no pull request merge, and no local merge on the default branch.',
                '- Push: push only a feature branch for a pull request; never the default branch.',
                '- Deletion: no deletion of files, branches or tags.']
    REFILL = (r'Ledger uses the pre-2\.11 Approval boundaries: copy the Merge, Push and Deletion lines from the template, '
              r'then arm again')

    def test_ledger_new_lines_arm(self):
        self.assertEqual(AUTONOMY_FIXED[1:4], (
            '- Merge: no merge into the default or a protected branch; a pull request whose base is a run branch may merge.',
            '- Push: push any branch except the default, protected branches and tags; never force.',
            '- Deletion: delete only what the run created: its run branches and worktrees, and files inside a linked '
            'worktree; never tags, the default branch or other branches.'))
        self.assertTrue(self.arm()['active'])
        self.assertIs(self.auto()['pull_requests'], True)

    def test_ledger_old_merge_push_deletion_lines_refused_with_refill_message(self):
        for index, old in enumerate(self.PRE_2_11):
            with self.subTest(line=old):
                boundaries = list(AUTONOMY_FIXED)
                boundaries[index + 1] = old
                self.ledger(boundaries=boundaries)
                with self.assertRaisesRegex(EngineError, self.REFILL):
                    self.engine.arm_autonomy()
                self.assertIsNone(self.auto())
        self.ledger(boundaries=[AUTONOMY_FIXED[0], *self.PRE_2_11, *AUTONOMY_FIXED[4:]])
        with self.assertRaisesRegex(EngineError, self.REFILL):
            self.engine.arm_autonomy()
        self.ledger(boundaries=[l for l in AUTONOMY_FIXED if not l.startswith('- Merge:')])  # a missing line keeps its message
        with self.assertRaisesRegex(EngineError, 'must keep the fixed line: - Merge:'):
            self.engine.arm_autonomy()

    def test_ledger_legacy_push_line_refused(self):
        boundaries = [('- Push: no push to any branch.' if line.startswith('- Push:') else line) for line in AUTONOMY_FIXED]
        self.ledger(boundaries=boundaries)
        with self.assertRaisesRegex(EngineError, self.REFILL):
            self.engine.arm_autonomy()
        import orchestra_core.engine as engine_module
        self.assertFalse(hasattr(engine_module, 'AUTONOMY_LEGACY_PUSH'))


class ArmRecordsTests(AutonomyFixture):
    def remote(self, name='origin', default='main', extra=()):
        bare = self.root / (name + '.git')
        self.git('init', '-q', '--bare', '-b', default, str(bare))
        self.git('remote', 'add', name, str(bare))
        self.git('push', '-q', name, 'HEAD:refs/heads/' + default)
        for branch in extra:
            self.git('push', '-q', name, 'HEAD:refs/heads/' + branch)
        self.git('fetch', '-q', name)

    def test_arm_refuses_on_default_branch_with_switch_hint(self):
        self.git('switch', '-q', self.default_branch)
        self.ledger()
        with self.assertRaisesRegex(EngineError, r'default branch .*git switch -c NAME'):
            self.engine.arm_autonomy()
        self.assertIsNone(self.auto())
        self.git('switch', '-qc', 'develop')  # a remote that reports `develop` as its default makes it the default branch
        self.remote(default='develop')
        with self.assertRaisesRegex(EngineError, r'default branch develop.*git switch -c NAME'):
            self.engine.arm_autonomy()
        self.assertIsNone(self.auto())
        self.git('switch', '-q', 'work')
        self.assertTrue(self.engine.arm_autonomy()['active'])
        self.engine.disarm_autonomy()
        self.git('checkout', '-q', '--detach')  # no branch name, nothing to refuse
        self.assertTrue(self.engine.arm_autonomy()['active'])

    def test_arm_stores_local_branches_at_arm(self):
        self.git('branch', 'feat/a')
        self.arm()
        self.assertEqual(self.auto()['local_branches_at_arm'], sorted([self.default_branch, 'feat/a', 'work']))

    def test_arm_stores_remote_branches_at_arm(self):
        self.remote(extra=('extra', 'feat/deep'))
        self.arm()
        self.assertEqual(self.auto()['remote_branches_at_arm'], ['extra', 'feat/deep', 'main'])  # no HEAD, no remote prefix

    def test_arm_stores_an_empty_remote_list_without_a_remote(self):
        self.arm()
        self.assertEqual(self.auto()['remote_branches_at_arm'], [])

    def test_arm_mints_run_id_for_old_state(self):
        raw = json.loads(self.engine.state_path.read_text())
        raw.pop('run_id')  # a state written before 2.11
        self.engine.state_path.write_text(json.dumps(raw))
        self.assertIsNone(self.engine.status().get('run_id'))
        self.arm()
        minted = self.engine.status()['run_id']
        self.assertRegex(minted, r'^[0-9a-f]{16}$')
        self.engine.disarm_autonomy()
        self.arm()
        self.assertEqual(self.engine.status()['run_id'], minted)  # arm keeps an id that exists

    def test_arm_clears_previous_receipt(self):
        self.arm()
        run = self.engine.status()['run_id']
        receipt = dict(run=run, prs=[], excluded=[])
        raw = json.loads(self.engine.state_path.read_text())
        raw['approval'] = receipt
        self.engine.state_path.write_text(json.dumps(raw))
        self.engine.disarm_autonomy()
        self.assertEqual(self.engine.status()['approval'], receipt)
        self.arm()
        status = self.engine.status()
        self.assertNotIn('approval', status)
        self.assertEqual(status['approval_history'], [receipt])
        raw = json.loads(self.engine.state_path.read_text())
        raw['approval'] = dict(run=run, prs=[1], excluded=[])
        self.engine.state_path.write_text(json.dumps(raw))
        self.engine.disarm_autonomy()
        self.arm()
        self.assertEqual(len(self.engine.status()['approval_history']), 2)


class NewRunRefusalTests(AutonomyFixture):
    def stopped(self):
        """Armed, stopped by a disarm (its report is kept) and the session ended."""
        self.arm()
        self.engine.disarm_autonomy()
        self.engine.interrupt('main', self.lease)

    def start(self):
        return run_cli(self, 'start', '--new-run', '--size', 'tiny')

    def test_new_run_refused_while_report_kept_without_receipt(self):
        self.stopped()
        run = self.engine.status()['run_id']
        code, _, err = self.start()
        self.assertEqual(code, 2)
        self.assertIn('New run refused: autonomy kept a report for run %s and the owner has not approved it; type approved '
                      "in the owner's session, or run orchestra.py autonomy disarm in a terminal" % run, err)
        self.assertEqual(self.engine.status()['run_id'], run)  # nothing archived
        self.assertFalse((self.state / 'history').exists())
        raw = json.loads(self.engine.state_path.read_text())
        raw['approval'] = dict(run='0' * 16, prs=[], excluded=[])  # a receipt for another run does not count
        self.engine.state_path.write_text(json.dumps(raw))
        self.assertEqual(self.start()[0], 2)

    def test_new_run_allowed_after_receipt_or_disarm(self):
        self.stopped()
        raw = json.loads(self.engine.state_path.read_text())
        raw['approval'] = dict(run=raw['run_id'], prs=[], excluded=[])
        self.engine.state_path.write_text(json.dumps(raw))
        self.assertEqual(self.start()[0], 0)
        self.assertEqual(len(list((self.state / 'history').glob('run-*.json'))), 1)
        self.fresh(None)
        self.stopped()
        self.assertEqual(self.start()[0], 2)
        self.assertFalse(self.engine.disarm_autonomy()['was_active'])  # the second disarm pops the kept report
        self.assertNotIn('report', self.auto() or {})
        self.assertEqual(self.start()[0], 0)

    def test_new_run_unaffected_for_unreadable_state_and_for_no_report(self):
        self.engine.interrupt('main', self.lease)
        self.assertEqual(self.start()[0], 0)  # no autonomy at all
        self.fresh(None)
        self.engine.state_path.write_text('{"version": 1, "autonomy": {"report"')  # truncated
        self.assertEqual(self.start()[0], 0)
        self.assertEqual(len(list((self.state / 'history').glob('unreadable-*.json'))), 1)


class CompleteStopTests(PullRequestFixture):
    """`complete` needs the work published: a verified autonomous pull request for the current head, or nothing beyond base."""

    def passing_gate(self):
        self.assertTrue(self.engine.run_gate('main', self.lease, 'fixture', PASS_ARGV)['passed'])

    def finish_line(self):
        self.built('B1')
        self.reviewed('clean', ['B1'])
        self.engine.accept('main', self.lease, 'B1')
        self.reviewed('final', ['B1'], final=True, categories=self.ALL)
        self.passing_gate()

    def last_stop(self):
        return self.auto().get('last_stop_reason')

    def edit_entry(self, **fields):
        raw = json.loads(self.engine.state_path.read_text())
        raw['pull_requests'][0].update(fields)
        self.engine.state_path.write_text(json.dumps(raw))

    def test_complete_not_returned_with_unpushed_commits_and_no_verified_pr(self):
        self.arm()
        self.finish_line()
        message = self.engine.hook_stop()
        self.assertIn('Autonomy pass 1:', message)
        self.assertIn('no verified pull request', message)
        self.assertTrue(self.auto()['active'])
        self.assertNotEqual(self.last_stop(), 'complete')

    def test_complete_with_verified_pr_for_head(self):
        self.arm()
        self.finish_line()
        self.view()
        self.engine.record_pr('main', self.lease, self.URL)
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.last_stop(), 'complete')

    def not_complete_with(self, **fields):
        self.arm()
        self.finish_line()
        self.view()
        self.engine.record_pr('main', self.lease, self.URL)
        self.edit_entry(**fields)
        self.assertIn('no verified pull request', self.engine.hook_stop())
        self.assertTrue(self.auto()['active'])

    def test_complete_ignores_an_unverified_pr(self):
        self.not_complete_with(verified_at=None)

    def test_complete_ignores_a_pr_the_run_did_not_open(self):
        self.not_complete_with(autonomous=False)

    def test_complete_ignores_a_pr_for_another_head(self):
        self.not_complete_with(head_sha='0' * 40)

    def test_complete_when_no_commits_beyond_base(self):
        self.git('switch', '-q', 'work')  # the branch AutonomyFixture cut at the session base: no commits beyond it
        self.arm()
        self.finish_line()
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.last_stop(), 'complete')

    def test_push_and_pr_continuation_keeps_going_then_escalates(self):
        self.arm()
        self.finish_line()
        self.assertIn('Autonomy pass 1:', self.engine.hook_stop())
        self.assertIn('Autonomy pass 2:', self.engine.hook_stop())  # nothing changed, yet the continuation repeats once
        self.assertIn('read the exact git or gh error', self.engine.hook_stop())  # then a different one, with the failure to read
        self.assertIn('still not done', self.engine.hook_stop())
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual((self.auto()['active'], self.last_stop()), (False, 'needs-owner:escalated'))
        self.assertIn('no verified pull request', self.engine.brief())

    def test_recording_the_pr_after_one_continuation_completes(self):
        self.arm()
        self.finish_line()
        self.assertIn('Autonomy pass 1:', self.engine.hook_stop())
        self.view()
        self.engine.record_pr('main', self.lease, self.URL)
        self.assertIsNone(self.engine.hook_stop())
        self.assertEqual(self.last_stop(), 'complete')


class StopReasonTests(AutonomyFixture):
    """A session that ends with autonomy active leaves the morning report and a reason."""

    def restart(self, harness_session=None):
        shutil.rmtree(self.state)
        self.engine = Engine(self.state, self.repo, clock=lambda: self.now[0])
        self.lease = self.engine.open_session('main', harness_session=harness_session)

    def check(self, call, reason):
        self.arm()
        self.now[0] += 60
        call()
        auto = self.auto()
        self.assertEqual((auto['active'], auto['last_stop_reason']), (False, reason))
        self.assertEqual(auto['report']['reason'], reason)
        self.assertIn('- stop reason: ' + reason, self.engine.autonomy_report()['text'])
        self.assertEqual(self.engine.status()['last_brief']['reason'], reason)
        self.assertEqual((self.state / 'progress.md').read_text().count('## Run brief'), 1)

    def test_interrupt_end_close_with_autonomy_leave_report_and_reason(self):
        with self.subTest('interrupt'):
            self.check(lambda: self.engine.interrupt('main', self.lease), 'interrupted')
        with self.subTest('interrupt_active'):
            self.restart()
            self.check(self.engine.interrupt_active, 'interrupted')
        with self.subTest('ended'):
            self.restart(harness_session='S')
            self.check(lambda: self.engine.end_harness_session('S'), 'ended')
        with self.subTest('finished'):
            self.restart()
            self.check(lambda: self.engine.close_session('main', self.lease), 'finished')

    def test_a_close_without_autonomy_still_writes_closed(self):
        self.engine.close_session('main', self.lease)
        self.assertEqual(self.engine.status()['last_brief']['reason'], 'closed')
        self.assertIsNone(self.auto())

    def test_interrupt_then_new_run_refused_until_receipt_or_disarm(self):
        self.arm()
        self.engine.interrupt('main', self.lease)
        run = self.engine.status()['run_id']
        start = lambda: run_cli(self, 'start', '--new-run', '--size', 'tiny')
        code, _, err = start()
        self.assertEqual(code, 2)
        self.assertIn('New run refused: autonomy kept a report for run ' + run, err)
        self.assertEqual(self.engine.status()['run_id'], run)
        self.assertFalse(self.engine.disarm_autonomy()['was_active'])  # pops the kept report
        self.assertEqual(start()[0], 0)

    def test_interrupt_then_a_receipt_lets_a_new_run_start(self):
        self.arm()
        self.engine.interrupt('main', self.lease)
        self.engine.record_owner_approval([], [], dict(event='UserPromptSubmit'))
        self.assertEqual(run_cli(self, 'start', '--new-run', '--size', 'tiny')[0], 0)



class OwnerApprovalTests(AutonomyFixture):
    """The receipt writer: only `Engine.record_owner_approval`, only for a stopped run."""

    EVIDENCE = dict(event='UserPromptSubmit', session_id='S', prompt_id=None, prompt_sha256='a' * 64)

    def pr(self, number=12, order=1):
        return dict(order=order, number=number, repo='o/r', url='https://github.example/o/r/pull/%d' % number,
                    head_ref='feat/%d' % number, head_sha='b' * 40, base_ref='main')

    def stopped(self):
        self.arm()
        self.engine.disarm_autonomy()  # the stop that leaves the morning report

    def raw(self):
        return json.loads(self.engine.state_path.read_text())

    def test_record_owner_approval_stores_the_receipt(self):
        self.stopped()
        excluded = [dict(number=13, reason='head moved')]
        receipt = self.engine.record_owner_approval([self.pr()], excluded, self.EVIDENCE)
        stored = self.raw()['approval']
        self.assertEqual(receipt, stored)
        self.assertEqual((stored['run'], stored['prs'], stored['excluded'], stored['evidence']),
                         (self.engine.status()['run_id'], [self.pr()], excluded, self.EVIDENCE))
        self.assertEqual((stored['version'], stored['recorded_at'], stored['default_branch']), (1, T0, self.default_branch))

    def test_record_owner_approval_replaces_previous_receipt(self):
        self.stopped()
        self.engine.record_owner_approval([self.pr(12)], [], self.EVIDENCE)
        self.now[0] += 60
        self.engine.record_owner_approval([self.pr(12), self.pr(13, 2)], [], self.EVIDENCE)
        stored = self.raw()
        self.assertEqual([p['number'] for p in stored['approval']['prs']], [12, 13])
        self.assertEqual(stored['approval']['recorded_at'], T0 + 60)
        self.assertNotIn('approval_history', stored)

    def test_record_owner_approval_with_no_prs(self):
        self.stopped()
        self.assertEqual(self.engine.record_owner_approval([], [], self.EVIDENCE)['prs'], [])
        self.assertEqual(self.raw()['approval']['prs'], [])

    def test_record_owner_approval_refused_while_autonomy_active(self):
        self.arm()
        with self.assertRaisesRegex(EngineError, 'autonomy is active'):
            self.engine.record_owner_approval([], [], self.EVIDENCE)
        self.assertNotIn('approval', self.raw())

    def test_record_owner_approval_refused_when_run_never_stopped(self):
        with self.assertRaisesRegex(EngineError, 'never stopped'):
            self.engine.record_owner_approval([], [], self.EVIDENCE)  # no autonomy at all
        self.arm()
        self.engine.disarm_autonomy()
        self.engine.disarm_autonomy()  # the second disarm pops the kept report
        with self.assertRaisesRegex(EngineError, 'never stopped'):
            self.engine.record_owner_approval([], [], self.EVIDENCE)
        self.assertNotIn('approval', self.raw())

    def test_record_owner_approval_refused_without_state(self):
        engine = Engine(self.root / 'empty', self.repo)
        with self.assertRaisesRegex(EngineError, 'never stopped'):
            engine.record_owner_approval([], [], self.EVIDENCE)
        self.assertFalse((self.root / 'empty' / 'state.json').exists())

    def test_record_owner_approval_refuses_malformed_input(self):
        self.stopped()
        bad = [([], [], None), ([], [], 'prompt'), ({}, [], self.EVIDENCE), ([], 'x', self.EVIDENCE),
               (['url'], [], self.EVIDENCE), ([{'number': 1}], [], self.EVIDENCE), ([], [{'number': 1}], self.EVIDENCE),
               ([dict(self.pr(), number='12')], [], self.EVIDENCE)]
        for prs, excluded, evidence in bad:
            with self.subTest(prs=prs, excluded=excluded, evidence=evidence), self.assertRaises(EngineError):
                self.engine.record_owner_approval(prs, excluded, evidence)
        self.assertNotIn('approval', self.raw())

    def test_start_new_run_archives_approval(self):
        self.stopped()
        self.engine.interrupt('main', self.lease)
        run = self.engine.status()['run_id']
        self.engine.record_owner_approval([self.pr()], [], self.EVIDENCE)
        self.assertEqual(run_cli(self, 'start', '--new-run', '--size', 'tiny')[0], 0)
        archived = json.loads(next((self.state / 'history').glob('run-*.json')).read_text())
        self.assertEqual((archived['state']['run_id'], archived['state']['approval']['run']), (run, run))
        self.assertNotIn('approval', self.raw())
        self.assertNotEqual(self.raw()['run_id'], run)

    def test_no_argparse_subcommand_writes_approval(self):
        self.assertNotIn('record_owner_approval', (SCRIPTS / 'orchestra.py').read_text())
        self.stopped()
        for words in (('approval',), ('approve',), ('approved',), ('autonomy', 'approval'), ('autonomy', 'approve')):
            with self.subTest(words=words):
                self.assertEqual(run_cli(self, *words)[0], 2)  # argparse refuses an unknown command
                self.assertNotIn('approval', self.raw())


    def test_record_owner_approval_raises_state_busy_within_lock_wait(self):
        self.stopped()
        hook_engine = Engine(self.state, self.repo, clock=lambda: self.now[0], lock_wait=0.2)
        handle = (self.state / 'state.lock').open('a+')
        self.addCleanup(handle.close)
        portable.lock(handle, exclusive=True)
        started = time.monotonic()
        with self.assertRaises(StateBusy):
            hook_engine.record_owner_approval([], [], self.EVIDENCE)
        self.assertLess(time.monotonic() - started, 1.5)
        portable.unlock(handle)
        self.assertNotIn('approval', self.raw())
        hook_engine.record_owner_approval([], [], self.EVIDENCE)  # free again: it records
        self.assertIn('approval', self.raw())


class StaleAutonomyTests(AutonomyFixture):
    """`stop_stale_autonomy`: a prompt from another session may end a run that stopped writing or ran out its deadline."""

    def bound(self, session='NIGHT'):
        shutil.rmtree(self.state)
        self.engine = Engine(self.state, self.repo, clock=lambda: self.now[0])
        self.lease = self.engine.open_session('main', harness_session=session)
        self.arm()

    def mtime(self):
        return self.engine.state_path.stat().st_mtime

    def stale(self):
        return self.engine.policy.get('worker_stale_seconds', 3600)

    def test_stop_stale_autonomy_deadline_passed(self):
        self.bound()
        self.assertFalse(self.engine.stop_stale_autonomy('MORNING', now=self.mtime() + 10))
        self.assertTrue(self.auto()['active'])
        self.now[0] += 7200
        self.assertTrue(self.engine.stop_stale_autonomy('NIGHT'))  # even the bound session: the deadline ends the run
        auto = self.auto()
        self.assertEqual((auto['active'], auto['last_stop_reason']), (False, 'deadline'))
        self.assertEqual(auto['report']['reason'], 'deadline')
        self.assertFalse(self.engine.stop_stale_autonomy('NIGHT'))  # already stopped: nothing to do

    def test_stop_stale_autonomy_other_session_and_old_mtime(self):
        self.bound()
        written = self.mtime()
        self.assertTrue(self.engine.stop_stale_autonomy('MORNING', now=written + self.stale() + 1))
        auto = self.auto()
        self.assertEqual((auto['active'], auto['last_stop_reason']), (False, 'stale'))
        self.assertIn('- stop reason: stale', self.engine.autonomy_report()['text'])

    def test_stop_stale_autonomy_other_session_fresh_mtime_does_nothing(self):
        self.bound()
        before = self.engine.state_path.read_bytes()
        self.assertFalse(self.engine.stop_stale_autonomy('MORNING', now=self.mtime() + self.stale() - 1))
        self.assertEqual(before, self.engine.state_path.read_bytes())  # a no-op never rewrites state.json
        self.assertTrue(self.auto()['active'])

    def test_stop_stale_autonomy_bound_session_with_old_mtime_does_nothing(self):
        self.bound()
        self.assertFalse(self.engine.stop_stale_autonomy('NIGHT', now=self.mtime() + 10 * self.stale()))
        self.assertTrue(self.auto()['active'])

    def test_stop_stale_autonomy_raises_state_busy_within_lock_wait(self):
        self.bound()
        hook_engine = Engine(self.state, self.repo, clock=lambda: self.now[0], lock_wait=0.2)
        handle = (self.state / 'state.lock').open('a+')
        self.addCleanup(handle.close)
        portable.lock(handle, exclusive=True)
        started = time.monotonic()
        with self.assertRaises(StateBusy):
            hook_engine.stop_stale_autonomy('MORNING', now=self.mtime() + self.stale() + 1)
        self.assertLess(time.monotonic() - started, 1.5)
        portable.unlock(handle)
        self.assertTrue(self.auto()['active'])
        self.assertTrue(hook_engine.stop_stale_autonomy('MORNING', now=self.mtime() + self.stale() + 1))

    def test_stop_stale_autonomy_without_active_autonomy_or_state(self):
        self.assertFalse(self.engine.stop_stale_autonomy('MORNING', now=self.mtime() + 10 * self.stale()))
        self.assertFalse(Engine(self.root / 'empty', self.repo).stop_stale_autonomy('X'))
        self.assertFalse((self.root / 'empty' / 'state.json').exists())


class DispatchDefaultTests(EngineFixture):
    def test_dispatch_defaults_the_worker_to_orchestra_task(self):
        self.task('x')
        token = self.engine.dispatch('main', self.lease, 'x')
        self.assertEqual('orchestra-x', self.engine.status()['tasks']['x']['worker'])
        self.engine.report('orchestra-x', token, done('Built x.'))

    def test_default_worker_is_still_reserved_and_never_the_coordinator(self):
        self.task('x')
        self.task('y')
        self.engine.dispatch('main', self.lease, 'x', serial='fixture: one card at a time')
        with self.assertRaisesRegex(EngineError, 'Worker is already reserved'):
            self.engine.dispatch('main', self.lease, 'y', 'orchestra-x')
        with self.assertRaisesRegex(EngineError, 'Worker must differ from coordinator'):
            self.engine.dispatch('main', self.lease, 'y', '')
        self.task('main', files=['main'])
        with self.assertRaisesRegex(EngineError, 'Worker must differ from coordinator'):
            self.engine.dispatch('main', self.lease, 'main', 'main')

    def test_cli_dispatch_without_a_worker_uses_the_default(self):
        self.task('x')
        code, out, err = run_cli(self, '--lease', self.lease, 'dispatch', 'x')
        self.assertEqual((0, ''), (code, err), out)
        self.assertEqual('orchestra-x', json.loads(out)['worker'])


class ReviewRecordingTests(EngineFixture):
    """The artifact string a reviewer saw, and `review FILE --token`."""

    def setUp(self):
        super().setUp()
        (self.repo / 'B1').write_text('built')
        self.git('add', 'B1')
        self.git('commit', '-qm', 'B1')
        self.task('B1')
        self.engine.report('w-B1', self.engine.dispatch('main', self.lease, 'B1', 'w-B1'), done('Built B1.'))
        self.task('C1', role='critic', mode='judge', files=[])
        self.critic_token = self.engine.dispatch('main', self.lease, 'C1', 'orchestra-C1')
        self.engine.report('orchestra-C1', self.critic_token, 'Judged.')
        self.head = self.git('rev-parse', 'HEAD')

    def receipt_file(self, name, artifact, reviewer='orchestra-C1', **kw):
        path = self.root / name
        self.review(path, reviewer=reviewer, **kw)
        body = json.loads(path.read_text())
        body['artifact'] = artifact
        path.write_text(json.dumps(body, indent=1))
        return path

    def record(self, path, reviewer='orchestra-C1'):
        return self.engine.record_review('main', self.lease, reviewer, path, ['correctness'], ['B1'])

    def test_artifact_string_head_clean_records_the_engine_artifact(self):
        for label, sha in (('full', self.head), ('seven', self.head[:7])):
            path = self.receipt_file(label + '.json', sha + ' clean', tasks=['B1'])
            before = path.read_bytes()
            receipt = self.record(path)
            self.assertEqual(self.engine.artifact(self.engine.scope_for(['B1'])), receipt['artifact'], label)
            self.assertEqual(before, path.read_bytes())  # the reviewer's file is untouched
            self.assertEqual(hashlib.sha256(before).hexdigest(), receipt['source_sha256'])
            self.assertEqual(str(path.resolve()), receipt['source'])
            self.assertEqual(self.engine.state_dir, Path(receipt['path']).parent)
            self.assertEqual(json.loads(Path(receipt['path']).read_text())['artifact'], receipt['artifact'])
        self.engine.accept('main', self.lease, 'B1')

    def test_artifact_string_receipt_notices_a_changed_original(self):
        path = self.receipt_file('r.json', self.head + ' clean', tasks=['B1'])
        self.record(path)
        path.write_text(path.read_text() + ' ')
        with self.assertRaisesRegex(EngineError, 'missing or altered'):
            self.engine.accept('main', self.lease, 'B1')

    def test_only_the_head_clean_string_is_taken(self):
        other = ('0' if self.head[0] != '0' else '1') * 40
        cases = {'bare sha': self.head, 'short bare sha': self.head[:7], 'six characters': self.head[:6] + ' clean',
                 'another commit': other + ' clean', 'dirty': self.head + ' dirty', 'extra word': self.head + ' clean now',
                 'upper case': self.head.upper() + ' clean', 'not hex': 'zzzzzzz clean', 'a number': 7, 'a list': [self.head]}
        for label, artifact in cases.items():
            path = self.receipt_file('x.json', artifact, tasks=['B1'])
            with self.subTest(label), self.assertRaisesRegex(EngineError, 'metadata, verdict or artifact does not match'):
                self.record(path)
        self.assertEqual([], self.engine.status()['reviews'])

    def test_artifact_string_refused_when_the_scope_is_not_clean(self):
        (self.repo / 'B1').write_text('edited after the commit')
        path = self.receipt_file('x.json', self.head + ' clean', tasks=['B1'])
        with self.assertRaisesRegex(EngineError, 'metadata, verdict or artifact does not match'):
            self.record(path)

    def test_artifact_string_needs_the_review_card_and_its_dispatch_policy(self):
        path = self.receipt_file('x.json', self.head + ' clean', tasks=['B1'], reviewer='stranger')
        with self.assertRaisesRegex(EngineError, 'metadata, verdict or artifact does not match'):
            self.record(path, 'stranger')
        state = json.loads(self.engine.state_path.read_text())
        self.assertEqual(self.engine.policy_hash, state['tasks']['C1']['dispatch_policy'])
        state['tasks']['C1']['dispatch_policy'] = 'older policy'
        self.engine.state_path.write_text(json.dumps(state))
        path = self.receipt_file('y.json', self.head + ' clean', tasks=['B1'])
        with self.assertRaisesRegex(EngineError, 'metadata, verdict or artifact does not match'):
            self.record(path)
        self.assertEqual([], self.engine.status()['reviews'])
        path = self.receipt_file('z.json', self.engine.artifact(self.engine.scope_for(['B1'])), tasks=['B1'])
        self.record(path)  # the structured form binds the policy itself and is unchanged

    def final_card(self):
        self.task('V1', role='code-reviewer', mode='final', files=[], review_of=['B1'])
        return self.engine.dispatch('main', self.lease, 'V1', 'orchestra-V1')

    def final_file(self, name='f.json', **kw):
        ids = sorted(self.engine.status()['tasks'])
        return self.receipt_file(name, self.head + ' clean', reviewer='orchestra-V1', tasks=ids, final=True,
                                 categories=ALL_CATEGORIES, **kw)

    def test_review_token_reports_records_and_accepts_in_one_step(self):
        self.engine.accept('main', self.lease, 'B1')
        self.engine.accept('main', self.lease, 'C1')
        token = self.final_card()
        path = self.final_file()
        result = self.engine.review_with_token('main', self.lease, token, path)
        card = self.engine.status()['tasks']['V1']
        self.assertEqual(('accepted', path.read_text()), (card['state'], card['report']))
        self.assertEqual([result['receipt']['id']], [r['id'] for r in self.engine.status()['reviews']])
        self.assertEqual((True, None, 'V1'), (result['accepted'], result['refusal'], result['card']))
        self.engine.check_completion('main', self.lease)

    def test_review_token_skips_the_report_of_an_already_reported_card(self):
        token = self.final_card()
        path = self.final_file()
        self.engine.report('orchestra-V1', token, 'My own report.')
        self.engine.review_with_token('main', self.lease, token, path)
        self.assertEqual('My own report.', self.engine.status()['tasks']['V1']['report'])
        self.assertEqual(1, len(self.engine.status()['reviews']))

    def test_review_token_leaves_a_card_the_accept_checks_refuse_reported(self):
        token = self.final_card()
        path = self.final_file(findings=['f'], task_findings={'V1': ['f']})
        result = self.engine.review_with_token('main', self.lease, token, path)
        self.assertFalse(result['accepted'])
        self.assertIn('current review findings', result['refusal'])
        self.assertEqual('reported', self.engine.status()['tasks']['V1']['state'])
        self.assertEqual(1, len(self.engine.status()['reviews']))

    def test_review_token_refusals_change_nothing(self):
        token = self.final_card()
        good = self.final_file()
        other = self.final_file('other.json')
        body = json.loads(other.read_text())
        body['reviewer'] = 'someone-else'
        other.write_text(json.dumps(body))
        nonfinal = self.receipt_file('nf.json', self.head + ' clean', reviewer='orchestra-V1', tasks=['B1'])
        nosummary = self.final_file('ns.json')
        body = json.loads(nosummary.read_text())
        body['summary'] = ''
        nosummary.write_text(json.dumps(body))
        for label, tok, path, message in (('wrong token', 'nope', good, 'Invalid assignment'),
                                          ('wrong reviewer', token, other, 'Invalid assignment'),
                                          ('not final', token, nonfinal, 'final receipts only'),
                                          ('invalid receipt', token, nosummary, 'semantic summary')):
            with self.subTest(label), self.assertRaisesRegex(EngineError, message):
                self.engine.review_with_token('main', self.lease, tok, path)
            card = self.engine.status()['tasks']['V1']
            self.assertEqual(('running', None, []), (card['state'], card.get('report'), self.engine.status()['reviews']))
        with self.assertRaisesRegex(EngineError, 'lease'):
            self.engine.review_with_token('main', 'not-the-lease', token, good)

    def test_review_token_of_a_builder_card_is_refused(self):
        token = self.engine.status()['tasks']['B1']['assignment']
        with self.assertRaisesRegex(EngineError, 'Invalid assignment'):
            self.engine.review_with_token('main', self.lease, token, self.final_file())

    def test_cli_review_token(self):
        token = self.final_card()
        path = self.final_file()
        code, out, err = run_cli(self, '--lease', self.lease, 'review', str(path), '--token', token)
        self.assertEqual((0, ''), (code, err), out)
        self.assertTrue(json.loads(out)['accepted'])
        self.assertEqual('accepted', self.engine.status()['tasks']['V1']['state'])

    def test_cli_review_token_prints_the_receipt_without_entries(self):
        token = self.final_card()
        code, out, err = run_cli(self, '--lease', self.lease, 'review', str(self.final_file()), '--token', token)
        self.assertEqual((0, ''), (code, err), out)
        self.assertNotIn('entries', json.loads(out)['receipt'])
        self.assertIn('entries', self.engine.status()['reviews'][0])


class LandedWorkTests(HoldFixture):
    """`finish` refuses an accepted builder card whose reported commit never reached HEAD."""

    def side_commit(self, branch, name):
        self.git('switch', '-qc', branch)
        (self.repo / name).write_text(name)
        self.git('add', name)
        self.git('commit', '-qm', name)
        sha = self.git('rev-parse', 'HEAD')
        self.git('switch', '-q', '-')
        return sha

    def accepted(self, name, artifact):
        self.task(name)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        self.engine.report('w-' + name, token, done('Built %s\nARTIFACT: %s' % (name, artifact)))
        self.engine.accept('main', self.lease, name)

    def landed(self):
        return {c['id']: c['landed'] for c in self.engine.view()['cards']}

    def test_finish_refuses_until_the_reported_commit_is_in_head(self):
        sha = self.side_commit('side', 'B3')
        self.accepted('B3', sha + ' clean')
        self.assertEqual(sha, self.engine.status()['tasks']['B3']['report_sha'])
        self.reviewed('final', ['B3'], final=True, categories=self.ALL)
        self.assertEqual({'B3': False}, self.landed())
        with self.assertRaisesRegex(EngineError, r'^Accepted work is not in HEAD: B3 \(%s\); merge it, or hold the card$' % sha[:8]):
            self.engine.close_session('main', self.lease)
        self.git('merge', '-q', 'side')
        self.assertEqual({'B3': True}, self.landed())
        self.reviewed('final-2', ['B3'], final=True, categories=self.ALL)
        self.engine.close_session('main', self.lease)

    def test_patch_equivalent_work_counts_as_landed(self):
        sha = self.side_commit('side', 'B4')
        self.git('cherry-pick', sha)
        self.accepted('B4', sha[:7] + ' clean')
        self.assertEqual({'B4': True}, self.landed())

    def squash_setup(self, move_main=False):
        # F37: two builder commits on a PR branch, the second rewriting the first's line, so `git cherry` cannot match
        # either one; the engine reviewed the branch tip, which was then squash-merged into main.
        first = self.side_commit('pr', 'B8')
        self.git('switch', '-q', 'pr')
        (self.repo / 'B8').write_text('B8 again')
        self.git('commit', '-qam', 'B9')
        second = self.git('rev-parse', 'HEAD')
        self.git('switch', '-q', '-')
        self.accepted('B8', first + ' clean')
        self.accepted('B9', second + ' clean')
        self.git('switch', '-q', 'pr')
        self.reviewed('final-pr', ['B8', 'B9'], final=True, categories=self.ALL)
        self.git('switch', '-q', '-')
        if move_main:
            (self.repo / 'other').write_text('landed on main meanwhile')
            self.git('add', 'other')
            self.git('commit', '-qm', 'other')
        self.git('merge', '-q', '--squash', 'pr')
        self.git('commit', '-qm', 'squash of pr')
        self.git('branch', '-q', '-D', 'pr')

    def test_squash_merged_work_counts_as_landed(self):
        self.squash_setup()
        self.assertEqual({'B8': True, 'B9': True}, self.landed())
        self.reviewed('final-main', ['B8', 'B9'], final=True, categories=self.ALL)
        self.engine.close_session('main', self.lease)

    def test_squash_after_main_moved_counts_as_landed(self):
        self.squash_setup(move_main=True)
        self.assertEqual({'B8': True, 'B9': True}, self.landed())

    def test_reviewed_branch_that_never_merged_is_not_landed(self):
        first = self.side_commit('pr', 'B8')
        self.accepted('B8', first + ' clean')
        self.git('switch', '-q', 'pr')
        self.reviewed('final-pr', ['B8'], final=True, categories=self.ALL)
        self.git('switch', '-q', '-')
        self.assertEqual({'B8': False}, self.landed())

    def test_a_report_without_a_commit_sha_is_not_checked(self):
        for name, artifact in (('B5', 'deadbeef nonsense'), ('B6', 'fixture'), ('B7', '')):
            self.accepted(name, artifact or self.git('rev-parse', 'HEAD')[:6] + ' clean')
        self.assertEqual({'B5': None, 'B6': None, 'B7': None}, self.landed())
        self.reviewed('final', [], final=True, categories=self.ALL)
        self.engine.close_session('main', self.lease)


class CliOutputSizeTests(EngineFixture):
    """`review` and `status` leave the per-file `entries` map out; `status --full` keeps it."""

    def test_receipts_print_without_entries_for_a_large_repository(self):
        for n in range(500):
            (self.repo / ('f%03d.txt' % n)).write_text(str(n))
        self.git('add', '.')
        self.git('commit', '-qm', 'many files')
        path = self.root / 'final.json'
        self.review(path, categories=ALL_CATEGORIES, final=True)
        code, out, err = run_cli(self, '--lease', self.lease, 'review', str(path))
        self.assertEqual((0, ''), (code, err), out)
        self.assertNotIn('entries', json.loads(out))
        self.assertEqual(500 + 1, len(self.engine.status()['reviews'][0]['entries']))  # state.json keeps the map
        short, full = run_cli(self, 'status')[1], run_cli(self, 'status', '--full')[1]
        self.assertNotIn('"entries"', short)
        self.assertIn('"entries"', full)
        self.assertLess(len(short) * 3, len(full))


class NextStepRefusalTests(HoldFixture):
    """Refusals name what to do next."""

    def test_review_without_issues_names_the_field_and_its_shape(self):
        self.built('B1')
        with self.assertRaisesRegex(EngineError, r'^Review needs `issues`: a list of \{text, severity, impact\}, or \[\] when clean$'):
            self.reviewed('r', ['B1'], mutate=lambda body: body.pop('issues'))

    def test_final_review_coverage_names_the_missing_cards(self):
        self.built('B1')
        self.built('B2')
        with self.assertRaisesRegex(EngineError, 'Final review must explicitly cover every task; missing: B1, B2$'):
            self.reviewed('partial', [], final=True, cover=False)

    def test_finish_with_findings_names_the_repair_and_finding_routes(self):
        self.built('B1')
        self.engine.accept('main', self.lease, 'B1')
        self.reviewed('final', ['B1'], findings=['f'], task_findings={'B1': ['f']}, final=True, categories=self.ALL)
        with self.assertRaisesRegex(EngineError, r'^Current final review has findings; add a repair card \(`repair_of`\) '
                                                 r'or record the finding with `finding add`$'):
            self.engine.close_session('main', self.lease)

    def test_finish_with_unaccepted_cards_names_them_and_their_states(self):
        self.built('B1')
        self.task('B2', files=['B2'])
        self.engine.dispatch('main', self.lease, 'B2', 'w-B2')
        with self.assertRaisesRegex(EngineError, r'^All tasks must be accepted: B1 \(reported\), B2 \(running\)$'):
            self.engine.close_session('main', self.lease)

    def test_finish_with_held_tips_names_the_cleared_route(self):
        self.blocked_chain()
        self.engine.hold('main', self.lease, 'R1', 'g')
        with self.assertRaisesRegex(EngineError, r'B1 \(held\), R1 \(held\).*a CLEAN final review with `cleared` closes'):
            self.engine.close_session('main', self.lease)

    def test_a_start_refusal_says_why_the_card_is_not_ready(self):
        self.task('a')
        self.task('b', dependencies=['a'])
        for task_id, why in (('nope', 'unknown task nope'), ('b', 'dependency a not accepted \\(queued\\)')):
            with self.subTest(task_id), self.assertRaisesRegex(EngineError, '^Task is not ready or capacity is exhausted: ' + why):
                self.engine.dispatch('main', self.lease, task_id, 'w')
        self.engine = Engine(self.root / 'capacity', self.repo, dict(schema_version=1, max_workers=1))
        self.lease = self.engine.open_session('main')
        self.task('a')
        self.engine.dispatch('main', self.lease, 'a', 'w')
        self.task('c', files=['c'])
        with self.assertRaisesRegex(EngineError, '^Task is not ready or capacity is exhausted: capacity: 1 of 1 workers running$'):
            self.engine.dispatch('main', self.lease, 'c', 'w2')

    def test_task_lists_default_to_empty_and_missing_lists_say_missing(self):
        self.engine.add_task('main', self.lease, dict(id='t', role='builder', mode='implementation', inputs=['s'], acceptance=['x']))
        stored = self.engine.status()['tasks']['t']
        self.assertEqual(([], [], []), (stored['files'], stored['resources'], stored['dependencies']))
        for key in ('inputs', 'acceptance'):
            task = dict(id='u', role='builder', mode='implementation', inputs=['s'], acceptance=['x'])
            del task[key]
            with self.subTest(key), self.assertRaisesRegex(EngineError, '^Missing task ' + key + '$'):
                self.engine.add_task('main', self.lease, task)


class RestartReceiptTests(EngineFixture):
    def test_plain_start_lists_the_requeued_cards(self):
        self.task('a')
        self.engine.dispatch('main', self.lease, 'a', 'w')
        self.engine.interrupt('main', self.lease)
        code, out, err = run_cli(self, 'start')
        self.assertEqual((0, ''), (code, err), out)
        self.assertEqual(['a'], json.loads(out)['requeued'])

    def test_recover_for_another_session_names_the_crash_route(self):
        self.engine.interrupt('main', self.lease)
        self.engine.open_session('main', harness_session='H1')
        with self.assertRaisesRegex(EngineError, r'belongs to session H1; this session reads only.*--take-over'):
            self.engine.recover_lease('main', 'H2')
