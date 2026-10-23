"""Guard modes (T2a1): normal relaxes what the classifier denies with `soften`; protect keeps today's verdicts."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_merge_guard as tm
from orchestra_core import hooks as hooks_module
from orchestra_core.guards import guard_digest
from orchestra_core.hooks import LEDGER_LOCKED, _guard_mode, _soften_call, handle_event, main


def git(cwd, *args):
    return subprocess.check_output(['git', '-C', str(cwd), *args], stderr=subprocess.PIPE, text=True).strip()


def verdict(result):
    """deny, ask, warn (context only) or allow."""
    hso = result.output.get('hookSpecificOutput', {})
    if 'permissionDecision' in hso:
        return hso['permissionDecision']
    return 'warn' if hso.get('additionalContext') else 'allow'


class FakeEngine:
    """The slice of Engine that handle_event reads."""

    def __init__(self, autonomy=False, gates=(), permit=False):
        self.autonomy, self.gates, self.permit = autonomy, list(gates), permit
        self.policy = {}

    def autonomy_active(self):
        return self.autonomy

    def status(self):
        return {'session': {'active': True}, 'autonomy': {}}

    def current_gate_ids(self):
        return self.gates

    def check_release(self, remote, target, argv=None):
        return self.permit


class RepoCase(unittest.TestCase):
    """A repository with an origin whose default branch is main."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init', '-q', '-b', 'main')
        git(self.repo, 'config', 'user.name', 'T')
        git(self.repo, 'config', 'user.email', 't@example.invalid')
        (self.repo / 'f.txt').write_text('x\n')
        git(self.repo, 'add', 'f.txt')
        git(self.repo, 'commit', '-q', '-m', 'f')
        git(self.repo, 'remote', 'add', 'origin', str(self.root / 'origin.git'))
        git(self.repo, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
        git(self.repo, 'symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main')

    def bash(self, command, mode, cwd=None, **kw):
        payload = {'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': str(cwd or self.repo)}
        return handle_event('PreToolUse', payload, mode=mode, **kw)


class GuardMatrixTest(RepoCase):
    """One subTest per row of the plan matrix whose answer depends on the mode, and the unchanged rows beside them."""

    def rows(self, command, expected, **kw):
        for mode, want in expected.items():
            with self.subTest(command=command, mode=mode):
                self.assertEqual(verdict(self.bash(command, mode, **kw)), want)

    def test_rows_4_10_11_12_soften_in_normal_and_deny_in_protect(self):
        self.rows('git stash', {'normal': 'warn', 'protect': 'deny'})  # row 4
        self.rows('git add -A', {'normal': 'allow', 'protect': 'deny'})  # row 10
        self.rows('git add .', {'normal': 'allow', 'protect': 'deny'})
        self.rows('git commit -a -m x', {'normal': 'allow', 'protect': 'deny'})  # row 11
        self.rows('git commit --amend -m x', {'normal': 'warn', 'protect': 'deny'})  # row 12

    def test_rows_14_15_soft_pushes_warn_in_normal(self):
        self.rows('git push --tags origin', {'normal': 'warn', 'protect': 'deny'})  # row 14
        self.rows('git push --all origin', {'normal': 'warn', 'protect': 'deny'})
        self.rows('git push origin :topic', {'normal': 'warn', 'protect': 'deny'})  # row 15

    def test_hard_denies_do_not_soften(self):
        for command in ('git reset --hard', 'git push --force origin x', 'git push --mirror origin',
                        'git push --prune origin', 'git clean -fd', 'git stash && git reset --hard'):
            self.rows(command, {'normal': 'deny', 'protect': 'deny'})

    def test_row_24_release_multi(self):
        command = 'git push origin x && gh pr create'
        self.rows(command, {'normal': 'allow', 'protect': 'allow'})  # no run
        self.rows(command, {'normal': 'allow', 'protect': 'ask'}, armed=True)
        self.rows(command, {'normal': 'deny', 'protect': 'deny'}, armed=True, autonomy=True)

    def test_rows_27_46_50_n1_release_class(self):
        for command in ('gh pr merge 3', 'git push origin main', 'gh release create v1', 'npm publish'):
            self.rows(command, {'normal': 'allow', 'protect': 'allow'})
            self.rows(command, {'normal': 'allow', 'protect': 'ask'}, armed=True)
            self.rows(command, {'normal': 'deny', 'protect': 'deny'}, armed=True, autonomy=True)

    def test_row_50_release_with_a_loaded_engine_and_no_permit(self):
        self.rows('git push origin main', {'normal': 'allow', 'protect': 'ask'}, engine=FakeEngine())
        self.rows('git push origin main', {'normal': 'allow', 'protect': 'allow'}, engine=FakeEngine(permit=True))

    def test_row_51_normal_never_asks(self):
        for command in ('git push origin main', 'gh pr merge 3', 'gh workflow run deploy.yml', 'gh pr edit 3 --base main',
                        'git push origin x && gh pr create', 'gh api -X DELETE repos/o/r', 'gh prm 12'):
            with self.subTest(command=command):
                self.assertNotEqual(verdict(self.bash(command, 'normal', armed=True)), 'ask')
                self.assertNotEqual(verdict(self.bash(command, 'normal', engine=FakeEngine())), 'ask')
                self.assertEqual(verdict(self.bash(command, 'protect', armed=True)), 'ask')

    def test_n10_n11_n13_new_release_classes(self):
        for command in ('gh pr edit 3 --base main', 'gh prm 12', 'gh api -X DELETE repos/o/r',
                        'gh api -X PATCH repos/o/r -f default_branch=x'):
            self.rows(command, {'normal': 'allow', 'protect': 'allow'})
            self.rows(command, {'normal': 'allow', 'protect': 'ask'}, armed=True)
            self.rows(command, {'normal': 'deny', 'protect': 'deny'}, armed=True, autonomy=True)
        self.rows('gh alias set x y', {'normal': 'allow', 'protect': 'allow'}, armed=True)  # config boundary
        self.rows('gh alias set x y', {'normal': 'deny', 'protect': 'deny'}, armed=True, autonomy=True)

    def test_row_42_busy_state(self):
        for command in ('git push origin main', 'git merge topic', 'rm -rf build'):
            with self.subTest(command=command):
                if command.startswith(('git push', 'git merge')):
                    self.assertEqual(verdict(self.bash(command, 'protect', busy=True, armed=True)), 'deny')
                    self.assertEqual(verdict(self.bash(command, 'normal', busy=True, armed=True)), 'allow')
                    self.assertEqual(verdict(self.bash(command, 'normal', busy=True, armed=True, autonomy=True)), 'deny')

    def test_rows_44_ledger_switch_stays_locked_in_both_modes(self):
        for mode in ('normal', 'protect'):
            with self.subTest(mode=mode):
                result = self.bash('python3 orchestra.py autonomy disarm', mode, engine=FakeEngine(autonomy=True))
                self.assertEqual(verdict(result), 'deny')
                self.assertIn(LEDGER_LOCKED, result.output['hookSpecificOutput']['permissionDecisionReason'])

    def test_rows_53_59_60_62_branch_deletion_has_no_mode_split(self):
        for mode in ('normal', 'protect'):
            with self.subTest(mode=mode):
                self.assertEqual(verdict(self.bash('git branch -D nope', mode)), 'deny')
                self.assertEqual(verdict(self.bash('git branch -d nope', mode)), 'allow')

    def test_n7_rm_and_n6_scheduler_have_no_mode_split_outside_autonomy(self):
        self.rows('rm -rf build', {'normal': 'allow', 'protect': 'allow'})
        for mode in ('normal', 'protect'):
            payload = {'tool_name': 'CronCreate', 'tool_input': {'prompt': 'go'}, 'cwd': str(self.repo)}
            self.assertEqual(verdict(handle_event('PreToolUse', payload, mode=mode)), 'allow')

    def test_row_31_worker_spawn(self):
        def spawn(mode, *, armed=False, agent_type=None):
            payload = {'tool_name': 'Agent', 'tool_input': {'subagent_type': 'orchestra:builder'}, 'cwd': str(self.repo)}
            if agent_type:
                payload['agent_type'] = agent_type
            with mock.patch.dict(os.environ, {'ORCHESTRA_ROLE': 'builder'}):
                return verdict(handle_event('PreToolUse', payload, mode=mode, armed=armed))
        self.assertEqual(spawn('protect'), 'deny')
        self.assertEqual(spawn('normal'), 'allow')  # no run, caller not an Orchestra agent
        self.assertEqual(spawn('normal', armed=True), 'deny')  # a run is active
        self.assertEqual(spawn('normal', agent_type='orchestra:builder'), 'deny')

    def test_rows_32_33_foreign_agents_warn_in_normal(self):
        sub = {'tool_name': 'Bash', 'tool_input': {'command': 'git status'}, 'cwd': str(self.repo),
               'agent_id': 'a1', 'agent_type': 'general-purpose'}
        agent = {'tool_name': 'Agent', 'tool_input': {'subagent_type': 'general-purpose'}, 'cwd': str(self.repo)}
        for name, payload in (('row 32', sub), ('row 33', agent)):
            with self.subTest(row=name):
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='protect', armed=True)), 'deny')
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', armed=True)), 'warn')
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal')), 'allow')  # no run
                self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', armed=True, autonomy=True)), 'deny')

    def test_row_43_reviewer_suite_rerun_warns_in_normal(self):
        payload = {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -m unittest discover'}, 'cwd': str(self.repo),
                   'agent_id': 'a1', 'agent_type': 'orchestra:code-reviewer'}
        engine = FakeEngine(gates=['g1'])
        result = handle_event('PreToolUse', payload, mode='protect', engine=engine)
        self.assertEqual(verdict(result), 'deny')
        self.assertIn('g1', result.output['hookSpecificOutput']['permissionDecisionReason'])
        result = handle_event('PreToolUse', payload, mode='normal', engine=engine)
        self.assertEqual(verdict(result), 'warn')
        self.assertIn('g1', result.output['hookSpecificOutput']['additionalContext'])
        self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal', engine=FakeEngine())), 'allow')

    def test_row_36_protected_edits_have_no_mode_split(self):
        state = self.root / 'state'
        for mode in ('normal', 'protect'):
            for path, want in ((state / 'state.json', 'deny'), (self.repo / '.claude' / 'hooks.json', 'deny'),
                               (self.repo / '.claude' / 'notes.md', 'allow'), (self.repo / 'f.txt', 'allow')):
                with self.subTest(mode=mode, path=path.name):
                    payload = {'tool_name': 'Write', 'tool_input': {'file_path': str(path)}, 'cwd': str(self.repo)}
                    self.assertEqual(verdict(handle_event('PreToolUse', payload, mode=mode, state_dir=str(state))), want)


class SoftenOutputTest(RepoCase):
    def test_normal_warn_emits_additionalContext_without_permissionDecision(self):
        result = self.bash('git stash', 'normal')
        self.assertEqual(result.exit_code, 0)
        hso = result.output['hookSpecificOutput']
        self.assertEqual(hso['hookEventName'], 'PreToolUse')
        self.assertNotIn('permissionDecision', hso)
        self.assertIn('stash', hso['additionalContext'])
        self.assertTrue(hso['additionalContext'].startswith('Orchestra'))

    def test_protect_still_denies(self):
        result = self.bash('git stash', 'protect')
        self.assertEqual(result.output['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_the_default_mode_is_protect(self):
        payload = {'tool_name': 'Bash', 'tool_input': {'command': 'git stash'}, 'cwd': str(self.repo)}
        self.assertEqual(verdict(handle_event('PreToolUse', payload)), 'deny')

    def test_active_autonomy_keeps_every_softened_deny(self):
        for command in ('git stash', 'git add -A', 'git commit --amend', 'git push --tags origin'):
            with self.subTest(command=command):
                self.assertEqual(verdict(self.bash(command, 'normal', engine=FakeEngine(autonomy=True))), 'deny')
                self.assertEqual(verdict(self.bash(command, 'normal', armed=True, autonomy=True)), 'deny')

    def test_a_command_with_a_hard_deny_beside_a_soft_one_denies(self):
        self.assertEqual(verdict(self.bash('git add -A && git reset --hard', 'normal')), 'deny')

    def test_a_warn_survives_a_later_allow_only(self):
        # An edit-protected path still denies; a warning never hides a deny.
        payload = {'tool_name': 'Bash', 'tool_input': {'command': 'git stash'}, 'cwd': str(self.repo),
                   'agent_id': 'a1', 'agent_type': 'general-purpose'}
        result = handle_event('PreToolUse', payload, mode='normal', armed=True)
        self.assertEqual(verdict(result), 'warn')
        self.assertIn('stash', result.output['hookSpecificOutput']['additionalContext'])


class SoftPushTest(RepoCase):
    def test_softened_push_delete_of_tag_default_or_protected_branch_still_denies(self):
        git(self.repo, 'tag', 'v1.0')
        git(self.repo, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
        for command in ('git push --delete origin v1.0', 'git push origin :v1.0', 'git push origin :refs/tags/v1.0',
                        'git push --delete origin tags/v1.0', 'git push --delete origin main', 'git push origin :main',
                        'git push origin :refs/heads/main', 'git push --delete origin production',
                        'git push --delete origin MAIN', 'git push -d origin gh-pages',
                        'git push origin :topic :main', 'git push --delete origin topic main'):
            with self.subTest(command=command):
                result = self.bash(command, 'normal')
                self.assertEqual(verdict(result), 'deny')
                self.assertIn('Orchestra', result.output['hookSpecificOutput']['permissionDecisionReason'])
        self.assertEqual(verdict(self.bash('git push origin :topic', 'normal')), 'warn')

    def test_a_tag_is_found_by_its_name_alone(self):
        git(self.repo, 'tag', 'release-candidate')
        self.assertEqual(verdict(self.bash('git push origin :release-candidate', 'normal')), 'deny')

    def test_a_compound_command_checks_every_push(self):
        self.assertEqual(verdict(self.bash('git push --tags origin && git push --delete origin main', 'normal')), 'deny')

    def test_softened_push_with_unresolved_default_denies(self):
        git(self.repo, 'symbolic-ref', '--delete', 'refs/remotes/origin/HEAD')
        for command in ('git push --tags origin', 'git push origin :topic', 'git push --all origin'):
            with self.subTest(command=command):
                self.assertEqual(verdict(self.bash(command, 'normal')), 'deny')

    def test_softened_push_without_a_remote_or_cwd_denies(self):
        self.assertEqual(verdict(self.bash('git push --tags', 'normal')), 'deny')
        payload = {'tool_name': 'Bash', 'tool_input': {'command': 'git push --tags origin'}}
        with mock.patch('os.getcwd', side_effect=OSError):
            self.assertEqual(verdict(handle_event('PreToolUse', payload, mode='normal')), 'deny')

    def test_the_armed_default_resolves_when_origin_head_is_missing(self):
        git(self.repo, 'symbolic-ref', '--delete', 'refs/remotes/origin/HEAD')

        class Armed(FakeEngine):
            def status(self):
                return {'session': {'active': True}, 'autonomy': {'remote_defaults': {'origin': 'trunk'}}}
        self.assertEqual(verdict(self.bash('git push origin :trunk', 'normal', engine=Armed())), 'deny')
        self.assertEqual(verdict(self.bash('git push origin :topic', 'normal', engine=Armed())), 'warn')


class WorkflowRunTest(RepoCase):
    """`gh workflow run NAME` is a release; a name outside `release_workflows` with a local file is not one."""

    def workflow(self, name, mode='protect', create=True, state_dir=None, **kw):
        if create:
            (self.repo / '.github' / 'workflows').mkdir(parents=True, exist_ok=True)
            (self.repo / '.github' / 'workflows' / name).write_text('name: x\n')
        return verdict(self.bash('gh workflow run ' + name, mode, state_dir=state_dir, **kw))

    def test_non_release_name_with_local_file_downgrades_to_allow(self):
        self.assertEqual(self.workflow('ci.yml', armed=True), 'allow')  # protect would ask for a release
        self.assertEqual(self.workflow('other', create=False, armed=True), 'ask')  # no such file
        self.assertEqual(self.workflow('ci', create=False, armed=True), 'allow')  # the name is a file stem
        self.assertEqual(self.workflow('ci.yml', mode='normal', armed=True), 'allow')

    def test_release_name_stays_release(self):
        for name in ('release.yml', 'publish-docs.yml', 'deploy.yaml', 'Release.yml'):
            with self.subTest(name=name):
                self.assertEqual(self.workflow(name, armed=True), 'ask')
                self.assertEqual(self.workflow(name, mode='normal', armed=True), 'allow')  # normal never asks

    def test_missing_workflow_file_stays_release(self):
        self.assertEqual(self.workflow('nothing.yml', create=False, armed=True), 'ask')
        self.assertEqual(self.workflow('nothing.yml', create=False, armed=True, autonomy=True), 'deny')

    def test_a_command_with_no_name_stays_release(self):
        self.assertEqual(verdict(self.bash('gh workflow run', 'protect', armed=True)), 'ask')

    def test_autonomy_denies_every_name(self):
        for name in ('ci.yml', 'release.yml'):
            for mode in ('normal', 'protect'):
                with self.subTest(name=name, mode=mode):
                    self.assertEqual(self.workflow(name, mode=mode, armed=True, autonomy=True), 'deny')
                    self.assertEqual(self.workflow(name, mode=mode, engine=FakeEngine(autonomy=True)), 'deny')

    def test_policy_release_workflows_replaces_the_default_globs(self):
        state = self.root / 'state'
        state.mkdir()
        (state / 'policy.json').write_text(json.dumps({'schema_version': 1, 'release_workflows': ['nightly*']}))
        self.assertEqual(self.workflow('nightly.yml', armed=True, state_dir=str(state)), 'ask')
        self.assertEqual(self.workflow('release.yml', armed=True, state_dir=str(state)), 'allow')
        engine = FakeEngine()
        engine.policy = {'release_workflows': ['ci*']}
        self.assertEqual(self.workflow('ci.yml', engine=engine), 'ask')
        self.assertEqual(self.workflow('release.yml', engine=engine), 'allow')

    def test_a_malformed_release_workflows_value_keeps_the_default_globs(self):
        state = self.root / 'state'
        state.mkdir()
        (state / 'policy.json').write_text(json.dumps({'schema_version': 1, 'release_workflows': 'ci*'}))
        self.assertEqual(self.workflow('release.yml', armed=True, state_dir=str(state)), 'ask')

    def test_a_workflow_name_with_a_path_or_glob_is_never_downgraded(self):
        (self.repo / '.github' / 'workflows').mkdir(parents=True)
        (self.repo / '.github' / 'workflows' / 'ci.yml').write_text('name: x\n')
        for name in ('../ci.yml', 'c*', '/etc/passwd', 'ci.yml/../x', '', 'c?.yml'):
            with self.subTest(name=name):
                self.assertFalse(hooks_module._workflow_is_plain(self.repo, name, None))
        self.assertTrue(hooks_module._workflow_is_plain(self.repo, 'ci.yml', None))


class ModeResolutionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def policy(self, text):
        (self.dir / 'policy.json').write_text(text)

    def test_no_policy_file_is_normal(self):
        self.assertEqual(_guard_mode(self.dir), 'normal')
        self.assertEqual(_guard_mode(str(self.dir / 'missing')), 'normal')

    def test_protect(self):
        self.policy(json.dumps({'schema_version': 1, 'guard_mode': 'protect'}))
        self.assertEqual(_guard_mode(self.dir), 'protect')

    def test_normal_and_key_absent_are_normal(self):
        self.policy(json.dumps({'schema_version': 1, 'guard_mode': 'normal'}))
        self.assertEqual(_guard_mode(self.dir), 'normal')
        self.policy(json.dumps({'schema_version': 1, 'worker_stale_seconds': 900}))
        self.assertEqual(_guard_mode(self.dir), 'normal')

    def test_corrupt_file_is_protect(self):
        for text in ('{not json', '', '[]', '"protect"', json.dumps({'guard_mode': 'normal'}),
                     json.dumps({'schema_version': 2, 'guard_mode': 'normal'})):
            with self.subTest(text=text):
                self.policy(text)
                self.assertEqual(_guard_mode(self.dir), 'protect')

    def test_unknown_value_is_protect(self):
        for value in ('strict', 'Normal', '', None, 1, ['normal']):
            with self.subTest(value=value):
                self.policy(json.dumps({'schema_version': 1, 'guard_mode': value}))
                self.assertEqual(_guard_mode(self.dir), 'protect')

    def test_unreadable_file_is_protect(self):
        (self.dir / 'policy.json').mkdir()
        self.assertEqual(_guard_mode(self.dir), 'protect')

    def test_policy_file_is_read_with_no_state_json(self):
        self.policy(json.dumps({'schema_version': 1, 'guard_mode': 'protect'}))
        self.assertFalse((self.dir / 'state.json').exists())
        self.assertEqual(_guard_mode(self.dir), 'protect')

    def test_no_state_dir_is_normal(self):
        self.assertEqual(_guard_mode(None), 'normal')


class MainPathDefaultsTest(RepoCase):
    """The hook entry point resolves the mode from policy.json, which most fixtures do not have."""

    def setUp(self):
        super().setUp()
        self.state = self.root / 'state'
        self.state.mkdir()
        patcher = mock.patch.dict(os.environ, {'ORCHESTRA_STATE_DIR': str(self.state), 'XDG_STATE_HOME': str(self.root / 'xdg')})
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, command, event='PreToolUse'):
        payload = {'cwd': str(self.repo), 'tool_name': 'Bash', 'tool_input': {'command': command}}
        with mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as output, mock.patch('sys.stderr', new_callable=io.StringIO):
            code = main([event])
            return code, json.loads(output.getvalue())

    def test_no_policy_file_main_path_is_normal(self):
        code, output = self.call('git stash')
        self.assertEqual(code, 0)
        self.assertNotIn('permissionDecision', output.get('hookSpecificOutput', {}))
        self.assertIn('additionalContext', output['hookSpecificOutput'])
        self.assertEqual(self.call('git add -A')[1], {})

    def test_protect_policy_main_path_denies(self):
        (self.state / 'policy.json').write_text(json.dumps({'schema_version': 1, 'guard_mode': 'protect'}))
        for command in ('git stash', 'git add -A'):
            with self.subTest(command=command):
                self.assertEqual(self.call(command)[1]['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_corrupt_policy_main_path_denies(self):
        (self.state / 'policy.json').write_text('{oops')
        self.assertEqual(self.call('git stash')[1]['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_policy_is_read_live_on_each_call(self):
        self.assertIn('additionalContext', self.call('git stash')[1]['hookSpecificOutput'])
        (self.state / 'policy.json').write_text(json.dumps({'schema_version': 1, 'guard_mode': 'protect'}))
        self.assertEqual(self.call('git stash')[1]['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_a_run_with_policy_guard_mode_protect_asks_for_a_release(self):
        (self.state / 'policy.json').write_text(json.dumps({'schema_version': 1, 'guard_mode': 'protect'}))
        subprocess.run([sys.executable, str(Path(hooks_module.__file__).resolve().parents[1] / 'orchestra.py'), '--repo',
                        str(self.repo), 'start', '--size', 'medium'], env=os.environ, capture_output=True, text=True, check=True)
        self.assertEqual(self.call('git push origin main')[1]['hookSpecificOutput']['permissionDecision'], 'ask')
        (self.state / 'policy.json').write_text(json.dumps({'schema_version': 1, 'guard_mode': 'normal'}))
        self.assertEqual(self.call('git push origin main')[1], {})

    def test_session_start_and_stop_do_not_need_a_mode(self):
        payload = {'cwd': str(self.repo), 'session_id': 's'}
        with mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(main(['SessionStart']), 0)
            self.assertIn('additionalContext', json.loads(out.getvalue())['hookSpecificOutput'])


class ModDelegationTest(unittest.TestCase):
    """A live mod skips Python for the calls it fully guards; a soften deny is not one of them."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.xdg, self.cwd = root / 'xdg', root / 'cwd'
        (self.xdg / 'orchestra' / 'mods').mkdir(parents=True)
        self.cwd.mkdir()
        data = {'session_id': 's1', 'heartbeat_ms': int(time.time() * 1000), 'plugin_version': '2.0.0',
                'rules_sha256': guard_digest()}
        (self.xdg / 'orchestra' / 'mods' / 's1.json').write_text(json.dumps(data))
        patcher = mock.patch.dict(os.environ, {'XDG_STATE_HOME': str(self.xdg), 'ORCHESTRA_STATE_DIR': str(root / 'state')})
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, command, *args):
        payload = {'cwd': str(self.cwd), 'session_id': 's1', 'tool_name': 'Bash', 'tool_input': {'command': command}}
        with mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as output, mock.patch('sys.stderr', new_callable=io.StringIO):
            code = main(['PreToolUse', '--harness', 'claude', *args])
            return code, json.loads(output.getvalue())

    def test_soften_deny_reaches_python(self):
        for command in ('git stash', 'git add -A', 'git commit --amend', 'git push --tags origin'):
            with self.subTest(command=command):
                self.assertTrue(_soften_call({'tool_name': 'Bash', 'tool_input': {'command': command}}))
                with mock.patch.object(hooks_module, 'handle_event', wraps=handle_event) as decide:
                    self.call(command)
                    self.assertEqual(decide.call_count, 1)

    def test_hard_deny_does_not(self):
        for command in ('git reset --hard', 'git push --force origin x', 'git status', 'git add src/a.py'):
            with self.subTest(command=command):
                self.assertFalse(_soften_call({'tool_name': 'Bash', 'tool_input': {'command': command}}))
                with mock.patch.object(hooks_module, 'handle_event', wraps=handle_event) as decide:
                    self.assertEqual(self.call(command), (0, {}))
                    self.assertEqual(decide.call_count, 0)

    def test_soften_call_is_false_for_other_tools_and_bad_payloads(self):
        for payload in ({'tool_name': 'Edit', 'tool_input': {'file_path': 'x'}}, {'tool_name': 'Bash'}, {'tool_name': 3},
                        {'tool_name': 'Bash', 'tool_input': {'command': 4}}, {}):
            with self.subTest(payload=payload):
                self.assertFalse(_soften_call(payload))

    def test_soften_call_is_true_when_the_command_cannot_be_classified(self):
        with mock.patch.object(hooks_module, 'classify_command', side_effect=RuntimeError('boom')):
            self.assertTrue(_soften_call({'tool_name': 'Bash', 'tool_input': {'command': 'git stash'}}))

    def test_soften_deny_from_the_mod_is_decided_by_the_resolved_mode(self):
        code, output = self.call('git stash', '--from-mod')
        self.assertEqual(code, 0)
        self.assertNotIn('permissionDecision', output.get('hookSpecificOutput', {}))
        (Path(os.environ['ORCHESTRA_STATE_DIR'])).mkdir()
        (Path(os.environ['ORCHESTRA_STATE_DIR']) / 'policy.json').write_text(json.dumps({'schema_version': 1, 'guard_mode': 'protect'}))
        code, output = self.call('git stash', '--from-mod')
        self.assertEqual(output['hookSpecificOutput']['permissionDecision'], 'deny')


class AutonomyThroughMainTest(RepoCase):
    """[C5 m2] With autonomy active a softened deny stays a deny, resolved through main() with no policy.json."""

    def test_softened_push_all_denied_under_autonomy_through_main(self):
        from orchestra_core.engine import AUTONOMY_FIXED, Engine
        from orchestra_core.paths import state_location
        env = {'XDG_STATE_HOME': str(self.root / 'xdg')}
        with mock.patch.dict(os.environ, env):
            os.environ.pop('ORCHESTRA_STATE_DIR', None)
            bare = self.root / 'bare.git'
            git(self.root, 'init', '-q', '--bare', '-b', 'main', str(bare))
            git(self.repo, 'remote', 'set-url', 'origin', str(bare))
            git(self.repo, 'push', '-q', 'origin', 'HEAD:refs/heads/main')
            git(self.repo, 'fetch', '-q', 'origin')
            git(self.repo, 'switch', '-q', '-c', 'work')
            state = state_location(self.repo)
            engine = Engine(state, self.repo)
            engine.open_session('main')
            when = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time() + 3600))
            text = ['goal: g', 'max_passes: 3', 'max_stalls: 2', 'deadline: ' + when, '', '## Completion checks', '',
                    'never: ' + sys.executable + ' -c "import sys; sys.exit(1)"', '', '## Approval boundaries', '', *AUTONOMY_FIXED]
            (state / 'autonomy.md').write_text('\n'.join(text) + '\n')
            engine.arm_autonomy()
            self.assertTrue(engine.autonomy_active())
            self.assertFalse((state / 'policy.json').exists())
            for command in ('git push --all origin', 'git push --tags origin', 'git stash', 'git add -A',
                            'git commit --amend', 'git push --delete origin topic'):
                with self.subTest(command=command):
                    payload = {'cwd': str(self.repo), 'tool_name': 'Bash', 'tool_input': {'command': command}}
                    with mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                            mock.patch('sys.stdout', new_callable=io.StringIO) as out, mock.patch('sys.stderr', new_callable=io.StringIO):
                        main(['PreToolUse'])
                        self.assertEqual(json.loads(out.getvalue())['hookSpecificOutput']['permissionDecision'], 'deny')


class SoftenedCompoundTest(tm.MergeFixture):
    """R4: normal relaxes only the softened item of a compound command; every other item keeps its own verdict."""

    def setUp(self):
        super().setUp()
        self.git('branch', '-m', self.default_branch, 'main')
        self.default_branch = 'main'
        self.git('remote', 'add', 'origin', str(self.root / 'origin.git'))
        self.git('update-ref', 'refs/remotes/origin/main', 'main')
        self.git('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main')
        self.git('tag', 'v1', 'main')
        self.git('switch', '-qc', 'x')
        (self.repo / 'x.txt').write_text('x')
        self.git('add', 'x.txt')
        self.git('commit', '-qm', 'x')
        self.git('switch', '-q', 'work')
        self.arm()
        self.open_pr(7)
        self.approve([7])

    def verdict(self, command, **kw):
        payload = {'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': str(self.repo)}
        return verdict(handle_event('PreToolUse', payload, mode='normal', **kw))

    def test_softened_item_does_not_hide_other_items(self):
        for item, kw in (('git push origin --delete main', {}), ('git push origin :main', {}), ('git push origin :v1', {}),
                         ('git branch -D x', {}), ('gh pr merge 7 --admin', {'state_dir': str(self.state)})):
            with self.subTest(command=item):
                self.assertEqual(self.verdict(item, **kw), 'deny')
                self.assertEqual(self.verdict('git add -A && ' + item, **kw), 'deny')
        with self.subTest(command='git add -A && git status'):
            self.assertEqual(self.verdict('git add -A && git status'), 'allow')
            self.assertEqual(self.verdict('git stash && git status'), 'warn')

    def test_comment_and_ansi_quote_do_not_hide_items(self):
        state = {'state_dir': str(self.state)}
        for command, kw in (("git add -A # it's\ngit push origin --delete main # it's", {}),
                            ("git add -A # it's\ngh pr merge 7 --admin # it's", state),
                            ("echo $'\\''; git add -A; git push origin --delete main # '", {}),
                            ("echo $'\\''; git add -A; gh pr merge 7 --admin # '", state)):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(command, **kw), 'deny')


if __name__ == '__main__':
    unittest.main()
