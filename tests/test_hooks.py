import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
from orchestra_core.guards import classify_command
from orchestra_core.hooks import handle_event


class GuardsTest(unittest.TestCase):
    def test_destructive_and_wholesale(self):
        for command in [
            'git reset --hard', 'git clean -fd', 'git branch -D topic',
            'git checkout -- .', 'git restore .', 'git stash push',
            'git add -A', 'git add .', 'git add -u src', 'git commit -am done',
            'exec env X=1 git -C "a b" -c color.ui=never reset --hard',
            'true && git clean -f', "sh -c 'git reset --hard'", 'git push --force origin main', 'git clean -f -e "--dry-run"',
            'git reset --hard=HEAD', 'cd other && git push origin main', 'git branch --delete --force topic',
        ]:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).action, 'deny')

    def test_semantic_arguments(self):
        for command in ['git add src/a.py', 'git commit -m "--all --dry-run"',
                        'echo "git reset --hard"', 'git log --oneline',
                        'git clean --dry-run', 'git push --dry-run origin main',
                        'git checkout feature', 'git add -- -A', 'echo ";"', 'wrangler dev']:
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).action, 'allow')
        self.assertEqual(classify_command('git reset --hard "--dry-run"').action, 'deny')

    def test_release(self):
        for command in ['git push origin HEAD:main', 'gh pr merge 3',
                        'az repos pr update --id 4 --status completed',
                        'npm publish', 'vercel --prod', 'az deployment group create']:
            self.assertEqual(classify_command(command).action, 'release')
        self.assertEqual(classify_command('git push -o \"--dry-run\" origin main').action, 'release')
        self.assertEqual(classify_command('git push -o \"--force\" origin main').action, 'release')
        decision = classify_command('git push origin HEAD:main')
        self.assertEqual((decision.remote, decision.target), ('origin', 'main'))
        self.assertEqual(classify_command('env --chdir=other git push origin main').argv[0], 'env')
        self.assertEqual(classify_command("sh -c 'git push origin main'").argv[0], 'sh')

    def test_malformed(self):
        self.assertEqual(classify_command("git 'reset").action, 'deny')


class HooksTest(unittest.TestCase):
    def pre(self, name, tool_input, **kw):
        return handle_event('PreToolUse', {'tool_name': name, 'tool_input': tool_input}, **kw)

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
        self.assertEqual(self.pre('Bash', {'command': 'git push origin main'}).output
                         ['hookSpecificOutput']['permissionDecision'], 'deny')

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
        for patch in ['*** Begin Patch\n*** Update File: .orchestra/state.json\n@@\n-x\n+y\n*** End Patch',
                      '*** Begin Patch\n*** Update File: a\n*** Move to: .codex/agents/orchestra-builder.toml\n*** End Patch']:
            self.assertEqual(self.pre('apply_patch', {'command': patch}).output
                             ['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(self.pre('apply_patch', {'command': 'bad patch'}).exit_code, 2)
        self.assertEqual(self.pre('Write', {'file_path': '.claude/agents/orchestra-builder.md', 'content': 'x'})
                         .output['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(self.pre('apply_patch', {'command': '*** Begin Patch\n*** Add File: a b.py\n+x\n*** End Patch'}).output, {})

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

    def test_cli_bad_json(self):
        result = subprocess.run([sys.executable, '-m', 'orchestra_core.hooks', 'PreToolUse'],
                                input='{', text=True, capture_output=True,
                                env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts')})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')


if __name__ == '__main__':
    unittest.main()
