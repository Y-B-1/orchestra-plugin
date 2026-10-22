"""T2a2: the autonomy plane and the unattended lock of the PreToolUse hook.

`unattended` is a stopped run whose report is kept and whose receipt for this run is not recorded: the hook then applies
the autonomy column to release classes and the protect column to everything else. Tests call `handle_event` with an
explicit mode and `unattended`, or go through `main()` with a temporary state home."""
import io
import json
import os
import pathlib
import subprocess
import sys
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(HERE))

import test_merge_guard as tm
from orchestra_core import hooks as hooks_module
from orchestra_core.engine import Engine
from orchestra_core.guards import guard_digest
from orchestra_core.hooks import LEDGER_LOCKED, _raw_unattended, handle_event, main
from orchestra_core.paths import state_location

EVIDENCE = tm.EVIDENCE
WAY_OUT = ('approved', 'autonomy disarm')
SCHEDULERS = ('CronCreate', 'ScheduleWakeup', 'RemoteTrigger')


def verdict(result):
    """deny, ask, warn (context only) or allow."""
    hso = result.output.get('hookSpecificOutput', {})
    if 'permissionDecision' in hso:
        return hso['permissionDecision']
    return 'warn' if hso.get('additionalContext') else 'allow'


def reason(result):
    return result.output['hookSpecificOutput'].get('permissionDecisionReason', '')


class FakeEngine:
    """The slice of Engine that handle_event reads."""

    def __init__(self, autonomy=False, gates=()):
        self.autonomy, self.gates, self.policy = autonomy, list(gates), {}

    def autonomy_active(self):
        return self.autonomy

    def status(self):
        return {'session': {'active': True}, 'autonomy': {}}

    def current_gate_ids(self):
        return self.gates

    def check_release(self, remote, target, argv=None):
        return False


class PlaneFixture(tm.MergeFixture):
    """A real repository on the branch `work`, a bare origin and a linked worktree, with a real engine. Nothing is
    armed: a test prepares what must exist before the arm, then calls `self.arm()`."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, XDG_STATE_HOME=str(self.root / 'xdg'))
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop('ORCHESTRA_STATE_DIR', None)  # a linked worktree finds the run of its main checkout by path
        self.repo = self.repo.resolve()
        self.state = state_location(self.repo)
        self.engine = Engine(self.state, self.repo, clock=lambda: self.now[0])
        self.lease = self.engine.open_session('main')
        bare = self.root / 'origin.git'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', self.default_branch, str(bare)], check=True)
        self.git('remote', 'add', 'origin', str(bare))
        self.git('push', '-q', 'origin', self.default_branch)
        self.git('fetch', '-q', 'origin')
        self.git('remote', 'set-head', 'origin', self.default_branch)
        self.wt = (self.root / 'wt').resolve()
        self.git('worktree', 'add', '-q', str(self.wt), '-b', 'wt-branch')

    def call(self, command, cwd=None, tool='Bash', data=None, event_args=(), session=None):
        """The real hook entry point: (exit code, decoded output)."""
        payload = {'cwd': str(cwd or self.repo), 'tool_name': tool, 'tool_input': data or {'command': command}}
        if session:
            payload['session_id'] = session
        with mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out, mock.patch('sys.stderr', new_callable=io.StringIO):
            code = main(['PreToolUse', *event_args])
            return code, json.loads(out.getvalue())

    def hook(self, command, cwd=None, **kw):
        """The permission answer of the real hook for a shell command: deny, ask or None."""
        code, output = self.call(command, cwd, **kw)
        self.assertEqual(code, 0)
        return output.get('hookSpecificOutput', {}).get('permissionDecision')

    def hook_reason(self, command, cwd=None, **kw):
        return self.call(command, cwd, **kw)[1]['hookSpecificOutput']['permissionDecisionReason']

    def decide(self, command, cwd=None, mode='normal', **kw):
        payload = {'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': str(cwd or self.repo)}
        return handle_event('PreToolUse', payload, mode=mode, **kw)

    def stop(self):
        """Arm, then end the session: the report is kept and no receipt exists."""
        self.arm()
        self.engine.interrupt('main', self.lease)

    def raw(self):
        return json.loads(self.engine.state_path.read_text())

    def branch(self, name, push=(), start='work'):
        """A branch with one commit of its own; `push` lists the remote branch names it is pushed to."""
        self.git('switch', '-q', start)
        self.git('switch', '-qc', name)
        (self.repo / (name.replace('/', '-') + '.txt')).write_text(name)
        self.git('add', '--', name.replace('/', '-') + '.txt')
        self.git('commit', '-qm', name)
        for remote_name in push:
            self.git('push', '-q', 'origin', '%s:refs/heads/%s' % (name, remote_name))
        self.git('switch', '-q', 'work')


MATRIX = [
    # row, command, normal, protect, autonomy, unattended (normal and protect run with no run at all)
    (4, 'git stash', 'warn', 'deny', 'deny', 'deny'),
    (10, 'git add -A', 'allow', 'deny', 'deny', 'deny'),
    (11, 'git commit -a -m x', 'allow', 'deny', 'deny', 'deny'),
    (12, 'git commit --amend -m x', 'warn', 'deny', 'deny', 'deny'),
    (14, 'git push --tags origin', 'warn', 'deny', 'deny', 'deny'),
    (14, 'git push --all origin', 'warn', 'deny', 'deny', 'deny'),
    (15, 'git push origin :topic', 'warn', 'deny', 'deny', 'deny'),
    (24, 'git push origin x && gh pr create', 'allow', 'allow', 'deny', 'deny'),
    (27, 'gh pr merge 3', 'allow', 'allow', 'deny', 'deny'),
    (27, 'git push origin main', 'allow', 'allow', 'deny', 'deny'),
    (27, 'gh release create v1', 'allow', 'allow', 'deny', 'deny'),
    (27, 'npm publish', 'allow', 'allow', 'deny', 'deny'),
    (46, 'gh workflow run ci.yml', 'allow', 'allow', 'deny', 'deny'),
    (50, 'git push origin HEAD:other', 'allow', 'allow', 'deny', 'deny'),
    (51, 'gh pr merge 3 --merge --delete-branch --match-head-commit abc', 'allow', 'allow', 'deny', 'deny'),
    ('N10', 'gh pr edit 3 --base main', 'allow', 'allow', 'deny', 'deny'),
    ('N11', 'gh prm 12', 'allow', 'allow', 'deny', 'deny'),
    ('N11', 'gh alias set x y', 'allow', 'allow', 'deny', 'allow'),  # a config boundary: autonomy only
    ('N13', 'gh api -X DELETE repos/o/r', 'allow', 'allow', 'deny', 'deny'),
    ('N13', 'gh api -X PATCH repos/o/r -f default_branch=x', 'allow', 'allow', 'deny', 'deny'),
    ('N13', 'gh api -X DELETE repos/o/r/rulesets/1', 'allow', 'allow', 'deny', 'deny'),
    (28, 'git merge topic', 'allow', 'allow', 'allow', 'allow'),  # a merge off the default branch
]


class GuardMatrixAutonomyTest(PlaneFixture):
    """The autonomy and unattended columns of the changed rows of the plan matrix, next to normal and protect."""

    def setUp(self):
        super().setUp()
        self.arm()

    def column(self, name, command, **kw):
        if name == 'autonomy':  # the mode argument is normal: the run alone must force the protect column
            return verdict(self.decide(command, mode='normal', engine=self.engine, **kw))
        if name == 'unattended':
            return verdict(self.decide(command, mode='normal', unattended=True, **kw))
        return verdict(self.decide(command, mode=name, **kw))

    def test_changed_rows_in_every_column(self):
        for row, command, *want in MATRIX:
            for name, expected in zip(('normal', 'protect', 'autonomy', 'unattended'), want):
                with self.subTest(row=row, command=command, column=name):
                    self.assertEqual(self.column(name, command), expected)

    def test_row_51_the_locked_columns_never_ask(self):
        for command in ('git push origin main', 'gh pr merge 3', 'gh workflow run deploy.yml', 'gh prm 12'):
            with self.subTest(command=command):
                for name in ('autonomy', 'unattended'):
                    self.assertNotEqual(self.column(name, command), 'ask')

    def test_row_31_a_worker_never_spawns_an_agent_while_locked(self):
        payload = {'tool_name': 'Agent', 'tool_input': {'subagent_type': 'orchestra:builder'}, 'cwd': str(self.repo)}
        with mock.patch.dict(os.environ, {'ORCHESTRA_ROLE': 'builder'}):
            self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal')), 'allow')
            self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', engine=self.engine)), 'deny')
            self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', unattended=True)), 'deny')

    def test_rows_32_33_foreign_agents(self):
        sub = {'tool_name': 'Bash', 'tool_input': {'command': 'git status'}, 'cwd': str(self.repo),
               'agent_id': 'a1', 'agent_type': 'general-purpose'}
        agent = {'tool_name': 'Agent', 'tool_input': {'subagent_type': 'general-purpose'}, 'cwd': str(self.repo)}
        for row, payload in ((32, sub), (33, agent)):
            with self.subTest(row=row):
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', engine=self.engine)), 'deny')
                # A stopped run has no active session to protect: the protect column finds nothing to deny.
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', unattended=True)), 'allow')

    def test_row_42_a_busy_state_denies_a_boundary_while_locked(self):
        self.assertEqual(verdict(self.decide('git merge topic', busy=True, armed=True)), 'allow')  # normal, no lock
        self.assertEqual(verdict(self.decide('git merge topic', busy=True, unattended=True)), 'deny')
        self.assertEqual(verdict(self.decide('git push origin main', busy=True, unattended=True)), 'deny')

    def test_row_43_a_reviewer_suite_rerun_denies_while_locked(self):
        payload = {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -m unittest discover'}, 'cwd': str(self.repo),
                   'agent_id': 'a1', 'agent_type': 'orchestra:code-reviewer'}
        gates = FakeEngine(gates=['g1'])
        self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', engine=gates)), 'warn')
        self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', engine=gates, unattended=True)), 'deny')
        self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', engine=FakeEngine(True, ['g1']))), 'deny')

    def test_row_36_and_n12_settings_files(self):
        settings = [self.repo / '.claude' / 'settings.json', self.repo / '.claude' / 'settings.local.json']
        for tool in ('Edit', 'Write', 'MultiEdit'):
            for path in settings:
                payload = {'tool_name': tool, 'tool_input': {'file_path': str(path)}, 'cwd': str(self.repo)}
                with self.subTest(tool=tool, path=path.name):
                    self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal')), 'allow')
                    self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='protect')), 'allow')
                    self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', engine=self.engine)), 'deny')
                    self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', unattended=True)), 'deny')
        other = {'tool_name': 'Write', 'tool_input': {'file_path': str(self.repo / '.claude' / 'notes.md')}, 'cwd': str(self.repo)}
        self.assertEqual(verdict(handle_event('PreToolUse', other, mode='normal', engine=self.engine)), 'allow')
        self.assertEqual(verdict(handle_event('PreToolUse', other, mode='normal', unattended=True)), 'allow')

    def test_row_44_a_ledger_switch_in_a_tool_call(self):
        commands = {'disarm': 'python3 orchestra.py autonomy disarm', 'arm': 'python3 orchestra.py autonomy arm',
                    'new-run': 'python3 orchestra.py --repo . start --size tiny --new-run',
                    'status': 'python3 orchestra.py autonomy status', 'start': 'python3 orchestra.py start --size tiny'}
        expected = {'autonomy': {'disarm': 'deny', 'arm': 'deny', 'new-run': 'deny', 'status': 'allow', 'start': 'allow'},
                    'unattended': {'disarm': 'deny', 'arm': 'allow', 'new-run': 'deny', 'status': 'allow', 'start': 'allow'},
                    'normal': {'disarm': 'allow', 'arm': 'allow', 'new-run': 'allow', 'status': 'allow', 'start': 'allow'}}
        for column, rows in expected.items():
            for name, command in commands.items():
                with self.subTest(column=column, command=name):
                    self.assertEqual(self.column(column, command), rows[name])
        self.assertIn(LEDGER_LOCKED, reason(self.decide(commands['disarm'], engine=self.engine)))


class UnattendedLockTest(PlaneFixture):
    """A stopped run keeps its report: release classes stay denied until the owner approves or disarms."""

    def test_release_class_denied_with_the_way_out_while_the_report_is_kept(self):
        self.stop()
        for command in ('git push origin main', 'gh pr merge 3', 'gh release create v1', 'git push origin x && gh pr create',
                        'gh api -X DELETE repos/o/r', 'gh workflow run ci.yml', 'gh pr edit 3 --base main'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), 'deny')
                for word in WAY_OUT:
                    self.assertIn(word, self.hook_reason(command))

    def test_release_class_allowed_after_a_receipt_for_the_same_run(self):
        self.stop()
        self.assertEqual(self.hook('git push origin main'), 'deny')
        self.engine.record_owner_approval([], [], EVIDENCE)
        self.assertEqual(self.raw()['approval']['run'], self.raw()['run_id'])
        for command in ('git push origin main', 'gh pr merge 3', 'gh release create v1'):
            with self.subTest(command=command):
                self.assertIsNone(self.hook(command))

    def test_a_receipt_for_another_run_id_stays_locked(self):
        self.stop()
        self.engine.record_owner_approval([], [], EVIDENCE)
        data = self.raw()
        data['approval']['run'] = '0' * 16
        self.engine.state_path.write_text(json.dumps(data))
        self.assertEqual(self.hook('git push origin main'), 'deny')

    def test_the_lock_follows_an_explicit_state_dir(self):
        self.stop()
        with mock.patch.dict(os.environ, ORCHESTRA_STATE_DIR=str(self.state)):
            self.assertEqual(self.hook('gh pr merge 3'), 'deny')

    def test_a_merge_on_the_default_branch_is_denied_while_unattended_only_there(self):
        self.stop()
        self.assertIsNone(self.hook('git merge topic'))  # the work branch
        self.git('switch', '-q', self.default_branch)
        self.assertEqual(self.hook('git merge topic'), 'deny')
        self.assertIn('approved', self.hook_reason('git merge topic'))

    def test_release_and_repo_delete_denied_while_unattended(self):
        commands = ('gh release delete v1 -y --cleanup-tag', 'gh repo delete o/r --yes')
        for mode in ('protect', 'normal'):
            for command in commands:
                with self.subTest(mode=mode, command=command):
                    output = self.decide(command, mode=mode, armed=True, unattended=True).output.get('hookSpecificOutput', {})
                    self.assertEqual(output.get('permissionDecision'), 'deny')
                    for word in WAY_OUT:
                        self.assertIn(word, output['permissionDecisionReason'])
            for command in ('rm -rf build', 'git tag -d v1'):  # a local delete keeps its ordinary path
                with self.subTest(mode=mode, command=command):
                    self.assertEqual(self.decide(command, mode=mode, armed=True, unattended=True).output,
                                     self.decide(command, mode=mode, armed=True).output)
        self.stop()
        for command in commands:
            with self.subTest(hook=True, command=command):
                self.assertEqual(self.hook(command), 'deny')
        self.engine.record_owner_approval([], [], EVIDENCE)
        for command in commands:
            with self.subTest(receipt=True, command=command):
                self.assertIsNone(self.hook(command))  # the receipt rules are unchanged: the owner's receipt lets it run

    def test_a_disarm_by_the_owner_ends_the_lock(self):
        self.stop()
        self.assertEqual(self.hook('git push origin main'), 'deny')
        self.engine.disarm_autonomy()  # the terminal route: pops the kept report
        self.assertIsNone(self.hook('git push origin main'))

    def test_unreadable_state_json_denies(self):
        self.stop()
        self.engine.state_path.write_text('{not json')
        self.assertEqual(self.hook('git push origin main'), 'deny')
        self.assertTrue(_raw_unattended(self.engine.state_path))

    def test_raw_unattended_reads_the_raw_state_only(self):
        path = self.engine.state_path
        self.assertFalse(_raw_unattended(self.root / 'missing.json'))
        self.assertFalse(_raw_unattended(path))  # a run that never armed
        self.arm()
        self.assertFalse(_raw_unattended(path))  # active
        self.engine.interrupt('main', self.lease)
        self.assertTrue(_raw_unattended(path))  # stopped, report kept, no receipt
        self.engine.record_owner_approval([], [], EVIDENCE)
        self.assertFalse(_raw_unattended(path))
        for text in ('', '[]', '"x"', '{', '\x00'):
            with self.subTest(text=text):
                path.write_text(text)
                self.assertTrue(_raw_unattended(path))
        path.write_text(json.dumps({'autonomy': None}))
        self.assertFalse(_raw_unattended(path))
        path.write_text(json.dumps({'autonomy': {'active': False}}))
        self.assertFalse(_raw_unattended(path))  # no report was kept

    def test_disarm_and_new_run_from_a_tool_call_denied_while_locked(self):
        self.stop()
        for command in ('python3 orchestra.py autonomy disarm', 'python3 orchestra.py start --size tiny --new-run',
                        'sh -c "python3 orchestra.py start --new-run"'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), 'deny')
        self.assertIsNone(self.hook('python3 orchestra.py autonomy status'))
        self.assertIsNone(self.hook('python3 orchestra.py start --size tiny'))
        self.assertEqual(self.raw()['autonomy']['active'], False)
        self.assertIn('report', self.raw()['autonomy'])  # nothing ran

    def test_disarm_from_a_tool_call_denied_while_active(self):
        self.arm()
        self.assertEqual(self.hook('python3 orchestra.py autonomy disarm'), 'deny')
        self.assertIn(LEDGER_LOCKED, self.hook_reason('python3 orchestra.py autonomy disarm'))

    def test_softened_push_all_and_tags_stay_denied(self):
        """B1: normal relaxes `--all` and `--tags`, but the stopped run is never on the normal column."""
        self.stop()
        self.assertFalse((self.state / 'policy.json').exists())  # the main() path resolves the mode: normal
        self.assertIsNone(self.hook('git branch -f main feat'))  # the classifier allows it; the push after it must fail
        for command in ('git push --all origin', 'git push --tags origin', 'git push origin :topic', 'git stash',
                        'git add -A', 'git commit --amend'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), 'deny')
        self.engine.record_owner_approval([], [], EVIDENCE)  # the lock ends: normal again, a push-all only warns
        code, output = self.call('git push --all origin')
        self.assertNotIn('permissionDecision', output.get('hookSpecificOutput', {}))

    def test_new_run_denied_from_tool_call_while_active_or_unattended(self):
        """B2: the run cannot clear its own lock with `interrupt` then `start --new-run`, with the mod live or not."""
        mods = self.root / 'xdg' / 'orchestra' / 'mods'
        mods.mkdir(parents=True)
        (mods / 's1.json').write_text(json.dumps({'session_id': 's1', 'heartbeat_ms': int(time.time() * 1000),
                                                  'plugin_version': '2.0.0', 'rules_sha256': guard_digest()}))
        command = 'python3 orchestra.py --repo . start --size tiny --new-run'
        self.assertIsNone(self.hook(command, session='s1'))  # no lock yet: ordinary use stays easy
        self.arm()
        for live in (None, 's1'):
            with self.subTest(state='active', mod_live=bool(live)):
                self.assertEqual(self.hook(command, session=live), 'deny')
        self.engine.interrupt('main', self.lease)
        for live in (None, 's1'):
            with self.subTest(state='unattended', mod_live=bool(live)):
                self.assertEqual(self.hook(command, session=live), 'deny')
        with mock.patch.object(hooks_module, 'handle_event', wraps=handle_event) as decide:
            self.hook(command, session='s1')
            self.assertEqual(decide.call_count, 1)  # the live mod did not skip Python
        self.engine.record_owner_approval([], [], EVIDENCE)
        self.assertIsNone(self.hook(command, session='s1'))

    def test_rearmed_run_with_old_receipt_is_locked(self):
        """B3: arming again moves the old receipt aside, so the next stop is locked again."""
        self.arm()
        self.engine.disarm_autonomy()
        self.engine.record_owner_approval([], [], EVIDENCE)
        self.assertIsNone(self.hook('git push origin main'))  # approved
        self.arm()  # real engine arm after a receipt
        self.assertNotIn('approval', self.raw())
        self.assertEqual(self.hook('git push origin main'), 'deny')  # active again
        self.engine.disarm_autonomy()  # the second stop keeps a new report
        self.assertEqual(self.hook('git push origin main'), 'deny')  # locked: the old receipt does not count
        self.assertTrue(_raw_unattended(self.engine.state_path))

    def test_settings_edit_denied_while_unattended_through_main_with_a_live_mod(self):
        """C5 X4: an edit the mod would skip still reaches Python, which knows the run is locked."""
        mods = self.root / 'xdg' / 'orchestra' / 'mods'
        mods.mkdir(parents=True)
        (mods / 's1.json').write_text(json.dumps({'session_id': 's1', 'heartbeat_ms': int(time.time() * 1000),
                                                  'plugin_version': '2.0.0', 'rules_sha256': guard_digest()}))
        target = self.repo / '.claude' / 'settings.local.json'
        data = {'file_path': str(target), 'old_string': 'a', 'new_string': 'b'}
        code, output = self.call('', tool='Edit', data=data, session='s1')
        self.assertEqual(output, {})  # no run: the live mod's skip stands
        self.stop()
        for tool in ('Edit', 'Write', 'MultiEdit'):
            with self.subTest(tool=tool):
                code, output = self.call('', tool=tool, data=data, session='s1')
                self.assertEqual(output['hookSpecificOutput']['permissionDecision'], 'deny')
        self.engine.record_owner_approval([], [], EVIDENCE)
        self.assertEqual(self.call('', tool='Edit', data=data, session='s1')[1], {})


class PlaneTest(PlaneFixture):
    """Section 3: what the run may do while autonomy is active."""

    def test_n7_rm_in_the_main_checkout_is_denied_and_in_a_linked_worktree_allowed(self):
        self.arm()
        self.assertEqual(self.hook('rm -rf ./build'), 'deny')
        self.assertIn('park', self.hook_reason('rm -rf ./build'))
        self.assertIsNone(self.hook('rm -rf ./build', cwd=self.wt))
        self.assertIsNone(self.hook('rm file.txt', cwd=self.wt))
        self.assertIsNone(self.hook('find build -delete', cwd=self.wt))
        self.assertEqual(self.hook('find build -delete'), 'deny')
        for command in ('rm .git/config', 'rm -rf ..', 'rm -rf .', 'rm -rf ../repo', 'rm -rf /', 'rmdir empty'):
            with self.subTest(command=command, where='main'):
                self.assertEqual(self.hook(command), 'deny')
        for command in ('rm .git', 'rm -rf .git/objects', 'rm -rf ..', 'rm -rf .', 'rm -rf ../repo/f.txt', 'rm -rf ../wt',
                        'rm -rf /', 'rm -rf build ../repo/a', 'rm -rf -- -x ..', 'find .. -delete', 'rmdir empty'):
            with self.subTest(command=command, where='linked'):
                self.assertEqual(self.hook(command, cwd=self.wt), 'deny')

    def test_rm_is_judged_once_for_the_whole_command(self):
        self.arm()
        for command in ('rm -rf build && rm -rf ..', 'cd .. && rm -rf build', 'rm -rf build; git push origin main',
                        'echo x | rm build', 'rm "build dir"', 'rm -rf build > out'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command, cwd=self.wt), 'deny')

    def test_rm_operands_with_variable_tilde_glob_backtick_denied(self):
        inner = self.repo / 'inner'
        self.git('worktree', 'add', '-q', str(inner), '-b', 'inner-branch')  # a linked worktree inside the main checkout
        self.arm()
        for command in ('rm -rf $DIR/x', 'rm -rf ${DIR}/x', 'rm ~/x', 'rm -rf ~', 'rm -rf `echo x`', 'rm -rf $(echo x)',
                        'rm -rf *', 'rm -rf build*', 'rm -rf inner*', 'rm -rf in*er/x', 'rm -rf inner/../*',
                        'rm -rf inner/.*', 'rm -rf inner/.git*', 'rm -rf inner/.g[i]t', 'rm -rf inner',
                        'rm -rf ../wt/*', 'rm -rf .*'):
            with self.subTest(command=command, where='main'):
                self.assertEqual(self.hook(command), 'deny')
        for command in ('rm -rf inner/*', 'rm -rf inner/build', 'rm -rf inner/src/*.o', 'rm -rf inner/a?'):
            with self.subTest(command=command, where='main'):
                self.assertIsNone(self.hook(command))  # a literal worktree prefix before the glob
        for command in ('rm -rf *', 'rm -rf build*', 'rm -rf *.o', 'rm -rf .git*', 'rm -rf ../*', 'rm -rf $DIR/x', 'rm ~/x'):
            with self.subTest(command=command, where='linked'):
                expected = None if command in ('rm -rf *', 'rm -rf build*', 'rm -rf *.o') else 'deny'
                self.assertEqual(self.hook(command, cwd=self.wt), expected)

    def add_origin_branches(self):
        """Run branches `feat/a` (also on `stack`) and `feat/b` (only its own counterpart), made after the arm."""
        self.arm()
        self.branch('feat/a', push=('feat/a', 'stack'))
        self.branch('feat/b', push=('feat/b',))

    def test_branch_delete_of_a_run_branch_covered_by_another_remote_branch(self):
        self.add_origin_branches()
        self.assertEqual(self.hook('git branch -D feat/b'), 'deny')  # its own counterpart does not count
        self.assertIsNone(self.hook('git branch -D feat/a'))  # reachable from origin/stack
        self.assertEqual(self.hook('git branch -d feat/b'), 'deny')
        self.branch('feat/c', push=('feat/c', 'stack2'))
        self.assertIsNone(self.hook('git branch -d feat/c'))

    def test_remote_delete_of_a_covered_run_branch(self):
        self.add_origin_branches()
        self.assertIsNone(self.hook('git push origin --delete feat/a'))
        self.assertEqual(self.hook('git push origin --delete feat/b'), 'deny')
        self.assertIsNone(self.hook('git push origin --delete stack'))  # origin/feat/a holds the same tip
        self.assertEqual(self.hook('git push origin --delete ' + self.default_branch), 'deny')

    def test_unpushed_or_unknown_branches_stay_under_the_merged_rule(self):
        self.branch('old')
        self.arm()
        self.branch('feat/local')
        self.assertEqual(self.hook('git branch -D feat/local'), 'deny')  # nothing lives on a remote
        self.assertEqual(self.hook('git branch -D work'), 'deny')  # checked out
        self.assertEqual(self.hook('git branch -D old'), 'deny')  # existed at arm and holds a commit of its own
        self.assertEqual(self.hook('git push origin --delete ' + self.default_branch), 'deny')

    def test_the_plane_only_relaxes_under_autonomy(self):
        self.arm()
        self.branch('feat/a', push=('feat/a', 'stack'))
        self.engine.disarm_autonomy()
        self.assertEqual(self.hook('git branch -D feat/a'), 'deny')  # the protect-free column keeps -D unmerged denied
        self.assertEqual(self.decide('git branch -D feat/a', mode='normal', unattended=True).output['hookSpecificOutput']
                         ['permissionDecision'], 'deny')

    def test_branch_with_an_open_pull_request_is_not_deletable_until_merged(self):
        self.arm()
        self.open_pr(5)
        self.git('push', '-q', 'origin', 'feat/5:refs/heads/stack')
        self.assertEqual(self.hook('git branch -D feat/5'), 'deny')  # head of a recorded open pull request
        self.assertEqual(self.hook('git push origin --delete stack'), 'deny')
        self.git('push', '-q', 'origin', 'feat/5:refs/heads/' + self.default_branch)  # merged into the default
        self.git('fetch', '-q', 'origin')
        self.assertIsNone(self.hook('git branch -D feat/5'))

    def test_the_base_of_a_recorded_pull_request_is_not_deletable_while_it_is_open(self):
        self.arm()
        self.open_pr(5)
        self.open_pr(6, base='feat/5')
        self.git('push', '-q', 'origin', 'feat/6:refs/heads/stack')
        self.assertEqual(self.hook('git branch -D feat/5'), 'deny')

    def test_branch_present_on_a_remote_at_arm_is_not_a_run_branch(self):
        self.branch('shared', push=('shared',))
        self.git('branch', '-D', 'shared')
        self.git('fetch', '-q', 'origin')
        self.arm()
        self.assertIn('shared', self.raw()['autonomy']['remote_branches_at_arm'])
        self.git('branch', 'shared', 'origin/shared')  # a local copy made after the arm
        self.git('push', '-q', 'origin', 'shared:refs/heads/stack')
        self.assertNotIn('shared', self.raw()['autonomy']['local_branches_at_arm'])
        self.assertEqual(self.hook('git branch -D shared'), 'deny')
        self.branch('fresh', push=('fresh', 'stack2'))
        self.assertIsNone(self.hook('git branch -D fresh'))  # the same shape for a branch the run made

    def test_worktree_remove_uses_the_same_evidence(self):
        self.arm()
        self.branch('feat/a', push=('feat/a', 'stack'))
        made = self.root / 'made'
        self.git('worktree', 'add', '-q', str(made), 'feat/a')
        self.assertIsNone(self.hook('git worktree remove ../made'))
        self.assertEqual(self.hook('git worktree remove ../repo'), 'deny')  # the main worktree

    def test_n6_scheduler_tools_denied_while_active_and_while_unattended(self):
        self.arm()
        for tool in SCHEDULERS:
            payload = {'tool_name': tool, 'tool_input': {'prompt': 'go'}, 'cwd': str(self.repo)}
            with self.subTest(tool=tool):
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', engine=self.engine)), 'deny')
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', unattended=True)), 'deny')
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', armed=True, autonomy=True)), 'deny')
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal')), 'allow')
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='protect')), 'allow')
        send = {'tool_name': 'SendMessage', 'tool_input': {'to': 'a', 'message': 'hi'}, 'cwd': str(self.repo)}
        self.assertEqual(verdict(handle_event('PreToolUse', send, mode='normal', engine=self.engine)), 'allow')
        self.assertEqual(verdict(handle_event('PreToolUse', send, mode='normal', unattended=True)), 'allow')

    def test_scheduler_tools_denied_through_main_once_the_run_stops(self):
        self.stop()
        for tool in SCHEDULERS:
            with self.subTest(tool=tool):
                code, output = self.call('', tool=tool, data={'prompt': 'go'})
                self.assertEqual(output['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(self.call('', tool='SendMessage', data={'to': 'a', 'message': 'hi'})[1], {})

    def test_settings_edit_denied_while_unattended(self):
        self.stop()
        for name in ('settings.json', 'settings.local.json'):
            with self.subTest(name=name):
                code, output = self.call('', tool='Write', data={'file_path': str(self.repo / '.claude' / name), 'content': '{}'})
                self.assertEqual(output['hookSpecificOutput']['permissionDecision'], 'deny')
        code, output = self.call('', tool='Write', data={'file_path': str(self.repo / '.claude' / 'notes.md'), 'content': 'x'})
        self.assertEqual(output, {})

    def test_gh_api_non_get_outside_allow_list_denied_under_autonomy_and_unattended(self):
        self.arm()
        denied = ('gh api -X DELETE repos/o/r', 'gh api -X PATCH repos/o/r -f default_branch=x',
                  'gh api -X DELETE repos/o/r/rulesets/1')
        allowed = ('gh api -X POST repos/o/r/pulls -f title=t -f head=h -f base=b',
                   'gh api -X POST repos/o/r/issues/3/comments -f body=hi',
                   'gh api -X POST repos/o/r/pulls/3/reviews -f event=COMMENT',
                   'gh api -X POST repos/o/r/pulls/3/comments -f body=hi')
        for command in denied:
            with self.subTest(command=command):
                self.assertEqual(verdict(self.decide(command, mode='normal', engine=self.engine)), 'deny')
                self.assertEqual(verdict(self.decide(command, mode='normal', unattended=True)), 'deny')
                self.assertEqual(verdict(self.decide(command, mode='normal')), 'allow')
        for command in allowed:
            with self.subTest(command=command):
                self.assertEqual(verdict(self.decide(command, mode='normal', engine=self.engine)), 'allow')
                self.assertEqual(verdict(self.decide(command, mode='normal', unattended=True)), 'allow')
                self.assertEqual(verdict(self.decide(command, mode='normal')), 'allow')

    def test_gh_pr_merge_denied_under_autonomy_and_unattended_without_guard(self):
        """M7: the plane has no gh call, so every merge is denied; only the merge guard (T2b2) can allow one."""
        self.arm()
        for command in ('gh pr merge 3', 'gh pr merge 3 --merge --delete-branch --match-head-commit abc',
                        'gh api -X PUT repos/o/r/pulls/3/merge'):
            with self.subTest(command=command):
                self.assertEqual(verdict(self.decide(command, mode='normal', engine=self.engine)), 'deny')
                self.assertEqual(verdict(self.decide(command, mode='normal', unattended=True)), 'deny')
                self.assertEqual(verdict(self.decide(command, mode='normal')), 'allow')
        self.assertEqual(self.calls(), [])  # no gh call anywhere in the plane

    def test_the_run_may_still_open_and_review_pull_requests(self):
        self.arm()
        for command in ('gh pr create --fill', 'gh pr comment 3 --body x', 'gh pr review 3 --approve', 'gh pr ready 3',
                        'gh pr close 3', 'gh pr reopen 3', 'gh pr view 3', 'gh pr list', 'gh pr checks 3', 'gh pr diff 3',
                        'git merge topic', 'git tag v1'):
            with self.subTest(command=command):
                self.assertIsNone(self.hook(command))


if __name__ == '__main__':
    unittest.main()
