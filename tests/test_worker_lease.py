"""A worker's shell command that carries --lease is denied in every guard mode (coordinator-only)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
from orchestra_core.hooks import handle_event

CLI = 'python3 /x/plugins/orchestra/scripts/orchestra.py'
MODES = ('minimal', 'normal', 'protect')


def run(command, mode, worker=True, kind='orchestra:builder'):
    payload = {'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': '/tmp'}
    if worker:
        payload.update(agent_id='a1', agent_type=kind)
    hso = handle_event('PreToolUse', payload, mode=mode).output.get('hookSpecificOutput', {})
    return hso.get('permissionDecision', 'allow'), hso.get('permissionDecisionReason', '')


class WorkerLeaseTests(unittest.TestCase):
    def test_worker_lease_denied_in_every_mode(self):
        spellings = (CLI + ' --lease L accept A', CLI + ' --lease=L accept A', CLI + ' --actor main --lease @session accept A',
                     CLI + " '--lease' L accept A", 'bash -c "' + CLI + ' --lease L accept A"')
        for mode in MODES:
            for command in spellings:
                with self.subTest(mode=mode, command=command):
                    verdict, reason = run(command, mode)
                    self.assertEqual(verdict, 'deny')
                    self.assertIn('coordinator', reason)

    def test_main_session_unchanged(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.assertEqual(run(CLI + ' --lease L accept A', mode, worker=False)[0], 'allow')

    def test_lease_free_worker_commands_stay_allowed(self):
        for mode in MODES:
            for sub in ('report A', 'status', 'board', 'card A'):
                with self.subTest(mode=mode, sub=sub):
                    self.assertEqual(run(CLI + ' ' + sub, mode)[0], 'allow')

    def test_force_with_lease_is_not_a_lease(self):
        self.assertEqual(run('git status --force-with-lease', 'minimal')[0], 'allow')


if __name__ == '__main__':
    unittest.main()
