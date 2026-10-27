"""T2 (2.15.3 strategic track): a fixed table of commands the merge gate must deny after the owner's receipt: every
merge-capable spelling found so far, plus deliberate fail-closed over-denies. Four review rounds found gate bypasses one spelling at a time and RG1 lost five that no test pinned; this
table only grows, so no rewrite of the gate can quietly un-gate a known form."""
import json
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import test_merge_guard as tm  # noqa: E402

TABLE = pathlib.Path(__file__).resolve().parent / 'data' / 'merge_gate_must_deny.json'


class MustDenyTableTest(tm.MergeFixture):
    def hook(self, command):
        from orchestra_core.hooks import handle_event
        payload = {'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': str(self.repo)}
        output = handle_event('PreToolUse', payload, mode='minimal', state_dir=str(self.state)).output
        return output.get('hookSpecificOutput', {}).get('permissionDecision')

    def test_every_listed_command_is_denied_after_the_receipt(self):
        self.arm()
        self.open_pr(3)
        self.approve([3])
        for command in json.loads(TABLE.read_text())['deny']:
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), 'deny')

    def test_every_listed_set_default_is_denied_while_armed(self):
        self.arm()
        self.open_pr(3)
        for command in json.loads(TABLE.read_text())['deny_while_armed']:
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), 'deny')

    def test_padded_commands_answer_fast(self):
        """RZ4: a timed-out PreToolUse hook does not block, so the hook must answer every padded shape (each keyword
        the gate looks for, repeated, before a real merge) well inside its timeout (30 s, 8 s on the mod path), and still deny."""
        import time
        n = 20000
        merge = '; gh pr merge 3 --squash'
        shapes = {'api': 'echo gh ' + 'api ' * n + 'graphql' + merge, 'repo': 'echo gh ' + 'repo ' * n + merge,
                  'pr flags': 'echo gh ' + 'pr -x ' * n + merge, 'graphql': 'echo gh api ' + 'graphql ' * n + merge,
                  'empty words': "echo gh pr " + "'' " * n + merge, 'continuations': 'echo gh ' + 'x \\\n' * n + merge,
                  'merge words': 'echo gh api ' + '/merge ' * n + merge, 'pr words': 'echo gh ' + 'pr ' * n + merge,
                  'gh words': 'echo ' + 'gh ' * 600 + merge,
                  'one long quoted word': "echo '" + 'a' * 700000 + "'" + merge}
        self.arm()
        self.open_pr(3)
        for label, command in shapes.items():
            with self.subTest(label):
                start = time.monotonic()
                self.assertEqual(self.hook(command), 'deny')
                self.assertLess(time.monotonic() - start, 2.0)


class OversizeCommandTest(tm.MergeFixture):
    """RZ5: shlex grows quadratically on one long word, so the real hook entry denies a shell command over 131072
    characters before any parse, in every mode, with or without a run: a timed-out hook does not block."""

    def main(self, command, *flags):
        import io
        from unittest import mock
        from orchestra_core.hooks import _main
        payload = {'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': str(self.repo)}
        with mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                mock.patch.dict(os.environ, ORCHESTRA_STATE_DIR=str(self.state)), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out, mock.patch('sys.stderr', new_callable=io.StringIO):
            _main(['PreToolUse', *flags])
        return json.loads(out.getvalue()).get('hookSpecificOutput', {})

    def test_a_huge_command_is_denied_fast_through_the_real_entry(self):
        import time
        self.arm()
        self.open_pr(3)
        for label, command in {'merge with a huge body': "gh pr merge 3 --merge --body '" + 'a' * 700000 + "'",
                               'huge echo, no gh': "echo '" + 'a' * 700000 + "'"}.items():
            with self.subTest(label):
                start = time.monotonic()
                output = self.main(command)
                self.assertLess(time.monotonic() - start, 2.0)
                self.assertEqual(output.get('permissionDecision'), 'deny')
                self.assertIn('131072 characters', output.get('permissionDecisionReason', ''))

    def test_the_cap_is_exact_on_both_entries(self):
        """RZ6 note: COMMAND_MAX characters pass the size check, one more is denied; --from-mod denies the same way."""
        from orchestra_core.approval import COMMAND_MAX
        self.arm()
        at_cap = "echo '" + 'a' * (COMMAND_MAX - 7) + "'"
        self.assertEqual(len(at_cap), COMMAND_MAX)
        for flags in ((), ('--from-mod',)):
            with self.subTest(flags=flags):
                self.assertNotIn('131072 characters', self.main(at_cap, *flags).get('permissionDecisionReason', ''))
                over = self.main(at_cap + ' ', *flags)
                self.assertEqual(over.get('permissionDecision'), 'deny')
                self.assertIn('131072 characters', over.get('permissionDecisionReason', ''))

    def test_a_command_under_the_cap_is_not_affected(self):
        output = self.main("echo '" + 'a' * 1000 + "'")
        self.assertNotEqual(output.get('permissionDecision'), 'deny')


class HookBudgetTest(tm.MergeFixture):
    """RZ6: a command under the 131072-character cap can still take the check past the 30 s hook timeout (nested `| sh`
    payloads are reparsed by each caller), and a timed-out hook does not block. hooks.main denies a guarded call
    that has not answered after HOOK_BUDGET seconds."""

    SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins' / 'orchestra' / 'scripts'

    def run_hook(self, command, prelude=''):
        import subprocess
        import sys
        import time
        payload = json.dumps({'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': str(self.repo),
                              'session_id': 's'})
        code = ('import sys; sys.path.insert(0, %r); from orchestra_core import hooks; %s'
                'sys.exit(hooks.main(["PreToolUse", "--harness", "claude"]))' % (str(self.SCRIPTS), prelude))
        env = dict(os.environ, ORCHESTRA_STATE_DIR=str(self.state))
        start = time.monotonic()
        done = subprocess.run([sys.executable, '-c', code], input=payload, capture_output=True, text=True,
                              cwd=str(self.repo), env=env, timeout=120)
        return done, time.monotonic() - start

    def test_a_padded_nested_sh_command_at_the_cap_is_denied_inside_the_hook_timeout(self):
        import shlex
        from orchestra_core.hooks import HOOK_BUDGET
        self.arm()

        def make(pad):
            inner = 'echo ' + 'a' * pad
            for _ in range(3):
                inner = 'echo ' + shlex.quote(inner) + ' | sh'
            return 'rm -f %s; %s' % (self.state / 'state.json', inner)
        pad = 131000
        while len(make(pad)) > 131000:
            pad -= len(make(pad)) - 131000
        done, took = self.run_hook(make(pad))
        self.assertEqual(json.loads(done.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertLess(took, HOOK_BUDGET + 5)

    def test_a_check_that_runs_past_the_budget_is_denied(self):
        prelude = ('import time; hooks.HOOK_BUDGET = 1.0; slow = hooks._decide; '
                   'hooks._decide = lambda *a, **k: (time.sleep(60), slow(*a, **k))[1]; ')
        done, took = self.run_hook('ls', prelude)
        self.assertEqual(done.returncode, 2)
        answer = json.loads(done.stdout)['hookSpecificOutput']
        self.assertEqual(answer['permissionDecision'], 'deny')
        self.assertIn('did not finish', answer['permissionDecisionReason'])
        self.assertIn('shorter commands', answer['permissionDecisionReason'])  # RZ7 note: say how to go on
        self.assertLess(took, 10)

    def test_a_crash_answers_once_with_the_deny(self):
        """FX10 note: output the check printed before it crashed is dropped, so the deny is the only answer."""
        prelude = ('hooks._decide = lambda *a, **k: (print("{}"), (_ for _ in ()).throw(RuntimeError("x"))); ')
        done, _ = self.run_hook('ls', prelude)
        self.assertEqual(done.returncode, 2)
        self.assertEqual(len(done.stdout.splitlines()), 1)
        self.assertEqual(json.loads(done.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_a_quick_check_answers_once(self):
        done, _ = self.run_hook('ls')
        self.assertEqual(done.returncode, 0)
        json.loads(done.stdout)  # one JSON answer, nothing printed twice

if __name__ == '__main__':
    unittest.main()
