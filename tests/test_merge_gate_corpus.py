"""T2 (2.15.3 strategic track): a fixed table of merge-capable commands the merge gate must deny after the owner's
receipt. Four review rounds found gate bypasses one spelling at a time and RG1 lost five that no test pinned; this
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

if __name__ == '__main__':
    unittest.main()
