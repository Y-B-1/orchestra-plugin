"""T2 (2.15.3 strategic track): a fixed table of commands the merge gate must deny after the owner's receipt: every
merge-capable spelling found so far, plus deliberate fail-closed over-denies. Four review rounds found gate bypasses one spelling at a time and RG1 lost five that no test pinned; this
table only grows, so no rewrite of the gate can quietly un-gate a known form."""
import json
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
        the gate looks for, repeated, before a real merge) well inside its 10 s timeout, and still deny."""
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


if __name__ == '__main__':
    unittest.main()
