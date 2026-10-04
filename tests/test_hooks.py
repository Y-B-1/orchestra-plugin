import hashlib
import json
import io
import shutil
import time
import types
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
from orchestra_core.guards import classify_command, RULES, RULES_PATH
from orchestra_core.hooks import handle_event, main

PLUGIN = Path(__file__).resolve().parents[1] / 'plugins/orchestra'
CLI = PLUGIN / 'scripts/orchestra.py'
RUN_HOOK = PLUGIN / 'scripts/run-hook.sh'

# Command lists shared with tests/test_guard_corpus.py, which requires each one in the corpus.
DENY_COMMANDS = [
    'git reset --hard', 'git clean -fd', 'git branch -D topic',
    'git checkout -- .', 'git restore .', 'git stash push',
    'git add -A', 'git add .', 'git add -u src', 'git commit -am done',
    'exec env X=1 git -C "a b" -c color.ui=never reset --hard',
    'true && git clean -f', "sh -c 'git reset --hard'", 'git push --force origin main', 'git clean -f -e "--dry-run"',
    '2>/dev/null sudo -n git reset --hard',
    '> /dev/null nice -n 5 git reset --hard',
    '2>&1 command -p git reset --hard',
    'sudo -n git reset --hard', "env --split-string='git reset --hard'",
    "env -S 'git reset --hard'", "bash -s -c 'git reset --hard'", "bash --norc -c 'git reset --hard'",
    "bash -O extglob -lc 'git reset --hard'",
    'nice -n 5 git reset --hard', 'timeout -s TERM 5 git reset --hard',
    'time git reset --hard', 'time -p git reset --hard',
    "builtin eval 'git reset --hard'", 'command -p git reset --hard', 'builtin command git reset --hard',
    "eval 'git reset --hard'", 'git --exec-path /tmp reset --hard',
    'git reset --hard=HEAD', 'cd other && git push origin main', 'git branch --delete --force topic',
]
DENY_GROUPED = ['sudo -nu root git reset --hard',
                'sudo -nuroot git reset --hard',
                'sudo -nEu root git reset --hard',
                'env -iS "git reset --hard"',
                'env -iS"git reset --hard"',
                'env -iugone git reset --hard']
ALLOW_GROUPED = ['sudo -nu root git commit -m "-a"',
                 'env -iS "echo git reset --hard"',
                 "echo 'env -iS git reset --hard'"]
ALLOW_SEMANTIC = ['git add src/a.py', 'git commit -m "--all --dry-run"',
                  'echo "git reset --hard"', "bash --norc -c 'echo safe'",
                  "sudo -n git commit -m '-a'", "bash -c 'git commit -m \"-a\"'", 'git log --oneline',
                  'git clean --dry-run', 'git push --dry-run origin main',
                  'git checkout feature', 'git add -- -A', 'echo ";"', 'wrangler dev']
DENY_SEMANTIC = ['git reset --hard "--dry-run"']
RELEASE_COMMANDS = ['git push origin HEAD:main', 'gh pr merge 3',
                    'az repos pr update --id 4 --status completed',
                    'npm publish', 'vercel --prod', 'az deployment group create',
                    'git push -o "--dry-run" origin main', 'git push -o "--force" origin main']
DENY_PUSH_DESTINATION = ['git push origin main side', 'git push --all origin',
                         'git push --tags origin', 'git push --delete origin main',
                         'git push origin :main', "git push origin 'refs/heads/*:refs/heads/*'",
                         'git push --follow-tags origin main']
DENY_MALFORMED = ["git 'reset"]

# A1 to A7 and A14: each command with its state-independent class (and boundary category).
UNARMED_RELEASES = ['git push origin feat/v2-roles-guard-mods', 'git push origin v2.0.0',
                    'gh pr merge 12 --squash --delete-branch',
                    'gh release create v2.0.0 dist/a.tgz --verify-tag --notes-file notes.md',
                    'npm publish', 'pnpm publish', 'vercel --prod', 'az deployment group create --name x']
MULTI_RELEASES = ['git push origin x && gh pr create', 'git push origin a && git push origin b',
                  'git tag v2.0.0 && git push origin v2.0.0', 'cd sub && git push origin x',
                  'gh pr merge 3 --squash; echo done']
STASH_ALLOWED = ['git stash list', 'git stash show', 'git stash show -p stash@{1}', 'git stash show --stat']
STASH_DENIED = ['git stash', 'git stash push', 'git stash pop', 'git stash apply', 'git stash drop',
                'git stash clear', 'git stash save wip', 'git stash branch topic', 'git stash create',
                'git stash store abc']
RESTORE_ALLOWED = ['git restore --staged .', 'git restore -S .', 'git restore --staged src/a.py',
                   'git restore --staged :/']
RESTORE_DENIED = ['git restore --staged --worktree .', 'git restore -SW .', 'git restore -W .',
                  'git restore --worktree .', 'git restore .']
SWITCH_DENIED = ['git switch -f main', 'git switch --force main', 'git switch --discard-changes main',
                 'git switch -c topic -f']
AZ_ALLOWED = ['az deployment group show --name x -g g', 'az deployment group list -g g',
              'az deployment group what-if --name x -g g', 'az group list']
BOUNDARY_DELETE = ['rm -rf build', 'rm file.txt', 'rmdir empty', 'unlink link', 'find . -name "*.o" -delete',
                   'git rm src/a.py', 'git branch -d topic', 'git branch --delete topic', 'git tag -d v1',
                   'git tag --delete v1', 'git worktree remove ../wt', 'git worktree prune',
                   'gh repo delete owner/name --yes', 'gh release delete v1', 'sudo rm -r x',
                   'git -C other rm a.py']
BOUNDARY_MERGE = ['git merge topic', 'git pull', 'git pull --rebase origin main', 'git rebase main',
                  'git cherry-pick abc123']
HEREDOC_DENIED = ["bash <<'EOF'\ngit reset --hard\nEOF",
                  'sh <<EOF\ngit reset --hard\nEOF',
                  "sudo bash <<'EOF'\ngit clean -f\nEOF",
                  "env X=1 sh <<-EOF\n\tgit reset --hard\n\tEOF",
                  'cat <<EOF && git reset --hard\nbody\nEOF',
                  'cat <<EOF\nbody\nEOF\ngit reset --hard',
                  'cat <<EOF\nnever ends']
HEREDOC_ALLOWED = ["cat <<'EOF'\nit's fine\nEOF",
                   'cat <<EOF\ngit reset --hard\nEOF',
                   "git commit -F - <<'EOF'\nmessage with a quote's apostrophe\nEOF",
                   "cat <<-EOF\n\tit's tabbed\n\tEOF\ngit status",
                   "bash -c 'cat' <<EOF\ngit reset --hard\nEOF",
                   'cat <<< "git reset --hard"',
                   'echo $((1 << 2))']
LINKED_WORKTREE_COMMANDS = {'git push origin side': 'release', 'git -C ../linked push origin side': 'release',
                            'git push origin side && git status': 'release-multi'}


def decision_of(result):
    return result.output.get('hookSpecificOutput', {}).get('permissionDecision')


class GuardsTest(unittest.TestCase):
    def test_destructive_and_wholesale(self):
        for command in DENY_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).action, 'deny')

    def test_grouped_wrapper_options(self):
        for command in DENY_GROUPED:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).action, 'deny')
        for command in ALLOW_GROUPED:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).action, 'allow')

    def test_push_source_metadata(self):
        for refspec,source,target in [('main','main','main'), ('HEAD:main','HEAD','main'),
                                      ('topic:refs/heads/main','topic','main'),
                                      ('HEAD~1:main','HEAD~1','main')]:
            with self.subTest(refspec=refspec):
                decision=classify_command('git push origin '+refspec)
                self.assertEqual((decision.source,decision.target),(source,target))
        self.assertEqual(classify_command('sudo -nu root git push origin HEAD:main').source,'HEAD')
        self.assertIsNone(classify_command('git push origin').source)
        self.assertIsNone(classify_command('git -C elsewhere push origin HEAD:main').source)
        self.assertIsNone(classify_command('echo "git push origin HEAD:main"').source)
        self.assertEqual(classify_command('git push origin HEAD:main:other').action,'deny')

    def test_semantic_arguments(self):
        for command in ALLOW_SEMANTIC:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).action, 'allow')
        for command in DENY_SEMANTIC:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).action, 'deny')

    def test_release(self):
        for command in RELEASE_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).action, 'release')
        decision = classify_command('git push origin HEAD:main')
        self.assertEqual((decision.remote, decision.target), ('origin', 'main'))
        dry_run = classify_command('git push --dry-run origin main')
        self.assertEqual((dry_run.action, dry_run.category, dry_run.remote, dry_run.target),
                         ('allow', 'gitpush', 'origin', 'main'))
        self.assertEqual(classify_command('env --chdir=other git push origin main').argv[0], 'env')
        self.assertEqual(classify_command("sh -c 'git push origin main'").argv[0], 'sh')

    def test_push_requires_one_destination(self):
        for command in DENY_PUSH_DESTINATION:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).action, 'deny')

    def test_malformed(self):
        for command in DENY_MALFORMED:
            self.assertEqual(classify_command(command).action, 'deny')

    def test_a1_release_classes_are_state_independent(self):
        for command in UNARMED_RELEASES:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'release')
        for command in MULTI_RELEASES:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'release-multi')
        self.assertEqual(classify_command('git push origin x && git reset --hard').klass, 'deny')
        self.assertEqual(classify_command('git reset --hard && git push origin x').klass, 'deny')

    def test_a2_always_deny_rules_remain(self):
        for command in ['git push --force origin x', 'git push -f origin x', 'git push --mirror origin',
                        'git push origin +x', 'git push --all origin', 'git push --tags origin',
                        'git push --delete origin x', 'git push origin a b', 'git reset --hard',
                        'git clean -f', 'git branch -D x', 'git add -A', 'git commit -a -m x',
                        'git checkout .', 'git checkout -f x', 'git restore .']:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'deny')

    def test_a3_stash_list_and_show(self):
        for command in STASH_ALLOWED:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'allow')
        for command in STASH_DENIED:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'deny')

    def test_a4_restore_staged(self):
        for command in RESTORE_ALLOWED:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'allow')
        for command in RESTORE_DENIED:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'deny')

    def test_a5_heredoc_bodies(self):
        for command in HEREDOC_DENIED:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'deny')
        for command in HEREDOC_ALLOWED:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'allow')
        self.assertEqual(classify_command('bash <<EOF\ngit push origin x\nEOF').klass, 'release')
        self.assertEqual(classify_command('cat <<EOF\nnever ends').category, 'malformed')

    def test_a6_az_release_needs_deployment_create(self):
        for command in AZ_ALLOWED:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'allow')
        self.assertEqual(classify_command('az deployment sub create --name x').klass, 'release')
        self.assertEqual(classify_command('az repos pr update --id 4 --status completed').klass, 'release')
        self.assertEqual(classify_command('az repos pr update --id 4 --status active').klass, 'allow')

    def test_a7_switch_force_denies_like_checkout(self):
        reason = classify_command('git checkout -f main').reason
        for command in SWITCH_DENIED:
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual((decision.klass, decision.reason), ('deny', reason))
        self.assertEqual(classify_command('git switch main').klass, 'allow')
        self.assertEqual(classify_command('git switch -c topic').klass, 'allow')

    def test_a14_boundary_class(self):
        for command in BOUNDARY_DELETE:
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual((decision.klass, decision.boundary, decision.action), ('boundary', 'delete', 'allow'))
        for command in BOUNDARY_MERGE:
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual((decision.klass, decision.boundary), ('boundary', 'merge'))
        for command in ['git branch', 'git branch -a', 'git tag v1', 'git worktree list', 'git log', 'ls rm',
                        'echo rm -rf x', 'gh pr view 3', 'gh release view v1', 'find . -name x']:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'allow')
        self.assertEqual(classify_command('git merge x && rm y').boundary, 'delete')
        self.assertEqual(classify_command('git merge x && git push origin b').klass, 'release-multi')


class HooksTest(unittest.TestCase):
    def pre(self, name, tool_input, cwd=None, **kw):
        payload = {'tool_name': name, 'tool_input': tool_input}
        if cwd is not None:
            payload['cwd'] = str(cwd)
        return handle_event('PreToolUse', payload, **kw)

    def test_native_deny(self):
        for harness in ['codex', 'claude']:
            result = self.pre('Bash', {'command': 'git stash'}, harness=harness)
            self.assertEqual(result.output['hookSpecificOutput']['permissionDecision'], 'deny')
            self.assertEqual(result.exit_code, 0)

    def test_malformed_relevant(self):
        for payload in [None, [], {}, {'tool_name': 'Bash'},
                        {'tool_name': 'Bash', 'tool_input': {'command': 2}}]:
            self.assertEqual(handle_event('PreToolUse', payload).exit_code, 2)
        self.assertEqual(self.pre('read_file', {'path': 'x'}).output, {})

    def test_release_unconfigured(self):
        # A1: with no armed run (engine None) every release class is allowed.
        for command in UNARMED_RELEASES + MULTI_RELEASES:
            with self.subTest(command=command):
                self.assertEqual(self.pre('Bash', {'command': command}).output, {})

    def test_armed_release_needs_a_permit(self):
        engine = mock.Mock()
        engine.check_release.side_effect = ValueError('No current explicit release permit')
        result = self.pre('Bash', {'command': 'git push origin feat/x'}, engine=engine)
        self.assertEqual(decision_of(result), 'deny')
        self.assertIn('No current explicit release permit', result.output['hookSpecificOutput']['permissionDecisionReason'])

    def test_armed_release_multi_denies_even_with_a_permit(self):
        engine = mock.Mock()
        engine.check_release.return_value = {'id': 'permit'}
        for command in MULTI_RELEASES:
            with self.subTest(command=command):
                self.assertEqual(decision_of(self.pre('Bash', {'command': command}, engine=engine)), 'deny')
        engine.check_release.assert_not_called()

    def test_armed_without_loadable_engine_denies_release_not_ordinary_commands(self):
        for command in ['git push origin feat/x', 'gh release create v1 --verify-tag']:
            self.assertEqual(decision_of(self.pre('Bash', {'command': command}, armed=True)), 'deny')
        self.assertEqual(self.pre('Bash', {'command': 'git status'}, armed=True).output, {})

    def test_boundary_class_is_allowed_without_autonomy(self):
        for command in BOUNDARY_DELETE + BOUNDARY_MERGE:
            with self.subTest(command=command):
                self.assertEqual(self.pre('Bash', {'command': command}).output, {})
                self.assertEqual(self.pre('Bash', {'command': command}, armed=True, engine=mock.Mock()).output, {})

    def test_session_context_only(self):
        result = handle_event('SessionStart', {'source': 'startup'})
        context = result.output['hookSpecificOutput']['additionalContext']
        self.assertIn('main coordinator', context)
        worker = handle_event('SessionStart', {'agent_type': 'orchestra-builder'})
        self.assertNotIn('main coordinator', worker.output['hookSpecificOutput']['additionalContext'])
        self.assertEqual(handle_event('SubagentStart', {'agent_type': 'orchestra-builder'})
                         .output['hookSpecificOutput']['hookEventName'], 'SubagentStart')

    def test_stop_unarmed_and_interrupt(self):
        self.assertEqual(handle_event('Stop', {}).output, {})
        self.assertEqual(handle_event('Stop', {'stop_hook_active': True}).output, {})
        self.assertEqual(handle_event('Interrupt', {}).exit_code, 0)

    def test_protected_patch_paths(self):
        with tempfile.TemporaryDirectory() as cwd:
            for patch in ['*** Begin Patch\n*** Update File: .orchestra/state.json\n@@\n-x\n+y\n*** End Patch',
                          '*** Begin Patch\n*** Update File: a\n*** Move to: .codex/agents/orchestra-builder.toml\n*** End Patch',
                          '*** Begin Patch\n*** Update File: .codex/hooks.json\n@@\n-x\n+y\n*** End Patch']:
                self.assertEqual(decision_of(self.pre('apply_patch', {'command': patch}, cwd=cwd)), 'deny')
            self.assertEqual(self.pre('apply_patch', {'command': 'bad patch'}, cwd=cwd).exit_code, 2)
            self.assertEqual(decision_of(self.pre('Write', {'file_path': '.claude/agents/orchestra-builder.md', 'content': 'x'}, cwd=cwd)), 'deny')
            self.assertEqual(self.pre('apply_patch', {'command': '*** Begin Patch\n*** Add File: a b.py\n+x\n*** End Patch'}, cwd=cwd).output, {})

    def test_protected_path_in_nested_harness_directory_b_f4(self):
        # B-F4: the first `.claude` in the resolved path is not the one that holds hooks.json.
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory) / '.claude' / 'plugins' / 'x'
            cwd.mkdir(parents=True)
            for tool, key in [('Edit', 'file_path'), ('Write', 'file_path'), ('MultiEdit', 'file_path')]:
                self.assertEqual(decision_of(self.pre(tool, {key: '.claude/hooks.json'}, cwd=cwd)), 'deny', tool)
            self.assertEqual(decision_of(self.pre('Write', {'file_path': '.codex/config.toml'}, cwd=cwd)), 'deny')
            self.assertEqual(decision_of(self.pre('Write', {'file_path': '.codex/agents/orchestra_builder.toml'}, cwd=cwd)), 'deny')
            self.assertEqual(self.pre('Write', {'file_path': 'notes.md'}, cwd=cwd).output, {})
            self.assertEqual(self.pre('Write', {'file_path': '.claude/plugins/x/readme.md'}, cwd=cwd).output, {})

    def test_a8_settings_json_is_no_longer_protected(self):
        with tempfile.TemporaryDirectory() as cwd:
            for path in ['.claude/settings.json', '.codex/settings.json', '.claude/settings.local.json']:
                with self.subTest(path=path):
                    self.assertEqual(self.pre('Write', {'file_path': path}, cwd=cwd).output, {})
            for path in ['.claude/hooks.json', '.codex/hooks.json', '.codex/config.toml', '.orchestra/x']:
                with self.subTest(path=path):
                    self.assertEqual(decision_of(self.pre('Write', {'file_path': path}, cwd=cwd)), 'deny')

    def test_a8_state_directory_protected_except_coordinator_files(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'state'
            state.mkdir()
            for name in ['progress.md', 'standing-orders.md', 'autonomy.md']:
                with self.subTest(name=name):
                    self.assertEqual(self.pre('Write', {'file_path': str(state / name)}, cwd=directory, state_dir=str(state)).output, {})
            for name in ['state.json', 'policy.json', 'sub/progress.md']:
                with self.subTest(name=name):
                    self.assertEqual(decision_of(self.pre('Write', {'file_path': str(state / name)}, cwd=directory, state_dir=str(state))), 'deny')

    def test_a12_marker_directory_is_protected(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {'XDG_STATE_HOME': directory}):
            marker = Path(directory) / 'orchestra' / 'mods' / 's1.json'
            for tool in ['Edit', 'Write', 'MultiEdit']:
                self.assertEqual(decision_of(self.pre(tool, {'file_path': str(marker)}, cwd=directory)), 'deny', tool)
            patch = '*** Begin Patch\n*** Add File: ' + str(marker) + '\n+x\n*** End Patch'
            self.assertEqual(decision_of(self.pre('apply_patch', {'command': patch}, cwd=directory)), 'deny')
            self.assertEqual(decision_of(self.pre('Write', {'file_path': 'mods/../mods/s2.json'}, cwd=marker.parent)), 'deny')
            self.assertEqual(self.pre('Write', {'file_path': str(Path(directory) / 'orchestra' / 'notes.md')}, cwd=directory).output, {})

    def test_a12_marker_directory_defaults_under_home(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {'HOME': home}):
            os.environ.pop('XDG_STATE_HOME', None)
            marker = Path(home) / '.local/state/orchestra/mods/s1.json'
            self.assertEqual(decision_of(self.pre('Write', {'file_path': str(marker)}, cwd=home)), 'deny')

    def test_external_state_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='orchestra path ') as directory:
            state = Path(directory) / 'state dir'
            patch = '*** Begin Patch\n*** Add File: ' + str(state / 'state.json') + '\n+x\n*** End Patch'
            result = self.pre('apply_patch', {'command': patch}, state_dir=str(state))
            self.assertEqual(result.output['hookSpecificOutput']['permissionDecision'], 'deny')
            self.assertFalse(state.exists())

    def test_worker_environment_is_advisory(self):
        with unittest.mock.patch.dict(os.environ, {'ORCHESTRA_ROLE': 'builder'}):
            self.assertEqual(self.pre('spawn_agent', {}).output['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_release_checks_exact_command(self):
        engine = mock.Mock()
        engine.check_release.return_value = {'id': 'permit'}
        command = 'git push origin HEAD:main'
        self.assertEqual(self.pre('Bash', {'command': command}, engine=engine).output, {})
        engine.check_release.assert_called_once_with('origin', 'main', argv=['git', 'push', 'origin', 'HEAD:main'])
        engine.check_release.side_effect = ValueError('stale')
        self.assertIn('stale', self.pre('Bash', {'command': command}, engine=engine).output['hookSpecificOutput']['permissionDecisionReason'])
        self.assertEqual(self.pre('Bash', {'command': 'git -C other push origin main'}, engine=engine).output['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_interrupt_and_bounded_adapter(self):
        engine = mock.Mock()
        engine.status.return_value = {'session': {'active': True, 'actor': 'main', 'lease': 'a'}}
        handle_event('Interrupt', {}, engine=engine)
        engine.interrupt.assert_called_once_with('main', 'a')
        engine.hook_stop.return_value = 'Continue one authorized bounded pass'
        self.assertEqual(handle_event('Stop', {}, engine=engine).output['decision'], 'block')
        engine.hook_stop.side_effect = ValueError('corrupt')
        self.assertEqual(handle_event('Stop', {}, engine=engine).output, {})

    def test_native_main_preserves_bad_json_exit(self):
        script = Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts/orchestra_hook.py'
        result = subprocess.run([sys.executable, str(script), 'PreToolUse'],
                                input='{', text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)

    def test_main_uses_existing_repository_state_and_policy(self):
        from orchestra_core.paths import state_location
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {'XDG_STATE_HOME': directory}):
            os.environ.pop('ORCHESTRA_STATE_DIR', None)
            repo = Path(directory) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            nested = repo / 'nested'
            nested.mkdir()
            state = state_location(repo)
            state.mkdir(parents=True)
            (state / 'state.json').write_text('{}')
            policy = {'schema_version': 1, 'release': {'remote': 'origin'}}
            (state / 'policy.json').write_text(json.dumps(policy))
            constructor = mock.Mock()
            constructor.return_value.check_release.return_value = {'id': 'permit'}
            payload = {'cwd': str(nested), 'tool_name': 'Bash', 'tool_input': {'command': 'git push origin main'}}
            with mock.patch.dict(sys.modules, {'orchestra_core.engine': types.SimpleNamespace(Engine=constructor)}), mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), mock.patch('sys.stdout', new_callable=io.StringIO) as output:
                self.assertEqual(main(['PreToolUse']), 0)
                self.assertEqual(json.loads(output.getvalue()), {})
            constructor.assert_called_once_with(state, repo.resolve(), policy=policy)

    def test_main_without_run_creates_no_state(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {'ORCHESTRA_STATE_DIR': str(Path(directory) / 'absent')}):
            constructor = mock.Mock()
            with mock.patch.dict(sys.modules, {'orchestra_core.engine': types.SimpleNamespace(Engine=constructor)}), mock.patch('sys.stdin', io.StringIO(json.dumps({'cwd': str(Path.cwd()), 'tool_name': 'read_file', 'tool_input': {}}))), mock.patch('sys.stdout', new_callable=io.StringIO):
                main(['PreToolUse'])
            constructor.assert_not_called()
            self.assertFalse((Path(directory) / 'absent').exists())

    def test_orchestrator_identity_and_skill_path(self):
        result = handle_event('SessionStart', {'agent_type': 'orchestra:orchestrator'})
        context = result.output['hookSpecificOutput']['additionalContext']
        self.assertIn('main coordinator', context)
        self.assertIn(str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/skills/orchestra/SKILL.md'), context)

    def test_underscore_profile_protected(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(decision_of(self.pre('Write', {'file_path': '.codex/agents/orchestra_builder.toml'}, cwd=cwd)), 'deny')

    def test_stop_continues_until_engine_cap(self):
        engine = mock.Mock()
        engine.hook_stop.side_effect = ['bounded continuation', None]
        self.assertEqual(handle_event('Stop', {'stop_hook_active': True}, engine=engine).output['decision'], 'block')
        self.assertEqual(handle_event('Stop', {'stop_hook_active': True}, engine=engine).output, {})

    def test_cli_bad_json(self):
        result = subprocess.run([sys.executable, '-m', 'orchestra_core.hooks', 'PreToolUse'],
                                input='{', text=True, capture_output=True,
                                env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts')})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_a9_claude_matcher_is_narrow_and_codex_is_unchanged(self):
        claude = json.loads((PLUGIN / 'hooks/claude.json').read_text())
        self.assertEqual(claude['hooks']['PreToolUse'][0]['matcher'], 'Bash|Edit|Write|MultiEdit')
        self.assertEqual(claude['hooks']['PreToolUse'][0]['matcher'], RULES['tools']['claude_matcher'])
        codex = json.loads((PLUGIN / 'hooks/codex.json').read_text())
        self.assertEqual(codex['hooks']['PreToolUse'][0]['matcher'], '.*')


def run_main(payload, *args, env=None):
    """Run the real hook entry point; returns (exit code, decoded stdout)."""
    with mock.patch.dict(os.environ, env or {}), mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
            mock.patch('sys.stdout', new_callable=io.StringIO) as output, mock.patch('sys.stderr', new_callable=io.StringIO):
        code = main(['PreToolUse', *args])
        return code, json.loads(output.getvalue())


def git(cwd, *args):
    return subprocess.check_output(['git', '-C', str(cwd), *args], stderr=subprocess.PIPE, text=True).strip()


class MarkerHandshakeTest(unittest.TestCase):
    """A12: a fresh marker with this copy's rules hash lets Python skip; anything else guards."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.xdg = Path(self.temp.name) / 'xdg'
        self.cwd = Path(self.temp.name) / 'cwd'
        self.cwd.mkdir()
        self.mods = self.xdg / 'orchestra' / 'mods'
        self.mods.mkdir(parents=True)
        self.env = {'XDG_STATE_HOME': str(self.xdg)}
        self.sha = hashlib.sha256(RULES_PATH.read_bytes()).hexdigest()

    def marker(self, session='s1', *, age_ms=0, sha=None, inner=None, name=None):
        data = {'session_id': inner or session, 'heartbeat_ms': int(time.time() * 1000) - age_ms,
                'plugin_version': '2.0.0', 'rules_sha256': self.sha if sha is None else sha}
        (self.mods / ((name or session) + '.json')).write_text(json.dumps(data))

    def call(self, session='s1', *args, harness='claude', command='git stash'):
        payload = {'cwd': str(self.cwd), 'session_id': session, 'tool_name': 'Bash', 'tool_input': {'command': command}}
        code, output = run_main(payload, '--harness', harness, *args, env=self.env)
        self.assertEqual(code, 0)
        return output

    def assertGuards(self, output):
        self.assertEqual(output['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_fresh_marker_with_matching_rules_skips_guarding(self):
        self.marker()
        self.assertEqual(self.call(), {})

    def test_stale_marker_guards(self):
        self.marker(age_ms=20000)
        self.assertGuards(self.call())

    def test_retired_marker_guards(self):
        self.marker()
        data = json.loads((self.mods / 's1.json').read_text())
        data['heartbeat_ms'] = 0
        (self.mods / 's1.json').write_text(json.dumps(data))
        self.assertGuards(self.call())

    def test_marker_just_inside_the_window_skips(self):
        self.marker(age_ms=10000)
        self.assertEqual(self.call(), {})

    def test_wrong_or_missing_rules_hash_guards(self):
        self.marker(sha='0' * 64)
        self.assertGuards(self.call())
        self.marker(sha='')
        data = json.loads((self.mods / 's1.json').read_text())
        data['rules_sha256'] = None
        (self.mods / 's1.json').write_text(json.dumps(data))
        self.assertGuards(self.call())

    def test_missing_unreadable_and_foreign_markers_guard(self):
        self.assertGuards(self.call())
        (self.mods / 's1.json').write_text('{not json')
        self.assertGuards(self.call())
        self.marker(session='s1', inner='other')
        self.assertGuards(self.call())

    def test_malformed_session_id_skips_the_marker_check(self):
        self.marker(session='bad id!')
        self.assertGuards(self.call('bad id!'))
        self.marker(session='escape', name='../escape')
        self.assertGuards(self.call('../escape'))
        self.marker(session='x' * 129)
        self.assertGuards(self.call('x' * 129))
        self.assertGuards(self.call(''))
        self.marker(session='ok_id-1')
        self.assertEqual(self.call('ok_id-1'), {})

    def test_from_mod_skips_the_marker_check(self):
        self.marker()
        self.assertGuards(self.call('s1', '--from-mod'))

    def test_marker_applies_only_to_claude(self):
        self.marker()
        self.assertGuards(self.call(harness='codex'))

    def test_marker_applies_only_to_pre_tool_use(self):
        self.marker()
        payload = {'cwd': str(self.cwd), 'session_id': 's1'}
        with mock.patch.dict(os.environ, self.env), mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(['SessionStart', '--harness', 'claude']), 0)
            self.assertIn('additionalContext', output.getvalue())

    def test_fresh_marker_skips_before_any_git_or_engine_work(self):
        self.marker()
        with mock.patch('subprocess.check_output', side_effect=AssertionError('git ran')):
            self.assertEqual(self.call(), {})


class RunStateResolutionTest(unittest.TestCase):
    """A1 states and A15: where the hook looks for the run."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = {'XDG_STATE_HOME': str(self.root / 'xdg')}
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('ORCHESTRA_STATE_DIR', None)
        self.repo = self.root / 'main'
        self.repo.mkdir()
        git(self.repo, 'init', '-q', '-b', 'main')
        git(self.repo, 'config', 'user.name', 'T')
        git(self.repo, 'config', 'user.email', 't@example.invalid')
        (self.repo / 'f.txt').write_text('x\n')
        git(self.repo, 'add', 'f.txt')
        git(self.repo, 'commit', '-q', '-m', 'f')
        self.linked = self.root / 'linked'
        git(self.repo, 'worktree', 'add', '-q', str(self.linked), '-b', 'side')

    def start(self, repo):
        out = subprocess.run([sys.executable, str(CLI), '--repo', str(repo), 'start'], env=os.environ,
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)['lease']

    def interrupt(self, repo, lease):
        subprocess.run([sys.executable, str(CLI), '--repo', str(repo), '--lease', lease, 'interrupt'],
                       env=os.environ, capture_output=True, text=True, check=True)

    def bash(self, cwd, command):
        code, output = run_main({'cwd': str(cwd), 'tool_name': 'Bash', 'tool_input': {'command': command}})
        self.assertEqual(code, 0)
        return output.get('hookSpecificOutput', {}).get('permissionDecision')

    def test_unarmed_repository_allows_release_classes(self):
        for command in UNARMED_RELEASES + MULTI_RELEASES:
            with self.subTest(command=command):
                self.assertIsNone(self.bash(self.repo, command))
        self.assertEqual(self.bash(self.repo, 'git push --force origin x'), 'deny')

    def test_armed_main_checkout_denies_release_without_a_permit(self):
        self.start(self.repo)
        self.assertEqual(self.bash(self.repo, 'git push origin side'), 'deny')
        self.assertEqual(self.bash(self.repo, 'git push origin x && git status'), 'deny')
        self.assertIsNone(self.bash(self.repo, 'git status'))
        self.assertIsNone(self.bash(self.repo, 'rm -rf build'))

    def test_interrupted_run_is_unarmed_again(self):
        lease = self.start(self.repo)
        self.assertEqual(self.bash(self.repo, 'git push origin side'), 'deny')
        self.interrupt(self.repo, lease)
        self.assertIsNone(self.bash(self.repo, 'git push origin side'))

    def test_unloadable_state_file_denies_release(self):
        from orchestra_core.paths import state_location
        state = state_location(self.repo)
        state.mkdir(parents=True)
        for text in ['{not json', '{}', '[]', '{"version": 1, "session": {"active": "yes"}}']:
            (state / 'state.json').write_text(text)
            with self.subTest(text=text):
                self.assertEqual(self.bash(self.repo, 'git push origin side'), 'deny')
                self.assertEqual(self.bash(self.repo, 'gh release create v1 --verify-tag'), 'deny')
                self.assertIsNone(self.bash(self.repo, 'git status'))

    def test_a15_linked_worktree_of_an_armed_repository_denies_release(self):
        self.start(self.repo)
        for command in LINKED_WORKTREE_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(self.bash(self.linked, command), 'deny')
        self.assertIsNone(self.bash(self.linked, 'git status'))

    def test_a15_linked_worktree_of_an_unarmed_repository_allows_release(self):
        for command in LINKED_WORKTREE_COMMANDS:
            with self.subTest(command=command):
                self.assertIsNone(self.bash(self.linked, command))
        lease = self.start(self.repo)
        self.interrupt(self.repo, lease)
        self.assertIsNone(self.bash(self.linked, 'git push origin side'))

    def test_a15_state_of_the_linked_worktree_itself_wins(self):
        # Its own armed run is found first; the main worktree's inactive state is never consulted.
        self.start(self.linked)
        self.assertEqual(self.bash(self.linked, 'git push origin side'), 'deny')
        self.assertIsNone(self.bash(self.repo, 'git push origin side'))

    def test_a15_protected_state_follows_the_main_worktree(self):
        from orchestra_core.paths import state_location
        self.start(self.repo)
        state = state_location(self.repo)
        payload = {'cwd': str(self.linked), 'tool_name': 'Write', 'tool_input': {'file_path': str(state / 'state.json')}}
        code, output = run_main(payload)
        self.assertEqual(output['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_a15_bare_common_directory_stays_unarmed(self):
        from orchestra_core.paths import state_location
        bare = self.root / 'bare.git'
        subprocess.run(['git', 'clone', '-q', '--bare', str(self.repo), str(bare)], check=True, capture_output=True)
        git(bare, 'worktree', 'add', '-q', str(self.root / 'bare-wt'), 'main')
        # Even an armed-looking state at the bare directory's parent must never be consulted.
        parent_state = state_location(self.root)
        parent_state.mkdir(parents=True)
        (parent_state / 'state.json').write_text('{}')
        self.assertIsNone(self.bash(self.root / 'bare-wt', 'git push origin main'))
        self.assertIsNone(self.bash(self.root / 'bare-wt', 'git push origin main && git status'))


class RunHookScriptTest(unittest.TestCase):
    def test_syntax(self):
        self.assertEqual(subprocess.run(['bash', '-n', str(RUN_HOOK)]).returncode, 0)
        self.assertEqual(subprocess.run(['/bin/sh', '-n', str(RUN_HOOK)]).returncode, 0)

    def run_hook(self, *args, trace=False, stdin=''):
        cmd = ['/bin/sh'] + (['-x'] if trace else []) + [str(RUN_HOOK), *args]
        return subprocess.run(cmd, input=stdin, text=True, capture_output=True, timeout=60)

    def test_hook_runs_python_once_without_a_probe(self):
        if not any(shutil.which(name) for name in ['python3.14', 'python3.13', 'python3.12', 'python3.11']):
            self.skipTest('no versioned Python on PATH; the probing fallback is the only path')
        result = self.run_hook('PreToolUse', '--harness', 'claude', trace=True,
                               stdin=json.dumps({'tool_name': 'Read', 'tool_input': {}}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertNotIn('sys.version_info', result.stderr)
        launches = [l for l in result.stderr.splitlines() if l.startswith('+ exec ')]
        self.assertEqual(len(launches), 1, result.stderr)
        self.assertTrue(launches[0].startswith('+ exec python3.'), launches)

    def test_cli_first_argument_execs_the_orchestra_cli(self):
        result = self.run_hook('--cli', 'classify', 'git reset --hard')
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision['action'], 'deny')
        usage = self.run_hook('--cli', '--help')
        self.assertEqual(usage.returncode, 0)
        self.assertIn('classify', usage.stdout)

    def test_cli_exit_status_is_preserved(self):
        self.assertNotEqual(self.run_hook('--cli', 'no-such-command').returncode, 0)

    def test_script_resolves_its_directory_from_dollar_zero(self):
        result = subprocess.run(['/bin/sh', 'run-hook.sh', '--cli', 'classify', 'git status'], cwd=RUN_HOOK.parent,
                                text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['action'], 'allow')


if __name__ == '__main__':
    unittest.main()
